"""Structural frequency analysis service wrapping welib.

Computes natural frequencies and Campbell diagrams for tower, blade,
monopile, and combined structures using welib's FEM beam routines.
All functions are synchronous (CPU-bound) and should be called via
asyncio.loop.run_in_executor() from async handlers.
"""

from __future__ import annotations

import logging
import math

import numpy as np
from welib.FEM.fem_beam import cbeam

logger = logging.getLogger("windforge.frequency")


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
# Low-level: tower frequencies
# ---------------------------------------------------------------------------
def compute_tower_frequencies(
    stations: list[dict],
    tower_height: float,
    tip_mass: float = 0.0,
    base_bc: str = "clamped-free",
    n_modes: int = 10,
) -> dict:
    """Compute tower natural frequencies via welib cbeam().

    Parameters
    ----------
    stations : list[dict]
        Tower station data with keys: frac, mass_den, fa_stiff, ss_stiff.
    tower_height : float
        Tower flexible length (m).
    tip_mass : float
        Lumped tip mass representing RNA (kg).  Added as a 6×6 M_tip.
    base_bc : str
        Boundary condition: "clamped-free" or "free-free".
    n_modes : int
        Number of modes to return.

    Returns
    -------
    dict with frequencies_hz, mode_descriptions, component.
    """
    if not stations or len(stations) < 2:
        return {"frequencies_hz": [], "mode_descriptions": [], "component": "tower"}

    # Sort stations by frac
    sorted_st = sorted(stations, key=lambda s: s["frac"])

    # Build arrays
    x_nodes = np.array([s["frac"] * tower_height for s in sorted_st])
    mass_den = np.array([s["mass_den"] for s in sorted_st])
    ei_fa = np.array([s["fa_stiff"] for s in sorted_st])
    ei_ss = np.array([s.get("ss_stiff", s["fa_stiff"]) for s in sorted_st])

    # Build 6x6 tip mass matrix (translational mass only, no inertia)
    M_tip = None
    if tip_mass > 0:
        M_tip = np.zeros((6, 6))
        M_tip[0, 0] = tip_mass  # axial
        M_tip[1, 1] = tip_mass  # lateral Y
        M_tip[2, 2] = tip_mass  # lateral Z

    # Run cbeam with frame3d elements
    fem = cbeam(
        xNodes=x_nodes,
        m=mass_den,
        EIy=ei_fa,
        EIz=ei_ss,
        element="frame3d",
        BC=base_bc,
        M_tip=M_tip,
    )

    # Extract frequencies and mode names
    freqs = fem["freq"]
    mode_names = fem.get("modeNames", [])

    # Take first n_modes
    n = min(n_modes, len(freqs))
    freq_hz = [float(f) for f in freqs[:n]]

    # Build mode descriptions
    descriptions = []
    for i in range(n):
        if i < len(mode_names) and mode_names[i]:
            descriptions.append(str(mode_names[i]))
        else:
            descriptions.append(f"Tower Mode {i + 1}")

    return {
        "frequencies_hz": freq_hz,
        "mode_descriptions": descriptions,
        "component": "tower",
    }


# ---------------------------------------------------------------------------
# Low-level: blade frequencies
# ---------------------------------------------------------------------------
def compute_blade_frequencies(
    structural_stations: list[dict],
    blade_length: float,
    rotor_speed_rpm: float = 0.0,
    base_bc: str = "clamped-free",
    n_modes: int = 10,
) -> dict:
    """Compute blade natural frequencies.

    For rotor_speed_rpm > 0, centrifugal stiffening is added via a
    geometric stiffness matrix proportional to ω².

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
    """
    if not structural_stations or len(structural_stations) < 2:
        return {"frequencies_hz": [], "mode_descriptions": [], "component": "blade"}

    sorted_st = sorted(structural_stations, key=lambda s: s["frac"])

    x_nodes = np.array([s["frac"] * blade_length for s in sorted_st])
    mass_den = np.array([s["mass_den"] for s in sorted_st])
    ei_flap = np.array([s["flap_stiff"] for s in sorted_st])
    ei_edge = np.array([s.get("edge_stiff", s["flap_stiff"]) for s in sorted_st])

    # Base FEM (no rotation)
    fem = cbeam(
        xNodes=x_nodes,
        m=mass_den,
        EIy=ei_flap,
        EIz=ei_edge,
        element="frame3d",
        BC=base_bc,
    )

    if rotor_speed_rpm > 0:
        # Add centrifugal stiffening
        omega = rotor_speed_rpm * 2.0 * math.pi / 60.0
        KKr = fem["KKr"].copy()
        MMr = fem["MMr"]

        # Compute centrifugal force at each node
        # F_c(r) = ω² × ∫_r^R m(s)·s ds
        # Approximate geometric stiffness contribution
        n_nodes = len(x_nodes)
        n_dof = KKr.shape[0]

        # Simplified approach: add centrifugal stiffening to diagonal
        # K_c_ii = ω² × Σ(m_j × r_j) for j > i (mass outboard)
        # This is a simplified version — for production, use welib's
        # GKBeamStiffnening() for more accurate results
        for i in range(n_nodes - 1):
            # Centrifugal tension at node i
            outboard_mass_moment = 0.0
            for j in range(i + 1, n_nodes):
                dr = x_nodes[j] - x_nodes[j - 1] if j > 0 else 0
                outboard_mass_moment += mass_den[j] * x_nodes[j] * dr
            F_c = omega**2 * outboard_mass_moment

            # Element length
            L_e = x_nodes[i + 1] - x_nodes[i]
            if L_e <= 0:
                continue

            # Add geometric stiffness to lateral DOFs for this element
            # For frame3d: DOF per node = 6 (ux, uy, uz, rx, ry, rz)
            # Lateral bending DOFs are uy(1), uz(2) per node
            kg_factor = F_c / L_e
            # Map to reduced DOF indices (after BC application)
            # This is approximate — exact mapping depends on BC transform
            dof_idx = i * 6  # approximate starting DOF for node i
            for d in [1, 2]:  # lateral DOFs
                idx = dof_idx + d
                if idx < n_dof and idx + 6 < n_dof:
                    KKr[idx, idx] += kg_factor
                    KKr[idx + 6, idx + 6] += kg_factor
                    KKr[idx, idx + 6] -= kg_factor
                    KKr[idx + 6, idx] -= kg_factor

        # Re-solve eigenvalue problem
        from welib.tools.eva import eig
        freq_new, _, _ = eig(KKr, MMr)
        freqs = freq_new
    else:
        freqs = fem["freq"]

    mode_names = fem.get("modeNames", [])
    n = min(n_modes, len(freqs))
    freq_hz = [float(f) for f in freqs[:n]]

    descriptions = []
    for i in range(n):
        if i < len(mode_names) and mode_names[i]:
            descriptions.append(str(mode_names[i]))
        else:
            descriptions.append(f"Blade Mode {i + 1}")

    return {
        "frequencies_hz": freq_hz,
        "mode_descriptions": descriptions,
        "component": "blade",
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
        {"stations": [...], "tower_height": float, "damping": {...}}
    blade_data : dict or None
        {"structural_stations": [...], "blade_length": float}
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

    # Compute RNA mass (hub + nacelle + blades)
    blade_mass = 0.0
    if blade_data and blade_data.get("structural_stations"):
        stations = blade_data["structural_stations"]
        bl = blade_data.get("blade_length", 0)
        sorted_st = sorted(stations, key=lambda s: s["frac"])
        for i in range(len(sorted_st) - 1):
            dr = (sorted_st[i + 1]["frac"] - sorted_st[i]["frac"]) * bl
            m_avg = (sorted_st[i]["mass_den"] + sorted_st[i + 1]["mass_den"]) / 2.0
            blade_mass += m_avg * dr

    rna_mass = hub_mass + nacelle_mass + num_blades * blade_mass

    if stage == "blade_alone":
        if not blade_data or not blade_data.get("structural_stations"):
            return results
        r = compute_blade_frequencies(
            blade_data["structural_stations"],
            blade_data["blade_length"],
            rotor_speed_rpm=0.0,
            base_bc="clamped-free",
            n_modes=n_modes,
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
        )
        results["frequencies_hz"] = r["frequencies_hz"]
        results["mode_descriptions"] = r["mode_descriptions"]

    elif stage == "full_operation":
        # Tower + RNA + blade centrifugal stiffening
        all_freqs = []
        all_descs = []

        if tower_data and tower_data.get("stations"):
            r_tower = compute_tower_frequencies(
                tower_data["stations"],
                tower_data["tower_height"],
                tip_mass=rna_mass,
                base_bc="clamped-free",
                n_modes=n_modes,
            )
            for f, d in zip(r_tower["frequencies_hz"], r_tower["mode_descriptions"]):
                all_freqs.append(f)
                all_descs.append(f"Tower: {d}")

        if blade_data and blade_data.get("structural_stations"):
            r_blade = compute_blade_frequencies(
                blade_data["structural_stations"],
                blade_data["blade_length"],
                rotor_speed_rpm=rated_rpm,
                base_bc="clamped-free",
                n_modes=n_modes,
            )
            for f, d in zip(r_blade["frequencies_hz"], r_blade["mode_descriptions"]):
                all_freqs.append(f)
                all_descs.append(f"Blade: {d}")

        # Sort by frequency and take first n_modes
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
        )
        results["frequencies_hz"] = r["frequencies_hz"]
        results["mode_descriptions"] = r["mode_descriptions"]

    elif stage == "installation":
        # Tower clamped at base, no RNA
        if not tower_data or not tower_data.get("stations"):
            return results
        r = compute_tower_frequencies(
            tower_data["stations"],
            tower_data["tower_height"],
            tip_mass=0.0,
            base_bc="clamped-free",
            n_modes=n_modes,
        )
        results["frequencies_hz"] = r["frequencies_hz"]
        results["mode_descriptions"] = r["mode_descriptions"]

    elif stage == "monopile_alone":
        # Use substructure_config if available, otherwise approximate
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
        else:
            return results

    elif stage == "monopile_tower":
        # Combined monopile + tower with RNA at top
        sub_config = turbine_model.get("substructure_config")
        if tower_data and tower_data.get("stations") and sub_config and sub_config.get("stations"):
            # Concatenate monopile and tower stations
            mono_len = sub_config.get("length", 30.0)
            tower_height = tower_data["tower_height"]
            total_len = mono_len + tower_height

            combined_stations = []
            # Monopile stations (remap frac to combined)
            for s in sub_config["stations"]:
                combined_stations.append({
                    **s,
                    "frac": s["frac"] * mono_len / total_len,
                })
            # Tower stations (remap frac to combined)
            for s in tower_data["stations"]:
                combined_stations.append({
                    **s,
                    "frac": (mono_len + s["frac"] * tower_height) / total_len,
                })

            r = compute_tower_frequencies(
                combined_stations,
                total_len,
                tip_mass=rna_mass,
                base_bc="clamped-free",
                n_modes=n_modes,
            )
            results["frequencies_hz"] = r["frequencies_hz"]
            results["mode_descriptions"] = r["mode_descriptions"]
        elif tower_data and tower_data.get("stations"):
            # Fallback: just tower + RNA
            r = compute_tower_frequencies(
                tower_data["stations"],
                tower_data["tower_height"],
                tip_mass=rna_mass,
                base_bc="clamped-free",
                n_modes=n_modes,
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

    Sweeps RPM from rpm_min to rpm_max, computing blade frequencies with
    centrifugal stiffening at each RPM point.  Tower frequencies are
    constant (no RPM dependence).

    Returns dict with rpm_values, modes, excitation_lines.
    """
    rpm_values = np.linspace(rpm_min, rpm_max, rpm_steps).tolist()

    # Pre-compute tower frequencies (RPM-independent)
    tower_freqs: list[float] = []
    tower_descs: list[str] = []
    hub_mass = turbine_model.get("hub_mass", 0) or 0
    nacelle_mass = turbine_model.get("nacelle_mass", 0) or 0
    num_blades = turbine_model.get("num_blades", 3) or 3

    # Estimate blade mass for RNA
    blade_mass = 0.0
    if blade_data and blade_data.get("structural_stations"):
        stations = blade_data["structural_stations"]
        bl = blade_data.get("blade_length", 0)
        sorted_st = sorted(stations, key=lambda s: s["frac"])
        for i in range(len(sorted_st) - 1):
            dr = (sorted_st[i + 1]["frac"] - sorted_st[i]["frac"]) * bl
            m_avg = (sorted_st[i]["mass_den"] + sorted_st[i + 1]["mass_den"]) / 2.0
            blade_mass += m_avg * dr

    rna_mass = hub_mass + nacelle_mass + num_blades * blade_mass

    n_tower_modes = min(n_modes // 2, 5) if blade_data else n_modes
    n_blade_modes = n_modes - n_tower_modes if blade_data else 0

    if tower_data and tower_data.get("stations"):
        r = compute_tower_frequencies(
            tower_data["stations"],
            tower_data["tower_height"],
            tip_mass=rna_mass,
            n_modes=n_tower_modes,
        )
        tower_freqs = r["frequencies_hz"]
        tower_descs = r["mode_descriptions"]

    # Sweep RPM for blade frequencies
    blade_sweep: dict[str, list[float]] = {}  # mode_name -> [freq per RPM]
    blade_descs: list[str] = []

    if blade_data and blade_data.get("structural_stations"):
        for rpm_idx, rpm in enumerate(rpm_values):
            r = compute_blade_frequencies(
                blade_data["structural_stations"],
                blade_data["blade_length"],
                rotor_speed_rpm=rpm,
                n_modes=n_blade_modes,
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

    # Tower modes (constant across RPM)
    for i, (freq, desc) in enumerate(zip(tower_freqs, tower_descs)):
        modes.append({
            "name": desc,
            "frequencies": [freq] * len(rpm_values),
            "component": "tower",
        })

    # Blade modes (vary with RPM)
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
