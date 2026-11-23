"""
Replay an already-generated OsdagBridge report (.tex) through the NEW report
pipeline, without needing the GUI or the structural solver.

What is re-generated with the real production code:
  * preamble / page geometry / footer      (report_theme.build_preamble)
  * Chapter 3 live-load tables             (live_loads.live_load_tables_tex)
  * Section 5.5 utilization-ratio charts   (report_charts.build_ur_charts)
  * Chapter 7 material charts              (report_charts.build_material_chart)
  * repeated headers, grouped rows, PASS/FAIL colours (report_tables.post_process_tex)

Chart inputs are parsed back out of the old report's own tables (Tables 5.12,
5.29 and 7.1), so the charts show exactly the numbers in that report.

Usage:
    python tools/replay_report_from_tex.py Report_Before.tex out_dir [--compile]
"""
import argparse
import os
import re
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from osdagbridge.core.reports.live_loads import live_load_tables_tex          # noqa: E402
from osdagbridge.core.reports.report_charts import (                           # noqa: E402
    UrRecord, build_material_chart, build_ur_charts, to_float,
    GROUP_GIRDER, GROUP_CB, GROUP_DECK, GROUP_ED)
from osdagbridge.core.reports.report_tables import post_process_tex           # noqa: E402
from osdagbridge.core.reports.report_theme import THEME, build_preamble       # noqa: E402
from osdagbridge.core.utils.common import (                                    # noqa: E402
    KEY_BL_IRC_CLASS_SV, KEY_FOOTPATH, KEY_LL_ECCENTRICITY, KEY_LL_FOOTPATH_PRESSURE_MODE,
    KEY_LL_IRC_70R_BOGIE, KEY_LL_IRC_70R_TRACKED, KEY_LL_IRC_70R_WHEELED,
    KEY_LL_IRC_AA_TRACKED, KEY_LL_IRC_AA_WHEELED, KEY_LL_IRC_CLASS_A,
    KEY_LL_IRC_CLASS_FATIGUE, KEY_LL_IRC_CLASS_SV, KEY_SPAN, KEY_TS_FOOTPATH_WIDTH)


def _table(tex, caption_fragment):
    """The single longtable whose caption contains *caption_fragment* ('' if absent)."""
    i = tex.find("\\caption{")
    while i != -1:
        end = tex.find("}", i)
        j = i
        if caption_fragment in tex[i:tex.find("\n", i)]:
            start = tex.rfind("\\begin{longtable}", 0, i)
            stop = tex.find("\\end{longtable}", i) + len("\\end{longtable}")
            return tex[start:stop]
        i = tex.find("\\caption{", i + 1)
    return ""


def _rows(table_tex):
    body = table_tex.split("\\hline", 2)[-1] if table_tex else ""
    for raw in re.split(r"\\\\(?:\[[^\]]*\])?\s*\\hline", body):
        cells = [c.strip() for c in raw.split("&")]
        if len(cells) > 1:
            yield cells


def parse_ur(tex):
    girder_ur = []
    for cells in _rows(_table(tex, "Girder Design Summary")):
        if re.fullmatch(r"G\d+", cells[0]) and len(cells) >= 6:
            ur = to_float(cells[5])
            if ur is not None:
                girder_ur.append((cells[0], ur))
    recs = []
    for cells in _rows(_table(tex, "Overall Design Check Summary --- All Members")):
        label, ur = cells[0], to_float(cells[-1].replace("\\\\", ""))
        if ur is None or len(cells) < 5:
            continue
        key = label.lower()
        grp = (GROUP_GIRDER if key.startswith("girder") else GROUP_CB if key.startswith("cross bracing")
               else GROUP_ED if key.startswith("end diaphragm") else GROUP_DECK)
        short = label.split("---")[-1].strip().replace("(slab)", "").strip()
        if key.startswith(("transverse shear", "crack width")):
            short = label.replace("(slab)", "").strip()
        recs.append(UrRecord(grp, short or label, ur))
    return girder_ur, recs


def parse_quantities(tex):
    """Pull the 'total weight' / 'total volume' columns out of Table 7.1 (Bill of Materials)."""
    keys = [("for Girders", "steel_girders"), ("Top Chord", "bracing_top"),
            ("Bottom Chord", "bracing_bot"), ("Diagonal Chord", "bracing_diag"),
            ("Deck Slab", "concrete_deck"), ("Reinforcement Steel", "rebar_deck")]
    q = {}
    for cells in _rows(_bom(tex)):
        if len(cells) >= 7:
            for frag, key in keys:
                if frag in cells[1]:
                    q[key + "_wt_total"] = cells[-1].replace("\\\\", "").strip()
                    q[key + "_vol_total"] = cells[4].strip()
                    break
    return q


def _bom(tex):
    i = tex.find("Bill of Materials")
    j = tex.find("\\begin{longtable}", i)
    k = tex.find("\\end{longtable}", j)
    return tex[j:k] if j != -1 else ""


def demo_inputs(span_m=30.0):
    """UI selections matching the Report_Before run (all IRC vehicles ticked, defaults)."""
    d = {KEY_SPAN: span_m, KEY_LL_ECCENTRICITY: "1.2", KEY_LL_FOOTPATH_PRESSURE_MODE: "As per IRC 6",
         KEY_FOOTPATH: "Single Side", KEY_TS_FOOTPATH_WIDTH: "1.5", KEY_BL_IRC_CLASS_SV: True}
    for k in (KEY_LL_IRC_CLASS_A, KEY_LL_IRC_AA_WHEELED, KEY_LL_IRC_AA_TRACKED, KEY_LL_IRC_70R_WHEELED,
              KEY_LL_IRC_70R_TRACKED, KEY_LL_IRC_70R_BOGIE, KEY_LL_IRC_CLASS_SV, KEY_LL_IRC_CLASS_FATIGUE):
        d[k] = True
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tex"); ap.add_argument("out_dir")
    ap.add_argument("--compile", action="store_true")
    ap.add_argument("--assets", help="dir with osdag_logo.png / org_logo.png")
    a = ap.parse_args()
    tex = open(a.tex, encoding="utf-8").read().replace("\r\n", "\n")
    os.makedirs(a.out_dir, exist_ok=True)
    img_dir = os.path.join(a.out_dir, "images")

    # ---- preamble ----------------------------------------------------------
    m = re.search(r"\\fancyhead\[L\]\{(.*?)\}", tex)
    head_l = m.group(1) if m else "Project"
    m2 = re.search(r"\\fancyhead\[R\]\{(.*?)\}", tex)
    parts_r = (m2.group(1) if m2 else "").split("$|$")
    pn, jn = (head_l.split("$|$") + [""])[:2]
    pre = build_preamble(pn.strip(), jn.strip(), parts_r[0].strip(), (parts_r + ["Rev 0"])[1].strip())
    body = tex[tex.index("\\begin{document}") + len("\\begin{document}"):]
    body = body.replace("≤", "$\\leq$")

    # ---- Chapter 3: replace old combined Live Loads table ------------------
    old = _table(body, "Live Loads (LL)")
    if old:
        body = body.replace(old, live_load_tables_tex(demo_inputs()), 1)

    # ---- charts --------------------------------------------------------------
    girder_ur, recs = parse_ur(body)
    imgs = build_ur_charts(girder_ur, recs, img_dir)
    w = THEME.chart.latex_width
    caps = {"ur_overview": "Governing utilization ratio (UR = Demand / Capacity) of each primary element. "
                           "The red dashed line marks UR = 1.0; bars above it fail.",
            "ur_breakdown": "Utilization ratio of every individual check, grouped by element (steel plate "
                            "girders, concrete deck slab, cross bracing, end diaphragms)."}
    block = "\\subsection*{Utilization Ratio Charts}\n"
    for k in ("ur_overview", "ur_breakdown"):
        if imgs.get(k):
            block += ("\\begin{figure}[H]\n\\centering\n\\includegraphics[width=%s]{images/%s.png}\n"
                      "\\caption{%s}\n\\end{figure}\n" % (w, k, caps[k]))
    anchor = re.search(r"\\chapter\{Drawings[^}]*\}", body).group(0)
    body = body.replace(anchor, block + "\n" + anchor, 1)

    mat = build_material_chart(parse_quantities(body), img_dir)
    if mat.get("material"):
        mblock = ("\\section*{Material Quantity Charts}\n\\begin{figure}[H]\n\\centering\n"
                  "\\includegraphics[width=%s]{images/material_quantities.png}\n"
                  "\\caption{Structural steel tonnage (girders, cross bracing, end diaphragms), concrete "
                  "volume and reinforcement weight, taken from Table 7.1.}\n\\end{figure}\n" % w)
        for n in mat.get("notes", []):
            mblock += "\\noindent\\textit{\\small Note: %s}\\par\n" % n
        c8 = re.search(r"\\chapter\{Standards[^}]*\}", body)
        body = body.replace(c8.group(0), mblock + "\n" + c8.group(0), 1)

    out = post_process_tex(pre + body, THEME)
    tex_path = os.path.join(a.out_dir, "Report_After.tex")
    open(tex_path, "w", encoding="utf-8").write(out)
    if a.assets:
        shutil.copytree(a.assets, os.path.join(a.out_dir, "assets"), dirs_exist_ok=True)
    print("wrote", tex_path)
    if a.compile:
        for _ in range(2):
            subprocess.run(["pdflatex", "-interaction=nonstopmode", "Report_After.tex"],
                           cwd=a.out_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


if __name__ == "__main__":
    main()
