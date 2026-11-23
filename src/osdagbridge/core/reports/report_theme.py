# =============================================================================
# OsdagBridge — Report Theme  (SINGLE SOURCE OF TRUTH for report styling)
# =============================================================================
# Every colour, font size, page margin, table padding, header/footer rule and
# chart style used by the report lives in THIS file. Chapter modules and the
# report generator import from here and never hard-code styling values.
#
# To restyle the whole report, edit the dataclass defaults below (or build a
# modified copy with ``dataclasses.replace`` and assign it to ``THEME``).
#
#   Palette      – colours, shared by LaTeX (\definecolor) and matplotlib
#   Typography   – base font size, line stretch, caption look
#   PageLayout   – paper, margins, header/footer geometry (overlap-safe)
#   TableStyle   – cell padding, rule widths, header shading, row spacing
#   ChartStyle   – figure size, dpi, bar colours, threshold-line style
#   Theme        – bundles all of the above; module-level ``THEME`` is the
#                  instance consumed by the rest of the report package
#
# Public helpers
#   build_preamble(...)   -> LaTeX preamble string (documentclass .. \begin{document})
#   latex_color_defs()    -> \definecolor lines for every palette entry
#   mpl_rc()              -> matplotlib rcParams dict matching the palette
# =============================================================================

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Dict

from osdagbridge.core.reports.report_utils import _tex


# -----------------------------------------------------------------------------
# Palette
# -----------------------------------------------------------------------------
@dataclass(frozen=True)
class Palette:
    """Hex colours (no leading '#'). Used by BOTH LaTeX and matplotlib."""
    osdag_green: str = "91B014"    # brand colour: rules, header/footer
    header_bg: str = "E6EEC4"      # table header row shading
    group_bg: str = "F5F8E8"       # sub-group tint (reserved for group rows)
    pass_green: str = "2E7D32"     # PASS text / passing bars
    fail_red: str = "C62828"       # FAIL text / failing bars
    threshold_red: str = "E53935"  # UR = 1.0 reference line
    text: str = "000000"
    muted: str = "5F6368"          # notes, continued-labels
    grid: str = "D0D4D9"           # chart grid lines
    steel_blue: str = "3F6D9A"     # material charts: structural steel
    concrete_grey: str = "8D99A6"  # material charts: concrete
    rebar_orange: str = "D9822B"   # material charts: reinforcement

    def as_dict(self) -> Dict[str, str]:
        return {
            "osdagGreen": self.osdag_green,
            "tableHeaderBg": self.header_bg,
            "tableGroupBg": self.group_bg,
            "statusPass": self.pass_green,
            "statusFail": self.fail_red,
            "mutedText": self.muted,
        }


# -----------------------------------------------------------------------------
# Typography
# -----------------------------------------------------------------------------
@dataclass(frozen=True)
class Typography:
    base_pt: int = 12
    line_stretch: float = 1.15
    caption_label_bold: bool = True
    chapter_title_size: str = r"\Large"


# -----------------------------------------------------------------------------
# Page layout  (footer-overlap-safe geometry)
# -----------------------------------------------------------------------------
@dataclass(frozen=True)
class PageLayout:
    paper: str = "a4paper"
    left: str = "1in"
    right: str = "1in"
    top: str = "1in"
    # The bottom margin + footskip together reserve a clear band for the footer
    # (and the optional "* Software default value" note) so that body text and
    # table rows can never run into it.
    bottom: str = "1.1in"
    head_height: str = "16pt"
    head_sep: str = "14pt"
    foot_skip: str = "38pt"
    head_rule_pt: float = 1.0
    foot_rule_pt: float = 1.0
    # Typographic page-break control
    widow_penalty: int = 10000
    club_penalty: int = 10000
    raggedbottom: bool = True
    # Move to a new page when fewer than this many lines are left before a
    # heading / table / figure starts.
    needspace_lines: int = 6


# -----------------------------------------------------------------------------
# Tables
# -----------------------------------------------------------------------------
@dataclass(frozen=True)
class TableStyle:
    tabcolsep: str = "6pt"
    array_stretch: float = 1.12
    array_rule_width: str = "0.5pt"
    extra_row_height: str = "0.6pt"
    lt_pre: str = "0pt"
    lt_post: str = "8pt"
    row_gap: str = "6pt"                       # \\[6pt] used by chapter tables
    # Named density presets, exposed to chapters as macros (\tableDense, \tableTight,
    # \tableNarrow, \tableRoomy) so chapters never set padding themselves.
    tabcolsep_dense: str = "4pt"
    tabcolsep_tight: str = "3.5pt"
    tabcolsep_narrow: str = "3pt"
    array_stretch_roomy: float = 1.25
    shade_header: bool = True
    continued_label: str = "Continued on next page"
    continued_caption: str = "(continued)"
    keep_group_together: bool = True           # never split a \multirow block
    colour_status_cells: bool = True           # PASS green / FAIL red


# -----------------------------------------------------------------------------
# Charts
# -----------------------------------------------------------------------------
@dataclass(frozen=True)
class ChartStyle:
    dpi: int = 220
    font_family: str = "serif"
    font_size: float = 9.5
    title_size: float = 11.0
    overview_size_in: tuple = (6.4, 3.6)       # (w, h) inches
    breakdown_size_in: tuple = (7.2, 7.0)
    material_size_in: tuple = (6.4, 3.3)
    bar_width: float = 0.62
    threshold_label: str = "UR = 1.0 (limit)"
    threshold_linewidth: float = 1.6
    threshold_dash: tuple = (6, 4)
    latex_width: str = r"0.92\linewidth"       # width used when embedding


# -----------------------------------------------------------------------------
# Theme bundle
# -----------------------------------------------------------------------------
@dataclass(frozen=True)
class Theme:
    palette: Palette = field(default_factory=Palette)
    typography: Typography = field(default_factory=Typography)
    page: PageLayout = field(default_factory=PageLayout)
    table: TableStyle = field(default_factory=TableStyle)
    chart: ChartStyle = field(default_factory=ChartStyle)

    # Unicode glyphs that pdflatex cannot typeset natively, mapped to math/text
    # fall-backs. Declared in the preamble AND applied by _tex().
    unicode_fallbacks: Dict[int, str] = field(default_factory=lambda: {
        0x2264: r"\ensuremath{\leq}",      # ≤
        0x2265: r"\ensuremath{\geq}",      # ≥
        0x00B1: r"\ensuremath{\pm}",       # ±
        0x00B0: r"\ensuremath{^{\circ}}",  # °
        0x00B5: r"\ensuremath{\mu}",       # µ
        0x03BC: r"\ensuremath{\mu}",       # μ
        0x00B2: r"\ensuremath{^{2}}",      # ²
        0x00B3: r"\ensuremath{^{3}}",      # ³
        0x2212: r"\ensuremath{-}",         # −
        0x2013: r"--",                     # –
        0x2014: r"---",                    # —
        0x03C3: r"\ensuremath{\sigma}",    # σ
        0x03C4: r"\ensuremath{\tau}",      # τ
        0x03C6: r"\ensuremath{\phi}",      # φ
        0x0394: r"\ensuremath{\Delta}",    # Δ
        0x03BB: r"\ensuremath{\lambda}",   # λ
        0x03B3: r"\ensuremath{\gamma}",    # γ
        0x03B4: r"\ensuremath{\delta}",    # δ
        0x2248: r"\ensuremath{\approx}",   # ≈
        0x00D7: r"\ensuremath{\times}",    # ×
    })


#: The theme instance consumed by every report module.
THEME = Theme()


# -----------------------------------------------------------------------------
# LaTeX helpers
# -----------------------------------------------------------------------------
def latex_color_defs(theme: Theme = THEME) -> str:
    return "\n".join(
        r"\definecolor{%s}{HTML}{%s}" % (name, hexv)
        for name, hexv in theme.palette.as_dict().items()
    )


def _unicode_declarations(theme: Theme = THEME) -> str:
    return "\n".join(
        r"\DeclareUnicodeCharacter{%04X}{%s}" % (cp, repl)
        for cp, repl in theme.unicode_fallbacks.items()
    )


def tex_unicode_fallback(s: str, theme: Theme = THEME) -> str:
    """Replace un-typesettable unicode characters in an already-escaped string."""
    for cp, repl in theme.unicode_fallbacks.items():
        s = s.replace(chr(cp), repl)
    return s


def _header_text(left_a: str, left_b: str) -> str:
    """'A $|$ B', but just 'A' when B is empty (no dangling separator)."""
    if left_a and left_b:
        return left_a + r" $|$ " + left_b
    return left_a or left_b


def _page_style(name: str, theme: Theme, head_l: str, head_r: str, with_head: bool = True) -> str:
    pg = theme.page
    head = ""
    if with_head:
        head = (
            "  \\fancyhead[L]{" + head_l + "}\n"
            "  \\fancyhead[R]{" + head_r + "}\n"
            "  \\renewcommand{\\headrule}{\\color{osdagGreen}"
            "\\hrule width\\headwidth height " + f"{pg.head_rule_pt}pt" + "}\n"
        )
    else:
        head = "  \\renewcommand{\\headrulewidth}{0pt}\n"
    return (
        "\\fancypagestyle{" + name + "}{\n"
        "  \\fancyhf{}\n" + head +
        "  \\fancyfoot[L]{Osdag $|$ FOSSEE $|$ Indian Institute of Technology Bombay}\n"
        "  \\fancyfoot[R]{Page \\thepage\\ of \\pageref{LastPage}}\n"
        # Footer rule. The optional "* Software default value" note sits ABOVE
        # the rule inside the reserved footer band (see PageLayout.foot_skip),
        # so it can no longer collide with the page body.
        "  \\renewcommand{\\footrule}{%\n"
        "    \\ifbool{hasSDonPage}{%\n"
        "      \\hbox to \\headwidth{\\textcolor{mutedText}{\\footnotesize\\textit{* Software default value}}\\hfil}%\n"
        "      \\vspace{3pt}%\n"
        "    }{}%\n"
        "    {\\color{osdagGreen}\\hrule width\\headwidth height " + f"{pg.foot_rule_pt}pt" + "}%\n"
        "    \\vspace{5pt}%\n"
        "  }\n"
        "}\n"
    )


def build_preamble(project_name, job_number, report_date, report_version="Rev 0",
                   theme: Theme = THEME) -> str:
    """Return the full LaTeX preamble up to and including \\begin{document}."""
    pg, ty, tb, pal = theme.page, theme.typography, theme.table, theme.palette
    pn, jn, rd, rv = _tex(project_name), _tex(job_number), _tex(report_date), _tex(report_version)
    head_l = _header_text(pn, jn)
    head_r = _header_text(rd, rv)
    label_bf = "labelfont=bf," if ty.caption_label_bold else ""

    geometry = (
        f"\\usepackage[{pg.paper}, left={pg.left}, right={pg.right}, top={pg.top}, "
        f"bottom={pg.bottom}, headheight={pg.head_height}, headsep={pg.head_sep}, "
        f"footskip={pg.foot_skip}]{{geometry}}"
    )

    raggedbottom = "\\raggedbottom" if pg.raggedbottom else ""

    return (
        f"\\documentclass[{ty.base_pt}pt,{pg.paper}]{{report}}\n\n"
        "% ---- Packages -------------------------------------------------------\n"
        "\\usepackage[T1]{fontenc}\n"
        "\\usepackage[utf8]{inputenc}\n"
        "\\usepackage{textcomp}\n"
        + geometry + "\n"
        "\\usepackage{graphicx}\n"
        "\\usepackage{amsmath}\n"
        "\\usepackage{amssymb}\n"
        "\\usepackage{booktabs}\n"
        "\\usepackage{array}\n"
        "\\usepackage{tabularx}\n"
        "\\usepackage{float}\n"
        "\\usepackage{fancyhdr}\n"
        "\\usepackage[hidelinks]{hyperref}\n"
        "\\usepackage{xcolor}\n"
        "\\usepackage{setspace}\n"
        "\\usepackage{enumitem}\n"
        "\\usepackage{caption}\n"
        "\\captionsetup{\n"
        f"    {label_bf}\n"
        "    justification=raggedright,\n"
        "    singlelinecheck=false,\n"
        "    format=plain\n"
        "}\n"
        "\\usepackage{subcaption}\n"
        "\\usepackage{multirow}\n"
        "\\usepackage{colortbl}\n"
        "\\usepackage{longtable}\n"
        "\\setlength{\\LTleft}{\\fill}\n"
        "\\setlength{\\LTright}{\\fill}\n"
        "\\usepackage{titlesec}\n"
        "\\usepackage{titletoc}\n"
        "\\usepackage{lastpage}\n"
        "\\usepackage{makecell}\n"
        "\\usepackage{etoolbox}\n"
        "\\usepackage{needspace}\n\n"
        "% ---- Unicode fall-backs (≤ ≥ ± ° ...) --------------------------------\n"
        + _unicode_declarations(theme) + "\n\n"
        "% ---- Colours (from report_theme.Palette) -----------------------------\n"
        + latex_color_defs(theme) + "\n"
        "\\newcommand{\\statuspass}{\\textcolor{statusPass}{\\textbf{PASS}}}\n"
        "\\newcommand{\\statusfail}{\\textcolor{statusFail}{\\textbf{FAIL}}}\n\n"
        "% ---- Numbering --------------------------------------------------------\n"
        "\\numberwithin{table}{chapter}\n"
        "\\numberwithin{figure}{chapter}\n\n"
        "% ---- Table layout (from report_theme.TableStyle) ---------------------\n"
        f"\\setlength{{\\tabcolsep}}{{{tb.tabcolsep}}}\n"
        f"\\renewcommand{{\\arraystretch}}{{{tb.array_stretch}}}\n"
        f"\\setlength{{\\LTpre}}{{{tb.lt_pre}}}\n"
        f"\\setlength{{\\LTpost}}{{{tb.lt_post}}}\n"
        f"\\setlength{{\\arrayrulewidth}}{{{tb.array_rule_width}}}\n"
        f"\\setlength{{\\extrarowheight}}{{{tb.extra_row_height}}}\n"
        f"\\newcommand{{\\tableDense}}{{\\setlength{{\\tabcolsep}}{{{tb.tabcolsep_dense}}}}}\n"
        f"\\newcommand{{\\tableTight}}{{\\setlength{{\\tabcolsep}}{{{tb.tabcolsep_tight}}}}}\n"
        f"\\newcommand{{\\tableNarrow}}{{\\setlength{{\\tabcolsep}}{{{tb.tabcolsep_narrow}}}}}\n"
        f"\\newcommand{{\\tableRoomy}}{{\\renewcommand{{\\arraystretch}}{{{tb.array_stretch_roomy}}}}}\n\n"
        "% ---- No-break \\cline: keeps \\multirow groups on one page ---------------\n"
        "\\makeatletter\n"
        "\\def\\clineNB#1{\\@clineNB#1\\@nil}\n"
        "\\def\\@clineNB#1-#2\\@nil{\\omit\\@multicnt#1\\advance\\@multispan\\m@ne"
        "\\ifnum\\@multicnt=\\@ne\\@firstofone{&\\omit}\\fi\\@multicnt#2\\advance\\@multicnt-#1"
        "\\advance\\@multispan\\@ne\\leaders\\hrule\\@height\\arrayrulewidth\\hfill\\cr"
        "\\noalign{\\nobreak\\vskip-\\arrayrulewidth}}\n"
        "\\makeatother\n\n"
        "% ---- Page-break control -----------------------------------------------\n"
        f"\\widowpenalty={pg.widow_penalty}\n"
        f"\\clubpenalty={pg.club_penalty}\n"
        + raggedbottom + "\n"
        f"\\BeforeBeginEnvironment{{table}}{{\\needspace{{{pg.needspace_lines}\\baselineskip}}}}\n"
        "% (no \\needspace before longtable: it duplicates the first head; longtable keeps\n"
        "%  head + first rows together on its own)\n"
        f"\\BeforeBeginEnvironment{{figure}}{{\\needspace{{{pg.needspace_lines + 4}\\baselineskip}}}}\n\n"
        "% ---- Header / footer -------------------------------------------------\n"
        + _page_style("main", theme, head_l, head_r) +
        _page_style("plain", theme, head_l, head_r) +
        "\\fancypagestyle{firstpage}{\n"
        "  \\fancyhf{}\n"
        "  \\renewcommand{\\headrulewidth}{0pt}\n"
        "  \\fancyfoot[L]{Osdag $|$ FOSSEE $|$ Indian Institute of Technology Bombay}\n"
        "  \\fancyfoot[R]{Page \\thepage\\ of \\pageref{LastPage}}\n"
        "  \\renewcommand{\\footrule}{{\\color{osdagGreen}\\hrule width\\headwidth height "
        f"{pg.foot_rule_pt}pt}}\\vspace{{5pt}}}}\n"
        "}\n"
        "\\pagestyle{main}\n"
        f"\\setstretch{{{ty.line_stretch}}}\n\n"
        "% ---- Custom commands --------------------------------------------------\n"
        "\\newcommand{\\placeholder}[1]{\\textit{\\textless #1\\textgreater}}\n"
        "\\newcommand{\\todo}[1]{\\colorbox{yellow}{TODO: #1}}\n"
        "\\newcolumntype{L}[1]{>{\\raggedright\\arraybackslash}p{#1}}\n"
        "\\newcolumntype{C}[1]{>{\\centering\\arraybackslash}p{#1}}\n"
        "\\newcolumntype{R}[1]{>{\\raggedleft\\arraybackslash}p{#1}}\n\n"
        "% Software-default asterisk\n"
        "\\newbool{hasSDonPage}\n"
        "\\boolfalse{hasSDonPage}\n"
        "\\newcommand{\\markSD}{\\global\\booltrue{hasSDonPage}}\n"
        "\\newcommand{\\sdstar}{\\textsuperscript{*}\\markSD{}}\n"
        "\\AddToHook{shipout/before}{\\global\\boolfalse{hasSDonPage}}\n\n"
        "\\title{\\Large\\textbf{OsdagBridge} \\\\ \\normalsize Open Source Software for "
        "Steel Girder Bridge Design \\\\ \\vspace{2cm} \\large Design Report}\n"
        "\\author{}\n"
        "\\date{}\n\n"
        "\\begin{document}\n"
    )


# -----------------------------------------------------------------------------
# matplotlib helpers (kept here so charts share the palette)
# -----------------------------------------------------------------------------
def mpl_rc(theme: Theme = THEME) -> Dict[str, object]:
    cs, pal = theme.chart, theme.palette
    return {
        "font.family": cs.font_family,
        "font.size": cs.font_size,
        "axes.titlesize": cs.title_size,
        "axes.labelsize": cs.font_size,
        "axes.edgecolor": "#" + pal.muted,
        "axes.linewidth": 0.8,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "axes.axisbelow": True,
        "grid.color": "#" + pal.grid,
        "grid.linewidth": 0.6,
        "grid.alpha": 0.9,
        "xtick.color": "#" + pal.text,
        "ytick.color": "#" + pal.text,
        "mathtext.fontset": "cm",
        "savefig.dpi": cs.dpi,
    }


def with_overrides(**kwargs) -> Theme:
    """Convenience: ``with_overrides(palette=replace(THEME.palette, osdag_green='1E88E5'))``."""
    return replace(THEME, **kwargs)
