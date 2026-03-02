"""Wind environment analysis service using welib.

Provides Kaimal spectrum computation, IEC turbulence envelopes (NTM/ETM),
extreme operating gust (EOG), and wind shear profile calculations.

All functions are synchronous (CPU-bound) and should be called via
asyncio.loop.run_in_executor() from async handlers.

Key welib functions used:
  - welib.wind.spectra.kaimal_f(f, V0, sigma, L)
  - welib.standards.IEC.NTM(WS, turbulence_class)
  - welib.standards.IEC.ETM(WS, turbulence_class)
  - welib.standards.IEC.EOG(WS, D, z_hub, WT_class, turbulence_class, ...)
  - welib.wind.shear.powerlaw(z, alpha, z_ref, U_ref)
  - welib.wind.shear.loglaw(z, z_0, z_ref, U_ref)
"""

from __future__ import annotations

import logging
from math import log10

import numpy as np
from welib.standards.IEC import EOG as iec_eog
from welib.standards.IEC import ETM as iec_etm
from welib.standards.IEC import NTM as iec_ntm
from welib.wind.shear import loglaw, powerlaw
from welib.wind.spectra import kaimal_f

logger = logging.getLogger("windforge.wind")


# ---------------------------------------------------------------------------
# IEC 61400-1 turbulence parameter helpers
# ---------------------------------------------------------------------------
# Reference turbulence intensity I_ref for each turbulence class
_I_REF = {"A": 0.16, "B": 0.14, "C": 0.12}

# IEC 61400-1 Ed.4 integral length scale (simplified approximation)
_LAMBDA1_HUB = 42.0  # for hub height >= 60 m


def _iec_sigma1(V_hub: float, turbulence_class: str = "A") -> float:
    """Approximate NTM standard deviation sigma_1 = I_ref * (0.75*V_hub + 5.6)."""
    I_ref = _I_REF.get(turbulence_class.upper(), 0.16)
    return I_ref * (0.75 * V_hub + 5.6)


def _iec_length_scale() -> float:
    """IEC 61400-1 Ed.4 longitudinal length scale L_1 = 8.1 * Lambda_1."""
    return 8.1 * _LAMBDA1_HUB


# ---------------------------------------------------------------------------
# 1. Kaimal spectrum
# ---------------------------------------------------------------------------
def compute_kaimal_spectrum(
    V_hub: float,
    freq_min: float = 0.001,
    freq_max: float = 10.0,
    n_points: int = 500,
    turbulence_class: str = "A",
) -> dict:
    """Compute single-sided Kaimal power spectral density for u, v, w components.

    Returns dict with keys: frequencies, Su, Sv, Sw (all as lists of floats).
    """
    freq = np.logspace(log10(freq_min), log10(freq_max), n_points)

    sigma1 = _iec_sigma1(V_hub, turbulence_class)
    L1 = _iec_length_scale()

    # IEC 61400-1 component ratios: sigma2 = 0.8*sigma1, sigma3 = 0.5*sigma1
    # Length scales: L2 = 2.7*Lambda1, L3 = 0.66*Lambda1
    sigma2 = 0.8 * sigma1
    sigma3 = 0.5 * sigma1
    L2 = 2.7 * _LAMBDA1_HUB
    L3 = 0.66 * _LAMBDA1_HUB

    Su = kaimal_f(freq, V_hub, sigma1, L1)
    Sv = kaimal_f(freq, V_hub, sigma2, L2)
    Sw = kaimal_f(freq, V_hub, sigma3, L3)

    return {
        "frequencies": freq.tolist(),
        "Su": Su.tolist(),
        "Sv": Sv.tolist(),
        "Sw": Sw.tolist(),
    }


# ---------------------------------------------------------------------------
# 2. Turbulence envelope (NTM / ETM across classes)
# ---------------------------------------------------------------------------
def compute_turbulence_envelope(
    wind_class: str = "I",
    v_ref: float = 50.0,
) -> dict:
    """Compute NTM and ETM turbulence standard deviation envelopes for classes A, B, C.

    Returns dict with keys: wind_speeds, ntm_A..C, etm_A..C (all as lists).
    """
    wind_speeds = np.arange(3.0, 26.0, 0.5)

    result: dict = {"wind_speeds": wind_speeds.tolist()}

    for tc in ("A", "B", "C"):
        # NTM(WS, turbulence_class) -> array of sigma_1
        sigma_ntm = iec_ntm(wind_speeds, turbulence_class=tc)
        result[f"ntm_{tc}"] = np.asarray(sigma_ntm).tolist()

        # ETM(WS, turbulence_class) -> array of sigma_1
        sigma_etm = iec_etm(wind_speeds, turbulence_class=tc)
        result[f"etm_{tc}"] = np.asarray(sigma_etm).tolist()

    return result


# ---------------------------------------------------------------------------
# 3. Extreme Operating Gust (EOG)
# ---------------------------------------------------------------------------
def compute_eog(
    V_hub: float,
    rotor_diameter: float,
    hub_height: float,
    wind_class: str = "I",
    turbulence_class: str = "A",
) -> dict:
    """Compute IEC Extreme Operating Gust time series.

    welib.standards.IEC.EOG returns (time, V_total, V_gust_max, V_gust).

    Returns dict with keys: time, wind_speed, gust_component, gust_peak.
    """
    # EOG signature: EOG(WS, D, z_hub, WT_class, turbulence_class, ...)
    t, V_total, V_gust_max, V_gust = iec_eog(
        V_hub,
        rotor_diameter,
        hub_height,
        WT_class=wind_class,
        turbulence_class=turbulence_class,
    )

    return {
        "time": t.tolist(),
        "wind_speed": V_total.tolist(),
        "gust_component": V_gust.tolist(),
        "gust_peak": float(V_gust_max),
    }


# ---------------------------------------------------------------------------
# 4. Wind shear profiles
# ---------------------------------------------------------------------------
def compute_wind_shear(
    V_hub: float,
    hub_height: float,
    shear_exp: float = 0.2,
    z0: float = 0.01,
    z_min: float = 0.0,
    z_max: float = 200.0,
    n_points: int = 100,
) -> dict:
    """Compute power-law and log-law wind shear profiles.

    welib signatures:
      powerlaw(z, alpha, z_ref, U_ref) -> array
      loglaw(z, z_0, z_ref, U_ref) -> array

    Returns dict with keys: heights, velocity_powerlaw, velocity_loglaw.
    """
    heights = np.linspace(max(z_min, 0.1), z_max, n_points)

    v_power = powerlaw(heights, shear_exp, hub_height, V_hub)
    v_log = loglaw(heights, z0, hub_height, V_hub)

    return {
        "heights": heights.tolist(),
        "velocity_powerlaw": v_power.tolist(),
        "velocity_loglaw": v_log.tolist(),
    }
