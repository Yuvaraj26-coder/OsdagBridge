# =============================================================================
# OsdagBridge — Chapter 3 live-load tables
# =============================================================================
# Builds two separate tables from the selections made in the UI
# (Additional Inputs -> Loading -> Live Load):
#
#   Table 3.3(a)  Vehicle Live Loads  - one row per vehicle ticked in the UI,
#                 with total load, impact factor and braking-load columns
#   Table 3.3(b)  Footway Live Load   - footway pressure, width and reference
#   Table 3.3(c)  Other live-load effects (centrifugal force)
#
# Only vehicles that are selected in the UI appear in (a).
# =============================================================================

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional

from osdagbridge.core.utils.common import (
    KEY_BL_IRC_CLASS_SV,
    KEY_FOOTPATH,
    KEY_LL_CUSTOM_VEHICLES,
    KEY_LL_ECCENTRICITY,
    KEY_LL_FOOTPATH_PRESSURE_MODE,
    KEY_LL_FOOTPATH_PRESSURE_VALUE,
    KEY_LL_IRC_70R_BOGIE,
    KEY_LL_IRC_70R_TRACKED,
    KEY_LL_IRC_70R_WHEELED,
    KEY_LL_IRC_AA_TRACKED,
    KEY_LL_IRC_AA_WHEELED,
    KEY_LL_IRC_CLASS_A,
    KEY_LL_IRC_CLASS_FATIGUE,
    KEY_LL_IRC_CLASS_SV,
    KEY_SPAN,
    KEY_TS_FOOTPATH_WIDTH,
)
from osdagbridge.core.reports.report_tables import longtable_tex
from osdagbridge.core.reports.report_utils import _tex

logger = logging.getLogger(__name__)

G = 9.81                      # m/s^2, same value the IRC6_2017 module uses
BRAKING_FRACTION = 0.20       # IRC 6 Cl. 211.2: 20 % of the first train of loads
DASH = "---"

# Nominal total loads in tonnes for vehicles that the IRC6_2017 module does not
# (yet) define geometrically. IRC 6 Cl. 204.1.
_NOMINAL_TONNES = {"aa_wheeled": 40.0, "aa_tracked": 70.0, "bogie_70r": 40.0}


@dataclass
class VehicleRow:
    label: str
    total_kN: Optional[float]
    impact: Optional[float]
    braking: bool
    braking_kN: Optional[float]


def _is_on(v) -> bool:
    if isinstance(v, str):
        return v.strip().lower() in ("true", "yes", "1", "checked", "on")
    return bool(v)


def _irc():
    from osdagbridge.core.utils.codes.irc6_2017 import IRC6_2017
    return IRC6_2017


def _total_kN(kind: str) -> Optional[float]:
    """Total vehicle load in kN, from the IRC6_2017 module where available."""
    try:
        irc = _irc()
        if kind == "A":
            return sum(irc.cl_204_1_ClassA_vehicle()["wheel_loads"]) / 1000.0
        if kind == "70R_W":
            return sum(irc.cl_204_1_Class70R_vehicle_wheel()["wheel_loads"]) / 1000.0
        if kind == "70R_T":
            t = irc.cl_204_1_Class70R_vehicle_track()
            length = t["x"][-1] - t["x"][0]
            return t["wheel_loads_udl"] * length * len(t["z"]) / 1000.0
        if kind == "SV":
            return float(irc.cl_204_5_1_special_vehicle()["total_load_kN"])
        if kind == "FATIGUE":
            return sum(irc.cl_204_6_fatigue_load()["wheel_loads"]) / 1000.0
        if kind in _NOMINAL_TONNES:
            return _NOMINAL_TONNES[kind] * G
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("vehicle total load (%s) unavailable: %s", kind, exc)
    return None


def _impact(kind: str, span_m: Optional[float]) -> Optional[float]:
    """1 + IM per IRC 6 Cl. 208 (Class A: 208.2; AA / 70R: 208.3)."""
    if span_m is None:
        return None
    try:
        irc = _irc()
        if kind == "A":
            return 1.0 + irc.cl_208_2_impact_factor(span_m)
        if kind in ("70R_W", "70R_T", "aa_wheeled", "aa_tracked", "bogie_70r"):
            return 1.0 + irc.cl_208_3_impact_factor(span_m)
    except Exception as exc:  # pragma: no cover
        logger.warning("impact factor (%s) unavailable: %s", kind, exc)
    return None            # SV / fatigue: not reported by this version


# (UI label, input key, kind, braking default)  — order follows the UI check-boxes
_VEHICLES = [
    ("Class A",             KEY_LL_IRC_CLASS_A,       "A",         True),
    ("Class AA (Wheeled)",  KEY_LL_IRC_AA_WHEELED,    "aa_wheeled", True),
    ("Class AA (Tracked)",  KEY_LL_IRC_AA_TRACKED,    "aa_tracked", True),
    ("Class 70R (Wheeled)", KEY_LL_IRC_70R_WHEELED,   "70R_W",     True),
    ("Class 70R (Tracked)", KEY_LL_IRC_70R_TRACKED,   "70R_T",     True),
    ("Class 70R (Bogie)",   KEY_LL_IRC_70R_BOGIE,     "bogie_70r", True),
    ("Class SV",            KEY_LL_IRC_CLASS_SV,      "SV",        None),   # opt-in via UI
    ("Class Fatigue",       KEY_LL_IRC_CLASS_FATIGUE, "FATIGUE",   False),
]


def collect_vehicle_rows(input_dict: dict) -> List[VehicleRow]:
    try:
        span_m = float(input_dict.get(KEY_SPAN))
    except (TypeError, ValueError):
        span_m = None
    rows: List[VehicleRow] = []
    for label, key, kind, brake_default in _VEHICLES:
        if not _is_on(input_dict.get(key)):
            continue
        braking = (_is_on(input_dict.get(KEY_BL_IRC_CLASS_SV, True)) if kind == "SV"
                   else bool(brake_default))
        total = _total_kN(kind)
        rows.append(VehicleRow(
            label=label, total_kN=total, impact=_impact(kind, span_m), braking=braking,
            braking_kN=(BRAKING_FRACTION * total) if (braking and total is not None) else None))
    custom = input_dict.get(KEY_LL_CUSTOM_VEHICLES)
    if isinstance(custom, list):
        for c in custom:
            name = c.get("name") if isinstance(c, dict) else (c if isinstance(c, str) else None)
            if name:
                rows.append(VehicleRow(str(name), None, None, False, None))
    return rows


def _f(v: Optional[float], nd: int = 1) -> str:
    return DASH if v is None else f"{v:,.{nd}f}"


def vehicle_table_tex(input_dict: dict) -> str:
    rows = collect_vehicle_rows(input_dict)
    spec = r"|L{2.7cm}|C{2.3cm}|C{1.8cm}|C{2.4cm}|C{1.7cm}|C{2.4cm}|"
    # Two-level header. First-row labels live in ordinary (wrapping) p-columns -
    # \multirow cells do not wrap - and the second row leaves them blank, so the
    # block reads as merged: only the Braking Load sub-columns get a rule.
    header = [
        r"\textbf{Vehicle} & \textbf{Total Load (kN)} & \textbf{Impact Factor} & "
        r"\multicolumn{3}{c|}{\textbf{Braking Load}} \\ \cline{4-6}",
        r" & & & \textbf{Considered?} & \textbf{Value (kN)} & \textbf{Eccentricity (m)}",
    ]
    if rows:
        ecc = input_dict.get(KEY_LL_ECCENTRICITY)
        ecc_s = _tex(ecc) if ecc not in (None, "") else DASH
        body = "\n".join(
            f"{_tex(r.label)} & {_f(r.total_kN)} & {_f(r.impact, 3)} & "
            f"{'Yes' if r.braking else 'No'} & {_f(r.braking_kN)} & "
            f"{ecc_s if r.braking else DASH} \\\\[6pt]\n\\hline"
            for r in rows)
    else:
        body = r"\multicolumn{6}{|c|}{No IRC vehicle class selected in Additional Inputs $\rightarrow$ Loading} \\[6pt]" + "\n\\hline"
    tex = longtable_tex(spec, header, "\\hline\n" + body,
                        caption=r"\textbf{Live Loads (LL) --- Vehicles (Carriageway)}")
    tex += (r"\noindent\textit{Note: Vehicles are those selected under Additional Inputs $\rightarrow$ "
            r"Loading $\rightarrow$ Live Load. Impact factor = 1 + IM (IRC 6 Cl. 208.2 / 208.3). "
            r"Braking value = 20\% of the vehicle load for the first train (IRC 6 Cl. 211.2), acting "
            r"at the eccentricity above the deck. --- : not applicable / not reported.}" "\n")
    return tex


def footway_table_tex(input_dict: dict) -> str:
    mode = str(input_dict.get(KEY_LL_FOOTPATH_PRESSURE_MODE, "") or "").strip()
    custom = input_dict.get(KEY_LL_FOOTPATH_PRESSURE_VALUE)
    present = str(input_dict.get(KEY_FOOTPATH, "") or "").strip()
    pressure, ref = DASH, DASH
    if mode.lower() in ("as per irc 6", "as per irc6", "automatic"):
        try:
            pressure = f"{_irc().cl_206_1_footway_load():.3f}"
            ref = "IRC 6 Cl. 206.1"
        except Exception:
            pass
    elif custom not in (None, ""):
        pressure, ref = _tex(custom), "User-defined"
    width = input_dict.get(KEY_TS_FOOTPATH_WIDTH)
    no_fp = present.lower() in ("", "none", "no footpath", "no")
    spec = r"|L{5.0cm}|C{2.6cm}|C{1.8cm}|L{3.2cm}|"
    header = [r"\textbf{Parameter} & \textbf{Value} & \textbf{Unit} & \textbf{Reference}"]
    rows = [
        ("Footpath provision", _tex(present) if present else DASH, DASH, "Geometry input"),
    ]
    if no_fp:
        rows.append(("Footway live load", "Not applicable", DASH, DASH))
    else:
        rows += [
            ("Footpath width", _tex(width) if width not in (None, "") else DASH, "m", "IRC 5 Cl. 104.3.6"),
            ("Footway live load intensity", pressure, "kN/m\\textsuperscript{2}", _tex(ref)),
            ("Load definition mode", _tex(mode) if mode else DASH, DASH, "Loading input"),
        ]
    body = "\n".join(f"{a} & {b} & {c} & {d} \\\\[6pt]\n\\hline" for a, b, c, d in rows)
    return longtable_tex(spec, header, "\\hline\n" + body,
                         caption=r"\textbf{Live Loads (LL) --- Footway}")


def other_effects_table_tex(input_dict: dict) -> str:
    spec = r"|L{5.0cm}|L{8.0cm}|"
    header = [r"\textbf{Effect} & \textbf{Treatment in this version}"]
    body = ("Centrifugal force & Not applicable: no horizontal curvature input in this version "
            "(straight bridge). \\\\[6pt]\n\\hline")
    return longtable_tex(spec, header, "\\hline\n" + body,
                         caption=r"\textbf{Live Loads (LL) --- Associated Effects}")


def live_load_tables_tex(input_dict: dict) -> str:
    """Tables 3.3(a)-(c): the complete live-load section of Chapter 3."""
    return "\n\\vspace{1em}\n".join([
        vehicle_table_tex(input_dict),
        footway_table_tex(input_dict),
        other_effects_table_tex(input_dict),
    ])
