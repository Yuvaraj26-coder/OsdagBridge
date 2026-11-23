---
title: "OsdagBridge LaTeX Report Generator — Technical Changes"
author: "Yuvaraj Satvik"
date: "2026-11-23"
---

# 1. Summary

The report generator (`src/osdagbridge/core/reports/`) was refactored so that table layout, page geometry,
live-load reporting, charts and all styling are controlled from one place. Every item of the task is covered:

| # | Task | Result |
|---|------|--------|
| 1 | Repeated table headers | All 49 longtables now repeat the column header (and a "(continued)" caption) on every page |
| 2 | Footer overlap / spacing | Overlap-safe page geometry; footer note moved into a reserved band; row groups no longer split |
| 3 | Load tables | Vehicles and footway separated; vehicles follow the UI selection |
| 4 | UR charts | Overview + per-check charts with red dashed UR = 1.0 line, embedded in Section 5.5 |
| 5 | Material charts | Steel tonnage, concrete volume, reinforcement weight in Chapter 7 |
| 6 | Central style system | `report_theme.py` — single source of truth, enforced by a lint test |

> **Architecture note.** The repository's generator emits LaTeX *strings* from each `chapN.py` and compiles
> them with `pdflatex`; it does not use PyLaTeX objects. The changes therefore follow the existing architecture
> (string builders + a central post-processing step) rather than introducing a second, parallel PyLaTeX stack.
> `longtable_tex()` is the equivalent of PyLaTeX's `LongTable` + `end_table_header()` / `end_table_first_header()`.

# 2. Defects found in the baseline report

| Defect | Root cause (found in `Report_Before.tex`) |
|--------|-------------------------------------------|
| No repeated headers (Tables 5.3-5.7, 5.9 ...) | Only 2 of 49 longtables defined `\endhead` |
| LaTeX errors `Misplaced \noalign` / `Misplaced \omit` | `\caption{...}` inside longtable was not terminated with `\\` |
| `Unicode character ≤` error (Executive Summary) | `_tex()` did not map `≤` |
| Table rows touching the footer (p. 30, "G4") | footer rule pulled up with negative `\vspace`, no reserved footer band; `\multirow` groups broke across pages |
| Girder label spilling out of a table at a page break | `\multirow` group split by `longtable` |
| Footway load blank in Table 3.3 | value read from the *custom* key even in "As per IRC 6" mode |
| Live loads merged into one table | single `parameter / value` table |

# 3. Changes by file (all under `src/osdagbridge/core/reports/`)

| File | Status | Purpose |
|------|--------|---------|
| `report_theme.py` | **new** | Central style system (see Section 4) |
| `report_tables.py` | **new** | `longtable_tex()`, `harden_longtables()`, `keep_groups_together()`, `style_status_cells()`, `post_process_tex()` |
| `report_charts.py` | **new** | `build_ur_charts()`, `build_material_chart()` (matplotlib, headless) |
| `live_loads.py` | **new** | Vehicle, footway and associated-effects tables for Chapter 3 |
| `report_generator.py` | modified | `preamble()` delegates to the theme; chapters receive the temp image dir; `post_process_tex()` runs once on the full document; old inline preamble (~140 lines) removed |
| `report_utils.py` | modified | `_tex()` applies the theme's Unicode fall-backs |
| `chap3.py` | modified | Old Table 3.3 replaced by `live_load_tables_tex()` |
| `chap5.py` | modified | Records every UR while building Table 5.29; embeds charts in Section 5.5 (`asset_dir` argument) |
| `chap7.py` | modified | Embeds material chart (`asset_dir` argument) |
| `chap2/4/8.py` | modified | Local `\setlength{\tabcolsep}` / `\arraystretch` replaced by theme macros |
| `tests/test_report_enhancements.py` | **new** | 20 tests incl. the "no hard-coded styling" lint |
| `tools/replay_report_from_tex.py` | **new** | Re-runs an existing `.tex` through the new pipeline (no GUI/solver needed) |

## 3.1 Repeated headers

`harden_longtables()` parses every `\begin{longtable}` and rebuilds its head as

```
\caption{...}\\ \hline <header> \hline \endfirsthead
\caption[]{... (continued)}\\ \hline <header> \hline \endhead
\hline \multicolumn{n}{r}{Continued on next page}\\ \endfoot
\hline \endlastfoot
```

* Header detection requires a bold label row. Tables that start directly with data (e.g. Table 5.7) get a
  caption-only repeat instead of wrongly repeating their first data row.
* Tables that already define `\endhead` (Tables 2.8 and 4.1, hand-tuned multi-row headers) are left untouched.
* The closing `\hline` moves into `\endlastfoot`; a trailing `\hline` otherwise allows a page break that
  produces an orphan header page.
* `\needspace` before a `longtable` was **removed**: combined with longtable's own first-head handling it
  printed the head twice.

## 3.2 Layout and footer overlap

* Geometry: `bottom=1.1in`, `footskip=38pt`, `headheight=16pt` (all in `PageLayout`).
* The footer rule no longer uses negative `\vspace`; the "* Software default value" note is drawn *above*
  the rule inside the reserved footer band.
* `widowpenalty`/`clubpenalty` = 10000, `\raggedbottom`, `\needspace` before figures and tables.
* `keep_groups_together()` rewrites the row terminators inside each `\multirow{N}` group to `\\*` and the
  following `\cline` to `\clineNB`. **Why a new macro:** `\\*` alone is not enough — LaTeX's `\cline`
  and longtable's `\hline` both insert a legal break point after the rule. `\clineNB` (defined in the theme
  preamble) is `\cline` with a `\nobreak` before that glue. Verified on a minimal test and on the full report.
* **Result:** automated check (`pdftotext -bbox`) finds body text beyond the bottom margin on 1 page in the
  baseline and on 0 pages in the new report.

## 3.3 Load tables

* Table 3.3 *Vehicles*: Vehicle | Total Load (kN) | Impact Factor | Braking Load (Considered? / Value (kN) /
  Eccentricity (m)), two-level header as in the task example.
* Rows come from the Live Load check-boxes (`KEY_LL_IRC_*`); unticked vehicles never appear. Selection is
  parsed safely (a stored string `"False"` is not treated as ticked).
* Total loads come from `IRC6_2017` (`cl_204_*`). Impact = 1 + IM (Cl. 208.2 / 208.3). Braking "Considered?" for
  Class SV follows `KEY_BL_IRC_CLASS_SV`; eccentricity from `KEY_LL_ECCENTRICITY`.
* Table 3.4 *Footway* (separate) and Table 3.5 *Associated effects* (centrifugal force).

## 3.4 Charts

* **Section 5.5:** Figure 5.1 = governing UR of each girder, deck slab, cross bracing and end diaphragms;
  Figure 5.2 = every individual check in four panels. Bars are green (UR <= 1.0) or red (UR > 1.0), annotated with
  their value; the red dashed line marks UR = 1.0. URs are recorded from the same cells that fill Table 5.29,
  so chart and table cannot disagree.
* **Chapter 7:** Figure 7.1 = structural steel tonnage (girders, cross bracing, end diaphragms), concrete volume (m^3)
  and reinforcement weight (MT) as three panels (different units are deliberately not forced onto a dual axis).
* Charts use matplotlib's object API with the Agg canvas (no `pyplot`, no global backend switch), so they are
  safe inside the Qt desktop app. Images are written to the temporary `images/` directory that
  `generate_report()` already creates and deletes after compilation.
* A chart failure is logged and skipped; it never aborts report generation.

# 4. Structure of `report_theme.py`

```
Palette      osdag_green, header_bg, group_bg, pass_green, fail_red, threshold_red, muted, grid,
             steel_blue, concrete_grey, rebar_orange                (one hex set, used by LaTeX AND matplotlib)
Typography   base_pt, line_stretch, caption look
PageLayout   paper, margins, head_height, head_sep, foot_skip, rule widths, widow/club penalties,
             raggedbottom, needspace_lines
TableStyle   tabcolsep, array_stretch, rule width, extra row height, header shading, density presets
             (\tableDense / \tableTight / \tableNarrow / \tableRoomy), "continued" labels, keep_group_together,
             colour_status_cells
ChartStyle   dpi, fonts, figure sizes, bar width, threshold label/width/dash, embed width
Theme        bundles the above + Unicode fall-back table;  THEME = Theme()

build_preamble(...)    -> complete LaTeX preamble
latex_color_defs()     -> \definecolor for each palette entry
mpl_rc()               -> matplotlib rcParams from the same palette
```

Restyle example: `THEME = replace(THEME, palette=replace(THEME.palette, osdag_green="1E88E5"))` changes the
header/footer rules, table header shading and chart accents everywhere.

`test_no_hardcoded_global_styling_in_chapters` fails if any chapter file reintroduces `\definecolor`,
`\geometry`, `\setlength{\tabcolsep}` or `\renewcommand{\arraystretch}`. PASS / FAIL colours are applied by one
post-processing rule (`style_status_cells`) instead of per-chapter `\textcolor`.

# 5. Rationale

* **String pipeline kept.** A PyLaTeX rewrite of ~4,000 lines would change every table and risk regressions in a
  working calculation report. A single post-processor gives uniform behaviour for all 49 tables today and for
  any table added later.
* **Theme as frozen dataclasses.** Typed, discoverable, immutable; one hex palette removes colour drift
  between LaTeX and charts.
* **Group integrity over page filling.** Keeping each girder's rows together costs some white space
  (report length 55 -> 60 pages in the replay) but removes orphaned labels and split groups.
* **No new LaTeX packages**; everything uses packages already loaded, which matters for the bundled
  `osdag_latex_env`.

# 6. Open polish added

* Shaded table headers; green PASS / red FAIL labels
* Header text without a dangling `|` when the job number is empty
* Unicode glyph fall-backs (<=, >=, +/-, degree, Greek letters)
* Footer note no longer collides with page content
* Chart legends, value labels and consistent colours with the report

# 7. Items for the maintainers (found, not changed)

1. `IRC6_2017.cl_211_2_braking_force()` raises `UnboundLocalError` for 1-2 lane bridges (`braking_force_2` unset),
   so the baseline printed "Braking Load: N/A". The report derives braking as 20 % of the first-train load
   (IRC 6 Cl. 211.2) instead; the helper should be fixed.
2. `IRC6_2017` has no Class AA / 70R-bogie definition; `live_loads._NOMINAL_TONNES` uses nominal tonnages
   (40 t, 70 t, 40 t). **Please verify against IRC 6 Cl. 204.1.**
3. The BOQ has no end-diaphragm quantity; the chart notes this instead of inventing a value.
4. Baseline data issues: Table 2.7 prints girder dimensions in metres labelled "mm"; Table 2.9 and 5.23 list
   different bracing sections; the footpath-pressure UI label says "kN/mm^2"; the Table 5.29 note says "all
   values <= 1.0" even when checks fail; the end-diaphragm rows of 5.29 mirror the cross-bracing rows.
5. Centrifugal force is reported as "not applicable" because the UI has no curvature input.

# 8. How the "After" report was produced and how to reproduce it

The desktop GUI and solver cannot run in a headless environment, so `Report_After.pdf` was made with
`tools/replay_report_from_tex.py`, which feeds the baseline `Report_Before.tex` through the **production** code
for the preamble, Chapter 3 tables, both chart sets and the table post-processing. Chart numbers are parsed
from the baseline report's own tables. To regenerate from the GUI: *Design -> Generate Report* (the same code path).

```
python -m pytest tests/test_report_enhancements.py
python tools/replay_report_from_tex.py Report_Before.tex out_dir --compile
```
