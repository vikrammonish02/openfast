"""Post-processing service using openfast_toolbox.

Provides fatigue (DEL / Markov), statistics (PDF), spectral (FFT / PSD),
and damping estimation – all powered by validated openfast_toolbox functions.

Key openfast_toolbox modules used:
  - openfast_toolbox.tools.fatigue   (equivalent_load, cycle_matrix, rainflow_windap)
  - openfast_toolbox.tools.stats     (pdf, rsquare, bin_DF)
  - openfast_toolbox.tools.spectral  (fft_wrap)
  - openfast_toolbox.tools.damping   (freqDampFromPeaks)
"""

from __future__ import annotations

import logging
import warnings

import numpy as np

logger = logging.getLogger("windforge.postprocessing")


# ---------------------------------------------------------------------------
# 1.  DEL & Fatigue  (Markov cycle matrix + Damage Equivalent Load)
# ---------------------------------------------------------------------------
def compute_del_fatigue(
    signal_type: str = "sine_noise",
    amplitude: float = 1000.0,
    frequency: float = 0.5,
    noise_std: float = 200.0,
    mean_load: float = 500.0,
    duration: float = 600.0,
    dt: float = 0.05,
    wohler_exponents: list[float] | None = None,
    n_bins: int = 46,
    rainflow_method: str = "windap",
) -> dict:
    """Compute DEL and Markov cycle matrix from a load signal.

    The signal is generated synthetically (user controls params).
    Fatigue analysis uses *openfast_toolbox.tools.fatigue*.

    Returns
    -------
    dict with keys:
        time, signal,
        del_values   – dict[str, float] for each Wohler exponent,
        rainflow_ranges, rainflow_counts,
        markov_cycles (2-D list), markov_ampl_edges, markov_mean_edges
    """
    from openfast_toolbox.tools.fatigue import (
        equivalent_load,
        cycle_matrix,
        rainflow_windap,
        rainflow_astm,
    )

    if wohler_exponents is None:
        wohler_exponents = [3.0, 4.0, 6.0, 8.0, 10.0, 12.0]

    try:
        t = np.arange(0, duration, dt)
        n = len(t)

        # --- Build synthetic load signal ---------------------------------
        if signal_type == "sine_noise":
            sig = (
                mean_load
                + amplitude * np.sin(2 * np.pi * frequency * t)
                + noise_std * np.random.default_rng(42).standard_normal(n)
            )
        elif signal_type == "random_walk":
            rng = np.random.default_rng(42)
            sig = mean_load + np.cumsum(rng.standard_normal(n)) * noise_std * np.sqrt(dt)
        else:
            sig = (
                mean_load
                + amplitude * np.sin(2 * np.pi * frequency * t)
                + noise_std * np.random.default_rng(42).standard_normal(n)
            )

        # --- DEL for each Wöhler exponent --------------------------------
        del_values: dict[str, float] = {}
        for m in wohler_exponents:
            try:
                leq = equivalent_load(t, sig, m=m, Teq=1.0, bins=n_bins)
                del_values[f"m={m:.0f}"] = float(leq)
            except Exception:
                del_values[f"m={m:.0f}"] = float("nan")

        # --- Rainflow counting (1-D histogram of ranges) -----------------
        rf_func = rainflow_astm if rainflow_method == "astm" else rainflow_windap
        ampl_mean = np.array(rf_func(sig))  # shape (N, 2)
        if ampl_mean.ndim == 2 and ampl_mean.shape[1] >= 1:
            ranges = ampl_mean[:, 0]
        else:
            ranges = ampl_mean.flatten()
        hist_counts, hist_edges = np.histogram(ranges, bins=min(n_bins, 50))
        hist_centers = ((hist_edges[:-1] + hist_edges[1:]) / 2).tolist()

        # --- Markov cycle matrix (2-D) -----------------------------------
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            cycles, ampl_bin_mean, ampl_edges, mean_bin_mean, mean_edges = cycle_matrix(
                sig, ampl_bins=min(n_bins, 30), mean_bins=min(n_bins, 30),
                rainflow_func=rf_func,
            )

        return {
            "time": t[::max(1, n // 2000)].tolist(),
            "signal": sig[::max(1, n // 2000)].tolist(),
            "del_values": del_values,
            "rainflow_ranges": hist_centers,
            "rainflow_counts": hist_counts.tolist(),
            "markov_cycles": cycles.tolist(),
            "markov_ampl_edges": ampl_edges.tolist(),
            "markov_mean_edges": mean_edges.tolist(),
        }
    except Exception as exc:
        logger.warning("DEL/Fatigue computation failed: %s", exc)
        t = np.arange(0, duration, dt)
        return {
            "time": t[::max(1, len(t) // 2000)].tolist(),
            "signal": [0.0] * min(len(t), 2000),
            "del_values": {},
            "rainflow_ranges": [],
            "rainflow_counts": [],
            "markov_cycles": [],
            "markov_ampl_edges": [],
            "markov_mean_edges": [],
        }


# ---------------------------------------------------------------------------
# 2.  Statistics & PDF
# ---------------------------------------------------------------------------
def compute_statistics(
    signal_type: str = "sine_noise",
    amplitude: float = 5.0,
    frequency: float = 1.0,
    noise_std: float = 2.0,
    mean_val: float = 0.0,
    duration: float = 60.0,
    dt: float = 0.01,
    pdf_method: str = "histogram",
    n_bins: int = 50,
) -> dict:
    """Compute PDF and basic statistics of a signal.

    Uses *openfast_toolbox.tools.stats.pdf* for the density estimate.

    Returns
    -------
    dict with keys:
        time, signal, pdf_x, pdf_y,
        stats (dict with mean, std, min, max, skew, kurtosis, rms)
    """
    from openfast_toolbox.tools.stats import pdf as ot_pdf

    try:
        t = np.arange(0, duration, dt)
        n = len(t)
        rng = np.random.default_rng(42)

        if signal_type == "sine_noise":
            sig = mean_val + amplitude * np.sin(2 * np.pi * frequency * t) + noise_std * rng.standard_normal(n)
        elif signal_type == "gaussian":
            sig = mean_val + noise_std * rng.standard_normal(n)
        elif signal_type == "uniform":
            sig = mean_val + amplitude * (2 * rng.random(n) - 1)
        else:
            sig = mean_val + amplitude * np.sin(2 * np.pi * frequency * t) + noise_std * rng.standard_normal(n)

        # --- PDF via openfast_toolbox ------------------------------------
        pdf_x, pdf_y = ot_pdf(sig, method=pdf_method, n=n_bins)

        # --- Basic statistics (numpy / scipy) ----------------------------
        from scipy.stats import skew, kurtosis
        stats_dict = {
            "mean": float(np.mean(sig)),
            "std": float(np.std(sig)),
            "min": float(np.min(sig)),
            "max": float(np.max(sig)),
            "rms": float(np.sqrt(np.mean(sig ** 2))),
            "skewness": float(skew(sig)),
            "kurtosis": float(kurtosis(sig)),
        }

        # Downsample time series for frontend
        step = max(1, n // 3000)
        return {
            "time": t[::step].tolist(),
            "signal": sig[::step].tolist(),
            "pdf_x": pdf_x.tolist(),
            "pdf_y": pdf_y.tolist(),
            "stats": stats_dict,
        }
    except Exception as exc:
        logger.warning("Statistics computation failed: %s", exc)
        return {
            "time": [],
            "signal": [],
            "pdf_x": [],
            "pdf_y": [],
            "stats": {"mean": 0, "std": 0, "min": 0, "max": 0, "rms": 0, "skewness": 0, "kurtosis": 0},
        }


# ---------------------------------------------------------------------------
# 3.  Spectral Analysis  (FFT / PSD)
# ---------------------------------------------------------------------------
def compute_spectral(
    signal_type: str = "multi_sine",
    frequencies: list[float] | None = None,
    amplitudes: list[float] | None = None,
    noise_std: float = 0.5,
    duration: float = 100.0,
    dt: float = 0.01,
    output_type: str = "PSD",
    averaging: str = "Welch",
    averaging_window: str = "hamming",
) -> dict:
    """Compute FFT / PSD of a signal.

    Uses *openfast_toolbox.tools.spectral.fft_wrap* for the spectral computation.

    Returns
    -------
    dict with keys:
        time, signal, freq, spectrum, output_type
    """
    from openfast_toolbox.tools.spectral import fft_wrap

    if frequencies is None:
        frequencies = [0.5, 1.2, 3.0]
    if amplitudes is None:
        amplitudes = [2.0, 1.0, 0.5]

    try:
        t = np.arange(0, duration, dt)
        n = len(t)
        rng = np.random.default_rng(42)

        # --- Build signal ------------------------------------------------
        sig = np.zeros(n)
        for f_i, a_i in zip(frequencies, amplitudes):
            sig += a_i * np.sin(2 * np.pi * f_i * t)
        sig += noise_std * rng.standard_normal(n)

        # --- Spectral analysis via openfast_toolbox ----------------------
        frq, Y, Info = fft_wrap(
            t, sig,
            output_type=output_type,
            averaging=averaging,
            averaging_window=averaging_window,
        )

        # Downsample time series for display
        step = max(1, n // 3000)
        return {
            "time": t[::step].tolist(),
            "signal": sig[::step].tolist(),
            "freq": frq.tolist(),
            "spectrum": Y.tolist(),
            "output_type": output_type,
        }
    except Exception as exc:
        logger.warning("Spectral computation failed: %s", exc)
        return {
            "time": [],
            "signal": [],
            "freq": [],
            "spectrum": [],
            "output_type": output_type,
        }


# ---------------------------------------------------------------------------
# 4.  Damping Estimation
# ---------------------------------------------------------------------------
def compute_damping(
    natural_freq: float = 0.1,
    damping_ratio: float = 0.05,
    amplitude: float = 10.0,
    mean_offset: float = 5.0,
    duration: float = 200.0,
    dt: float = 0.05,
) -> dict:
    """Estimate frequency and damping ratio from a decaying signal.

    Uses *openfast_toolbox.tools.damping.freqDampFromPeaks*.

    Returns
    -------
    dict with keys:
        time, signal, x_model, epos, eneg,
        peaks_pos_t, peaks_pos_x, peaks_neg_t, peaks_neg_x,
        estimated (dict with fn, fd, zeta, zetaMin, zetaMax, omega0, Td, logdec)
        input_params (dict echoing the input values)
    """
    from openfast_toolbox.tools.damping import freqDampFromPeaks

    try:
        t = np.arange(0, duration, dt)

        # --- Generate damped oscillation ---------------------------------
        omega_n = 2 * np.pi * natural_freq
        omega_d = omega_n * np.sqrt(max(0, 1 - damping_ratio ** 2))
        alpha = damping_ratio * omega_n
        sig = amplitude * np.exp(-alpha * t) * np.cos(omega_d * t) + mean_offset

        # --- Estimate using openfast_toolbox -----------------------------
        fn_est, zeta_est, info = freqDampFromPeaks(sig, t)

        IPos = info["IPos"]
        INeg = info["INeg"]

        # Downsample for frontend
        step = max(1, len(t) // 3000)

        return {
            "time": t[::step].tolist(),
            "signal": sig[::step].tolist(),
            "x_model": info["x_model"][::step].tolist(),
            "epos": info["epos"][::step].tolist(),
            "eneg": info["eneg"][::step].tolist(),
            "peaks_pos_t": t[IPos].tolist(),
            "peaks_pos_x": sig[IPos].tolist(),
            "peaks_neg_t": t[INeg].tolist(),
            "peaks_neg_x": sig[INeg].tolist(),
            "estimated": {
                "fn": float(fn_est),
                "fd": float(info["fd"]),
                "zeta": float(zeta_est),
                "zetaMin": float(info["zetaMin"]),
                "zetaMax": float(info["zetaMax"]),
                "omega0": float(info["omega0"]),
                "Td": float(info["Td"]),
            },
            "input_params": {
                "fn_true": float(natural_freq),
                "zeta_true": float(damping_ratio),
            },
        }
    except Exception as exc:
        logger.warning("Damping estimation failed: %s", exc)
        t = np.arange(0, duration, dt)
        step = max(1, len(t) // 3000)
        return {
            "time": t[::step].tolist(),
            "signal": [0.0] * min(len(t), 3000),
            "x_model": [],
            "epos": [],
            "eneg": [],
            "peaks_pos_t": [],
            "peaks_pos_x": [],
            "peaks_neg_t": [],
            "peaks_neg_x": [],
            "estimated": {"fn": 0, "fd": 0, "zeta": 0, "zetaMin": 0, "zetaMax": 0, "omega0": 0, "Td": 0},
            "input_params": {"fn_true": float(natural_freq), "zeta_true": float(damping_ratio)},
        }
