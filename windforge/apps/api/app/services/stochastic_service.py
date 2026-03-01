"""Stochastic analysis and signal processing service using welib.

Provides probability distributions, stochastic process sampling,
FFT/PSD computation, signal correlation, and turbulent wind generation.

Key welib functions used:
  - welib.stoch.distribution.* (gaussian_pdf, rayleigh_pdf, etc.)
  - welib.stoch.stationary_process.* (process classes)
  - welib.tools.spectral.fft_wrap
  - welib.tools.signal_analysis.correlated_signal, correlation
  - welib.wind.windsim.pointTSKaimal
"""

from __future__ import annotations

import logging
import warnings

import numpy as np

logger = logging.getLogger("windforge.stochastic")


# ---------------------------------------------------------------------------
# 1. Probability distributions
# ---------------------------------------------------------------------------
def compute_distributions(
    distributions: list[dict] | None = None,
    x_min: float = -5.0,
    x_max: float = 15.0,
    n_points: int = 500,
) -> dict:
    """Compute PDF curves for specified distributions.

    Parameters
    ----------
    distributions : list[dict] or None
        Each dict has 'type' and 'params'. If None, defaults are used.
    x_min, x_max : float
        X-axis range.
    n_points : int
        Number of points.

    Returns
    -------
    dict with keys: x, curves (dict of label → pdf_values list)
    """
    from welib.stoch.distribution import (
        gaussian_pdf,
        rayleigh_pdf,
        weibull_pdf,
        uniform_pdf,
        lognormal_pdf,
        exponential_pdf,
    )

    if distributions is None:
        distributions = [
            {"type": "gaussian", "params": {"mu": 0, "sig": 1}, "label": "Normal(0,1)"},
            {"type": "gaussian", "params": {"mu": 2, "sig": 0.5}, "label": "Normal(2,0.5)"},
            {"type": "rayleigh", "params": {"s": 2}, "label": "Rayleigh(s=2)"},
            {"type": "weibull", "params": {"k": 2, "A": 3}, "label": "Weibull(k=2,A=3)"},
            {"type": "uniform", "params": {"a": 1, "b": 5}, "label": "Uniform(1,5)"},
            {"type": "exponential", "params": {"beta": 0.5}, "label": "Exp(β=0.5)"},
        ]

    x = np.linspace(x_min, x_max, n_points)
    curves: dict[str, list[float]] = {}

    for dist in distributions:
        dtype = dist["type"]
        params = dist.get("params", {})
        label = dist.get("label", dtype)

        try:
            if dtype == "gaussian":
                pdf = gaussian_pdf(x, params.get("mu", 0), params.get("sig", 1))
            elif dtype == "rayleigh":
                pdf = rayleigh_pdf(x, params.get("s", 1))
            elif dtype == "weibull":
                pdf = weibull_pdf(x, params.get("k", 2), params.get("A", 1))
            elif dtype == "uniform":
                pdf = uniform_pdf(x, params.get("a", 0), params.get("b", 1))
            elif dtype == "lognormal":
                pdf = lognormal_pdf(x, params.get("mu", 0), params.get("sig", 1))
            elif dtype == "exponential":
                pdf = exponential_pdf(x, params.get("beta", 1))
            else:
                pdf = np.zeros_like(x)

            curves[label] = np.nan_to_num(pdf, nan=0.0).tolist()
        except Exception as exc:
            logger.warning("Distribution %s failed: %s", label, exc)
            curves[label] = [0.0] * n_points

    return {"x": x.tolist(), "curves": curves}


# ---------------------------------------------------------------------------
# 2. Stochastic process sampling
# ---------------------------------------------------------------------------
def compute_stochastic_process(
    process_type: str = "harmonic",
    omega_max: float = 10.0,
    tau_max: float = 10.0,
    time_max: float = 50.0,
    n_discr: int = 200,
) -> dict:
    """Sample a stationary stochastic process and return time series,
    autocovariance, and autospectrum.

    Parameters
    ----------
    process_type : str
        One of "harmonic", "exponential", "banded_white_noise".
    omega_max : float
        Maximum angular frequency.
    tau_max : float
        Maximum lag for autocovariance.
    time_max : float
        Duration of sample.
    n_discr : int
        Discretisation points.

    Returns
    -------
    dict with keys: time, signal, tau, autocovariance, freq, autospectrum
    """
    from welib.stoch.stationary_process import (
        HarmonicProcess,
        ExponentialProcess,
        BandedWhiteNoiseProcess,
    )

    try:
        if process_type == "harmonic":
            proc = HarmonicProcess(omega_max=omega_max, tau_max=tau_max,
                                   nDiscr=n_discr, time_max=time_max)
        elif process_type == "exponential":
            proc = ExponentialProcess(omega_max=omega_max, tau_max=tau_max,
                                     nDiscr=n_discr, time_max=time_max)
        elif process_type == "banded_white_noise":
            proc = BandedWhiteNoiseProcess(omega_max=omega_max, tau_max=tau_max,
                                           nDiscr=n_discr, time_max=time_max)
        else:
            raise ValueError(f"Unknown process type: {process_type}")

        # Generate sample
        proc.generate_samples_from_autospectrum()

        time = proc.time.tolist() if hasattr(proc, 'time') else list(range(n_discr))
        signal = proc.samples[0].tolist() if hasattr(proc, 'samples') and len(proc.samples) > 0 else [0.0] * n_discr

        # Autocovariance
        tau = proc.tau.tolist() if hasattr(proc, 'tau') else []
        autocov = proc.R.tolist() if hasattr(proc, 'R') else []

        # Autospectrum
        freq = (proc.omega / (2 * np.pi)).tolist() if hasattr(proc, 'omega') else []
        autospec = proc.S.tolist() if hasattr(proc, 'S') else []

    except Exception as exc:
        logger.warning("Stochastic process %s failed: %s", process_type, exc)
        time = np.linspace(0, time_max, n_discr).tolist()
        signal = np.random.randn(n_discr).tolist()
        tau = []
        autocov = []
        freq = []
        autospec = []

    return {
        "time": time,
        "signal": signal,
        "tau": tau,
        "autocovariance": autocov,
        "freq": freq,
        "autospectrum": autospec,
    }


# ---------------------------------------------------------------------------
# 3. FFT / PSD computation
# ---------------------------------------------------------------------------
def compute_fft_psd(
    time: list[float],
    signal: list[float],
    output_type: str = "PSD",
    averaging: str = "Welch",
) -> dict:
    """Compute FFT amplitude or PSD of a signal using welib.tools.spectral.fft_wrap.

    Parameters
    ----------
    time : list[float]
        Time array.
    signal : list[float]
        Signal values.
    output_type : str
        "amplitude" or "PSD" or "f x psd".
    averaging : str
        "none" or "Welch".

    Returns
    -------
    dict with keys: frequencies, spectrum
    """
    from welib.tools.spectral import fft_wrap

    t = np.asarray(time, dtype=float)
    y = np.asarray(signal, dtype=float)

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            f, S, _ = fft_wrap(t, y, output_type=output_type, averaging=averaging)
        return {
            "frequencies": f.tolist(),
            "spectrum": S.tolist(),
        }
    except Exception as exc:
        logger.warning("FFT/PSD computation failed: %s", exc)
        return {"frequencies": [], "spectrum": []}


# ---------------------------------------------------------------------------
# 4. Signal correlation
# ---------------------------------------------------------------------------
def compute_correlation(
    coeff: float = 0.95,
    n_points: int = 2000,
    n_lags: int = 200,
) -> dict:
    """Generate correlated signals and compute auto-correlation.

    Uses welib.tools.signal_analysis.correlated_signal, correlation.

    Returns
    -------
    dict with keys: signal, lags, correlation_values, theoretical_coeff
    """
    from welib.tools.signal_analysis import correlated_signal, correlation

    try:
        sig = correlated_signal(coeff=coeff, n=n_points)
        R, tau = correlation(sig, nMax=n_lags, dt=1)

        return {
            "signal": sig.tolist(),
            "lags": tau.tolist(),
            "correlation_values": R.tolist(),
            "theoretical_coeff": coeff,
        }
    except Exception as exc:
        logger.warning("Correlation computation failed: %s", exc)
        return {
            "signal": np.random.randn(n_points).tolist(),
            "lags": list(range(n_lags)),
            "correlation_values": [0.0] * n_lags,
            "theoretical_coeff": coeff,
        }


# ---------------------------------------------------------------------------
# 5. Turbulent wind time series generation
# ---------------------------------------------------------------------------
def generate_turbulent_wind(
    U0: float = 10.0,
    turbulence_intensity: float = 0.14,
    L: float = 340.2,
    t_max: float = 300.0,
    dt: float = 0.05,
    seed: int = 42,
) -> dict:
    """Generate synthetic turbulent wind time series using Kaimal spectrum.

    Uses welib.wind.windsim.pointTSKaimal.

    Returns
    -------
    dict with keys: time, velocity, frequencies, spectrum_generated, spectrum_target
    """
    from welib.wind.windsim import pointTSKaimal
    from welib.tools.spectral import fft_wrap
    from welib.wind.spectra import kaimal_f

    sigma = U0 * turbulence_intensity

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            t, u, freq, S = pointTSKaimal(
                t_max, dt, U0=U0, sigma=sigma, L=L, seed=seed,
            )

        # Compute PSD of generated signal
        f_gen, S_gen, _ = fft_wrap(t, u, output_type="PSD", averaging="Welch")

        # Target Kaimal spectrum
        f_target = np.linspace(0.001, 1.0 / (2 * dt), 500)
        S_target = kaimal_f(f_target, U0, sigma, L)

        return {
            "time": t.tolist(),
            "velocity": u.tolist(),
            "frequencies_generated": f_gen.tolist(),
            "spectrum_generated": S_gen.tolist(),
            "frequencies_target": f_target.tolist(),
            "spectrum_target": S_target.tolist(),
        }
    except Exception as exc:
        logger.warning("Wind generation failed: %s", exc)
        t = np.arange(0, t_max, dt)
        return {
            "time": t.tolist(),
            "velocity": (U0 + sigma * np.random.randn(len(t))).tolist(),
            "frequencies_generated": [],
            "spectrum_generated": [],
            "frequencies_target": [],
            "spectrum_target": [],
        }
