# =============================================================================
# OsdagBridge — Report table utilities
# =============================================================================
# Everything that decides HOW a table behaves across page breaks lives here:
#
#   longtable_tex()          build a longtable whose header repeats on every page
#   harden_longtables()      normalise every longtable already emitted by the
#                            chapter modules: terminated caption, \endfirsthead /
#                            \endhead / \endfoot, shaded header, "continued" label
#   keep_groups_together()   stop a \multirow group (e.g. one girder's rows)
#                            being split by a page break
#   style_status_cells()     PASS / FAIL -> theme colours
#   post_process_tex()       runs all of the above (called once, on the full
#                            document, by report_generator.generate_report)
#
# All visual parameters come from report_theme.THEME — nothing is hard-coded.
# =============================================================================

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from osdagbridge.core.reports.report_theme import THEME, Theme

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Low-level scanning helpers (brace / row aware)
# -----------------------------------------------------------------------------
def _match_brace(s: str, i: int) -> int:
    """Index of the '}' matching the '{' at s[i]; -1 if unbalanced."""
    depth = 0
    n = len(s)
    j = i
    while j < n:
        c = s[j]
        if c == "\\":
            j += 2
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return j
        j += 1
    return -1


def _row_terminators(s: str) -> List[Tuple[int, int]]:
    """(start, end) spans of every depth-0 row terminator ``\\\\[*][[len]]``."""
    spans: List[Tuple[int, int]] = []
    depth = 0
    i, n = 0, len(s)
    while i < n:
        c = s[i]
        if c == "\\":
            if i + 1 < n and s[i + 1] == "\\":
                start = i
                i += 2
                if i < n and s[i] == "*":
                    i += 1
                j = i
                while j < n and s[j] in " \t":
                    j += 1
                if j < n and s[j] == "[":
                    k = s.find("]", j)
                    if k != -1:
                        i = k + 1
                if depth == 0:
                    spans.append((start, i))
                continue
            i += 2
            continue
        if c == "%":
            nl = s.find("\n", i)
            i = n if nl == -1 else nl + 1
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
        i += 1
    return spans


def _count_columns(spec: str) -> int:
    """Number of data columns in a tabular column spec."""
    out, i = [], 0
    while i < len(spec):
        if spec[i] == "{":
            j = _match_brace(spec, i)
            i = (j + 1) if j != -1 else len(spec)
            continue
        out.append(spec[i])
        i += 1
    return sum(1 for ch in "".join(out) if ch in "lcrpmbLCRX")


_HLINE_RE = re.compile(r"^(\s*(\\hline|\\cline\{[^}]*\}|\\midrule|\\toprule|\\bottomrule)\s*)+")


def _strip_rules(s: str) -> str:
    return _HLINE_RE.sub("", s)



def _drop_trailing_hline(body: str) -> str:
    """The closing rule moves into \\endlastfoot: a trailing \\hline would offer
    a page break after the last row and produce an orphan header page."""
    b = body.strip("\n").rstrip()
    while b.endswith("\\hline"):
        b = b[: -len("\\hline")].rstrip()
    return b

# -----------------------------------------------------------------------------
# Public builder for NEW tables (used by live-load tables etc.)
# -----------------------------------------------------------------------------
_TRAILING_CLINE = re.compile(r"\\cline\{[^}]*\}\s*$")


def longtable_tex(spec: str,
                  header_rows: Sequence[str],
                  body: str,
                  caption: Optional[str] = None,
                  theme: Theme = THEME) -> str:
    """
    Build a ``longtable`` whose column header(s) repeat on every page.

    ``header_rows``  one or more LaTeX row strings (each WITHOUT trailing ``\\\\``);
                     several rows give a multi-level header.
    ``body``         pre-built body rows, each ending in ``\\\\`` (+ ``\\hline``).
    ``caption``      caption text (LaTeX); ``None`` for a caption-less table.
    """
    ncols = _count_columns(spec)
    tb = theme.table
    shade = r"\rowcolor{tableHeaderBg}" if tb.shade_header else ""

    def head_block() -> str:
        if not header_rows:
            return r"\hline" if not caption else ""
        lines = [r"\hline"]
        for k, h in enumerate(header_rows):
            m = _TRAILING_CLINE.search(h)
            rule = ""
            if m:                                # e.g. "... \\cline{4-6}" -> row end, then rule
                h, rule = h[:m.start()].rstrip(), m.group(0)
                if h.endswith("\\\\"):
                    h = h[:-2]
            lines.append(((shade + " ") if shade else "") + h.rstrip() + r" \\" + (("\n" + rule) if rule else ""))
        lines.append(r"\hline")
        return "\n".join(lines)

    first = ""
    cont = ""
    if caption:
        first = "\\caption{" + caption + "}\\\\\n"
        cont = "\\caption[]{" + caption + r" \textit{" + tb.continued_caption + "}}\\\\\n"

    return (
        "\\begin{longtable}{" + spec + "}\n"
        + first + head_block() + "\n\\endfirsthead\n"
        + cont + head_block() + "\n\\endhead\n"
        + "\\hline\\multicolumn{" + str(ncols) + "}{r}{\\footnotesize\\textit{\\textcolor{mutedText}{"
        + tb.continued_label + "}}}\\\\\n\\endfoot\n"
        + "\\hline\n\\endlastfoot\n"
        + _drop_trailing_hline(body) + "\n"
        + "\\end{longtable}\n"
    )


# -----------------------------------------------------------------------------
# Normaliser for longtables emitted by chapter modules
# -----------------------------------------------------------------------------
_LT_BEGIN = re.compile(r"\\begin\{longtable\}(\[[a-z]\])?\{")


@dataclass
class HardenStats:
    total: int = 0
    hardened: int = 0
    already_ok: int = 0
    skipped: int = 0


def _parse_longtable(tex: str, start: int):
    """Return (spec, body, end_index_after_\\end{longtable}) for the table at *start*."""
    m = _LT_BEGIN.match(tex, start)
    spec_open = m.end() - 1
    spec_close = _match_brace(tex, spec_open)
    spec = tex[spec_open + 1:spec_close]
    end_tok = tex.find("\\end{longtable}", spec_close)
    body = tex[spec_close + 1:end_tok]
    return spec, body, end_tok + len("\\end{longtable}")


def _split_head(body: str):
    """
    Split a table body into (caption, labels, header_row, rest).
    Returns None when the layout is not the standard
    ``[\\caption] \\hline <header row> \\hline <body>`` shape.
    """
    s = body.lstrip()
    caption = None
    labels: List[str] = []
    if s.startswith("\\caption"):
        i = len("\\caption")
        if s[i:i + 1] == "[":
            i = s.find("]", i) + 1
        if s[i:i + 1] != "{":
            return None
        j = _match_brace(s, i)
        if j == -1:
            return None
        caption = s[i + 1:j]
        s = s[j + 1:].lstrip()
        # an existing terminator after the caption is dropped (we re-add it)
        if s.startswith("\\\\"):
            s = s[2:].lstrip()
        while s.startswith("\\label{"):
            j = _match_brace(s, len("\\label"))
            labels.append(s[:j + 1])
            s = s[j + 1:].lstrip()
    if not s.startswith("\\hline"):
        return None
    s = s[len("\\hline"):].lstrip()
    terms = _row_terminators(s)
    if not terms:
        return None
    t0, t1 = terms[0]
    header = s[:t0].strip()
    if not header:
        return None
    # A real column header is a row of bold labels. Tables whose first row is
    # already data (e.g. starts a \\multirow group) have NO header: repeat the
    # caption only and keep that first row in the body.
    if "\\textbf{" not in header or header.startswith("\\multirow"):
        return caption, labels, None, "\\hline\n" + s
    rest = _strip_rules(s[t1:].lstrip())
    # a leading \hline belongs to the head, but the *body* keeps its own rules,
    # so we re-add exactly one \hline separating head from body rows.
    return caption, labels, header, rest


def harden_longtables(tex: str, theme: Theme = THEME) -> Tuple[str, HardenStats]:
    """
    Rewrite every ``longtable`` so that its header repeats on every page.

    Tables that already define ``\\endhead`` are left untouched (they were
    hand-tuned, e.g. the two-row header of the maximum-demand table).
    """
    stats = HardenStats()
    out: List[str] = []
    pos = 0
    for m in _LT_BEGIN.finditer(tex):
        if m.start() < pos:
            continue
        stats.total += 1
        spec, body, end = _parse_longtable(tex, m.start())
        out.append(tex[pos:m.start()])
        pos = end
        if "\\endhead" in body:
            stats.already_ok += 1
            out.append(tex[m.start():end])
            continue
        parts = _split_head(body)
        if parts is None:
            stats.skipped += 1
            logger.warning("longtable not in standard layout - left unchanged: %.60s", body.strip())
            out.append(tex[m.start():end])
            continue
        caption, labels, header, rest = parts
        if header is None:
            new = longtable_tex(spec, [], rest, caption, theme)
        else:
            new = longtable_tex(spec, [header], "\\hline\n" + rest, caption, theme)
        if labels:
            new = new.replace("\\endfirsthead", "".join(labels) + "\n\\endfirsthead", 1)
        out.append(new.rstrip("\n"))
        stats.hardened += 1
    out.append(tex[pos:])
    return "".join(out), stats


# -----------------------------------------------------------------------------
# Keep \multirow groups together
# -----------------------------------------------------------------------------
_MULTIROW = re.compile(r"^\\multirow\{(\d+)\}")


def keep_groups_together(tex: str, theme: Theme = THEME) -> str:
    """
    In every longtable, row-terminators inside a ``\\multirow{N}{*}{label}``
    block (first N-1 rows) become ``\\\\*`` so LaTeX will not break the page
    in the middle of one girder's / panel's block of rows.
    """
    if not theme.table.keep_group_together:
        return tex
    out: List[str] = []
    pos = 0
    for m in _LT_BEGIN.finditer(tex):
        if m.start() < pos:
            continue
        spec, body, end = _parse_longtable(tex, m.start())
        out.append(tex[pos:m.start()])
        pos = end
        spec_open = m.end() - 1
        spec_close = _match_brace(tex, spec_open)
        head_text = tex[m.start():spec_close + 1]
        # operate only on the part of the body after \endlastfoot / \endhead
        cut = max(body.rfind("\\endlastfoot"), body.rfind("\\endhead"))
        cut = 0 if cut == -1 else cut + (len("\\endlastfoot") if body.rfind("\\endlastfoot") == cut else len("\\endhead"))
        prefix, rows_text = body[:cut], body[cut:]
        terms = _row_terminators(rows_text)
        mark = set()
        prev_end = 0
        for idx, (a, b) in enumerate(terms):
            row = _strip_rules(rows_text[prev_end:a].lstrip())
            mm = _MULTIROW.match(row)
            if mm:
                n = int(mm.group(1))
                for k in range(max(n - 1, 0)):
                    if idx + k < len(terms):
                        mark.add(idx + k)
            prev_end = b
        if mark:
            rebuilt, last = [], 0
            for idx, (a, b) in enumerate(terms):
                seg = rows_text[last:a]
                # the separator rule that FOLLOWS a protected row must not allow a break
                if (idx - 1) in mark:
                    seg = seg.replace("\\cline{", "\\clineNB{")
                rebuilt.append(seg)
                term = rows_text[a:b]
                if idx in mark and not term.startswith("\\\\*"):
                    term = "\\\\*" + term[2:]
                rebuilt.append(term)
                last = b
            rebuilt.append(rows_text[last:])
            rows_text = "".join(rebuilt)
        out.append(head_text + prefix + rows_text + "\\end{longtable}")
    out.append(tex[pos:])
    return "".join(out)


# -----------------------------------------------------------------------------
# PASS / FAIL cells
# -----------------------------------------------------------------------------
_STATUS_PATTERNS = [
    (re.compile(r"\\textcolor\{black\}\{PASS\}"), r"\\statuspass{}"),
    (re.compile(r"\\textcolor\{red\}\{FAIL\}"), r"\\statusfail{}"),
    (re.compile(r"(?<=& )PASS(?=\s*(?:&|\\\\))"), r"\\statuspass{}"),
    (re.compile(r"(?<=& )FAIL(?=\s*(?:&|\\\\))"), r"\\statusfail{}"),
]


def style_status_cells(tex: str, theme: Theme = THEME) -> str:
    if not theme.table.colour_status_cells:
        return tex
    for pat, repl in _STATUS_PATTERNS:
        tex = pat.sub(lambda _m, r=repl: r.replace("\\\\", "\\"), tex)
    return tex


# -----------------------------------------------------------------------------
# One-shot pipeline
# -----------------------------------------------------------------------------
def post_process_tex(tex: str, theme: Theme = THEME) -> str:
    """Apply all table post-processing to the assembled document."""
    tex = tex.replace("\r\n", "\n")
    tex, stats = harden_longtables(tex, theme)
    logger.info("longtables: %d total, %d hardened, %d already repeating, %d unchanged",
                stats.total, stats.hardened, stats.already_ok, stats.skipped)
    tex = keep_groups_together(tex, theme)
    tex = style_status_cells(tex, theme)
    return tex
