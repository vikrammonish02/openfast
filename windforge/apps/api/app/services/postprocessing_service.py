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


# ---------------------------------------------------------------------------
# 5.  Extreme Value Extrapolation  (Gumbel / EV1)
#     Based on: NREL/CP-500-25787 (Madsen, Pierce, Buhl, 1999)
#               NREL/TP-500-34421 (Moriarty, Holley, Butterfield, 2004)
# ---------------------------------------------------------------------------
def _gumbel_cdf(x: np.ndarray, alpha: float, beta: float) -> np.ndarray:
    """Gumbel (EV1) CDF: F(x) = exp(-exp(-alpha*(x - beta)))"""
    return np.exp(-np.exp(-alpha * (x - beta)))


def _gumbel_ppf(p: np.ndarray, alpha: float, beta: float) -> np.ndarray:
    """Gumbel (EV1) percent-point (inverse CDF):
    x = beta - (1/alpha) * ln(-ln(p))
    """
    return beta - (1.0 / alpha) * np.log(-np.log(np.clip(p, 1e-15, 1 - 1e-15)))


def _gumbel_fit_moments(extremes: np.ndarray) -> tuple[float, float]:
    """Fit Gumbel distribution using method of moments (Eq. from NREL/TP-500-34421).

    Parameters
    ----------
    extremes : 1-D array of observed extreme values (e.g., block maxima).

    Returns
    -------
    alpha : scale parameter  (alpha = pi / (sqrt(6) * sigma))
    beta  : location parameter  (beta = mu - euler_gamma / alpha)
    """
    mu = float(np.mean(extremes))
    sigma = float(np.std(extremes, ddof=1))
    if sigma < 1e-12:
        sigma = 1e-12  # avoid division by zero
    euler_gamma = 0.5772156649015329  # Euler-Mascheroni constant
    alpha = np.pi / (np.sqrt(6.0) * sigma)
    beta = mu - euler_gamma / alpha
    return float(alpha), float(beta)


def compute_extreme_value(
    signal_type: str = "turbulent_load",
    amplitude: float = 2000.0,
    frequency: float = 0.3,
    noise_std: float = 500.0,
    mean_load: float = 3000.0,
    duration: float = 600.0,
    dt: float = 0.05,
    n_simulations: int = 6,
    block_size: float = 600.0,
    threshold_sigma: float = 1.4,
    return_periods: list[float] | None = None,
) -> dict:
    """Extreme-value extrapolation using the Gumbel (EV1) distribution.

    Methodology follows NREL/CP-500-25787 and NREL/TP-500-34421:
      1) Generate N independent turbulent load time-series (simulated DLC seeds)
      2) Extract block maxima from each simulation (one extreme per block)
      3) Fit Gumbel distribution via method of moments
      4) Extrapolate to target return periods (e.g. 1-yr, 20-yr, 50-yr)
      5) Produce Gumbel probability plot

    Parameters
    ----------
    signal_type : str
        Type of synthetic signal to generate.
    amplitude, frequency, noise_std, mean_load : float
        Signal generation parameters.
    duration : float
        Duration of each simulation (s).
    dt : float
        Timestep (s).
    n_simulations : int
        Number of independent simulations (seed count, like DLC 1.1).
    block_size : float
        Block duration for block-maxima extraction (s). Typically = duration.
    threshold_sigma : float
        Threshold = mean + threshold_sigma * std for peaks-over-threshold.
    return_periods : list[float] | None
        Target return periods in multiples of block_size.
        Default: [1, 10, 50, 100, 500, 1000].

    Returns
    -------
    dict with keys:
        time, signal (last simulation for display),
        block_maxima,
        gumbel_params (dict with alpha, beta, mu, sigma),
        prob_plot_x, prob_plot_y, prob_plot_fit_x, prob_plot_fit_y,
        return_periods, extrapolated_loads,
        pot_threshold, pot_peaks_t, pot_peaks_x,
        confidence_95_lower, confidence_95_upper
    """
    if return_periods is None:
        return_periods = [1.0, 10.0, 50.0, 100.0, 500.0, 1000.0]

    try:
        n_per_sim = int(duration / dt)

        # --- Generate N independent simulations --------------------------
        block_maxima = []
        last_t = None
        last_sig = None

        for seed in range(n_simulations):
            rng = np.random.default_rng(seed + 100)
            t = np.arange(0, duration, dt)
            n = len(t)

            if signal_type == "turbulent_load":
                # Realistic turbulent load: sine + filtered noise + random gusts
                sig = mean_load + amplitude * np.sin(2 * np.pi * frequency * t)
                # Add broadband turbulence
                sig += noise_std * rng.standard_normal(n)
                # Add occasional gusts (Poisson-like)
                n_gusts = rng.poisson(3)
                for _ in range(n_gusts):
                    t_gust = rng.uniform(0, duration)
                    gust_amp = rng.uniform(0.5, 2.0) * amplitude
                    gust_width = rng.uniform(5.0, 30.0)
                    sig += gust_amp * np.exp(-0.5 * ((t - t_gust) / gust_width) ** 2)
            elif signal_type == "weibull_process":
                # Weibull-like extreme process
                sig = mean_load + noise_std * rng.weibull(2.0, n) * np.sign(rng.standard_normal(n))
                sig += amplitude * np.sin(2 * np.pi * frequency * t)
            else:
                sig = mean_load + amplitude * np.sin(2 * np.pi * frequency * t) + noise_std * rng.standard_normal(n)

            # --- Block maxima extraction ---------------------------------
            n_blocks = max(1, int(duration / block_size))
            block_len = len(t) // n_blocks
            for b in range(n_blocks):
                i_start = b * block_len
                i_end = min((b + 1) * block_len, n)
                if i_end > i_start:
                    block_maxima.append(float(np.max(sig[i_start:i_end])))

            last_t = t
            last_sig = sig

        block_maxima = np.array(block_maxima)

        # --- Peaks-over-threshold for display ----------------------------
        sig_mean = float(np.mean(last_sig))
        sig_std = float(np.std(last_sig))
        pot_threshold = sig_mean + threshold_sigma * sig_std
        pot_mask = last_sig > pot_threshold
        # Get local peaks above threshold
        pot_peaks_idx = []
        in_exceedance = False
        local_max_idx = 0
        local_max_val = -np.inf
        for i in range(len(last_sig)):
            if last_sig[i] > pot_threshold:
                if not in_exceedance:
                    in_exceedance = True
                    local_max_val = last_sig[i]
                    local_max_idx = i
                elif last_sig[i] > local_max_val:
                    local_max_val = last_sig[i]
                    local_max_idx = i
            else:
                if in_exceedance:
                    pot_peaks_idx.append(local_max_idx)
                    in_exceedance = False
                    local_max_val = -np.inf
        if in_exceedance:
            pot_peaks_idx.append(local_max_idx)
        pot_peaks_idx = np.array(pot_peaks_idx)

        # --- Fit Gumbel (Method of Moments) ------------------------------
        alpha, beta = _gumbel_fit_moments(block_maxima)
        mu_ext = float(np.mean(block_maxima))
        sigma_ext = float(np.std(block_maxima, ddof=1))

        # --- Gumbel probability plot (Gumbel paper format) ---------------
        n_ext = len(block_maxima)
        sorted_ext = np.sort(block_maxima)
        # Plotting positions: Gringorton (i - 0.44) / (n + 0.12)
        plotting_pos = (np.arange(1, n_ext + 1) - 0.44) / (n_ext + 0.12)
        # Reduced variate: y = -ln(-ln(F))
        prob_plot_y_data = -np.log(-np.log(plotting_pos))
        prob_plot_x_data = sorted_ext.tolist()

        # Fitted line
        x_fit = np.linspace(sorted_ext[0] * 0.95, sorted_ext[-1] * 1.15, 200)
        cdf_fit = _gumbel_cdf(x_fit, alpha, beta)
        # Clamp for log
        cdf_fit = np.clip(cdf_fit, 1e-15, 1 - 1e-15)
        prob_plot_y_fit = -np.log(-np.log(cdf_fit))

        # --- Return period extrapolation ---------------------------------
        extrapolated = {}
        conf_lower = {}
        conf_upper = {}
        for rp in return_periods:
            # Probability of non-exceedance for return period rp
            # P = 1 - 1/N where N is the return period in block-units
            if rp <= 1.0:
                # For T=1 just use the mode (beta)
                x_rp = float(beta)
                se = 0.0
            else:
                p = 1.0 - 1.0 / rp
                x_rp = _gumbel_ppf(np.array([p]), alpha, beta)[0]

                # Approximate 95% confidence bounds (from NREL/CP-500-25787, Eq. 14)
                # Var(x_p) ≈ (1/alpha^2) * [1.109 + 0.514*y + 0.608*y^2] / n
                # where y = -ln(-ln(p))
                y_val = -np.log(-np.log(p))
                var_x = (1.0 / alpha ** 2) * (1.109 + 0.514 * y_val + 0.608 * y_val ** 2) / n_ext
                se = np.sqrt(max(var_x, 0))

            extrapolated[f"T={rp:.0f}"] = float(x_rp)
            conf_lower[f"T={rp:.0f}"] = float(x_rp - 1.96 * se)
            conf_upper[f"T={rp:.0f}"] = float(x_rp + 1.96 * se)

        # Downsample time series for display
        step = max(1, len(last_t) // 3000)
        return {
            "time": last_t[::step].tolist(),
            "signal": last_sig[::step].tolist(),
            "block_maxima": block_maxima.tolist(),
            "gumbel_params": {
                "alpha": alpha,
                "beta": beta,
                "mu": mu_ext,
                "sigma": sigma_ext,
                "n_extremes": n_ext,
            },
            "prob_plot_x": prob_plot_x_data,
            "prob_plot_y": prob_plot_y_data.tolist(),
            "prob_plot_fit_x": x_fit.tolist(),
            "prob_plot_fit_y": prob_plot_y_fit.tolist(),
            "return_periods": [f"T={rp:.0f}" for rp in return_periods],
            "extrapolated_loads": extrapolated,
            "confidence_95_lower": conf_lower,
            "confidence_95_upper": conf_upper,
            "pot_threshold": pot_threshold,
            "pot_peaks_t": last_t[pot_peaks_idx].tolist() if len(pot_peaks_idx) > 0 else [],
            "pot_peaks_x": last_sig[pot_peaks_idx].tolist() if len(pot_peaks_idx) > 0 else [],
        }
    except Exception as exc:
        logger.warning("Extreme value extrapolation failed: %s", exc)
        return {
            "time": [],
            "signal": [],
            "block_maxima": [],
            "gumbel_params": {"alpha": 0, "beta": 0, "mu": 0, "sigma": 0, "n_extremes": 0},
            "prob_plot_x": [],
            "prob_plot_y": [],
            "prob_plot_fit_x": [],
            "prob_plot_fit_y": [],
            "return_periods": [],
            "extrapolated_loads": {},
            "confidence_95_lower": {},
            "confidence_95_upper": {},
            "pot_threshold": 0,
            "pot_peaks_t": [],
            "pot_peaks_x": [],
        }
