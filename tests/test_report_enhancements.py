"""Tests for the report-generator enhancements (tables, live loads, charts, theme)."""
import os
import re

import pytest

from osdagbridge.core.reports import live_loads, report_charts, report_tables, report_theme
from osdagbridge.core.reports.report_theme import THEME
from osdagbridge.core.utils.common import (
    KEY_BL_IRC_CLASS_SV, KEY_LL_IRC_70R_WHEELED, KEY_LL_IRC_CLASS_A,
    KEY_LL_IRC_CLASS_SV, KEY_SPAN)

SAMPLE = r"""
\begin{longtable}{|L{3cm}|L{3cm}|}
\caption{\textbf{Demo}}
\hline
\textbf{A} & \textbf{B} \\
\hline
\multirow{2}{*}{G1} & x \\[6pt]
\cline{2-2}
 & y \\[6pt]
\hline
\multirow{2}{*}{G2} & x \\[6pt]
\cline{2-2}
 & PASS \\[6pt]
\hline
\end{longtable}
"""


def test_header_repeats_and_caption_terminated():
    out, stats = report_tables.harden_longtables(SAMPLE)
    assert stats.hardened == 1
    assert "\\endfirsthead" in out and "\\endhead" in out and "\\endlastfoot" in out
    assert re.search(r"\\caption\{[^}]*\}\}?\\\\", out)          # caption ends with \\
    assert out.count("\\textbf{A} & \\textbf{B}") == 2            # header in first + continued head
    assert "(continued)" in out


def test_tables_with_endhead_untouched():
    t = SAMPLE.replace("\\hline\n\\multirow{2}{*}{G1}", "\\endhead\n\\multirow{2}{*}{G1}", 1)
    _, stats = report_tables.harden_longtables(t)
    assert stats.already_ok == 1 and stats.hardened == 0


def test_headerless_table_gets_caption_only_head():
    t = SAMPLE.replace("\\textbf{A} & \\textbf{B}", "\\multirow{2}{*}{G0} & first")
    out, _ = report_tables.harden_longtables(t)
    assert "\\rowcolor" not in out.split("\\endfirsthead")[0]


def test_groups_kept_together_and_status_coloured():
    out = report_tables.post_process_tex(SAMPLE)
    assert "\\\\*[6pt]" in out and "\\clineNB{2-2}" in out
    assert "\\statuspass{}" in out


def test_vehicles_follow_ui_selection():
    sel = {KEY_SPAN: 30, KEY_LL_IRC_CLASS_A: True, KEY_LL_IRC_70R_WHEELED: False,
           KEY_LL_IRC_CLASS_SV: True, KEY_BL_IRC_CLASS_SV: False}
    rows = live_loads.collect_vehicle_rows(sel)
    assert [r.label for r in rows] == ["Class A", "Class SV"]
    assert rows[0].braking and rows[0].braking_kN == pytest.approx(0.2 * rows[0].total_kN)
    assert not rows[1].braking and rows[1].braking_kN is None


def test_no_vehicle_selected_message():
    assert "No IRC vehicle class selected" in live_loads.vehicle_table_tex({KEY_SPAN: 30})


def test_ur_charts_written(tmp_path):
    recs = [report_charts.UrRecord(report_charts.GROUP_DECK, "Flexure", 0.9),
            report_charts.UrRecord(report_charts.GROUP_CB, "Compression", 1.2)]
    out = report_charts.build_ur_charts([("G1", 0.5), ("G2", 3.6)], recs, str(tmp_path))
    assert os.path.getsize(out["ur_overview"]) > 5000
    assert os.path.getsize(out["ur_breakdown"]) > 5000


def test_material_chart_and_missing_end_diaphragm_note(tmp_path):
    q = {"steel_girders_wt_total": "41.12", "bracing_top_wt_total": "0.36",
         "concrete_deck_vol_total": "179.81", "rebar_deck_wt_total": "21.58"}
    res = report_charts.build_material_chart(q, str(tmp_path))
    assert os.path.exists(res["material"]) and res["notes"]


def test_theme_is_single_source():
    pre = report_theme.build_preamble("P", "", "2026-01-01", "Rev 0")
    assert THEME.palette.osdag_green in pre and "footskip=" + THEME.page.foot_skip in pre
    assert "P $|$" not in pre          # no dangling separator when job number is empty


CHAPTER_FILES = ["chap1.py", "chap2.py", "chap3.py", "chap4.py", "chap5.py", "chap6.py",
                 "chap7.py", "chap8.py", "chap9.py", "executive_summary.py", "live_loads.py"]


@pytest.mark.parametrize("fname", CHAPTER_FILES)
def test_no_hardcoded_global_styling_in_chapters(fname):
    """Fonts, colours, page margins and table padding must come from report_theme."""
    here = os.path.dirname(report_theme.__file__)
    src = open(os.path.join(here, fname), encoding="utf-8").read()
    for pat in (r"\\definecolor", r"\\geometry", r"\\setlength\{\\tabcolsep", r"\\renewcommand\{\\arraystretch"):
        assert not re.search(pat, src), f"{fname} hard-codes {pat}"
