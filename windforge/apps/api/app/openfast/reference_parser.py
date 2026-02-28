"""Parsers for NREL OpenFAST / ROSCO reference input files.

These parsers read validated reference files (airfoil .dat, blade .dat,
tower .dat, Cp_Ct_Cq .txt) and return structured dicts suitable for
JSON serialisation to the frontend visualisation components.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import numpy as np


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_REF_DIR = Path(__file__).resolve().parent / "reference_inputs"


def _get_deck_dir(turbine: str) -> Path:
    """Return the reference deck directory for a turbine name."""
    deck = _REF_DIR / turbine
    if not deck.is_dir():
        raise FileNotFoundError(f"No reference deck for '{turbine}' at {deck}")
    return deck


def _strip_comments(lines: list[str]) -> list[str]:
    """Return lines with leading/trailing whitespace stripped, comments removed."""
    out = []
    for ln in lines:
        s = ln.strip()
        if not s or s.startswith("!") or s.startswith("#"):
            continue
        out.append(s)
    return out


# ---------------------------------------------------------------------------
# Airfoil parser
# ---------------------------------------------------------------------------

def parse_airfoil(filepath: Path) -> dict[str, Any]:
    """Parse an AeroDyn airfoil .dat file.

    Returns dict with:
      name, alpha, cl, cd, cm   (polars)
      coords_x, coords_y        (if _coords.txt exists)
    """
    text = filepath.read_text(encoding="utf-8", errors="replace")
    lines = text.split("\n")

    name = filepath.stem

    # Find the polar table: starts after "NumAlf" line
    polars_start = None
    num_alf = 0
    for i, ln in enumerate(lines):
        if "NumAlf" in ln:
            match = re.match(r"\s*(\d+)", ln)
            if match:
                num_alf = int(match.group(1))
                polars_start = i + 1
            break

    alpha, cl, cd, cm = [], [], [], []
    if polars_start is not None:
        # Skip header lines (starting with !)
        idx = polars_start
        while idx < len(lines) and lines[idx].strip().startswith("!"):
            idx += 1
        for j in range(idx, min(idx + num_alf, len(lines))):
            parts = lines[j].split()
            if len(parts) >= 3:
                alpha.append(float(parts[0]))
                cl.append(float(parts[1]))
                cd.append(float(parts[2]))
                cm.append(float(parts[3]) if len(parts) >= 4 else 0.0)

    # Read coordinates from companion _coords.txt
    coords_file = filepath.parent / f"{name}_coords.txt"
    coords_x, coords_y = [], []
    if coords_file.exists():
        coord_text = coords_file.read_text(encoding="utf-8", errors="replace")
        coord_lines = coord_text.split("\n")
        in_coords = False
        for ln in coord_lines:
            s = ln.strip()
            if not s or s.startswith("!") or s.startswith("#"):
                if "x/c" in s.lower() and "y/c" in s.lower():
                    in_coords = True
                continue
            if in_coords or (not s.startswith("!") and re.match(r"^\s*[\d.-]", s)):
                parts = s.split()
                if len(parts) >= 2:
                    try:
                        coords_x.append(float(parts[0]))
                        coords_y.append(float(parts[1]))
                    except ValueError:
                        continue

    return {
        "name": name,
        "alpha": alpha,
        "cl": cl,
        "cd": cd,
        "cm": cm,
        "coords_x": coords_x,
        "coords_y": coords_y,
    }


def list_airfoils(turbine: str) -> list[dict[str, Any]]:
    """Parse all airfoil .dat files for a reference turbine."""
    deck = _get_deck_dir(turbine)
    airfoil_dir = deck / "Airfoils"
    if not airfoil_dir.is_dir():
        return []
    results = []
    for f in sorted(airfoil_dir.glob("*.dat")):
        results.append(parse_airfoil(f))
    return results


# ---------------------------------------------------------------------------
# Blade properties parser (ElastoDyn blade .dat)
# ---------------------------------------------------------------------------

def parse_blade_properties(turbine: str) -> dict[str, Any]:
    """Parse distributed blade properties from ElastoDyn blade .dat file.

    Returns dict with arrays: bl_fract, pitch_axis, struct_twist, b_mass_den,
    flp_stff, edg_stff.
    """
    deck = _get_deck_dir(turbine)
    # Find blade file
    candidates = list(deck.glob("*Blade*.dat")) + list(deck.glob("*_Blade.dat"))
    if not candidates:
        raise FileNotFoundError("No blade .dat file found")
    blade_file = candidates[0]

    text = blade_file.read_text(encoding="utf-8", errors="replace")
    lines = text.split("\n")

    # Find NBlInpSt
    n_stations = 0
    table_start = None
    for i, ln in enumerate(lines):
        if "NBlInpSt" in ln:
            m = re.match(r"\s*(\d+)", ln)
            if m:
                n_stations = int(m.group(1))

    # Find the table header line (BlFract ... )
    for i, ln in enumerate(lines):
        if "BlFract" in ln and "PitchAxis" in ln:
            # Skip units line
            table_start = i + 2
            break

    if table_start is None:
        raise ValueError("Could not find blade property table")

    bl_fract, pitch_axis, struct_twist = [], [], []
    b_mass_den, flp_stff, edg_stff = [], [], []

    for j in range(table_start, min(table_start + n_stations, len(lines))):
        parts = lines[j].split()
        if len(parts) >= 6:
            bl_fract.append(float(parts[0]))
            pitch_axis.append(float(parts[1]))
            struct_twist.append(float(parts[2]))
            b_mass_den.append(float(parts[3]))
            flp_stff.append(float(parts[4]))
            edg_stff.append(float(parts[5]))

    return {
        "name": blade_file.stem,
        "n_stations": len(bl_fract),
        "bl_fract": bl_fract,
        "pitch_axis": pitch_axis,
        "struct_twist": struct_twist,
        "b_mass_den": b_mass_den,
        "flp_stff": flp_stff,
        "edg_stff": edg_stff,
    }


# ---------------------------------------------------------------------------
# Tower properties parser (ElastoDyn tower .dat)
# ---------------------------------------------------------------------------

def parse_tower_properties(turbine: str) -> dict[str, Any]:
    """Parse distributed tower properties from ElastoDyn tower .dat file.

    Returns dict with arrays: ht_fract, t_mass_den, tw_fa_stif, tw_ss_stif.
    """
    deck = _get_deck_dir(turbine)
    candidates = list(deck.glob("*Tower*.dat"))
    if not candidates:
        raise FileNotFoundError("No tower .dat file found")
    tower_file = candidates[0]

    text = tower_file.read_text(encoding="utf-8", errors="replace")
    lines = text.split("\n")

    # Find NTwInpSt
    n_stations = 0
    for ln in lines:
        if "NTwInpSt" in ln:
            m = re.match(r"\s*(\d+)", ln)
            if m:
                n_stations = int(m.group(1))
            break

    # Find table header
    table_start = None
    for i, ln in enumerate(lines):
        if "HtFract" in ln and "TMassDen" in ln:
            table_start = i + 2
            break

    if table_start is None:
        raise ValueError("Could not find tower property table")

    ht_fract, t_mass_den, tw_fa_stif, tw_ss_stif = [], [], [], []

    for j in range(table_start, min(table_start + n_stations, len(lines))):
        parts = lines[j].split()
        if len(parts) >= 4:
            ht_fract.append(float(parts[0]))
            t_mass_den.append(float(parts[1]))
            tw_fa_stif.append(float(parts[2]))
            tw_ss_stif.append(float(parts[3]))

    return {
        "name": tower_file.stem,
        "n_stations": len(ht_fract),
        "ht_fract": ht_fract,
        "t_mass_den": t_mass_den,
        "tw_fa_stif": tw_fa_stif,
        "tw_ss_stif": tw_ss_stif,
    }


# ---------------------------------------------------------------------------
# Cp-Ct-Cq surface parser (ROSCO format)
# ---------------------------------------------------------------------------

def parse_cp_ct_cq(turbine: str) -> dict[str, Any]:
    """Parse Cp_Ct_Cq performance surface from ROSCO .txt file.

    Returns dict with: pitch (deg), tsr, cp (2D), ct (2D), cq (2D).
    """
    deck = _get_deck_dir(turbine)
    candidates = list(deck.glob("Cp_Ct_Cq*"))
    if not candidates:
        raise FileNotFoundError("No Cp_Ct_Cq file found")
    cp_file = candidates[0]

    text = cp_file.read_text(encoding="utf-8", errors="replace")
    lines = text.split("\n")

    # Parse header: pitch vector, TSR vector
    pitch = None
    tsr = None
    section = None  # 'cp', 'ct', 'cq'
    matrices: dict[str, list[list[float]]] = {"cp": [], "ct": [], "cq": []}

    for ln in lines:
        s = ln.strip()

        # Detect section headers
        if "pitch angle vector" in s.lower():
            section = "pitch_next"
            continue
        if "tsr vector" in s.lower():
            section = "tsr_next"
            continue
        if "wind speed vector" in s.lower():
            section = "ws_next"
            continue
        if "power coefficient" in s.lower():
            section = "cp"
            continue
        if "thrust coefficient" in s.lower():
            section = "ct"
            continue
        if "torque coefficient" in s.lower():
            section = "cq"
            continue

        if not s or s.startswith("#") or s.startswith("!"):
            continue

        # Data lines
        if section == "pitch_next":
            pitch = [float(x) for x in s.split()]
            section = None
        elif section == "tsr_next":
            tsr = [float(x) for x in s.split()]
            section = None
        elif section == "ws_next":
            section = None  # skip wind speed
        elif section in ("cp", "ct", "cq"):
            row = [float(x) for x in s.split()]
            if row:
                matrices[section].append(row)

    return {
        "pitch": pitch or [],
        "tsr": tsr or [],
        "cp": matrices["cp"],
        "ct": matrices["ct"],
        "cq": matrices["cq"],
    }


# ---------------------------------------------------------------------------
# Cost breakdown (NREL CSM reference values for NREL 5MW)
# ---------------------------------------------------------------------------

def get_cost_breakdown(turbine: str) -> dict[str, Any]:
    """Return reference cost breakdown based on NREL Cost & Scaling Model.

    Values from NREL/TP-500-38060 for the 5MW reference turbine.
    """
    # Reference costs in USD from NREL 5MW baseline (2006 dollars)
    costs = {
        "turbine": {
            "label": "Turbine Capital Cost",
            "total": 6_017_000,
            "rotor": {
                "label": "Rotor",
                "total": 1_530_000,
                "components": {
                    "blades": 1_035_000,
                    "hub": 198_000,
                    "pitch_system": 267_000,
                    "spinner": 30_000,
                },
            },
            "nacelle": {
                "label": "Nacelle",
                "total": 3_020_000,
                "components": {
                    "low_speed_shaft": 253_000,
                    "main_bearing": 117_000,
                    "gearbox": 648_000,
                    "high_speed_shaft": 10_000,
                    "generator": 435_000,
                    "bedplate": 605_000,
                    "yaw_system": 155_000,
                    "hvac": 64_000,
                    "nacelle_cover": 76_000,
                    "electrical": 390_000,
                    "controls": 117_000,
                    "transformer": 150_000,
                },
            },
            "tower": {
                "label": "Tower",
                "total": 1_467_000,
                "components": {
                    "tower_structure": 1_467_000,
                },
            },
        },
    }
    return costs


# ---------------------------------------------------------------------------
# List available reference turbines
# ---------------------------------------------------------------------------

def list_available_turbines() -> list[str]:
    """Return list of available reference turbine deck names."""
    if not _REF_DIR.is_dir():
        return []
    return sorted(d.name for d in _REF_DIR.iterdir() if d.is_dir())
