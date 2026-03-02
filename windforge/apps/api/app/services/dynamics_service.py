"""System dynamics service using welib.system.

Provides forced vibration frequency response, Bode plots,
step/impulse response, Lorenz attractor, and pendulum dynamics.

All functions are synchronous (CPU-bound) and should be called via
asyncio.loop.run_in_executor() from async handlers.

Key welib functions/classes used:
  - welib.system.singledof.forced_vibration_particular_cst
  - welib.system.statespacelinear.LinearStateSpace
  - welib.system.mech_system.MechSystem
  - welib.system.chaos.dqdt_lorenz
"""

from __future__ import annotations

import logging
import warnings

import numpy as np
from scipy.integrate import solve_ivp

logger = logging.getLogger("windforge.dynamics")


# ---------------------------------------------------------------------------
# 1. Forced vibration frequency response (SDOF)
# ---------------------------------------------------------------------------
def compute_forced_vibration(
    zeta_values: list[float] | None = None,
    frat_min: float = 0.0,
    frat_max: float = 3.0,
    n_points: int = 500,
) -> dict:
    """Compute non-dimensional amplitude and phase vs frequency ratio
    for a single DOF system with different damping ratios.

    Uses welib.system.singledof.forced_vibration_particular_cst

    Parameters
    ----------
    zeta_values : list[float] or None
        Damping ratios to compare.  Defaults to [0.0, 0.1, 0.2, 0.5, 1.0].
    frat_min, frat_max : float
        Frequency ratio (f/fn) range.
    n_points : int
        Number of points.

    Returns
    -------
    dict with keys: frequency_ratios, amplitude_curves, phase_curves
    """
    from welib.system.singledof import forced_vibration_particular_cst

    if zeta_values is None:
        zeta_values = [0.0, 0.1, 0.2, 0.5, 1.0]

    frat = np.linspace(frat_min, frat_max, n_points)
    # Avoid exact resonance for undamped case
    frat[frat == 0] = 1e-10

    amplitude_curves: dict[str, list[float]] = {}
    phase_curves: dict[str, list[float]] = {}

    for zeta in zeta_values:
        label = f"ζ={zeta:.2f}"
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                # Returns (H0, phi) where H0 = amplitude ratio xk/F0, phi = phase
                H0_arr = []
                phi_arr = []
                for fr in frat:
                    H0, phi = forced_vibration_particular_cst(fr, 1.0, zeta)
                    H0_arr.append(float(H0))
                    phi_arr.append(float(phi))
            amplitude_curves[label] = H0_arr
            phase_curves[label] = phi_arr
        except Exception as exc:
            logger.warning("Forced vibration failed for zeta=%s: %s", zeta, exc)
            amplitude_curves[label] = [float("nan")] * n_points
            phase_curves[label] = [float("nan")] * n_points

    return {
        "frequency_ratios": frat.tolist(),
        "amplitude_curves": amplitude_curves,
        "phase_curves": phase_curves,
    }


# ---------------------------------------------------------------------------
# 2. Bode plot (state-space system)
# ---------------------------------------------------------------------------
def compute_bode_plot(
    mass: float = 1.0,
    damping: float = 0.5,
    stiffness: float = 10.0,
    freq_min: float = 0.01,
    freq_max: float = 100.0,
    n_points: int = 500,
) -> dict:
    """Compute Bode plot (magnitude in dB and phase in degrees) for
    a simple mass-spring-damper system in state-space form.

    Uses welib.system.statespacelinear.LinearStateSpace

    Returns
    -------
    dict with keys: frequencies, magnitude_db, phase_deg
    """
    from welib.system.statespacelinear import LinearStateSpace

    # State-space form: x = [q, qdot], u = F
    # qdotdot = (-k*q - c*qdot + F) / m
    # A = [[0, 1], [-k/m, -c/m]], B = [[0], [1/m]]
    # C = [[1, 0]] (measure displacement), D = [[0]]
    m, c, k = mass, damping, stiffness
    A = np.array([[0, 1], [-k / m, -c / m]])
    B = np.array([[0], [1 / m]])
    C = np.array([[1, 0]])
    D = np.array([[0]])

    ss = LinearStateSpace(A, B, C, D)

    freq = np.logspace(np.log10(freq_min), np.log10(freq_max), n_points)
    omega = 2 * np.pi * freq

    try:
        # frequency_response returns (magnitude, phase_deg) arrays
        mag, phase = ss.frequency_response(omega, deg=True)
        # mag shape: (n_outputs, n_inputs, n_freq) → take (0,0,:)
        if mag.ndim == 3:
            mag_vals = mag[0, 0, :]
            phase_vals = phase[0, 0, :]
        elif mag.ndim == 1:
            mag_vals = mag
            phase_vals = phase
        else:
            mag_vals = mag.flatten()
            phase_vals = phase.flatten()

        mag_db = 20 * np.log10(np.maximum(mag_vals, 1e-20))
    except Exception as exc:
        logger.warning("Bode plot via LinearStateSpace failed: %s", exc)
        # Fallback: manual transfer function
        H = np.zeros(len(omega), dtype=complex)
        for i, w in enumerate(omega):
            H[i] = 1.0 / (-m * w**2 + 1j * c * w + k)
        mag_db = 20 * np.log10(np.maximum(np.abs(H), 1e-20))
        phase_vals = np.degrees(np.angle(H))

    return {
        "frequencies": freq.tolist(),
        "magnitude_db": mag_db.tolist(),
        "phase_deg": phase_vals.tolist(),
    }


# ---------------------------------------------------------------------------
# 3. Step / Impulse response
# ---------------------------------------------------------------------------
def compute_step_impulse_response(
    mass: float = 1.0,
    damping: float = 0.5,
    stiffness: float = 10.0,
    response_type: str = "step",
    t_max: float = 10.0,
    dt: float = 0.01,
) -> dict:
    """Compute step or impulse response of a SDOF system.

    Parameters
    ----------
    mass, damping, stiffness : float
        System parameters.
    response_type : str
        One of "step", "impulse", "ramp".
    t_max : float
        Duration (s).
    dt : float
        Time step (s).

    Returns
    -------
    dict with keys: time, displacement, velocity
    """
    m, c, k = mass, damping, stiffness
    time = np.arange(0, t_max, dt)

    wn = np.sqrt(k / m)
    zeta = c / (2 * np.sqrt(k * m))

    if response_type == "step":
        # Analytical step response
        if zeta < 1:
            wd = wn * np.sqrt(1 - zeta**2)
            disp = (1.0 / k) * (1 - np.exp(-zeta * wn * time) * (
                np.cos(wd * time) + (zeta / np.sqrt(1 - zeta**2)) * np.sin(wd * time)
            ))
            vel = (1.0 / k) * (wn / np.sqrt(1 - zeta**2)) * np.exp(-zeta * wn * time) * np.sin(wd * time)
        elif zeta == 1:
            disp = (1.0 / k) * (1 - (1 + wn * time) * np.exp(-wn * time))
            vel = (1.0 / k) * wn**2 * time * np.exp(-wn * time)
        else:
            s1 = -zeta * wn + wn * np.sqrt(zeta**2 - 1)
            s2 = -zeta * wn - wn * np.sqrt(zeta**2 - 1)
            disp = (1.0 / k) * (1 + (s2 * np.exp(s1 * time) - s1 * np.exp(s2 * time)) / (s1 - s2))
            vel = (1.0 / k) * (s1 * s2 * (np.exp(s1 * time) - np.exp(s2 * time))) / (s1 - s2)
    elif response_type == "impulse":
        if zeta < 1:
            wd = wn * np.sqrt(1 - zeta**2)
            disp = (1.0 / (m * wd)) * np.exp(-zeta * wn * time) * np.sin(wd * time)
            vel = (1.0 / (m * wd)) * np.exp(-zeta * wn * time) * (
                wd * np.cos(wd * time) - zeta * wn * np.sin(wd * time)
            )
        else:
            s1 = -zeta * wn + wn * np.sqrt(zeta**2 - 1)
            s2 = -zeta * wn - wn * np.sqrt(zeta**2 - 1)
            disp = (1.0 / (m * (s1 - s2))) * (np.exp(s1 * time) - np.exp(s2 * time))
            vel = (1.0 / (m * (s1 - s2))) * (s1 * np.exp(s1 * time) - s2 * np.exp(s2 * time))
    else:  # ramp
        # Numerical integration for ramp: F(t) = t
        def rhs(t, y):
            return [y[1], (t - c * y[1] - k * y[0]) / m]

        sol = solve_ivp(rhs, [0, t_max], [0, 0], t_eval=time, method="RK45")
        disp = sol.y[0]
        vel = sol.y[1]

    return {
        "time": time.tolist(),
        "displacement": np.asarray(disp).tolist(),
        "velocity": np.asarray(vel).tolist(),
    }


# ---------------------------------------------------------------------------
# 4. Lorenz attractor
# ---------------------------------------------------------------------------
def compute_lorenz_attractor(
    sigma: float = 10.0,
    rho: float = 28.0,
    beta: float = 8.0 / 3.0,
    x0: float = 1.0,
    y0: float = 1.0,
    z0: float = 1.0,
    t_max: float = 50.0,
    dt: float = 0.01,
) -> dict:
    """Integrate the Lorenz system and return the 3D trajectory.

    Uses welib.system.chaos.dqdt_lorenz

    Returns
    -------
    dict with keys: x, y, z, time
    """
    from welib.system.chaos import dqdt_lorenz

    time = np.arange(0, t_max, dt)

    sol = solve_ivp(
        lambda t, q: dqdt_lorenz(t, q, sigma, beta, rho),
        [0, t_max],
        [x0, y0, z0],
        t_eval=time,
        method="RK45",
        max_step=dt,
    )

    return {
        "time": sol.t.tolist(),
        "x": sol.y[0].tolist(),
        "y": sol.y[1].tolist(),
        "z": sol.y[2].tolist(),
    }


# ---------------------------------------------------------------------------
# 5. Pendulum dynamics
# ---------------------------------------------------------------------------
def compute_pendulum(
    length: float = 1.0,
    mass: float = 1.0,
    damping_ratio: float = 0.0,
    theta0: float = 30.0,
    omega0: float = 0.0,
    t_max: float = 20.0,
    dt: float = 0.01,
) -> dict:
    """Simulate a simple pendulum (possibly nonlinear, damped).

    Parameters
    ----------
    length : float
        Pendulum length (m).
    mass : float
        Mass (kg).
    damping_ratio : float
        Damping ratio (0 = undamped).
    theta0 : float
        Initial angle (degrees).
    omega0 : float
        Initial angular velocity (deg/s).
    t_max : float
        Duration (s).
    dt : float
        Time step (s).

    Returns
    -------
    dict with keys: time, theta_deg, omega_deg_s, x_pos, y_pos
    """
    g = 9.81
    wn = np.sqrt(g / length)
    c_coeff = 2 * damping_ratio * mass * wn

    theta0_rad = np.radians(theta0)
    omega0_rad = np.radians(omega0)

    def rhs(t, y):
        th, om = y
        return [om, (-g / length * np.sin(th) - c_coeff / (mass * length**2) * om)]

    time = np.arange(0, t_max, dt)
    sol = solve_ivp(rhs, [0, t_max], [theta0_rad, omega0_rad], t_eval=time, method="RK45")

    theta = sol.y[0]
    omega = sol.y[1]

    # Cartesian positions for visualization
    x_pos = length * np.sin(theta)
    y_pos = -length * np.cos(theta)

    return {
        "time": sol.t.tolist(),
        "theta_deg": np.degrees(theta).tolist(),
        "omega_deg_s": np.degrees(omega).tolist(),
        "x_pos": x_pos.tolist(),
        "y_pos": y_pos.tolist(),
    }
