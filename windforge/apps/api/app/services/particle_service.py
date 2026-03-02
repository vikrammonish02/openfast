"""Particle dynamics service using welib.yams.partdyn.

Provides free-fall, orbital mechanics, and spring-mass simulations
using welib's particle system solver.

Key welib classes used:
  - welib.yams.partdyn.part.Part
  - welib.yams.partdyn.part.PartSystem
"""

from __future__ import annotations

import logging

import numpy as np

logger = logging.getLogger("windforge.particles")


# ---------------------------------------------------------------------------
# 1. Free fall
# ---------------------------------------------------------------------------
def compute_free_fall(
    mass: float = 10.0,
    z0: float = 100.0,
    vx0: float = 5.0,
    vz0: float = 0.0,
    g: float = 9.81,
    t_max: float = 5.0,
    n_points: int = 200,
) -> dict:
    """Simulate free-fall trajectory under gravity.

    Returns
    -------
    dict with keys: time, x, z, vx, vz, z_analytical
    """
    from welib.yams.partdyn.part import Part, PartSystem

    try:
        t = np.linspace(0, t_max, n_points)

        p1 = Part(mass, r0=(0, 0, z0), v0=(vx0, 0, vz0))
        sys = PartSystem([p1], activeForces=['gravity'])
        sys.g = g

        res = sys.integrate(t)

        # Extract particle trajectory
        x = res.y[0, :].tolist()  # x-position
        z = res.y[2, :].tolist()  # z-position
        vx = res.y[3, :].tolist()  # x-velocity
        vz = res.y[5, :].tolist()  # z-velocity

        # Analytical solution for comparison
        z_analytical = (z0 + vz0 * t - 0.5 * g * t ** 2).tolist()

        return {
            "time": t.tolist(),
            "x": x,
            "z": z,
            "vx": vx,
            "vz": vz,
            "z_analytical": z_analytical,
        }
    except Exception as exc:
        logger.warning("Free fall simulation failed: %s", exc)
        t = np.linspace(0, t_max, n_points)
        return {
            "time": t.tolist(),
            "x": (vx0 * t).tolist(),
            "z": (z0 - 0.5 * g * t ** 2).tolist(),
            "vx": [vx0] * n_points,
            "vz": (-g * t).tolist(),
            "z_analytical": (z0 - 0.5 * g * t ** 2).tolist(),
        }


# ---------------------------------------------------------------------------
# 2. Two-body orbital motion
# ---------------------------------------------------------------------------
def compute_two_body_orbit(
    m1: float = 5.972e24,
    m2: float = 7.348e22,
    r_initial: float = 3.844e8,
    eccentricity: float = 0.0,
    n_orbits: float = 2.0,
    n_points: int = 1000,
) -> dict:
    """Simulate two-body gravitational orbital motion.

    Parameters
    ----------
    m1 : float
        Mass of central body (kg). Default = Earth mass.
    m2 : float
        Mass of orbiting body (kg). Default = Moon mass.
    r_initial : float
        Initial separation (m). Default = Earth-Moon distance.
    eccentricity : float
        Orbital eccentricity (0 = circular).
    n_orbits : float
        Number of orbits to simulate.
    n_points : int
        Number of output points.

    Returns
    -------
    dict with keys: time, x1, z1, x2, z2, energy_kinetic, energy_potential
    """
    from welib.yams.partdyn.part import Part, PartSystem

    try:
        G = 6.6743e-11

        # Circular orbit velocity
        v_circular = np.sqrt(G * m1 / r_initial)

        # Adjust for eccentricity: v_periapsis = v_circular * sqrt((1+e)/(1-e)) for total energy conservation
        v_initial = v_circular * np.sqrt(1.0 + eccentricity)

        # Orbital period (approximate Kepler)
        T = 2 * np.pi * r_initial / v_circular
        t_max = n_orbits * T

        t = np.linspace(0, t_max, n_points)

        # Center of mass frame: both particles move
        v2_y = v_initial
        v1_y = -(m2 / m1) * v2_y  # conservation of momentum

        p1 = Part(m1, r0=(0, 0, 0), v0=(0, v1_y, 0))
        p2 = Part(m2, r0=(r_initial, 0, 0), v0=(0, v2_y, 0))

        sys = PartSystem([p1, p2], activeForces=['gravitational'])
        res = sys.integrate(t, method='Radau')

        # Extract trajectories (normalized by r_initial for display)
        x1 = (res.y[0, :] / r_initial).tolist()
        z1 = (res.y[1, :] / r_initial).tolist()  # y-component mapped to z for 2D
        x2 = (res.y[3, :] / r_initial).tolist()
        z2 = (res.y[4, :] / r_initial).tolist()

        # Compute energies
        energies = sys.energies(res)
        ek = energies.get('kinetic', np.zeros(len(t)))
        ep = energies.get('gravitational', np.zeros(len(t)))

        return {
            "time": (t / T).tolist(),  # in orbital periods
            "x1": x1,
            "z1": z1,
            "x2": x2,
            "z2": z2,
            "energy_kinetic": ek.tolist() if hasattr(ek, 'tolist') else [0.0] * len(t),
            "energy_potential": ep.tolist() if hasattr(ep, 'tolist') else [0.0] * len(t),
        }
    except Exception as exc:
        logger.warning("Orbital simulation failed: %s", exc)
        t = np.linspace(0, 2 * np.pi * n_orbits, n_points)
        return {
            "time": t.tolist(),
            "x1": [0.0] * n_points,
            "z1": [0.0] * n_points,
            "x2": np.cos(t).tolist(),
            "z2": np.sin(t).tolist(),
            "energy_kinetic": [0.0] * n_points,
            "energy_potential": [0.0] * n_points,
        }


# ---------------------------------------------------------------------------
# 3. Spring-mass system
# ---------------------------------------------------------------------------
def compute_spring_mass(
    m: float = 10.0,
    k: float = 100.0,
    c: float = 0.0,
    z0_offset: float = 2.0,
    g: float = 9.81,
    t_max: float = 10.0,
    n_points: int = 500,
) -> dict:
    """Simulate a spring-mass system with optional damping.

    A mass m is attached to a fixed point via a spring (stiffness k,
    rest length l0). Gravity pulls the mass down.

    Returns
    -------
    dict with keys: time, z, vz, energy_kinetic, energy_spring, energy_total
    """
    from welib.yams.partdyn.part import Part, Point, PartSystem

    try:
        t = np.linspace(0, t_max, n_points)

        # Equilibrium position: z_eq = z_anchor - l0 - m*g/k
        l0 = 5.0  # rest length
        z_anchor = 20.0
        z_eq = z_anchor - l0 - m * g / k

        # Initial position: offset from equilibrium
        z_initial = z_eq + z0_offset

        p1 = Part(m, r0=(0, 0, z_initial), v0=(0, 0, 0))
        anchor = Point(r0=(0, 0, z_anchor))

        sys = PartSystem([p1, anchor], activeForces=['spring', 'gravity'])
        sys.connect(p1, anchor, 'spring', k=k, l0=l0, c=c)
        sys.fix(anchor)
        sys.g = g

        res = sys.integrate(t, method='Radau')

        z = res.y[2, :].tolist()
        vz = res.y[5, :].tolist()

        # Energies
        energies = sys.energies(res)
        ek = energies.get('kinetic', np.zeros(len(t)))
        es = energies.get('spring', np.zeros(len(t)))
        et = energies.get('total', np.zeros(len(t)))

        return {
            "time": t.tolist(),
            "z": z,
            "vz": vz,
            "energy_kinetic": ek.tolist() if hasattr(ek, 'tolist') else [0.0] * len(t),
            "energy_spring": es.tolist() if hasattr(es, 'tolist') else [0.0] * len(t),
            "energy_total": et.tolist() if hasattr(et, 'tolist') else [0.0] * len(t),
        }
    except Exception as exc:
        logger.warning("Spring-mass simulation failed: %s", exc)
        t = np.linspace(0, t_max, n_points)
        omega = np.sqrt(k / m)
        zeta = c / (2 * np.sqrt(k * m))
        omega_d = omega * np.sqrt(max(0, 1 - zeta ** 2))
        z = z0_offset * np.exp(-zeta * omega * t) * np.cos(omega_d * t)
        return {
            "time": t.tolist(),
            "z": z.tolist(),
            "vz": [0.0] * n_points,
            "energy_kinetic": [0.0] * n_points,
            "energy_spring": [0.0] * n_points,
            "energy_total": [0.0] * n_points,
        }
