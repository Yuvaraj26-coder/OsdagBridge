# =============================================================================
# OsdagBridge — Report charts (matplotlib, headless)
# =============================================================================
#   build_ur_charts()        Utilization-ratio bar charts for Section 5.5
#   build_material_chart()   Material-quantity bar charts for Chapter 7
#
# * Uses matplotlib's object-oriented API with the Agg canvas directly — no
#   pyplot, no global backend switch — so it is safe inside the Qt desktop app.
# * All colours / sizes come from report_theme.THEME.
# * Images are written to the temporary asset directory supplied by the caller
#   (report_generator uses a TemporaryDirectory that is deleted after pdflatex).
# =============================================================================

from __future__ import annotations

import logging
import math
import os
import re
import textwrap
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.patches import Patch
from matplotlib.lines import Line2D

from osdagbridge.core.reports.report_theme import THEME, Theme, mpl_rc

logger = logging.getLogger(__name__)

# Element groups, in the order they appear in the charts.
GROUP_GIRDER = "Steel Plate Girders"
GROUP_DECK = "Concrete Deck Slab"
GROUP_CB = "Cross Bracing"
GROUP_ED = "End Diaphragms"
GROUPS = (GROUP_GIRDER, GROUP_DECK, GROUP_CB, GROUP_ED)


@dataclass
class UrRecord:
    group: str      # one of GROUPS
    label: str      # check name, e.g. "Moment"
    ur: float       # demand / capacity


# -----------------------------------------------------------------------------
# helpers
# -----------------------------------------------------------------------------
_NUM = re.compile(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?")


def to_float(value) -> Optional[float]:
    """Parse '0.42', '\\textcolor{red}{1.64}', 3.61, 'N.A.' ... -> float | None."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return None if (isinstance(value, float) and math.isnan(value)) else float(value)
    m = _NUM.search(str(value).replace("\\textcolor{red}", ""))
    return float(m.group(0)) if m else None


def _color(ur: float, theme: Theme) -> str:
    return "#" + (theme.palette.pass_green if ur <= 1.0 else theme.palette.fail_red)


def _save(fig: Figure, path: str, theme: Theme) -> str:
    FigureCanvasAgg(fig)
    fig.savefig(path, dpi=theme.chart.dpi, bbox_inches="tight", facecolor="white")
    return path.replace("\\", "/")


def _threshold(ax, theme: Theme, xmax: float):
    cs, pal = theme.chart, theme.palette
    ax.axhline(1.0, color="#" + pal.threshold_red, linestyle=(0, cs.threshold_dash),
               linewidth=cs.threshold_linewidth, zorder=3)


def _legend_handles(theme: Theme) -> List:
    pal, cs = theme.palette, theme.chart
    return [
        Patch(facecolor="#" + pal.pass_green, label="Pass (UR \u2264 1.0)"),
        Patch(facecolor="#" + pal.fail_red, label="Fail (UR > 1.0)"),
        Line2D([0], [0], color="#" + pal.threshold_red, linestyle=(0, cs.threshold_dash),
               linewidth=cs.threshold_linewidth, label=cs.threshold_label),
    ]


def _ylim_top(values: Sequence[float]) -> float:
    top = max([1.0] + [v for v in values if v is not None])
    return max(1.25, top * 1.18)


_SHORT = {
    "Flexure (sagging)": "Flexure (sag.)", "Flexure (hogging)": "Flexure (hog.)",
    "Cantilever Overhang": "Cantilever", "Punching Shear": "Punching", "One-Way Shear": "One-way shear",
    "Transverse Shear": "Transv. shear", "Crack Width": "Crack width", "LTB (constr.)": "LTB",
}


def _bars(ax, labels: Sequence[str], values: Sequence[float], theme: Theme, rotate: int = 0):
    cs = theme.chart
    xs = range(len(labels))
    ax.bar(xs, values, width=cs.bar_width, color=[_color(v, theme) for v in values],
           edgecolor="white", linewidth=0.6, zorder=2)
    for x, v in zip(xs, values):
        ax.text(x, v + 0.02 * _ylim_top(values), f"{v:.2f}", ha="center", va="bottom",
                fontsize=cs.font_size - 1.5, zorder=4)
    ax.set_xticks(list(xs))
    ax.set_xticklabels([textwrap.fill(_SHORT.get(str(l), str(l)), 12) for l in labels], rotation=rotate,
                       ha="right" if rotate else "center", rotation_mode="anchor")
    ax.set_ylim(0, _ylim_top(values))
    ax.set_ylabel("Utilization Ratio (Demand / Capacity)")
    _threshold(ax, theme, len(labels))


# -----------------------------------------------------------------------------
# Section 5.5 — utilization ratio charts
# -----------------------------------------------------------------------------
def build_ur_charts(girder_ur: Sequence[Tuple[str, float]],
                    records: Iterable[UrRecord],
                    out_dir: str,
                    theme: Theme = THEME) -> Dict[str, str]:
    """
    Returns {'ur_overview': path, 'ur_breakdown': path} (keys missing on failure).

    girder_ur  [(girder label, governing UR), ...]  one entry per girder
    records    every individual check UR (group, label, ur)
    """
    out: Dict[str, str] = {}
    os.makedirs(out_dir, exist_ok=True)
    recs = [r for r in records if r.ur is not None]
    by_group: Dict[str, List[UrRecord]] = {g: [r for r in recs if r.group == g] for g in GROUPS}

    try:
        import matplotlib
        with matplotlib.rc_context(mpl_rc(theme)):
            # ---- (1) overview: governing UR of every primary element --------
            labels, values = [], []
            for lbl, ur in girder_ur:
                if ur is not None:
                    labels.append(str(lbl))
                    values.append(float(ur))
            for g, short in ((GROUP_DECK, "Deck Slab"), (GROUP_CB, "Cross Bracing"),
                             (GROUP_ED, "End Diaphragms")):
                if by_group[g]:
                    labels.append(short)
                    values.append(max(r.ur for r in by_group[g]))
            if values:
                fig = Figure(figsize=theme.chart.overview_size_in)
                ax = fig.add_subplot(111)
                _bars(ax, labels, values, theme, rotate=20 if len(labels) > 6 else 0)
                ax.set_title("Governing Utilization Ratio of Primary Elements")
                ax.legend(handles=_legend_handles(theme), loc="upper right",
                          fontsize=theme.chart.font_size - 1.5, frameon=False, ncol=1)
                out["ur_overview"] = _save(fig, os.path.join(out_dir, "ur_overview.png"), theme)

            # ---- (2) breakdown: 2x2 panel, one per element -------------------
            if any(by_group[g] for g in GROUPS) or girder_ur:
                fig = Figure(figsize=theme.chart.breakdown_size_in)
                for k, g in enumerate(GROUPS):
                    ax = fig.add_subplot(2, 2, k + 1)
                    items = by_group[g]
                    if g == GROUP_GIRDER and not items and girder_ur:
                        items = [UrRecord(g, str(l), u) for l, u in girder_ur if u is not None]
                    if items:
                        _bars(ax, [i.label for i in items], [i.ur for i in items], theme, rotate=40)
                        if k % 2:
                            ax.set_ylabel("")
                    else:
                        ax.set_xticks([]); ax.set_yticks([])
                        ax.text(0.5, 0.5, "No utilization data\navailable", ha="center",
                                va="center", transform=ax.transAxes,
                                color="#" + theme.palette.muted)
                    ax.set_title(g, fontsize=theme.chart.font_size + 0.5)
                fig.legend(handles=_legend_handles(theme), loc="lower center", ncol=3,
                           frameon=False, fontsize=theme.chart.font_size - 1)
                fig.subplots_adjust(left=0.09, right=0.985, top=0.94, bottom=0.17,
                                    hspace=0.85, wspace=0.28)
                out["ur_breakdown"] = _save(fig, os.path.join(out_dir, "ur_breakdown.png"), theme)
    except Exception as exc:  # a chart must never break report generation
        logger.warning("UR chart generation failed: %s", exc, exc_info=True)
    return out


# -----------------------------------------------------------------------------
# Chapter 7 — material quantity charts
# -----------------------------------------------------------------------------
def build_material_chart(quantities: Dict[str, object], out_dir: str,
                         theme: Theme = THEME) -> Dict[str, object]:
    """
    quantities  the dict produced by boq_generator.calculate_material_quantities
                (string values such as '41.12' / 'N.A.').

    Returns {'material': path, 'notes': [str,...]} ; 'material' missing on failure.
    """
    q = {k: to_float(v) for k, v in quantities.items()}
    notes: List[str] = []
    os.makedirs(out_dir, exist_ok=True)

    steel_items: List[Tuple[str, float]] = []
    if q.get("steel_girders_wt_total") is not None:
        steel_items.append(("Girders", q["steel_girders_wt_total"]))
    cb = [q.get(k) for k in ("bracing_top_wt_total", "bracing_bot_wt_total", "bracing_diag_wt_total")]
    if any(v is not None for v in cb):
        steel_items.append(("Cross Bracing", sum(v for v in cb if v is not None)))
    if q.get("end_diaphragm_wt_total") is not None:
        steel_items.append(("End Diaphragms", q["end_diaphragm_wt_total"]))
    else:
        notes.append("End-diaphragm steel is not yet part of the quantity take-off "
                     "module and is therefore not plotted.")
    conc = q.get("concrete_deck_vol_total")
    rebar = q.get("rebar_deck_wt_total")
    if not steel_items and conc is None and rebar is None:
        return {"notes": notes}

    pal = theme.palette
    try:
        import matplotlib
        with matplotlib.rc_context(mpl_rc(theme)):
            fig = Figure(figsize=theme.chart.material_size_in)
            gs = fig.add_gridspec(1, 3, width_ratios=[2.2, 1, 1], wspace=0.55)

            def single(ax, labels, vals, colors, ylabel, title):
                ax.bar(range(len(vals)), vals, width=theme.chart.bar_width, color=colors,
                       edgecolor="white", zorder=2)
                top = max(vals) if vals else 1
                for i, v in enumerate(vals):
                    ax.text(i, v + 0.02 * top, f"{v:,.2f}", ha="center", va="bottom",
                            fontsize=theme.chart.font_size - 1.5)
                ax.set_xticks(range(len(vals))); ax.set_xticklabels(labels)
                ax.set_ylim(0, top * 1.22 if top else 1)
                ax.set_ylabel(ylabel); ax.set_title(title, fontsize=theme.chart.font_size + 0.5)

            ax1 = fig.add_subplot(gs[0, 0])
            if steel_items:
                single(ax1, [a for a, _ in steel_items], [b for _, b in steel_items],
                       ["#" + pal.steel_blue] * len(steel_items), "Weight (MT)", "Structural Steel")
            else:
                ax1.axis("off")
            ax2 = fig.add_subplot(gs[0, 1])
            if conc is not None:
                single(ax2, ["Deck Slab"], [conc], ["#" + pal.concrete_grey], "Volume (m$^3$)", "Concrete")
            else:
                ax2.axis("off")
            ax3 = fig.add_subplot(gs[0, 2])
            if rebar is not None:
                single(ax3, ["Deck Slab"], [rebar], ["#" + pal.rebar_orange], "Weight (MT)", "Reinforcement")
            else:
                ax3.axis("off")
            path = _save(fig, os.path.join(out_dir, "material_quantities.png"), theme)
        return {"material": path, "notes": notes}
    except Exception as exc:
        logger.warning("Material chart generation failed: %s", exc, exc_info=True)
        return {"notes": notes}
