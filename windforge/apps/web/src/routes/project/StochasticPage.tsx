import { useState, useCallback, useMemo } from 'react';
import { useParams } from 'react-router-dom';
import { Activity, BarChart3, TrendingUp, Wind, Loader2 } from 'lucide-react';
import toast from 'react-hot-toast';
import Plot from 'react-plotly.js';
import axios from 'axios';

const API_BASE = (window as unknown as Record<string, string>).__WINDFORGE_API_URL__
  ? `${(window as unknown as Record<string, string>).__WINDFORGE_API_URL__}/api/v1` : '/api/v1';

function stochPost<T>(projectId: string, endpoint: string, data: unknown): Promise<T> {
  const token = localStorage.getItem('windforge_token');
  return axios.post<T>(`${API_BASE}/projects/${projectId}/stochastic/${endpoint}`, data, {
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
  }).then((res) => res.data);
}

const TABS = [
  { key: 'distributions', label: 'Distributions', icon: BarChart3 },
  { key: 'process', label: 'Stochastic Processes', icon: Activity },
  { key: 'fft', label: 'FFT / PSD', icon: TrendingUp },
  { key: 'correlation', label: 'Correlation', icon: Activity },
  { key: 'wind', label: 'Wind Generation', icon: Wind },
] as const;
type TabKey = (typeof TABS)[number]['key'];

/* ---- Result interfaces ---- */
interface DistResult { x: number[]; curves: Record<string, number[]>; }
interface ProcessResult { time: number[]; signal: number[]; tau: number[]; autocovariance: number[]; freq: number[]; autospectrum: number[]; }
interface FftResult { frequencies: number[]; spectrum: number[]; }
interface CorrResult { signal: number[]; lags: number[]; correlation_values: number[]; theoretical_coeff: number; }
interface WindResult { time: number[]; velocity: number[]; frequencies_generated: number[]; spectrum_generated: number[]; frequencies_target: number[]; spectrum_target: number[]; }

function makePlotLayout(overrides: Record<string, unknown> = {}) {
  return {
    paper_bgcolor: 'transparent', plot_bgcolor: 'rgba(17,24,39,0.8)',
    font: { family: 'ui-monospace, monospace', size: 10, color: '#9ca3af' },
    margin: { t: 40, r: 30, b: 60, l: 70 },
    xaxis: { gridcolor: 'rgba(100,116,139,0.2)', zeroline: false, ...(overrides.xaxis as object || {}) },
    yaxis: { gridcolor: 'rgba(100,116,139,0.2)', zeroline: false, ...(overrides.yaxis as object || {}) },
    legend: { bgcolor: 'rgba(0,0,0,0.3)', font: { size: 9, color: '#9ca3af' } },
    showlegend: true,
    ...Object.fromEntries(Object.entries(overrides).filter(([k]) => k !== 'xaxis' && k !== 'yaxis')),
  };
}

function NumberInput({ label, value, onChange, step, min, max, unit }: {
  label: string; value: number; onChange: (v: number) => void; step?: number; min?: number; max?: number; unit?: string;
}) {
  return (
    <div>
      <label className="block text-xs font-medium text-slate-400 mb-1">{label}{unit && <span className="text-slate-500 ml-1">({unit})</span>}</label>
      <input type="number" value={value} onChange={(e) => onChange(Number(e.target.value))} step={step ?? 0.1} min={min} max={max}
        className="bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-sm text-slate-100 w-full focus:ring-1 focus:ring-accent-500 focus:border-accent-500" />
    </div>
  );
}

export default function StochasticPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const [activeTab, setActiveTab] = useState<TabKey>('distributions');
  const [error, setError] = useState<string | null>(null);

  /* ---- Distributions state ---- */
  const [distResult, setDistResult] = useState<DistResult | null>(null);
  const [distLoading, setDistLoading] = useState(false);

  /* ---- Process state ---- */
  const [procType, setProcType] = useState('harmonic');
  const [procOmega, setProcOmega] = useState(10.0);
  const [procTau, setProcTau] = useState(10.0);
  const [procTmax, setProcTmax] = useState(50.0);
  const [procResult, setProcResult] = useState<ProcessResult | null>(null);
  const [procLoading, setProcLoading] = useState(false);

  /* ---- FFT state ---- */
  const [fftOutputType, setFftOutputType] = useState('PSD');
  const [fftAveraging, setFftAveraging] = useState('Welch');
  const [fftResult, setFftResult] = useState<FftResult | null>(null);
  const [fftLoading, setFftLoading] = useState(false);
  // We'll compute FFT from the process signal or generate a test signal
  const [fftSourceSignal, setFftSourceSignal] = useState<{ time: number[]; signal: number[] } | null>(null);

  /* ---- Correlation state ---- */
  const [corrCoeff, setCorrCoeff] = useState(0.95);
  const [corrNpts, setCorrNpts] = useState(2000);
  const [corrNlags, setCorrNlags] = useState(200);
  const [corrResult, setCorrResult] = useState<CorrResult | null>(null);
  const [corrLoading, setCorrLoading] = useState(false);

  /* ---- Wind state ---- */
  const [windU0, setWindU0] = useState(10.0);
  const [windTI, setWindTI] = useState(0.14);
  const [windL, setWindL] = useState(340.2);
  const [windTmax, setWindTmax] = useState(300.0);
  const [windDt, setWindDt] = useState(0.05);
  const [windSeed, setWindSeed] = useState(42);
  const [windResult, setWindResult] = useState<WindResult | null>(null);
  const [windLoading, setWindLoading] = useState(false);

  /* ---- Handlers ---- */
  const handleDistributions = useCallback(async () => {
    if (!projectId) return;
    setDistLoading(true); setError(null); setDistResult(null);
    try {
      setDistResult(await stochPost<DistResult>(projectId, 'distributions', {}));
      toast.success('Distributions computed');
    } catch { setError('Distributions failed'); toast.error('Failed'); }
    finally { setDistLoading(false); }
  }, [projectId]);

  const handleProcess = useCallback(async () => {
    if (!projectId) return;
    setProcLoading(true); setError(null); setProcResult(null);
    try {
      const res = await stochPost<ProcessResult>(projectId, 'process', {
        process_type: procType, omega_max: procOmega, tau_max: procTau, time_max: procTmax,
      });
      setProcResult(res);
      // Save signal for FFT tab
      setFftSourceSignal({ time: res.time, signal: res.signal });
      toast.success('Process sampled');
    } catch { setError('Process sampling failed'); toast.error('Failed'); }
    finally { setProcLoading(false); }
  }, [projectId, procType, procOmega, procTau, procTmax]);

  const handleFft = useCallback(async () => {
    if (!projectId) return;
    setFftLoading(true); setError(null); setFftResult(null);
    // Use saved signal from process tab, or generate a test one
    let time: number[];
    let signal: number[];
    if (fftSourceSignal && fftSourceSignal.time.length > 0) {
      time = fftSourceSignal.time;
      signal = fftSourceSignal.signal;
    } else {
      // Generate a test signal: 3 Hz + 7 Hz + noise
      const dt = 0.01;
      const N = 2000;
      time = Array.from({ length: N }, (_, i) => i * dt);
      signal = time.map((t) => Math.sin(2 * Math.PI * 3 * t) + 0.5 * Math.sin(2 * Math.PI * 7 * t) + 0.3 * (Math.random() - 0.5));
    }
    try {
      setFftResult(await stochPost<FftResult>(projectId, 'fft-psd', {
        time, signal, output_type: fftOutputType, averaging: fftAveraging,
      }));
      toast.success('FFT/PSD computed');
    } catch { setError('FFT computation failed'); toast.error('Failed'); }
    finally { setFftLoading(false); }
  }, [projectId, fftSourceSignal, fftOutputType, fftAveraging]);

  const handleCorrelation = useCallback(async () => {
    if (!projectId) return;
    setCorrLoading(true); setError(null); setCorrResult(null);
    try {
      setCorrResult(await stochPost<CorrResult>(projectId, 'correlation', {
        coeff: corrCoeff, n_points: corrNpts, n_lags: corrNlags,
      }));
      toast.success('Correlation computed');
    } catch { setError('Correlation failed'); toast.error('Failed'); }
    finally { setCorrLoading(false); }
  }, [projectId, corrCoeff, corrNpts, corrNlags]);

  const handleWind = useCallback(async () => {
    if (!projectId) return;
    setWindLoading(true); setError(null); setWindResult(null);
    try {
      const res = await stochPost<WindResult>(projectId, 'turbulent-wind', {
        U0: windU0, turbulence_intensity: windTI, L: windL, t_max: windTmax, dt: windDt, seed: windSeed,
      });
      setWindResult(res);
      toast.success('Turbulent wind generated');
    } catch { setError('Wind generation failed'); toast.error('Failed'); }
    finally { setWindLoading(false); }
  }, [projectId, windU0, windTI, windL, windTmax, windDt, windSeed]);

  /* ---- Plot traces ---- */
  const COLORS = ['#22d3ee', '#f97316', '#a78bfa', '#34d399', '#f472b6', '#fbbf24'];

  const distTraces = useMemo(() => {
    if (!distResult) return [];
    return Object.entries(distResult.curves).map(([label, vals], i) => ({
      x: distResult.x, y: vals, name: label, type: 'scatter' as const,
      line: { color: COLORS[i % COLORS.length] },
    }));
  }, [distResult]);

  const processSignalTrace = useMemo(() => procResult ? [{
    x: procResult.time, y: procResult.signal, name: 'Sample', type: 'scatter' as const, line: { color: '#22d3ee' },
  }] : [], [procResult]);

  const processAutocovTrace = useMemo(() => procResult && procResult.tau.length > 0 ? [{
    x: procResult.tau, y: procResult.autocovariance, name: 'R(τ)', type: 'scatter' as const, line: { color: '#f97316' },
  }] : [], [procResult]);

  const processSpectrumTrace = useMemo(() => procResult && procResult.freq.length > 0 ? [{
    x: procResult.freq, y: procResult.autospectrum, name: 'S(f)', type: 'scatter' as const, line: { color: '#a78bfa' },
  }] : [], [procResult]);

  const fftTraces = useMemo(() => fftResult ? [{
    x: fftResult.frequencies, y: fftResult.spectrum, name: fftOutputType, type: 'scatter' as const, line: { color: '#22d3ee' },
  }] : [], [fftResult, fftOutputType]);

  const corrSignalTrace = useMemo(() => corrResult ? [{
    x: Array.from({ length: Math.min(corrResult.signal.length, 500) }, (_, i) => i),
    y: corrResult.signal.slice(0, 500),
    name: `Signal (ρ=${corrResult.theoretical_coeff})`, type: 'scatter' as const, line: { color: '#22d3ee' },
  }] : [], [corrResult]);

  const corrLagTrace = useMemo(() => corrResult ? [{
    x: corrResult.lags, y: corrResult.correlation_values,
    name: 'R(τ)', type: 'scatter' as const, line: { color: '#f97316' },
  }] : [], [corrResult]);

  const windTimeTrace = useMemo(() => windResult ? [{
    x: windResult.time, y: windResult.velocity,
    name: 'u(t)', type: 'scatter' as const, line: { color: '#22d3ee', width: 0.8 },
  }] : [], [windResult]);

  const windSpecTraces = useMemo(() => {
    if (!windResult) return [];
    const traces: Plotly.Data[] = [];
    if (windResult.frequencies_generated.length > 0)
      traces.push({ x: windResult.frequencies_generated, y: windResult.spectrum_generated, name: 'Generated PSD', type: 'scatter' as const, line: { color: '#22d3ee' } } as Plotly.Data);
    if (windResult.frequencies_target.length > 0)
      traces.push({ x: windResult.frequencies_target, y: windResult.spectrum_target, name: 'Kaimal target', type: 'scatter' as const, line: { color: '#f97316', dash: 'dash' } } as Plotly.Data);
    return traces;
  }, [windResult]);

  const isLoading: Record<TabKey, boolean> = { distributions: distLoading, process: procLoading, fft: fftLoading, correlation: corrLoading, wind: windLoading };
  const handleCompute: Record<TabKey, () => Promise<void>> = { distributions: handleDistributions, process: handleProcess, fft: handleFft, correlation: handleCorrelation, wind: handleWind };

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <Activity className="h-6 w-6 text-teal-400" />
        <h2 className="text-lg font-semibold text-white">Stochastic & Signal Processing</h2>
        <span className="text-xs text-slate-500 bg-slate-800 px-2 py-0.5 rounded">welib.stoch</span>
      </div>

      {/* Sub-tab pills */}
      <div className="flex flex-wrap gap-1">
        {TABS.map((tab) => { const Icon = tab.icon; return (
          <button key={tab.key} onClick={() => setActiveTab(tab.key)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              activeTab === tab.key ? 'bg-teal-500/20 text-teal-300 ring-1 ring-teal-500/40' : 'bg-slate-800 text-slate-400 hover:text-slate-200 hover:bg-slate-700'}`}>
            <Icon className="h-3.5 w-3.5" />{tab.label}
          </button>
        ); })}
      </div>

      {error && <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3 text-sm text-red-300">{error}</div>}

      <div className="grid grid-cols-1 xl:grid-cols-4 gap-4">
        {/* ---- Parameters panel ---- */}
        <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-700/50 space-y-3">
          <h3 className="text-sm font-medium text-slate-300 mb-2">Parameters</h3>

          {activeTab === 'distributions' && (
            <p className="text-xs text-slate-500">Computes PDFs for Gaussian, Rayleigh, Weibull, Uniform, Log-Normal, and Exponential distributions with default parameters.</p>
          )}

          {activeTab === 'process' && (<>
            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1">Process Type</label>
              <select value={procType} onChange={(e) => setProcType(e.target.value)}
                className="bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-sm text-slate-100 w-full">
                <option value="harmonic">Harmonic</option>
                <option value="exponential">Exponential</option>
                <option value="banded_white_noise">Banded White Noise</option>
              </select>
            </div>
            <NumberInput label="ω_max" value={procOmega} onChange={setProcOmega} unit="rad/s" step={1} min={1} />
            <NumberInput label="τ_max" value={procTau} onChange={setProcTau} step={1} min={1} />
            <NumberInput label="Duration" value={procTmax} onChange={setProcTmax} unit="s" step={10} min={10} />
          </>)}

          {activeTab === 'fft' && (<>
            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1">Output Type</label>
              <select value={fftOutputType} onChange={(e) => setFftOutputType(e.target.value)}
                className="bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-sm text-slate-100 w-full">
                <option value="PSD">PSD</option>
                <option value="amplitude">Amplitude</option>
                <option value="f x psd">f × PSD</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1">Averaging</label>
              <select value={fftAveraging} onChange={(e) => setFftAveraging(e.target.value)}
                className="bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-sm text-slate-100 w-full">
                <option value="Welch">Welch</option>
                <option value="none">None</option>
              </select>
            </div>
            <p className="text-xs text-slate-500">
              {fftSourceSignal ? `Using signal from Stochastic Process tab (${fftSourceSignal.time.length} pts)` : 'Will generate a test signal (3 Hz + 7 Hz + noise)'}
            </p>
          </>)}

          {activeTab === 'correlation' && (<>
            <NumberInput label="Correlation coeff" value={corrCoeff} onChange={setCorrCoeff} step={0.05} min={-1} max={1} />
            <NumberInput label="Signal length" value={corrNpts} onChange={setCorrNpts} step={500} min={100} />
            <NumberInput label="Lags" value={corrNlags} onChange={setCorrNlags} step={50} min={10} />
          </>)}

          {activeTab === 'wind' && (<>
            <NumberInput label="Mean wind" value={windU0} onChange={setWindU0} unit="m/s" step={1} min={1} />
            <NumberInput label="Turb. Intensity" value={windTI} onChange={setWindTI} step={0.02} min={0.01} max={1} />
            <NumberInput label="Length scale" value={windL} onChange={setWindL} unit="m" step={10} min={10} />
            <NumberInput label="Duration" value={windTmax} onChange={setWindTmax} unit="s" step={60} min={60} />
            <NumberInput label="Time step" value={windDt} onChange={setWindDt} unit="s" step={0.01} min={0.01} />
            <NumberInput label="Seed" value={windSeed} onChange={setWindSeed} step={1} min={0} />
          </>)}

          <button onClick={handleCompute[activeTab]} disabled={isLoading[activeTab]}
            className="w-full mt-2 flex items-center justify-center gap-2 px-4 py-2 rounded-lg bg-teal-600 text-white text-sm font-medium hover:bg-teal-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors">
            {isLoading[activeTab] ? <><Loader2 className="h-4 w-4 animate-spin" />Computing…</> : 'Compute'}
          </button>
        </div>

        {/* ---- Plots ---- */}
        <div className="xl:col-span-3 space-y-4">

          {/* Distributions */}
          {activeTab === 'distributions' && distResult && (
            <div className="bg-slate-800/30 rounded-xl border border-slate-700/30 p-2">
              <Plot data={distTraces as Plotly.Data[]}
                layout={makePlotLayout({ title: 'Probability Distributions', xaxis: { title: 'x' }, yaxis: { title: 'f(x)' }, height: 500 }) as Partial<Plotly.Layout>}
                config={{ responsive: true }} className="w-full" />
            </div>
          )}

          {/* Stochastic Process — 3 stacked plots */}
          {activeTab === 'process' && procResult && (
            <div className="space-y-4">
              <div className="bg-slate-800/30 rounded-xl border border-slate-700/30 p-2">
                <Plot data={processSignalTrace as Plotly.Data[]}
                  layout={makePlotLayout({ title: `${procType.charAt(0).toUpperCase() + procType.slice(1)} Process — Sample`, xaxis: { title: 'Time' }, yaxis: { title: 'x(t)' }, height: 280, showlegend: false }) as Partial<Plotly.Layout>}
                  config={{ responsive: true }} className="w-full" />
              </div>
              {processAutocovTrace.length > 0 && (
                <div className="bg-slate-800/30 rounded-xl border border-slate-700/30 p-2">
                  <Plot data={processAutocovTrace as Plotly.Data[]}
                    layout={makePlotLayout({ title: 'Autocovariance R(τ)', xaxis: { title: 'τ' }, yaxis: { title: 'R(τ)' }, height: 250, showlegend: false }) as Partial<Plotly.Layout>}
                    config={{ responsive: true }} className="w-full" />
                </div>
              )}
              {processSpectrumTrace.length > 0 && (
                <div className="bg-slate-800/30 rounded-xl border border-slate-700/30 p-2">
                  <Plot data={processSpectrumTrace as Plotly.Data[]}
                    layout={makePlotLayout({ title: 'Autospectrum S(ω)', xaxis: { title: 'Frequency (Hz)' }, yaxis: { title: 'S(f)' }, height: 250, showlegend: false }) as Partial<Plotly.Layout>}
                    config={{ responsive: true }} className="w-full" />
                </div>
              )}
            </div>
          )}

          {/* FFT / PSD */}
          {activeTab === 'fft' && fftResult && (
            <div className="bg-slate-800/30 rounded-xl border border-slate-700/30 p-2">
              <Plot data={fftTraces as Plotly.Data[]}
                layout={makePlotLayout({
                  title: `${fftOutputType} — ${fftAveraging} averaging`,
                  xaxis: { title: 'Frequency (Hz)', type: fftOutputType === 'amplitude' ? 'linear' : 'log' },
                  yaxis: { title: fftOutputType, type: fftOutputType === 'amplitude' ? 'linear' : 'log' },
                  height: 450, showlegend: false,
                }) as Partial<Plotly.Layout>}
                config={{ responsive: true }} className="w-full" />
            </div>
          )}

          {/* Correlation — 2 stacked plots */}
          {activeTab === 'correlation' && corrResult && (
            <div className="space-y-4">
              <div className="bg-slate-800/30 rounded-xl border border-slate-700/30 p-2">
                <Plot data={corrSignalTrace as Plotly.Data[]}
                  layout={makePlotLayout({ title: `Correlated Signal (ρ = ${corrResult.theoretical_coeff})`, xaxis: { title: 'Sample' }, yaxis: { title: 'x(n)' }, height: 280, showlegend: false }) as Partial<Plotly.Layout>}
                  config={{ responsive: true }} className="w-full" />
              </div>
              <div className="bg-slate-800/30 rounded-xl border border-slate-700/30 p-2">
                <Plot data={corrLagTrace as Plotly.Data[]}
                  layout={makePlotLayout({ title: 'Auto-correlation R(τ)', xaxis: { title: 'Lag' }, yaxis: { title: 'R(τ)' }, height: 280, showlegend: false }) as Partial<Plotly.Layout>}
                  config={{ responsive: true }} className="w-full" />
              </div>
            </div>
          )}

          {/* Wind generation — time series + PSD */}
          {activeTab === 'wind' && windResult && (
            <div className="space-y-4">
              <div className="bg-slate-800/30 rounded-xl border border-slate-700/30 p-2">
                <Plot data={windTimeTrace as Plotly.Data[]}
                  layout={makePlotLayout({ title: 'Turbulent Wind Time Series (Kaimal)', xaxis: { title: 'Time (s)' }, yaxis: { title: 'u (m/s)' }, height: 300, showlegend: false }) as Partial<Plotly.Layout>}
                  config={{ responsive: true }} className="w-full" />
              </div>
              {windSpecTraces.length > 0 && (
                <div className="bg-slate-800/30 rounded-xl border border-slate-700/30 p-2">
                  <Plot data={windSpecTraces}
                    layout={makePlotLayout({
                      title: 'PSD: Generated vs Kaimal Target',
                      xaxis: { title: 'Frequency (Hz)', type: 'log' },
                      yaxis: { title: 'S(f) (m²/s²/Hz)', type: 'log' },
                      height: 350,
                    }) as Partial<Plotly.Layout>}
                    config={{ responsive: true }} className="w-full" />
                </div>
              )}
            </div>
          )}

          {/* Empty states */}
          {((activeTab === 'distributions' && !distResult && !distLoading) ||
            (activeTab === 'process' && !procResult && !procLoading) ||
            (activeTab === 'fft' && !fftResult && !fftLoading) ||
            (activeTab === 'correlation' && !corrResult && !corrLoading) ||
            (activeTab === 'wind' && !windResult && !windLoading)) && (
            <div className="bg-slate-800/20 rounded-xl border border-slate-700/30 p-12 text-center text-slate-500">
              Click <span className="text-teal-400">Compute</span> to generate the visualization
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
