"""Structural frequency analysis service using welib.

Uses welib's GeneralizedMCK_PolyBeam for computing generalized M/C/K
matrices from polynomial mode shape coefficients (the OpenFAST approach),
and welib's eigMCK for damped eigenvalue analysis.

For structures without polynomial coefficients, falls back to welib's
cbeam() FEM beam routine with frame3d elements.

All functions are synchronous (CPU-bound) and should be called via
asyncio.loop.run_in_executor() from async handlers.

Key welib functions used:
  - welib.yams.flexibility.GeneralizedMCK_PolyBeam
  - welib.tools.eva.eigMCK / eigMK
  - welib.FEM.fem_beam.cbeam
"""

from __future__ import annotations

import logging
import math
import warnings

import numpy as np
from welib.FEM.fem_beam import cbeam
from welib.tools.eva import eigMCK, eigMK
from welib.yams.flexibility import GeneralizedMCK_PolyBeam

logger = logging.getLogger("windforge.frequency")

# Steel properties (for cross-section estimation when geometry unavailable)
STEEL_E = 210e9   # Young's modulus [Pa]
STEEL_G = 80.8e9  # Shear modulus [Pa]

# Standard OpenFAST polynomial exponents for mode shapes
OPENFAST_POLY_EXP = np.array([2, 3, 4, 5, 6])

# Default mode shape coefficients (2nd-order polynomial) when none stored
DEFAULT_MODE_COEFFS = [1.0, 0.0, 0.0, 0.0, 0.0]


# ---------------------------------------------------------------------------
# Stage labels for display
# ---------------------------------------------------------------------------
STAGE_LABELS: dict[str, str] = {
    "blade_alone": "Blade Alone",
    "tower_alone": "Tower Alone",
    "tower_rna": "Tower + RNA",
    "monopile_alone": "Monopile Alone",
    "monopile_tower": "Monopile + Tower",
    "full_operation": "Full System (Operation)",
    "transport_blade": "Transport (Blade)",
    "transport_tower": "Transport (Tower)",
    "installation": "Installation",
}


# ---------------------------------------------------------------------------
# Helper: tube cross-section (only for cbeam fallback)
# ---------------------------------------------------------------------------
def _tube_section_props(D: float, t: float) -> dict:
    """Cross-section properties for a thin-walled circular tube."""
    r_o = D / 2.0
    r_i = max(r_o - t, 0.0)
    A = math.pi * (r_o**2 - r_i**2)
    I = math.pi / 4.0 * (r_o**4 - r_i**4)
    return {"A": A, "I": I, "Kt": 2.0 * I}


# ---------------------------------------------------------------------------
# Tower frequencies — using welib GeneralizedMCK_PolyBeam + eigMCK
# ---------------------------------------------------------------------------
def compute_tower_frequencies(
    stations: list[dict],
    tower_height: float,
    tip_mass: float = 0.0,
    base_bc: str = "clamped-free",
    n_modes: int = 10,
    damping: dict | None = None,
    mode_coeffs: dict | None = None,
) -> dict:
    """Compute tower natural frequencies.

    Uses welib's GeneralizedMCK_PolyBeam when polynomial mode shape
    coefficients are available (the OpenFAST-native approach with gravity
    stiffening, self-weight, and top-mass effects built in).

    Falls back to welib's cbeam() FEM when no mode coefficients exist.

    Parameters
    ----------
    stations : list[dict]
        Tower station data with keys: frac, mass_den, fa_stiff, ss_stiff,
        and optionally outer_diameter, wall_thickness.
    tower_height : float
        Tower flexible length (m).
    tip_mass : float
        RNA mass at tower top (kg).
    base_bc : str
        Boundary condition ("clamped-free" or "free-free").
    n_modes : int
        Number of modes to return.
    damping : dict or None
        {"fa_1": %, "fa_2": %, "ss_1": %, "ss_2": %}.
    mode_coeffs : dict or None
        {"fa_mode_1": [...], "fa_mode_2": [...],
         "ss_mode_1": [...], "ss_mode_2": [...]}.
    """
    if not stations or len(stations) < 2:
        return {"frequencies_hz": [], "mode_descriptions": [], "component": "tower"}

    sorted_st = sorted(stations, key=lambda s: s["frac"])
    s_span = np.array([s["frac"] * tower_height for s in sorted_st])
    mass_den = np.array([s["mass_den"] for s in sorted_st])
    ei_fa = np.array([s["fa_stiff"] for s in sorted_st])
    ei_ss = np.array([s.get("ss_stiff", s["fa_stiff"]) for s in sorted_st])

    # --- Try GeneralizedMCK_PolyBeam (preferred: uses welib's stiffening) ---
    fa1 = (mode_coeffs or {}).get("fa_mode_1")
    fa2 = (mode_coeffs or {}).get("fa_mode_2")
    ss1 = (mode_coeffs or {}).get("ss_mode_1")
    ss2 = (mode_coeffs or {}).get("ss_mode_2")

    has_poly = fa1 and fa2 and ss1 and ss2

    if has_poly:
        coeffs = np.array([fa1, fa2, ss1, ss2]).T  # (5, 4)
        n_shapes = 4
        exp = OPENFAST_POLY_EXP

        # Damping ratios (percent → fraction)
        d = damping or {}
        damp_zeta = np.array([
            (d.get("fa_1", 1.0) or 1.0) / 100.0,
            (d.get("fa_2", 1.0) or 1.0) / 100.0,
            (d.get("ss_1", 1.0) or 1.0) / 100.0,
            (d.get("ss_2", 1.0) or 1.0) / 100.0,
        ])

        # welib GeneralizedMCK_PolyBeam: tower main_axis='x'
        # Includes self-weight stiffening + top mass gravity effects
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            result = GeneralizedMCK_PolyBeam(
                s_span, mass_den, ei_fa, ei_ss,
                coeffs, exp, damp_zeta,
                gravity=9.81,
                Mtop=tip_mass,
                Omega=0.0,
                main_axis="x",
                bStiffening=True,
            )

        # Extract generalized submatrices (skip 6 rigid-body DOFs)
        MM_full, KK_full, DD_full = result["MM"], result["KK"], result["DD"]
        MM_gen = MM_full[6:, 6:]
        KK_gen = KK_full[6:, 6:]
        DD_gen = DD_full[6:, 6:]

        # welib eigMCK: damped eigenvalue analysis on generalized DOFs
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            freq_d, zeta, Q, freq_0 = eigMCK(MM_gen, DD_gen, KK_gen)

        # freq_0 = undamped natural frequencies
        n = min(n_modes, len(freq_0))
        freq_hz = [float(f) for f in freq_0[:n]]
        descriptions = []
        mode_labels = ["FA 1st", "FA 2nd", "SS 1st", "SS 2nd"]
        for i in range(n):
            if i < len(mode_labels):
                descriptions.append(f"Tower {mode_labels[i]}")
            else:
                descriptions.append(f"Tower Mode {i + 1}")

        return {
            "frequencies_hz": freq_hz,
            "mode_descriptions": descriptions,
            "component": "tower",
        }

    # --- Fallback: welib cbeam FEM (no polynomial coefficients) ---
    return _cbeam_frequencies(
        s_span, mass_den, ei_fa, ei_ss, sorted_st,
        tip_mass=tip_mass,
        base_bc=base_bc,
        n_modes=n_modes,
        component="tower",
    )


# ---------------------------------------------------------------------------
# Blade frequencies — using welib GeneralizedMCK_PolyBeam + eigMCK
# ---------------------------------------------------------------------------
def compute_blade_frequencies(
    structural_stations: list[dict],
    blade_length: float,
    rotor_speed_rpm: float = 0.0,
    base_bc: str = "clamped-free",
    n_modes: int = 10,
    damping: dict | None = None,
    mode_coeffs: dict | None = None,
) -> dict:
    """Compute blade natural frequencies.

    Uses welib's GeneralizedMCK_PolyBeam when polynomial mode shape
    coefficients are available.  Centrifugal stiffening at the given
    rotor speed is handled by welib via the Omega parameter (using
    welib's GKBeamStiffnening internally).

    Falls back to welib's cbeam() FEM when no mode coefficients exist.

    Parameters
    ----------
    structural_stations : list[dict]
        Blade station data with keys: frac, mass_den, flap_stiff, edge_stiff.
    blade_length : float
        Blade span (m).
    rotor_speed_rpm : float
        Rotor speed for centrifugal stiffening.
    base_bc : str
        Boundary condition.
    n_modes : int
        Number of modes to return.
    damping : dict or None
        {"flap": %, "edge": %}.
    mode_coeffs : dict or None
        {"flap_mode_1": [...], "flap_mode_2": [...], "edge_mode_1": [...]}.
    """
    if not structural_stations or len(structural_stations) < 2:
        return {"frequencies_hz": [], "mode_descriptions": [], "component": "blade"}

    sorted_st = sorted(structural_stations, key=lambda s: s["frac"])
    s_span = np.array([s["frac"] * blade_length for s in sorted_st])
    mass_den = np.array([s["mass_den"] for s in sorted_st])
    ei_flap = np.array([s["flap_stiff"] for s in sorted_st])
    ei_edge = np.array([s.get("edge_stiff", s["flap_stiff"]) for s in sorted_st])

    # --- Try GeneralizedMCK_PolyBeam (preferred) ---
    flap1 = (mode_coeffs or {}).get("flap_mode_1")
    flap2 = (mode_coeffs or {}).get("flap_mode_2")
    edge1 = (mode_coeffs or {}).get("edge_mode_1")

    has_poly = flap1 and flap2

    if has_poly:
        # Build shape coefficients
        if edge1:
            coeffs = np.array([flap1, flap2, edge1]).T  # (5, 3)
            n_shapes = 3
            shapes = [0, 1, 2]
        else:
            coeffs = np.array([flap1, flap2]).T  # (5, 2)
            n_shapes = 2
            shapes = [0, 1]

        exp = OPENFAST_POLY_EXP

        # Damping ratios (percent → fraction)
        d = damping or {}
        if n_shapes == 3:
            damp_zeta = np.array([
                (d.get("flap", 2.0) or 2.0) / 100.0,
                (d.get("flap", 2.0) or 2.0) / 100.0,
                (d.get("edge", 2.0) or 2.0) / 100.0,
            ])
        else:
            damp_zeta = np.array([
                (d.get("flap", 2.0) or 2.0) / 100.0,
                (d.get("flap", 2.0) or 2.0) / 100.0,
            ])

        # Convert RPM to rad/s
        omega = rotor_speed_rpm * 2.0 * math.pi / 60.0

        # welib GeneralizedMCK_PolyBeam: blade main_axis='z'
        # Includes centrifugal stiffening via Omega parameter
        # (uses welib's GKBeamStiffnening internally)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            result = GeneralizedMCK_PolyBeam(
                s_span, mass_den, ei_flap, ei_edge,
                coeffs, exp, damp_zeta,
                gravity=9.81,
                Mtop=0,
                Omega=omega,
                main_axis="z",
                bStiffening=True,
                shapes=shapes,
            )

        # Extract generalized submatrices (skip 6 rigid-body DOFs)
        MM_full, KK_full, DD_full = result["MM"], result["KK"], result["DD"]
        MM_gen = MM_full[6:, 6:]
        KK_gen = KK_full[6:, 6:]
        DD_gen = DD_full[6:, 6:]

        # welib eigMCK: damped eigenvalue analysis on generalized DOFs
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            freq_d, zeta, Q, freq_0 = eigMCK(MM_gen, DD_gen, KK_gen)

        n = min(n_modes, len(freq_0))
        freq_hz = [float(f) for f in freq_0[:n]]
        descriptions = []
        if n_shapes == 3:
            mode_labels = ["Flap 1st", "Flap 2nd", "Edge 1st"]
        else:
            mode_labels = ["Flap 1st", "Flap 2nd"]
        for i in range(n):
            if i < len(mode_labels):
                descriptions.append(f"Blade {mode_labels[i]}")
            else:
                descriptions.append(f"Blade Mode {i + 1}")

        return {
            "frequencies_hz": freq_hz,
            "mode_descriptions": descriptions,
            "component": "blade",
        }

    # --- Fallback: welib cbeam FEM ---
    return _cbeam_frequencies(
        s_span, mass_den, ei_flap, ei_edge, sorted_st,
        tip_mass=0.0,
        base_bc=base_bc,
        n_modes=n_modes,
        component="blade",
    )


# ---------------------------------------------------------------------------
# Fallback: welib cbeam FEM (when polynomial coefficients unavailable)
# ---------------------------------------------------------------------------
def _cbeam_frequencies(
    x_nodes: np.ndarray,
    mass_den: np.ndarray,
    ei_y: np.ndarray,
    ei_z: np.ndarray,
    sorted_st: list[dict],
    tip_mass: float = 0.0,
    base_bc: str = "clamped-free",
    n_modes: int = 10,
    component: str = "tower",
) -> dict:
    """Fallback using welib cbeam() with frame3d elements.

    Computes cross-section properties (EA, EIx) from geometry when
    available, or estimates from EI.  Uses welib's cbeam for FEM
    assembly and built-in eigenvalue solving.
    """
    n_st = len(sorted_st)
    EA_arr = np.zeros(n_st)
    EIx_arr = np.zeros(n_st)

    for i, s in enumerate(sorted_st):
        D = s.get("outer_diameter", 0)
        t = s.get("wall_thickness", 0)
        if D > 0 and t > 0:
            props = _tube_section_props(D, t)
            EA_arr[i] = STEEL_E * props["A"]
            EIx_arr[i] = STEEL_G * props["Kt"]
        else:
            # Estimate from EI
            I_est = ei_y[i] / STEEL_E if ei_y[i] > 0 else 1.0
            EIx_arr[i] = STEEL_G * 2.0 * I_est
            EA_arr[i] = ei_y[i] * 100.0

    # Build 6×6 tip mass matrix
    M_tip = None
    if tip_mass > 0:
        M_tip = np.zeros((6, 6))
        M_tip[0, 0] = tip_mass
        M_tip[1, 1] = tip_mass
        M_tip[2, 2] = tip_mass

    # welib cbeam: FEM assembly + eigenvalue solving
    fem = cbeam(
        xNodes=x_nodes,
        m=mass_den,
        EIx=EIx_arr,
        EIy=ei_y,
        EIz=ei_z,
        EA=EA_arr,
        element="frame3d",
        BC=base_bc,
        M_tip=M_tip,
    )

    freqs = fem["freq"]
    mode_names = fem.get("modeNames", [])

    n = min(n_modes, len(freqs))
    freq_hz = [float(f) for f in freqs[:n]]

    descriptions = []
    label = "Tower" if component == "tower" else "Blade"
    for i in range(n):
        if i < len(mode_names) and mode_names[i]:
            descriptions.append(f"{label}: {mode_names[i]}")
        else:
            descriptions.append(f"{label} Mode {i + 1}")

    return {
        "frequencies_hz": freq_hz,
        "mode_descriptions": descriptions,
        "component": component,
    }


# ---------------------------------------------------------------------------
# Combined / multi-stage frequencies
# ---------------------------------------------------------------------------
def compute_combined_frequencies(
    tower_data: dict | None,
    blade_data: dict | None,
    turbine_model: dict,
    stage: str,
    n_modes: int = 10,
) -> dict:
    """Compute frequencies for a given structural configuration/stage.

    Parameters
    ----------
    tower_data : dict or None
        {"stations": [...], "tower_height": float, "damping": {...},
         "mode_coeffs": {"fa_mode_1": [...], ...}}
    blade_data : dict or None
        {"structural_stations": [...], "blade_length": float,
         "damping": {...}, "mode_coeffs": {"flap_mode_1": [...], ...}}
    turbine_model : dict
        {"hub_mass", "nacelle_mass", "rotor_speed_rated", "num_blades", ...}
    stage : str
        Configuration stage name.
    n_modes : int
        Number of modes to return.
    """
    results = {
        "stage": stage,
        "stage_label": STAGE_LABELS.get(stage, stage),
        "frequencies_hz": [],
        "mode_descriptions": [],
    }

    hub_mass = turbine_model.get("hub_mass", 0) or 0
    nacelle_mass = turbine_model.get("nacelle_mass", 0) or 0
    num_blades = turbine_model.get("num_blades", 3) or 3
    rated_rpm = turbine_model.get("rotor_speed_rated", 0) or 0

    # Compute RNA mass
    blade_mass = _compute_blade_mass(blade_data)
    rna_mass = hub_mass + nacelle_mass + num_blades * blade_mass

    # Extract damping and mode coefficients
    tower_damping = (tower_data or {}).get("damping")
    tower_mode_coeffs = (tower_data or {}).get("mode_coeffs")
    blade_damping = (blade_data or {}).get("damping")
    blade_mode_coeffs = (blade_data or {}).get("mode_coeffs")

    if stage == "blade_alone":
        if not blade_data or not blade_data.get("structural_stations"):
            return results
        r = compute_blade_frequencies(
            blade_data["structural_stations"],
            blade_data["blade_length"],
            rotor_speed_rpm=0.0,
            base_bc="clamped-free",
            n_modes=n_modes,
            damping=blade_damping,
            mode_coeffs=blade_mode_coeffs,
        )
        results["frequencies_hz"] = r["frequencies_hz"]
        results["mode_descriptions"] = r["mode_descriptions"]

    elif stage == "tower_alone":
        if not tower_data or not tower_data.get("stations"):
            return results
        r = compute_tower_frequencies(
            tower_data["stations"],
            tower_data["tower_height"],
            tip_mass=0.0,
            base_bc="clamped-free",
            n_modes=n_modes,
            damping=tower_damping,
            mode_coeffs=tower_mode_coeffs,
        )
        results["frequencies_hz"] = r["frequencies_hz"]
        results["mode_descriptions"] = r["mode_descriptions"]

    elif stage == "tower_rna":
        if not tower_data or not tower_data.get("stations"):
            return results
        r = compute_tower_frequencies(
            tower_data["stations"],
            tower_data["tower_height"],
            tip_mass=rna_mass,
            base_bc="clamped-free",
            n_modes=n_modes,
            damping=tower_damping,
            mode_coeffs=tower_mode_coeffs,
        )
        results["frequencies_hz"] = r["frequencies_hz"]
        results["mode_descriptions"] = r["mode_descriptions"]

    elif stage == "full_operation":
        all_freqs = []
        all_descs = []

        if tower_data and tower_data.get("stations"):
            r_tower = compute_tower_frequencies(
                tower_data["stations"],
                tower_data["tower_height"],
                tip_mass=rna_mass,
                n_modes=n_modes,
                damping=tower_damping,
                mode_coeffs=tower_mode_coeffs,
            )
            for f, d in zip(r_tower["frequencies_hz"], r_tower["mode_descriptions"]):
                all_freqs.append(f)
                all_descs.append(d if d.startswith("Tower") else f"Tower: {d}")

        if blade_data and blade_data.get("structural_stations"):
            r_blade = compute_blade_frequencies(
                blade_data["structural_stations"],
                blade_data["blade_length"],
                rotor_speed_rpm=rated_rpm,
                n_modes=n_modes,
                damping=blade_damping,
                mode_coeffs=blade_mode_coeffs,
            )
            for f, d in zip(r_blade["frequencies_hz"], r_blade["mode_descriptions"]):
                all_freqs.append(f)
                all_descs.append(d if d.startswith("Blade") else f"Blade: {d}")

        combined = sorted(zip(all_freqs, all_descs), key=lambda x: x[0])
        n = min(n_modes, len(combined))
        results["frequencies_hz"] = [c[0] for c in combined[:n]]
        results["mode_descriptions"] = [c[1] for c in combined[:n]]

    elif stage == "transport_blade":
        if not blade_data or not blade_data.get("structural_stations"):
            return results
        r = compute_blade_frequencies(
            blade_data["structural_stations"],
            blade_data["blade_length"],
            rotor_speed_rpm=0.0,
            base_bc="free-free",
            n_modes=n_modes,
            damping=blade_damping,
            mode_coeffs=blade_mode_coeffs,
        )
        results["frequencies_hz"] = r["frequencies_hz"]
        results["mode_descriptions"] = r["mode_descriptions"]

    elif stage == "transport_tower":
        if not tower_data or not tower_data.get("stations"):
            return results
        r = compute_tower_frequencies(
            tower_data["stations"],
            tower_data["tower_height"],
            tip_mass=0.0,
            base_bc="free-free",
            n_modes=n_modes,
            damping=tower_damping,
            mode_coeffs=tower_mode_coeffs,
        )
        results["frequencies_hz"] = r["frequencies_hz"]
        results["mode_descriptions"] = r["mode_descriptions"]

    elif stage == "installation":
        if not tower_data or not tower_data.get("stations"):
            return results
        r = compute_tower_frequencies(
            tower_data["stations"],
            tower_data["tower_height"],
            tip_mass=0.0,
            base_bc="clamped-free",
            n_modes=n_modes,
            damping=tower_damping,
            mode_coeffs=tower_mode_coeffs,
        )
        results["frequencies_hz"] = r["frequencies_hz"]
        results["mode_descriptions"] = r["mode_descriptions"]

    elif stage == "monopile_alone":
        sub_config = turbine_model.get("substructure_config")
        if sub_config and sub_config.get("stations"):
            r = compute_tower_frequencies(
                sub_config["stations"],
                sub_config.get("length", 30.0),
                tip_mass=0.0,
                base_bc="clamped-free",
                n_modes=n_modes,
            )
            results["frequencies_hz"] = r["frequencies_hz"]
            results["mode_descriptions"] = [
                d.replace("Tower", "Monopile") for d in r["mode_descriptions"]
            ]

    elif stage == "monopile_tower":
        sub_config = turbine_model.get("substructure_config")
        if tower_data and tower_data.get("stations") and sub_config and sub_config.get("stations"):
            mono_len = sub_config.get("length", 30.0)
            t_height = tower_data["tower_height"]
            total_len = mono_len + t_height

            combined_stations = []
            for s in sub_config["stations"]:
                combined_stations.append({**s, "frac": s["frac"] * mono_len / total_len})
            for s in tower_data["stations"]:
                combined_stations.append({
                    **s, "frac": (mono_len + s["frac"] * t_height) / total_len,
                })

            r = compute_tower_frequencies(
                combined_stations, total_len,
                tip_mass=rna_mass, base_bc="clamped-free", n_modes=n_modes,
            )
            results["frequencies_hz"] = r["frequencies_hz"]
            results["mode_descriptions"] = r["mode_descriptions"]
        elif tower_data and tower_data.get("stations"):
            r = compute_tower_frequencies(
                tower_data["stations"],
                tower_data["tower_height"],
                tip_mass=rna_mass, base_bc="clamped-free", n_modes=n_modes,
                damping=tower_damping, mode_coeffs=tower_mode_coeffs,
            )
            results["frequencies_hz"] = r["frequencies_hz"]
            results["mode_descriptions"] = r["mode_descriptions"]

    return results


# ---------------------------------------------------------------------------
# Campbell diagram
# ---------------------------------------------------------------------------
def compute_campbell_diagram(
    tower_data: dict | None,
    blade_data: dict | None,
    turbine_model: dict,
    rpm_min: float = 0.0,
    rpm_max: float = 15.0,
    rpm_steps: int = 30,
    n_modes: int = 10,
) -> dict:
    """Compute Campbell diagram: frequency vs rotor speed.

    Sweeps RPM, computing blade frequencies with centrifugal stiffening
    at each point (via welib's GeneralizedMCK_PolyBeam Omega parameter).
    Tower frequencies are constant (no RPM dependence).

    Returns dict with rpm_values, modes, excitation_lines.
    """
    rpm_values = np.linspace(rpm_min, rpm_max, rpm_steps).tolist()

    hub_mass = turbine_model.get("hub_mass", 0) or 0
    nacelle_mass = turbine_model.get("nacelle_mass", 0) or 0
    num_blades = turbine_model.get("num_blades", 3) or 3

    blade_mass = _compute_blade_mass(blade_data)
    rna_mass = hub_mass + nacelle_mass + num_blades * blade_mass

    tower_damping = (tower_data or {}).get("damping")
    tower_mode_coeffs = (tower_data or {}).get("mode_coeffs")
    blade_damping = (blade_data or {}).get("damping")
    blade_mode_coeffs = (blade_data or {}).get("mode_coeffs")

    n_tower_modes = min(n_modes // 2, 5) if blade_data else n_modes
    n_blade_modes = n_modes - n_tower_modes if blade_data else 0

    # Pre-compute tower frequencies (RPM-independent)
    tower_freqs: list[float] = []
    tower_descs: list[str] = []
    if tower_data and tower_data.get("stations"):
        r = compute_tower_frequencies(
            tower_data["stations"],
            tower_data["tower_height"],
            tip_mass=rna_mass,
            n_modes=n_tower_modes,
            damping=tower_damping,
            mode_coeffs=tower_mode_coeffs,
        )
        tower_freqs = r["frequencies_hz"]
        tower_descs = r["mode_descriptions"]

    # Sweep RPM for blade frequencies (centrifugal stiffening via welib)
    blade_sweep: dict[str, list[float]] = {}
    blade_descs: list[str] = []

    if blade_data and blade_data.get("structural_stations"):
        for rpm_idx, rpm in enumerate(rpm_values):
            r = compute_blade_frequencies(
                blade_data["structural_stations"],
                blade_data["blade_length"],
                rotor_speed_rpm=rpm,
                n_modes=n_blade_modes,
                damping=blade_damping,
                mode_coeffs=blade_mode_coeffs,
            )

            if rpm_idx == 0:
                blade_descs = r["mode_descriptions"]
                for desc in blade_descs:
                    blade_sweep[desc] = []

            for i, desc in enumerate(blade_descs):
                if i < len(r["frequencies_hz"]):
                    blade_sweep[desc].append(r["frequencies_hz"][i])
                else:
                    blade_sweep[desc].append(0.0)

    # Build mode data
    modes = []
    for freq, desc in zip(tower_freqs, tower_descs):
        modes.append({
            "name": desc,
            "frequencies": [freq] * len(rpm_values),
            "component": "tower",
        })
    for desc in blade_descs:
        if desc in blade_sweep:
            modes.append({
                "name": desc,
                "frequencies": blade_sweep[desc],
                "component": "blade",
            })

    # Excitation lines: nP = n × RPM/60
    excitation_lines = {}
    for n_p in [1, 3, 6, 9]:
        label = f"{n_p}P"
        excitation_lines[label] = {
            "rpm": rpm_values,
            "freq": [n_p * rpm / 60.0 for rpm in rpm_values],
            "label": label,
        }

    return {
        "rpm_values": rpm_values,
        "modes": modes,
        "excitation_lines": excitation_lines,
    }


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------
def _compute_blade_mass(blade_data: dict | None) -> float:
    """Integrate blade mass from structural stations (trapezoidal rule)."""
    if not blade_data or not blade_data.get("structural_stations"):
        return 0.0
    stations = blade_data["structural_stations"]
    bl = blade_data.get("blade_length", 0)
    if not bl:
        return 0.0
    sorted_st = sorted(stations, key=lambda s: s["frac"])
    blade_mass = 0.0
    for i in range(len(sorted_st) - 1):
        dr = (sorted_st[i + 1]["frac"] - sorted_st[i]["frac"]) * bl
        m_avg = (sorted_st[i]["mass_den"] + sorted_st[i + 1]["mass_den"]) / 2.0
        blade_mass += m_avg * dr
    return blade_mass
