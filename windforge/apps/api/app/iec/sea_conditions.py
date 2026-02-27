"""
IEC 61400-3-1 sea state condition models.

Provides Normal Sea State (NSS), Severe Sea State (SSS), and
Extreme Sea State (ESS) calculations per IEC 61400-3-1.
"""

from __future__ import annotations
import math


def nss_wave_height(v_hub: float, water_depth: float = 30.0) -> float:
    """Normal Sea State significant wave height (Hs) per IEC 61400-3-1.

    Simplified Hs-Vhub correlation.

    Parameters
    ----------
    v_hub : float
        Hub-height mean wind speed (m/s).
    water_depth : float
        Water depth (m).

    Returns
    -------
    float
        Significant wave height Hs (m).
    """
    # Simplified correlation: Hs ≈ 0.1 * Vhub for typical North Sea conditions
    # Capped at depth-limited breaking wave height
    hs = 0.1 * v_hub + 0.5
    # Depth-limited: Hs_max ≈ 0.5 * d for shallow water
    hs_max = 0.5 * water_depth
    return min(hs, hs_max)


def nss_wave_period(hs: float) -> float:
    """Associated peak period for Normal Sea State.

    Uses Tp = 11.1 * sqrt(Hs/g) empirical relation.

    Parameters
    ----------
    hs : float
        Significant wave height (m).

    Returns
    -------
    float
        Peak spectral period Tp (s).
    """
    g = 9.80665
    return 11.1 * math.sqrt(hs / g)


def ess_wave_height_50yr(water_depth: float = 30.0) -> float:
    """Extreme Sea State 50-year significant wave height.

    Parameters
    ----------
    water_depth : float
        Water depth (m).

    Returns
    -------
    float
        50-year extreme significant wave height Hs50 (m).
    """
    # Typical North Sea: Hs50 ≈ 9-12m, depth limited
    hs50 = 9.5
    hs_max = 0.5 * water_depth
    return min(hs50, hs_max)


def ess_wave_height_1yr(water_depth: float = 30.0) -> float:
    """Extreme Sea State 1-year significant wave height.

    Parameters
    ----------
    water_depth : float
        Water depth (m).

    Returns
    -------
    float
        1-year extreme significant wave height Hs1 (m).
    """
    # Hs1 ≈ 0.8 * Hs50
    hs1 = 0.8 * ess_wave_height_50yr(water_depth)
    return hs1


def sss_wave_height(v_hub: float, water_depth: float = 30.0) -> float:
    """Severe Sea State significant wave height.

    SSS represents the most severe sea state with a specified
    return period conditioned on concurrent wind speed.

    Parameters
    ----------
    v_hub : float
        Hub-height mean wind speed (m/s).
    water_depth : float
        Water depth (m).

    Returns
    -------
    float
        Severe sea state significant wave height Hs (m).
    """
    # SSS: approximately 1.5x NSS
    hs_nss = nss_wave_height(v_hub, water_depth)
    return min(1.5 * hs_nss, 0.5 * water_depth)
