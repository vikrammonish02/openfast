"""Potential flow & vortex element service using welib.

Provides:
  - 2D vortex point flow field (velocity + stream function)
  - Cylinder in uniform flow (with/without circulation)
  - Karman-Trefftz conformal-mapping airfoil (shape + flow + wall Cp)

Key welib functions used:
  - welib.vortilib.elements.VortexPoint.vp_u, vp_psi
  - welib.vortilib.elements.VortexCylinder2D.vc_u, vc_stag, vc_coords, vc_Cptheta
  - welib.airfoils.karman_trefftz.KT_shape, KT_flow, KT_wall, cyl_params
"""

from __future__ import annotations

import logging

import numpy as np

logger = logging.getLogger("windforge.potentialflow")


# ---------------------------------------------------------------------------
# 1. Vortex point flow field
# ---------------------------------------------------------------------------
def compute_vortex_point_flow(
    Gamma: float = 1.0,
    x_min: float = -3.0,
    x_max: float = 3.0,
    y_min: float = -3.0,
    y_max: float = 3.0,
    n_grid: int = 80,
    vortex_x: float = 0.0,
    vortex_y: float = 0.0,
) -> dict:
    """Compute 2D velocity field + stream function from a single vortex point.

    Returns
    -------
    dict with keys: x_grid, y_grid, U, V, speed, psi
    (all 2D arrays flattened to list-of-lists for JSON)
    """
    from welib.vortilib.elements.VortexPoint import vp_u, vp_psi

    x = np.linspace(x_min, x_max, n_grid)
    y = np.linspace(y_min, y_max, n_grid)
    X, Y = np.meshgrid(x, y)

    Pv = [vortex_x, vortex_y]

    try:
        U, V = vp_u(X, Y, Pv=Pv, Gamma=Gamma)
        psi = vp_psi(X, Y, Pv=Pv, Gamma=Gamma)

        speed = np.sqrt(U ** 2 + V ** 2)
        # Clip extreme values near the vortex core
        speed_clip = np.clip(speed, 0, np.percentile(speed, 99))

        return {
            "x": x.tolist(),
            "y": y.tolist(),
            "U": np.nan_to_num(U, nan=0.0).tolist(),
            "V": np.nan_to_num(V, nan=0.0).tolist(),
            "speed": np.nan_to_num(speed_clip, nan=0.0).tolist(),
            "psi": np.nan_to_num(psi, nan=0.0).tolist(),
        }
    except Exception as exc:
        logger.warning("Vortex point flow failed: %s", exc)
        return {
            "x": x.tolist(),
            "y": y.tolist(),
            "U": np.zeros((n_grid, n_grid)).tolist(),
            "V": np.zeros((n_grid, n_grid)).tolist(),
            "speed": np.zeros((n_grid, n_grid)).tolist(),
            "psi": np.zeros((n_grid, n_grid)).tolist(),
        }


# ---------------------------------------------------------------------------
# 2. Cylinder in uniform flow
# ---------------------------------------------------------------------------
def compute_cylinder_flow(
    U0: float = 1.0,
    R: float = 1.0,
    Gamma: float = 0.0,
    alpha_deg: float = 0.0,
    x_min: float = -4.0,
    x_max: float = 4.0,
    y_min: float = -3.0,
    y_max: float = 3.0,
    n_grid: int = 100,
    n_theta: int = 200,
) -> dict:
    """Compute flow around a 2D cylinder with optional circulation.

    Returns
    -------
    dict with keys: x, y, U, V, speed, xc, yc, stag_x, stag_y,
                    theta, Cp_theta
    """
    from welib.vortilib.elements.VortexCylinder2D import (
        vc_u,
        vc_stag,
        vc_coords,
        vc_Cptheta,
    )

    alpha = np.radians(alpha_deg)

    x = np.linspace(x_min, x_max, n_grid)
    y = np.linspace(y_min, y_max, n_grid)
    X, Y = np.meshgrid(x, y)

    try:
        # Velocity field
        U, V = vc_u(X, Y, P=[0, 0], U0=U0, R=R, Gamma=Gamma, alpha=alpha)

        # Mask interior of cylinder
        r2 = X ** 2 + Y ** 2
        mask = r2 < R ** 2 * 0.99
        U[mask] = np.nan
        V[mask] = np.nan

        speed = np.sqrt(np.nan_to_num(U, nan=0.0) ** 2 + np.nan_to_num(V, nan=0.0) ** 2)

        # Cylinder boundary
        xc, yc = vc_coords(R, ne=200)

        # Stagnation points
        try:
            xs, ys = vc_stag(U0=U0, R=R, Gamma=Gamma, alpha=alpha)
            stag_x = np.atleast_1d(xs).tolist()
            stag_y = np.atleast_1d(ys).tolist()
        except Exception:
            stag_x = []
            stag_y = []

        # Surface Cp
        theta = np.linspace(0, 2 * np.pi, n_theta)
        Cp = vc_Cptheta(theta, U0=U0, R=R, Gamma=Gamma, alpha=alpha)

        return {
            "x": x.tolist(),
            "y": y.tolist(),
            "U": np.nan_to_num(U, nan=0.0).tolist(),
            "V": np.nan_to_num(V, nan=0.0).tolist(),
            "speed": np.nan_to_num(speed, nan=0.0).tolist(),
            "xc": xc.tolist(),
            "yc": yc.tolist(),
            "stag_x": stag_x,
            "stag_y": stag_y,
            "theta_deg": np.degrees(theta).tolist(),
            "Cp_theta": np.nan_to_num(Cp, nan=0.0).tolist(),
        }
    except Exception as exc:
        logger.warning("Cylinder flow failed: %s", exc)
        xc, yc = np.cos(np.linspace(0, 2 * np.pi, 100)), np.sin(np.linspace(0, 2 * np.pi, 100))
        return {
            "x": x.tolist(),
            "y": y.tolist(),
            "U": np.zeros((n_grid, n_grid)).tolist(),
            "V": np.zeros((n_grid, n_grid)).tolist(),
            "speed": np.zeros((n_grid, n_grid)).tolist(),
            "xc": xc.tolist(),
            "yc": yc.tolist(),
            "stag_x": [],
            "stag_y": [],
            "theta_deg": [],
            "Cp_theta": [],
        }


# ---------------------------------------------------------------------------
# 3. Karman-Trefftz conformal-mapping airfoil
# ---------------------------------------------------------------------------
def compute_karman_trefftz(
    XC: float = -0.2,
    YC: float = 0.1,
    tau_deg: float = 10.0,
    alpha_deg: float = 5.0,
    U0: float = 1.0,
    A: float = 1.0,
    n_surface: int = 150,
    x_min: float = -3.0,
    x_max: float = 4.0,
    y_min: float = -2.5,
    y_max: float = 2.5,
    n_grid: int = 120,
) -> dict:
    """Compute Karman-Trefftz airfoil shape, flow field, and surface Cp.

    Parameters
    ----------
    XC, YC : float
        Cylinder center in the conformal-map plane.
    tau_deg : float
        Trailing edge angle in degrees. Larger = thicker.
    alpha_deg : float
        Angle of attack in degrees.
    U0 : float
        Freestream speed.
    A : float
        Cylinder x-intercept in the mapping plane.
    n_surface : int
        Number of surface points.

    Returns
    -------
    dict with keys: airfoil_x, airfoil_y, wall_x, wall_y, wall_Cp,
                    x, y, u_field, v_field, Cp_field, speed_field
    """
    from welib.airfoils.karman_trefftz import KT_shape, KT_flow, KT_wall

    l = 2.0 - tau_deg / 180.0
    alpha = np.radians(alpha_deg)

    try:
        # Airfoil shape
        xa, ya = KT_shape(XC, YC, l=l, A=A, n=n_surface)

        # Wall quantities
        wa_x, wa_y, Cp_w, u_w, v_w = KT_wall(
            XC, YC, l=l, A=A, n=n_surface, U0=U0, alpha=alpha,
        )

        # Flow field
        x = np.linspace(x_min, x_max, n_grid)
        y = np.linspace(y_min, y_max, n_grid)
        Xg, Yg = np.meshgrid(x, y)

        u, v, CP = KT_flow(Xg, Yg, XC, YC, l=l, A=A, U0=U0, alpha=alpha)

        speed = np.sqrt(np.nan_to_num(u, nan=0.0) ** 2 + np.nan_to_num(v, nan=0.0) ** 2)

        return {
            "airfoil_x": xa.tolist(),
            "airfoil_y": ya.tolist(),
            "wall_x": wa_x.tolist(),
            "wall_y": wa_y.tolist(),
            "wall_Cp": np.nan_to_num(Cp_w, nan=0.0).tolist(),
            "x": x.tolist(),
            "y": y.tolist(),
            "u_field": np.nan_to_num(u, nan=0.0).tolist(),
            "v_field": np.nan_to_num(v, nan=0.0).tolist(),
            "Cp_field": np.nan_to_num(CP, nan=0.0).tolist(),
            "speed_field": np.nan_to_num(speed, nan=0.0).tolist(),
        }
    except Exception as exc:
        logger.warning("Karman-Trefftz failed: %s", exc)
        return {
            "airfoil_x": [],
            "airfoil_y": [],
            "wall_x": [],
            "wall_y": [],
            "wall_Cp": [],
            "x": [],
            "y": [],
            "u_field": [],
            "v_field": [],
            "Cp_field": [],
            "speed_field": [],
        }
