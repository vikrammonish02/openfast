"""Hydrodynamics service using welib.hydro.

Wraps welib functions for wave kinematics, spectral analysis, Morison
loading, and hydrostatic/added-mass computations.

All functions are synchronous (CPU-bound) and should be called via
asyncio.loop.run_in_executor() from async handlers.

Key welib functions used:
  - welib.hydro.spectra.jonswap
  - welib.hydro.wavekin.wavenumber / elevation2d / kinematics2d
  - welib.hydro.morison.inline_load
  - welib.hydro.hydrostat.cylindervert_hydrostat
  - welib.hydro.addedmass.cylindervert_addedmass
"""

from __future__ import annotations

import logging

import numpy as np
from welib.hydro.addedmass import cylindervert_addedmass
from welib.hydro.hydrostat import cylindervert_hydrostat
from welib.hydro.morison import inline_load
from welib.hydro.spectra import jonswap
from welib.hydro.wavekin import elevation2d, kinematics2d, wavenumber

logger = logging.getLogger("windforge.hydro")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
GRAVITY = 9.81
RHO_WATER = 1025.0  # kg/m^3


# ---------------------------------------------------------------------------
# 1. Wave kinematics
# ---------------------------------------------------------------------------
def compute_wave_kinematics(
    Hs: float,
    Tp: float,
    water_depth: float,
    time_duration: float = 60.0,
    n_freq: int = 200,
    z_positions: list[float] | None = None,
) -> dict:
    """Compute wave kinematics (elevation, velocity, acceleration) using
    a JONSWAP spectrum with linear Airy wave theory.

    Parameters
    ----------
    Hs : float
        Significant wave height (m).
    Tp : float
        Peak spectral period (s).
    water_depth : float
        Water depth (m), positive value.
    time_duration : float
        Duration of the time series (s).
    n_freq : int
        Number of frequency components.
    z_positions : list[float] or None
        Vertical positions for kinematics (m, negative below MSL).
        If None, 20 stations from -water_depth to 0 are used.

    Returns
    -------
    dict with keys: time, elevation, z_positions, velocity, acceleration
    """
    # Frequency array
    freq = np.linspace(0.01, 1.0, n_freq)
    df = freq[1] - freq[0]

    # JONSWAP spectrum via welib
    S = jonswap(freq, Hs, Tp)

    # Wave amplitudes from spectral density
    a = np.sqrt(2.0 * S * df)

    # Wavenumber via welib dispersion relation (takes freq in Hz)
    k = wavenumber(freq, water_depth, GRAVITY)

    # Random phases
    eps = np.random.uniform(0, 2.0 * np.pi, n_freq)

    # Time array (10 samples per second)
    n_time = int(time_duration * 10)
    t = np.linspace(0, time_duration, n_time)

    # Surface elevation via welib (at x=0)
    eta = elevation2d(a, freq, k, eps, t, 0)

    # Vertical positions
    if z_positions is not None:
        z = np.array(z_positions)
    else:
        z = np.linspace(-water_depth, 0, 20)

    # Velocity and acceleration via welib
    # kinematics2d signature: (a, f, k, eps, h, t, z, x=None, Wheeler=False, eta=None)
    u, du = kinematics2d(a, freq, k, eps, water_depth, t, z)

    return {
        "time": t.tolist(),
        "elevation": eta.tolist(),
        "z_positions": z.tolist(),
        "velocity": u.tolist(),         # shape (nz, nt)
        "acceleration": du.tolist(),    # shape (nz, nt)
    }


# ---------------------------------------------------------------------------
# 2. JONSWAP spectrum
# ---------------------------------------------------------------------------
def compute_jonswap_spectrum(
    Hs: float,
    Tp: float,
    freq_min: float = 0.01,
    freq_max: float = 0.5,
    n_points: int = 500,
) -> dict:
    """Compute a JONSWAP spectral density curve.

    Parameters
    ----------
    Hs : float
        Significant wave height (m).
    Tp : float
        Peak spectral period (s).
    freq_min : float
        Minimum frequency (Hz).
    freq_max : float
        Maximum frequency (Hz).
    n_points : int
        Number of frequency points.

    Returns
    -------
    dict with keys: frequencies, spectral_density
    """
    freq = np.linspace(freq_min, freq_max, n_points)

    # JONSWAP spectrum via welib
    S = jonswap(freq, Hs, Tp)

    return {
        "frequencies": freq.tolist(),
        "spectral_density": S.tolist(),
    }


# ---------------------------------------------------------------------------
# 3. Morison loads
# ---------------------------------------------------------------------------
def compute_morison_loads(
    Hs: float,
    Tp: float,
    water_depth: float,
    monopile_diameter: float,
    Cd: float = 1.0,
    Cm: float = 2.0,
    time_duration: float = 60.0,
    n_freq: int = 200,
) -> dict:
    """Compute Morison inline loads on a monopile using welib.

    Generates wave kinematics from a JONSWAP spectrum and applies
    Morison's equation at each depth station, then integrates to
    obtain base shear and overturning moment.

    Parameters
    ----------
    Hs : float
        Significant wave height (m).
    Tp : float
        Peak spectral period (s).
    water_depth : float
        Water depth (m), positive value.
    monopile_diameter : float
        Monopile outer diameter (m).
    Cd : float
        Drag coefficient.
    Cm : float
        Inertia coefficient (CM = Cp + Ca).
    time_duration : float
        Duration of the time series (s).
    n_freq : int
        Number of frequency components.

    Returns
    -------
    dict with keys: time, base_shear, overturning_moment, max_base_shear,
                    max_moment
    """
    # Frequency array
    freq = np.linspace(0.01, 1.0, n_freq)
    df = freq[1] - freq[0]

    # JONSWAP spectrum via welib
    S = jonswap(freq, Hs, Tp)
    a = np.sqrt(2.0 * S * df)

    # Wavenumber via welib
    k = wavenumber(freq, water_depth, GRAVITY)

    # Random phases
    eps = np.random.uniform(0, 2.0 * np.pi, n_freq)

    # Time array
    n_time = int(time_duration * 10)
    t = np.linspace(0, time_duration, n_time)

    # Depth stations for integration
    z_stations = np.linspace(-water_depth, 0, 50)
    dz = z_stations[1] - z_stations[0]  # positive spacing

    # Velocity and acceleration at each depth station via welib
    # u, du have shape (n_z, n_t)
    u, du = kinematics2d(a, freq, k, eps, water_depth, t, z_stations)

    # Morison inline force per unit length at each (z, t) via welib
    # inline_load(u_rel, a_wav, a_rel, D, rho, Cd, Cp, Ca, CM)
    # For a fixed structure: u_rel = u (wave vel), a_rel = du (wave accel)
    # a_rel is the *relative* acceleration = a_wav - a_str; for fixed structure a_str=0 so a_rel=a_wav
    # Using CM parameter: internally sets Cp = CM-1, Ca = 1
    p_tot, _, _, _, _, _ = inline_load(
        u, du, du, monopile_diameter, RHO_WATER, Cd, CM=Cm
    )

    # Integrate force distribution along depth via trapezoidal rule
    # p_tot shape: (n_z, n_t) -- force per unit length
    # base_shear = integral of p_tot dz
    base_shear = np.trapz(p_tot, z_stations, axis=0)  # shape (n_t,)

    # Overturning moment about mudline (z = -water_depth)
    # moment arm = z - (-water_depth) = z + water_depth
    moment_arm = (z_stations + water_depth).reshape(-1, 1)  # (n_z, 1)
    overturning_moment = np.trapz(p_tot * moment_arm, z_stations, axis=0)  # shape (n_t,)

    return {
        "time": t.tolist(),
        "base_shear": base_shear.tolist(),
        "overturning_moment": overturning_moment.tolist(),
        "max_base_shear": float(np.max(np.abs(base_shear))),
        "max_moment": float(np.max(np.abs(overturning_moment))),
    }


# ---------------------------------------------------------------------------
# 4. Hydrostatic properties
# ---------------------------------------------------------------------------
def compute_hydrostatic_properties(
    radius: float,
    z_bottom: float,
    z_top: float,
    rho_water: float = 1025.0,
    mass_structure: float = 0.0,
    z_cg: float = 0.0,
) -> dict:
    """Compute hydrostatic restoring and added-mass matrices for a
    vertical cylinder using welib.

    Parameters
    ----------
    radius : float
        Cylinder radius (m).
    z_bottom : float
        Bottom position of cylinder (m, negative below MSL).
    z_top : float
        Top position of cylinder (m, positive above MSL if piercing).
    rho_water : float
        Water density (kg/m^3).
    mass_structure : float
        Total structural mass (kg), for ballast/flooding correction.
    z_cg : float
        Vertical position of structure centre of gravity (m).

    Returns
    -------
    dict with keys: stiffness_matrix, added_mass_matrix
        Each is a 6x6 nested list.
    """
    # welib cylindervert_hydrostat: z1 must be above z2
    # z1 = top, z2 = bottom
    K = cylindervert_hydrostat(
        radius, z_top, z_bottom, rho_water, GRAVITY,
        m_f=mass_structure, z_f=z_cg,
        m_mg=mass_structure, z_mg=z_cg,
    )

    # welib cylindervert_addedmass: same z convention (z1=top, z2=bottom)
    M_a = cylindervert_addedmass(
        radius, z_top, z_bottom, rho_water,
    )

    return {
        "stiffness_matrix": K.tolist(),
        "added_mass_matrix": M_a.tolist(),
    }
