import { useState, useCallback, useMemo, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { BarChart3, Activity, Waves, TrendingDown, Loader2, TrendingUp, AlertTriangle, Download, FileSpreadsheet, ChevronDown, ChevronRight, CheckSquare, Square, Zap } from 'lucide-react';
import toast from 'react-hot-toast';
import Plot from 'react-plotly.js';
import axios from 'axios';

const API_BASE = (window as unknown as Record<string, string>).__WINDFORGE_API_URL__
  ? `${(window as unknown as Record<string, string>).__WINDFORGE_API_URL__}/api/v1` : '/api/v1';

function ppPost<T>(projectId: string, endpoint: string, data: unknown): Promise<T> {
  const token = localStorage.getItem('windforge_token');
  return axios.post<T>(`${API_BASE}/projects/${projectId}/postprocessing/${endpoint}`, data, {
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
  }).then((res) => res.data);
}

function ppGet<T>(projectId: string, endpoint: string): Promise<T> {
  const token = localStorage.getItem('windforge_token');
  return axios.get<T>(`${API_BASE}/projects/${projectId}/postprocessing/${endpoint}`, {
    headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
  }).then((res) => res.data);
}

function ppDownload(projectId: string, endpoint: string, data: unknown, filename: string): void {
  const token = localStorage.getItem('windforge_token');
  axios.post(`${API_BASE}/projects/${projectId}/postprocessing/${endpoint}`, data, {
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    responseType: 'blob',
  }).then((res) => {
    const url = window.URL.createObjectURL(new Blob([res.data]));
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', filename);
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
    toast.success(`Downloaded ${filename}`);
  }).catch(() => toast.error('Download failed'));
}

const TABS = [
  { key: 'fatigue', label: 'DEL & Fatigue', icon: BarChart3 },
  { key: 'statistics', label: 'Statistics & PDF', icon: Activity },
  { key: 'spectral', label: 'Spectral Analysis', icon: Waves },
  { key: 'damping', label: 'Damping Estimation', icon: TrendingDown },
  { key: 'extremevalue', label: 'Gumbel Extrapolation', icon: TrendingUp },
  // --- IEC Loads Analysis (Real Data) ---
  { key: 'iec-extreme', label: 'IEC Extreme Loads', icon: AlertTriangle },
  { key: 'iec-fatigue', label: 'IEC Fatigue DEL', icon: FileSpreadsheet },
  { key: 'iec-statistics', label: 'IEC Statistics', icon: Activity },
  { key: 'iec-gumbel', label: 'IEC Gumbel EV', icon: Zap },
] as const;
type TabKey = (typeof TABS)[number]['key'];

/* ---- result interfaces ---- */
interface DelResult {
  time: number[]; signal: number[];
  del_values: Record<string, number>;
  rainflow_ranges: number[]; rainflow_counts: number[];
  markov_cycles: number[][]; markov_ampl_edges: number[]; markov_mean_edges: number[];
}
interface StatsResult {
  time: number[]; signal: number[];
  pdf_x: number[]; pdf_y: number[];
  stats: { mean: number; std: number; min: number; max: number; rms: number; skewness: number; kurtosis: number };
}
interface SpectralResult { time: number[]; signal: number[]; freq: number[]; spectrum: number[]; output_type: string; }
interface DampingResult {
  time: number[]; signal: number[]; x_model: number[]; epos: number[]; eneg: number[];
  peaks_pos_t: number[]; peaks_pos_x: number[]; peaks_neg_t: number[]; peaks_neg_x: number[];
  estimated: { fn: number; fd: number; zeta: number; zetaMin: number; zetaMax: number; omega0: number; Td: number };
  input_params: { fn_true: number; zeta_true: number };
}
interface EVResult {
  time: number[]; signal: number[];
  block_maxima: number[];
  gumbel_params: { alpha: number; beta: number; mu: number; sigma: number; n_extremes: number };
  prob_plot_x: number[]; prob_plot_y: number[];
  prob_plot_fit_x: number[]; prob_plot_fit_y: number[];
  return_periods: string[];
  extrapolated_loads: Record<string, number>;
  confidence_95_lower: Record<string, number>;
  confidence_95_upper: Record<string, number>;
  pot_threshold: number;
  pot_peaks_t: number[]; pot_peaks_x: number[];
}

/* ---- IEC Loads interfaces ---- */
interface IECSimulationInfo {
  id: string; name: string; status: string;
  total_cases: number; completed_cases: number; failed_cases: number;
  dlc_numbers: string[]; created_at: string;
}
interface IECCaseInfo {
  case_id: string; dlc_number: string; wind_speed: number;
  seed_number: number; yaw_misalignment: number; analysis_type: string;
  safety_factor: number; probability_weight: number; status: string;
}
interface IECCasesGrouped {
  dlc_number: string; cases: IECCaseInfo[];
  total_cases: number; completed_cases: number;
}
interface IECExtremeRow {
  channel: string; unit: string;
  max_characteristic: number; max_design: number; max_dlc: string; max_vhub: number; max_time: number; max_case_id: string;
  min_characteristic: number; min_design: number; min_dlc: string; min_vhub: number; min_time: number; min_case_id: string;
  safety_factor_max: number; safety_factor_min: number;
}
interface IECConcurrentLoad {
  governing_channel: string; extreme_type: string; timestep_values: Record<string, number>;
}
interface IECDELRow {
  channel: string; unit: string; del_values: Record<string, number>; n_equivalent: number;
}
interface IECStatRow {
  channel: string; unit: string; mean: number; std: number;
  min_val: number; max_val: number; abs_max: number; n_cases: number;
}
interface IECCaseSummary {
  case_id: string; dlc_number: string; wind_speed: number; seed_number: number;
  yaw_misalignment: number; analysis_type: string; safety_factor: number; probability_weight: number;
}
interface IECLoadsResult {
  simulation_id: string; simulation_name: string;
  n_cases_analyzed: number; channels_analyzed: string[];
  extreme_loads: IECExtremeRow[];
  concurrent_loads: IECConcurrentLoad[];
  del_table: IECDELRow[];
  statistics_table: IECStatRow[];
  case_summary: IECCaseSummary[];
}
interface ExceedanceFitCurve { x: number[]; y: number[] }
interface IECGumbelResult {
  channel: string; n_cases: number; n_blocks: number; n_peaks: number;
  time: number[]; signal: number[];
  block_maxima: number[];
  gumbel_params: { alpha: number; beta: number; mu: number; sigma: number; n_extremes: number };
  prob_plot_x: number[]; prob_plot_y: number[];
  prob_plot_fit_x: number[]; prob_plot_fit_y: number[];
  return_periods: string[];
  extrapolated_loads: Record<string, number>;
  confidence_95_lower: Record<string, number>;
  confidence_95_upper: Record<string, number>;
  case_block_info: { case_id: string; dlc: string; vhub: number; block: number }[];
  exceedance_data_x: number[]; exceedance_data_y: number[];
  exceedance_fits: Record<string, ExceedanceFitCurve>;
  pot_threshold: number;
  distribution_params: Record<string, Record<string, number>>;
}

/* ---- helpers ---- */
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

function SelectInput({ label, value, onChange, options }: {
  label: string; value: string; onChange: (v: string) => void; options: { value: string; label: string }[];
}) {
  return (
    <div>
      <label className="block text-xs font-medium text-slate-400 mb-1">{label}</label>
      <select value={value} onChange={(e) => onChange(e.target.value)}
        className="bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-sm text-slate-100 w-full focus:ring-1 focus:ring-accent-500 focus:border-accent-500">
        {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </div>
  );
}

const COLORS = ['#22d3ee', '#f472b6', '#a78bfa', '#34d399', '#fbbf24', '#fb923c', '#e879f9', '#60a5fa', '#f87171', '#4ade80', '#c084fc', '#facc15'];

export default function PostProcessingPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const [activeTab, setActiveTab] = useState<TabKey>('fatigue');
  const [error, setError] = useState<string | null>(null);

  /* ---- DEL & Fatigue state ---- */
  const [fSigType, setFSigType] = useState('sine_noise');
  const [fAmpl, setFAmpl] = useState(1000.0);
  const [fFreq, setFFreq] = useState(0.5);
  const [fNoise, setFNoise] = useState(200.0);
  const [fMean, setFMean] = useState(500.0);
  const [fDur, setFDur] = useState(600.0);
  const [fDt, setFDt] = useState(0.05);
  const [fBins, setFBins] = useState(46);
  const [fRfMethod, setFRfMethod] = useState('windap');
  const [fResult, setFResult] = useState<DelResult | null>(null);
  const [fLoading, setFLoading] = useState(false);

  /* ---- Statistics state ---- */
  const [sSigType, setSSigType] = useState('sine_noise');
  const [sAmpl, setSAmpl] = useState(5.0);
  const [sFreq, setSFreq] = useState(1.0);
  const [sNoise, setSNoise] = useState(2.0);
  const [sMean, setSMean] = useState(0.0);
  const [sDur, setSDur] = useState(60.0);
  const [sDt, setSDt] = useState(0.01);
  const [sPdfMethod, setSPdfMethod] = useState('histogram');
  const [sNBins, setSNBins] = useState(50);
  const [sResult, setSResult] = useState<StatsResult | null>(null);
  const [sLoading, setSLoading] = useState(false);

  /* ---- Spectral state ---- */
  const [spFreqs, setSpFreqs] = useState('0.5, 1.2, 3.0');
  const [spAmpls, setSpAmpls] = useState('2.0, 1.0, 0.5');
  const [spNoise, setSpNoise] = useState(0.5);
  const [spDur, setSpDur] = useState(100.0);
  const [spDt, setSpDt] = useState(0.01);
  const [spOutType, setSpOutType] = useState('PSD');
  const [spAvg, setSpAvg] = useState('Welch');
  const [spWin, setSpWin] = useState('hamming');
  const [spResult, setSpResult] = useState<SpectralResult | null>(null);
  const [spLoading, setSpLoading] = useState(false);

  /* ---- Damping state ---- */
  const [dFn, setDFn] = useState(0.1);
  const [dZeta, setDZeta] = useState(0.05);
  const [dAmpl, setDAmpl] = useState(10.0);
  const [dOffset, setDOffset] = useState(5.0);
  const [dDur, setDDur] = useState(200.0);
  const [dDt, setDDt] = useState(0.05);
  const [dResult, setDResult] = useState<DampingResult | null>(null);
  const [dLoading, setDLoading] = useState(false);

  /* ---- Extreme Value (Gumbel) state ---- */
  const [evSigType, setEvSigType] = useState('turbulent_load');
  const [evAmpl, setEvAmpl] = useState(2000.0);
  const [evFreq, setEvFreq] = useState(0.3);
  const [evNoise, setEvNoise] = useState(500.0);
  const [evMean, setEvMean] = useState(3000.0);
  const [evDur, setEvDur] = useState(600.0);
  const [evDt, setEvDt] = useState(0.05);
  const [evNSim, setEvNSim] = useState(6);
  const [evBlockSize, setEvBlockSize] = useState(600.0);
  const [evThreshSigma, setEvThreshSigma] = useState(1.4);
  const [evResult, setEvResult] = useState<EVResult | null>(null);
  const [evLoading, setEvLoading] = useState(false);

  /* ---- IEC Loads state ---- */
  const [iecSimulations, setIecSimulations] = useState<IECSimulationInfo[]>([]);
  const [iecSelectedSimId, setIecSelectedSimId] = useState('');
  const [iecCasesGrouped, setIecCasesGrouped] = useState<IECCasesGrouped[]>([]);
  const [iecSelectedDlcs, setIecSelectedDlcs] = useState<Set<string>>(new Set());
  const [iecTStart, setIecTStart] = useState(30.0);
  const [iecConsFactor, setIecConsFactor] = useState(1.0);
  const [iecResult, setIecResult] = useState<IECLoadsResult | null>(null);
  const [iecLoading, setIecLoading] = useState(false);
  const [iecExcelLoading, setIecExcelLoading] = useState(false);
  const [iecExpandedRows, setIecExpandedRows] = useState<Set<string>>(new Set());

  /* ---- IEC Gumbel state ---- */
  const [gumbelSimId, setGumbelSimId] = useState('');
  const [gumbelCasesGrouped, setGumbelCasesGrouped] = useState<IECCasesGrouped[]>([]);
  const [gumbelSelectedDlcs, setGumbelSelectedDlcs] = useState<Set<string>>(new Set());
  const [gumbelChannels, setGumbelChannels] = useState<string[]>([]);
  const [gumbelSelectedChannel, setGumbelSelectedChannel] = useState('');
  const [gumbelTStart, setGumbelTStart] = useState(30.0);
  const [gumbelBlockSize, setGumbelBlockSize] = useState(600.0);
  const [gumbelThreshSigma, setGumbelThreshSigma] = useState(1.4);
  const [gumbelResult, setGumbelResult] = useState<IECGumbelResult | null>(null);
  const [gumbelLoading, setGumbelLoading] = useState(false);

  const isIecTab = activeTab === 'iec-extreme' || activeTab === 'iec-fatigue' || activeTab === 'iec-statistics';
  const isIecGumbelTab = activeTab === 'iec-gumbel';

  // Fetch simulations when IEC tab is first opened
  useEffect(() => {
    if (!(isIecTab || isIecGumbelTab) || !projectId || iecSimulations.length > 0) return;
    ppGet<IECSimulationInfo[]>(projectId, 'iec-loads/simulations')
      .then(setIecSimulations)
      .catch(() => toast.error('Failed to load simulations'));
  }, [isIecTab, isIecGumbelTab, projectId, iecSimulations.length]);

  // Fetch cases when simulation changes
  useEffect(() => {
    if (!projectId || !iecSelectedSimId) {
      setIecCasesGrouped([]);
      return;
    }
    ppGet<IECCasesGrouped[]>(projectId, `iec-loads/simulations/${iecSelectedSimId}/cases`)
      .then((groups) => {
        setIecCasesGrouped(groups);
        // Auto-select all DLCs
        setIecSelectedDlcs(new Set(groups.map((g) => g.dlc_number)));
      })
      .catch(() => toast.error('Failed to load cases'));
  }, [projectId, iecSelectedSimId]);

  // Fetch cases for Gumbel tab when simulation changes
  useEffect(() => {
    if (!projectId || !gumbelSimId) {
      setGumbelCasesGrouped([]);
      setGumbelChannels([]);
      setGumbelSelectedChannel('');
      return;
    }
    ppGet<IECCasesGrouped[]>(projectId, `iec-loads/simulations/${gumbelSimId}/cases`)
      .then((groups) => {
        setGumbelCasesGrouped(groups);
        // Auto-select DLC 1.1 if available, otherwise all
        const dlc11 = groups.find((g) => g.dlc_number === '1.1');
        setGumbelSelectedDlcs(dlc11 ? new Set(['1.1']) : new Set(groups.map((g) => g.dlc_number)));
      })
      .catch(() => toast.error('Failed to load cases'));
    // Also fetch available channels
    ppGet<{ simulation_id: string; channels: string[] }>(projectId, `iec-gumbel/simulations/${gumbelSimId}/channels`)
      .then((resp) => {
        setGumbelChannels(resp.channels);
        if (resp.channels.length > 0 && !resp.channels.includes(gumbelSelectedChannel)) {
          setGumbelSelectedChannel(resp.channels[0]);
        }
      })
      .catch(() => toast.error('Failed to load channels'));
  }, [projectId, gumbelSimId]);

  const handleIecAnalysis = useCallback(async () => {
    if (!projectId || !iecSelectedSimId) return;
    setIecLoading(true); setError(null); setIecResult(null);
    try {
      const dlcFilter = iecSelectedDlcs.size > 0 ? Array.from(iecSelectedDlcs) : undefined;
      const result = await ppPost<IECLoadsResult>(projectId, 'iec-loads', {
        simulation_id: iecSelectedSimId,
        dlc_filter: dlcFilter,
        t_start: iecTStart,
        consequence_factor: iecConsFactor,
      });
      setIecResult(result);
      toast.success(`IEC analysis complete: ${result.n_cases_analyzed} cases, ${result.channels_analyzed.length} channels`);
    } catch { setError('IEC analysis failed'); toast.error('Failed'); }
    finally { setIecLoading(false); }
  }, [projectId, iecSelectedSimId, iecSelectedDlcs, iecTStart, iecConsFactor]);

  const handleIecExcel = useCallback(async () => {
    if (!projectId || !iecSelectedSimId) return;
    setIecExcelLoading(true);
    const dlcFilter = iecSelectedDlcs.size > 0 ? Array.from(iecSelectedDlcs) : undefined;
    ppDownload(projectId, 'iec-loads/excel', {
      simulation_id: iecSelectedSimId,
      dlc_filter: dlcFilter,
      t_start: iecTStart,
      consequence_factor: iecConsFactor,
    }, `IEC_Loads_${new Date().toISOString().slice(0, 10)}.xlsx`);
    setIecExcelLoading(false);
  }, [projectId, iecSelectedSimId, iecSelectedDlcs, iecTStart, iecConsFactor]);

  const handleIecGumbel = useCallback(async () => {
    if (!projectId || !gumbelSimId || !gumbelSelectedChannel) return;
    setGumbelLoading(true); setError(null); setGumbelResult(null);
    try {
      const dlcFilter = gumbelSelectedDlcs.size > 0 ? Array.from(gumbelSelectedDlcs) : undefined;
      const result = await ppPost<IECGumbelResult>(projectId, 'iec-gumbel', {
        simulation_id: gumbelSimId,
        channel: gumbelSelectedChannel,
        dlc_filter: dlcFilter,
        t_start: gumbelTStart,
        block_size: gumbelBlockSize,
        threshold_sigma: gumbelThreshSigma,
      });
      setGumbelResult(result);
      toast.success(`Gumbel fit: ${result.n_blocks} block maxima from ${result.n_cases} cases`);
    } catch { setError('IEC Gumbel analysis failed'); toast.error('Failed'); }
    finally { setGumbelLoading(false); }
  }, [projectId, gumbelSimId, gumbelSelectedChannel, gumbelSelectedDlcs, gumbelTStart, gumbelBlockSize, gumbelThreshSigma]);

  const toggleGumbelDlc = useCallback((dlc: string) => {
    setGumbelSelectedDlcs((prev) => {
      const next = new Set(prev);
      if (next.has(dlc)) next.delete(dlc); else next.add(dlc);
      return next;
    });
  }, []);

  const toggleDlc = useCallback((dlc: string) => {
    setIecSelectedDlcs((prev) => {
      const next = new Set(prev);
      if (next.has(dlc)) next.delete(dlc); else next.add(dlc);
      return next;
    });
  }, []);

  const toggleExpandRow = useCallback((key: string) => {
    setIecExpandedRows((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key); else next.add(key);
      return next;
    });
  }, []);

  /* ---- handlers ---- */
  const handleFatigue = useCallback(async () => {
    if (!projectId) return;
    setFLoading(true); setError(null); setFResult(null);
    try {
      setFResult(await ppPost<DelResult>(projectId, 'del-fatigue', {
        signal_type: fSigType, amplitude: fAmpl, frequency: fFreq, noise_std: fNoise,
        mean_load: fMean, duration: fDur, dt: fDt, n_bins: fBins, rainflow_method: fRfMethod,
      }));
      toast.success('DEL & Fatigue computed');
    } catch { setError('DEL computation failed'); toast.error('Failed'); }
    finally { setFLoading(false); }
  }, [projectId, fSigType, fAmpl, fFreq, fNoise, fMean, fDur, fDt, fBins, fRfMethod]);

  const handleStats = useCallback(async () => {
    if (!projectId) return;
    setSLoading(true); setError(null); setSResult(null);
    try {
      setSResult(await ppPost<StatsResult>(projectId, 'statistics', {
        signal_type: sSigType, amplitude: sAmpl, frequency: sFreq, noise_std: sNoise,
        mean_val: sMean, duration: sDur, dt: sDt, pdf_method: sPdfMethod, n_bins: sNBins,
      }));
      toast.success('Statistics computed');
    } catch { setError('Statistics failed'); toast.error('Failed'); }
    finally { setSLoading(false); }
  }, [projectId, sSigType, sAmpl, sFreq, sNoise, sMean, sDur, sDt, sPdfMethod, sNBins]);

  const handleSpectral = useCallback(async () => {
    if (!projectId) return;
    setSpLoading(true); setError(null); setSpResult(null);
    try {
      const freqs = spFreqs.split(',').map(Number);
      const ampls = spAmpls.split(',').map(Number);
      setSpResult(await ppPost<SpectralResult>(projectId, 'spectral', {
        frequencies: freqs, amplitudes: ampls, noise_std: spNoise,
        duration: spDur, dt: spDt, output_type: spOutType, averaging: spAvg, averaging_window: spWin,
      }));
      toast.success('Spectral analysis computed');
    } catch { setError('Spectral failed'); toast.error('Failed'); }
    finally { setSpLoading(false); }
  }, [projectId, spFreqs, spAmpls, spNoise, spDur, spDt, spOutType, spAvg, spWin]);

  const handleDamping = useCallback(async () => {
    if (!projectId) return;
    setDLoading(true); setError(null); setDResult(null);
    try {
      setDResult(await ppPost<DampingResult>(projectId, 'damping', {
        natural_freq: dFn, damping_ratio: dZeta, amplitude: dAmpl,
        mean_offset: dOffset, duration: dDur, dt: dDt,
      }));
      toast.success('Damping estimated');
    } catch { setError('Damping estimation failed'); toast.error('Failed'); }
    finally { setDLoading(false); }
  }, [projectId, dFn, dZeta, dAmpl, dOffset, dDur, dDt]);

  const handleExtremeValue = useCallback(async () => {
    if (!projectId) return;
    setEvLoading(true); setError(null); setEvResult(null);
    try {
      setEvResult(await ppPost<EVResult>(projectId, 'extreme-value', {
        signal_type: evSigType, amplitude: evAmpl, frequency: evFreq, noise_std: evNoise,
        mean_load: evMean, duration: evDur, dt: evDt, n_simulations: evNSim,
        block_size: evBlockSize, threshold_sigma: evThreshSigma,
      }));
      toast.success('Gumbel extrapolation computed');
    } catch { setError('Extreme value extrapolation failed'); toast.error('Failed'); }
    finally { setEvLoading(false); }
  }, [projectId, evSigType, evAmpl, evFreq, evNoise, evMean, evDur, evDt, evNSim, evBlockSize, evThreshSigma]);

  /* ---- plot memos ---- */
  const fatigueSignalTrace = useMemo(() => fResult ? [
    { x: fResult.time, y: fResult.signal, type: 'scatter' as const, mode: 'lines' as const, name: 'Load signal', line: { color: '#22d3ee', width: 1 } },
  ] : [], [fResult]);

  const rainflowTrace = useMemo(() => fResult ? [
    { x: fResult.rainflow_ranges, y: fResult.rainflow_counts, type: 'bar' as const, name: 'Cycle counts', marker: { color: '#a78bfa' } },
  ] : [], [fResult]);

  const markovTrace = useMemo(() => {
    if (!fResult || !fResult.markov_cycles.length) return [];
    return [{
      z: fResult.markov_cycles,
      x: fResult.markov_mean_edges,
      y: fResult.markov_ampl_edges,
      type: 'heatmap' as const,
      colorscale: 'Viridis',
      colorbar: { title: 'Cycles', titlefont: { color: '#9ca3af' }, tickfont: { color: '#9ca3af' } },
    }];
  }, [fResult]);

  const statsSignalTrace = useMemo(() => sResult ? [
    { x: sResult.time, y: sResult.signal, type: 'scatter' as const, mode: 'lines' as const, name: 'Signal', line: { color: '#22d3ee', width: 1 } },
  ] : [], [sResult]);

  const pdfTrace = useMemo(() => sResult ? [
    { x: sResult.pdf_x, y: sResult.pdf_y, type: 'scatter' as const, mode: 'lines' as const, name: 'PDF', line: { color: '#f472b6', width: 2 }, fill: 'tozeroy' as const, fillcolor: 'rgba(244,114,182,0.15)' },
  ] : [], [sResult]);

  const spectralTimeTrace = useMemo(() => spResult ? [
    { x: spResult.time, y: spResult.signal, type: 'scatter' as const, mode: 'lines' as const, name: 'Signal', line: { color: '#22d3ee', width: 1 } },
  ] : [], [spResult]);

  const spectralFreqTrace = useMemo(() => spResult ? [
    { x: spResult.freq, y: spResult.spectrum, type: 'scatter' as const, mode: 'lines' as const, name: spResult.output_type, line: { color: '#fbbf24', width: 2 } },
  ] : [], [spResult]);

  const dampingTraces = useMemo(() => {
    if (!dResult) return [];
    return [
      { x: dResult.time, y: dResult.signal, type: 'scatter' as const, mode: 'lines' as const, name: 'Signal', line: { color: '#22d3ee', width: 1 } },
      { x: dResult.time, y: dResult.x_model, type: 'scatter' as const, mode: 'lines' as const, name: 'Model fit', line: { color: '#fbbf24', width: 1, dash: 'dot' as const } },
      { x: dResult.time, y: dResult.epos, type: 'scatter' as const, mode: 'lines' as const, name: 'Envelope +', line: { color: '#f87171', width: 2, dash: 'dash' as const } },
      { x: dResult.time, y: dResult.eneg, type: 'scatter' as const, mode: 'lines' as const, name: 'Envelope -', line: { color: '#f87171', width: 2, dash: 'dash' as const }, showlegend: false },
      { x: dResult.peaks_pos_t, y: dResult.peaks_pos_x, type: 'scatter' as const, mode: 'markers' as const, name: 'Peaks +', marker: { color: '#34d399', size: 6 } },
      { x: dResult.peaks_neg_t, y: dResult.peaks_neg_x, type: 'scatter' as const, mode: 'markers' as const, name: 'Peaks -', marker: { color: '#a78bfa', size: 6 } },
    ];
  }, [dResult]);

  /* Extreme Value traces */
  const evSignalTrace = useMemo(() => {
    if (!evResult) return [];
    const traces: Plotly.Data[] = [
      { x: evResult.time, y: evResult.signal, type: 'scatter', mode: 'lines', name: 'Last simulation', line: { color: '#22d3ee', width: 1 } } as Plotly.Data,
    ];
    if (evResult.pot_peaks_t.length > 0) {
      traces.push({ x: evResult.pot_peaks_t, y: evResult.pot_peaks_x, type: 'scatter', mode: 'markers', name: 'Peaks over threshold', marker: { color: '#f87171', size: 7, symbol: 'diamond' } } as Plotly.Data);
    }
    // Threshold line
    const tMin = evResult.time[0] ?? 0;
    const tMax = evResult.time[evResult.time.length - 1] ?? 1;
    traces.push({ x: [tMin, tMax], y: [evResult.pot_threshold, evResult.pot_threshold], type: 'scatter', mode: 'lines', name: `Threshold (${evResult.pot_threshold.toFixed(0)})`, line: { color: '#fbbf24', width: 2, dash: 'dash' } } as Plotly.Data);
    return traces;
  }, [evResult]);

  const evGumbelPlotTrace = useMemo(() => {
    if (!evResult) return [];
    return [
      { x: evResult.prob_plot_x, y: evResult.prob_plot_y, type: 'scatter', mode: 'markers', name: 'Block maxima', marker: { color: '#22d3ee', size: 8 } } as Plotly.Data,
      { x: evResult.prob_plot_fit_x, y: evResult.prob_plot_fit_y, type: 'scatter', mode: 'lines', name: 'Gumbel fit', line: { color: '#f472b6', width: 2 } } as Plotly.Data,
    ];
  }, [evResult]);

  const evReturnPeriodTrace = useMemo(() => {
    if (!evResult || !Object.keys(evResult.extrapolated_loads).length) return [];
    const rps = evResult.return_periods;
    const loads = rps.map((k) => evResult.extrapolated_loads[k]);
    const lower = rps.map((k) => evResult.confidence_95_lower[k]);
    const upper = rps.map((k) => evResult.confidence_95_upper[k]);
    const rpNums = rps.map((k) => parseFloat(k.replace('T=', '')));
    return [
      { x: rpNums, y: upper, type: 'scatter', mode: 'lines', name: '95% CI upper', line: { color: 'rgba(244,114,182,0.3)', width: 0 }, showlegend: false } as Plotly.Data,
      { x: rpNums, y: lower, type: 'scatter', mode: 'lines', name: '95% CI', line: { color: 'rgba(244,114,182,0.3)', width: 0 }, fill: 'tonexty', fillcolor: 'rgba(244,114,182,0.15)' } as Plotly.Data,
      { x: rpNums, y: loads, type: 'scatter', mode: 'lines+markers', name: 'Extrapolated load', line: { color: '#f472b6', width: 2 }, marker: { size: 7 } } as Plotly.Data,
    ];
  }, [evResult]);

  /* IEC Gumbel traces */
  const iecGumbelSignalTrace = useMemo(() => {
    if (!gumbelResult || !gumbelResult.time.length) return [];
    return [
      { x: gumbelResult.time, y: gumbelResult.signal, type: 'scatter', mode: 'lines', name: `${gumbelResult.channel} (last case)`, line: { color: '#22d3ee', width: 1 } } as Plotly.Data,
    ];
  }, [gumbelResult]);

  const iecGumbelProbPlotTrace = useMemo(() => {
    if (!gumbelResult || !gumbelResult.prob_plot_x.length) return [];
    return [
      { x: gumbelResult.prob_plot_x, y: gumbelResult.prob_plot_y, type: 'scatter', mode: 'markers', name: 'Block maxima', marker: { color: '#fbbf24', size: 8, symbol: 'diamond' } } as Plotly.Data,
      { x: gumbelResult.prob_plot_fit_x, y: gumbelResult.prob_plot_fit_y, type: 'scatter', mode: 'lines', name: 'Gumbel fit', line: { color: '#f472b6', width: 2 } } as Plotly.Data,
    ];
  }, [gumbelResult]);

  const iecGumbelReturnTrace = useMemo(() => {
    if (!gumbelResult || !Object.keys(gumbelResult.extrapolated_loads).length) return [];
    const rps = gumbelResult.return_periods;
    const loads = rps.map((k) => gumbelResult.extrapolated_loads[k]);
    const lower = rps.map((k) => gumbelResult.confidence_95_lower[k]);
    const upper = rps.map((k) => gumbelResult.confidence_95_upper[k]);
    const rpNums = rps.map((k) => parseFloat(k.replace('T=', '')));
    return [
      { x: rpNums, y: upper, type: 'scatter', mode: 'lines', name: '95% CI upper', line: { color: 'rgba(251,191,36,0.3)', width: 0 }, showlegend: false } as Plotly.Data,
      { x: rpNums, y: lower, type: 'scatter', mode: 'lines', name: '95% CI', line: { color: 'rgba(251,191,36,0.3)', width: 0 }, fill: 'tonexty', fillcolor: 'rgba(251,191,36,0.15)' } as Plotly.Data,
      { x: rpNums, y: loads, type: 'scatter', mode: 'lines+markers', name: 'Extrapolated', line: { color: '#fbbf24', width: 2 }, marker: { size: 7 } } as Plotly.Data,
    ];
  }, [gumbelResult]);

  const loading = activeTab === 'fatigue' ? fLoading : activeTab === 'statistics' ? sLoading : activeTab === 'spectral' ? spLoading : activeTab === 'damping' ? dLoading : activeTab === 'extremevalue' ? evLoading : activeTab === 'iec-gumbel' ? gumbelLoading : iecLoading;
  const handleCompute = activeTab === 'fatigue' ? handleFatigue : activeTab === 'statistics' ? handleStats : activeTab === 'spectral' ? handleSpectral : activeTab === 'damping' ? handleDamping : activeTab === 'extremevalue' ? handleExtremeValue : handleIecAnalysis;

  return (
    <div className="h-full flex flex-col">
      {/* Sub-tab bar */}
      <div className="flex items-center gap-1 border-b border-slate-700/50 px-4 py-2 bg-slate-900/30">
        {TABS.map((tab, idx) => {
          const Icon = tab.icon;
          const active = activeTab === tab.key;
          return (
            <span key={tab.key} className="flex items-center">
              {idx === 5 && <span className="mx-2 h-5 border-l border-slate-600/60" />}
              <button onClick={() => setActiveTab(tab.key)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${active ? (idx >= 5 ? 'bg-amber-500/20 text-amber-400 ring-1 ring-amber-500/30' : 'bg-accent-500/20 text-accent-400 ring-1 ring-accent-500/30') : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'}`}>
                <Icon className="w-3.5 h-3.5" />{tab.label}
              </button>
            </span>
          );
        })}
      </div>

      {/* Main content */}
      <div className="flex-1 overflow-auto p-4">
        <div className="grid grid-cols-1 xl:grid-cols-4 gap-4">

          {/* -------- Left: Parameters -------- */}
          <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-700/40 space-y-3 max-h-[calc(100vh-180px)] overflow-y-auto">
            <h3 className="text-sm font-semibold text-slate-200 mb-2">Parameters</h3>
            <p className="text-[10px] text-slate-500 leading-tight mb-2">
              {activeTab === 'fatigue' && 'Compute DEL (Damage Equivalent Load) and Markov cycle matrix using openfast_toolbox rainflow counting. Reference: NREL/TP-500-34421.'}
              {activeTab === 'statistics' && 'Compute PDF and basic statistics using openfast_toolbox stats module.'}
              {activeTab === 'spectral' && 'Compute FFT/PSD using openfast_toolbox spectral module with Welch averaging.'}
              {activeTab === 'damping' && 'Estimate natural frequency and damping ratio from a decaying signal using openfast_toolbox peak detection.'}
              {activeTab === 'extremevalue' && 'Extreme value extrapolation using Gumbel (EV1) distribution. Based on NREL/CP-500-25787 and NREL/TP-500-34421. Generates N simulations, extracts block maxima, fits Gumbel, and extrapolates to target return periods with 95% confidence bounds.'}
              {isIecGumbelTab && 'IEC Gumbel (EV1) extrapolation from real simulation outputs. Select DLC cases (typically DLC 1.1), choose a channel, and extract block maxima across seeds for Gumbel fitting and return period extrapolation per NREL/CP-500-25787.'}
            </p>

            {activeTab === 'fatigue' && <>
              <SelectInput label="Signal Type" value={fSigType} onChange={setFSigType} options={[{ value: 'sine_noise', label: 'Sine + Noise' }, { value: 'random_walk', label: 'Random Walk' }]} />
              <NumberInput label="Amplitude" value={fAmpl} onChange={setFAmpl} step={100} min={0} unit="N" />
              <NumberInput label="Frequency" value={fFreq} onChange={setFFreq} step={0.1} min={0.01} unit="Hz" />
              <NumberInput label="Noise Std" value={fNoise} onChange={setFNoise} step={50} min={0} unit="N" />
              <NumberInput label="Mean Load" value={fMean} onChange={setFMean} step={100} unit="N" />
              <NumberInput label="Duration" value={fDur} onChange={setFDur} step={60} min={10} max={3600} unit="s" />
              <NumberInput label="Time Step" value={fDt} onChange={setFDt} step={0.01} min={0.001} max={1} unit="s" />
              <NumberInput label="Bins" value={fBins} onChange={setFBins} step={1} min={10} max={200} />
              <SelectInput label="Rainflow Method" value={fRfMethod} onChange={setFRfMethod} options={[{ value: 'windap', label: 'WindAP (IEC)' }, { value: 'astm', label: 'ASTM E1049' }]} />
            </>}

            {activeTab === 'statistics' && <>
              <SelectInput label="Signal Type" value={sSigType} onChange={setSSigType} options={[{ value: 'sine_noise', label: 'Sine + Noise' }, { value: 'gaussian', label: 'Gaussian' }, { value: 'uniform', label: 'Uniform' }]} />
              <NumberInput label="Amplitude" value={sAmpl} onChange={setSAmpl} step={1} min={0} />
              <NumberInput label="Frequency" value={sFreq} onChange={setSFreq} step={0.1} min={0.01} unit="Hz" />
              <NumberInput label="Noise Std" value={sNoise} onChange={setSNoise} step={0.5} min={0} />
              <NumberInput label="Mean" value={sMean} onChange={setSMean} step={1} />
              <NumberInput label="Duration" value={sDur} onChange={setSDur} step={10} min={1} max={600} unit="s" />
              <NumberInput label="Time Step" value={sDt} onChange={setSDt} step={0.001} min={0.001} max={1} unit="s" />
              <SelectInput label="PDF Method" value={sPdfMethod} onChange={setSPdfMethod} options={[{ value: 'histogram', label: 'Histogram' }, { value: 'gaussian_kde', label: 'Gaussian KDE' }]} />
              <NumberInput label="Bins" value={sNBins} onChange={setSNBins} step={10} min={10} max={500} />
            </>}

            {activeTab === 'spectral' && <>
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Frequencies <span className="text-slate-500">(Hz, comma-sep)</span></label>
                <input type="text" value={spFreqs} onChange={(e) => setSpFreqs(e.target.value)}
                  className="bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-sm text-slate-100 w-full focus:ring-1 focus:ring-accent-500 focus:border-accent-500" />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Amplitudes <span className="text-slate-500">(comma-sep)</span></label>
                <input type="text" value={spAmpls} onChange={(e) => setSpAmpls(e.target.value)}
                  className="bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-sm text-slate-100 w-full focus:ring-1 focus:ring-accent-500 focus:border-accent-500" />
              </div>
              <NumberInput label="Noise Std" value={spNoise} onChange={setSpNoise} step={0.1} min={0} />
              <NumberInput label="Duration" value={spDur} onChange={setSpDur} step={10} min={1} max={1000} unit="s" />
              <NumberInput label="Time Step" value={spDt} onChange={setSpDt} step={0.001} min={0.001} max={1} unit="s" />
              <SelectInput label="Output" value={spOutType} onChange={setSpOutType} options={[{ value: 'PSD', label: 'PSD' }, { value: 'amplitude', label: 'Amplitude' }, { value: 'f x PSD', label: 'f x PSD' }]} />
              <SelectInput label="Averaging" value={spAvg} onChange={setSpAvg} options={[{ value: 'Welch', label: 'Welch' }, { value: 'None', label: 'None' }, { value: 'Binning', label: 'Binning' }]} />
              <SelectInput label="Window" value={spWin} onChange={setSpWin} options={[{ value: 'hamming', label: 'Hamming' }, { value: 'hann', label: 'Hann' }, { value: 'rectangular', label: 'Rectangular' }]} />
            </>}

            {activeTab === 'damping' && <>
              <NumberInput label="Natural Frequency" value={dFn} onChange={setDFn} step={0.01} min={0.001} max={10} unit="Hz" />
              <NumberInput label="Damping Ratio" value={dZeta} onChange={setDZeta} step={0.01} min={0.001} max={0.99} unit="zeta" />
              <NumberInput label="Amplitude" value={dAmpl} onChange={setDAmpl} step={1} min={0.1} />
              <NumberInput label="Mean Offset" value={dOffset} onChange={setDOffset} step={1} />
              <NumberInput label="Duration" value={dDur} onChange={setDDur} step={10} min={10} max={1000} unit="s" />
              <NumberInput label="Time Step" value={dDt} onChange={setDDt} step={0.01} min={0.001} max={1} unit="s" />
            </>}

            {activeTab === 'extremevalue' && <>
              <SelectInput label="Signal Type" value={evSigType} onChange={setEvSigType} options={[{ value: 'turbulent_load', label: 'Turbulent + Gusts' }, { value: 'weibull_process', label: 'Weibull Process' }]} />
              <NumberInput label="Amplitude" value={evAmpl} onChange={setEvAmpl} step={200} min={0} unit="N" />
              <NumberInput label="Frequency" value={evFreq} onChange={setEvFreq} step={0.1} min={0.01} unit="Hz" />
              <NumberInput label="Noise Std" value={evNoise} onChange={setEvNoise} step={100} min={0} unit="N" />
              <NumberInput label="Mean Load" value={evMean} onChange={setEvMean} step={500} unit="N" />
              <NumberInput label="Duration/sim" value={evDur} onChange={setEvDur} step={60} min={60} max={3600} unit="s" />
              <NumberInput label="Time Step" value={evDt} onChange={setEvDt} step={0.01} min={0.001} max={1} unit="s" />
              <NumberInput label="N Simulations" value={evNSim} onChange={setEvNSim} step={1} min={2} max={100} />
              <NumberInput label="Block Size" value={evBlockSize} onChange={setEvBlockSize} step={60} min={10} max={3600} unit="s" />
              <NumberInput label="Threshold (\u03C3)" value={evThreshSigma} onChange={setEvThreshSigma} step={0.1} min={0.5} max={5} />
            </>}

            {/* ===== IEC Loads Parameters ===== */}
            {isIecTab && <>
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Simulation</label>
                <select value={iecSelectedSimId} onChange={(e) => setIecSelectedSimId(e.target.value)}
                  className="bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-sm text-slate-100 w-full focus:ring-1 focus:ring-amber-500 focus:border-amber-500">
                  <option value="">Select simulation...</option>
                  {iecSimulations.map((sim) => (
                    <option key={sim.id} value={sim.id}>
                      {sim.name} ({sim.completed_cases}/{sim.total_cases} cases)
                    </option>
                  ))}
                </select>
              </div>

              {iecCasesGrouped.length > 0 && (
                <div>
                  <label className="block text-xs font-medium text-slate-400 mb-1">DLC Selection</label>
                  <div className="space-y-1 max-h-40 overflow-y-auto bg-slate-900/40 rounded-lg p-2 border border-slate-700/40">
                    {iecCasesGrouped.map((group) => (
                      <button key={group.dlc_number} onClick={() => toggleDlc(group.dlc_number)}
                        className={`flex items-center gap-2 w-full text-left px-2 py-1 rounded text-xs transition-colors ${iecSelectedDlcs.has(group.dlc_number) ? 'bg-amber-500/15 text-amber-300' : 'text-slate-400 hover:text-slate-200'}`}>
                        {iecSelectedDlcs.has(group.dlc_number) ? <CheckSquare className="w-3.5 h-3.5 text-amber-400" /> : <Square className="w-3.5 h-3.5" />}
                        <span className="font-mono">DLC {group.dlc_number}</span>
                        <span className="text-slate-500 ml-auto">{group.completed_cases}/{group.total_cases}</span>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              <NumberInput label="Transient Skip" value={iecTStart} onChange={setIecTStart} step={5} min={0} max={120} unit="s" />
              <NumberInput label="Consequence Factor" value={iecConsFactor} onChange={setIecConsFactor} step={0.05} min={1.0} max={1.3} />
            </>}

            {/* ===== IEC Gumbel Parameters ===== */}
            {isIecGumbelTab && <>
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Simulation</label>
                <select value={gumbelSimId} onChange={(e) => setGumbelSimId(e.target.value)}
                  className="bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-sm text-slate-100 w-full focus:ring-1 focus:ring-amber-500 focus:border-amber-500">
                  <option value="">Select simulation...</option>
                  {iecSimulations.map((sim) => (
                    <option key={sim.id} value={sim.id}>
                      {sim.name} ({sim.completed_cases}/{sim.total_cases} cases)
                    </option>
                  ))}
                </select>
              </div>

              {gumbelCasesGrouped.length > 0 && (
                <div>
                  <label className="block text-xs font-medium text-slate-400 mb-1">DLC Selection</label>
                  <div className="space-y-1 max-h-40 overflow-y-auto bg-slate-900/40 rounded-lg p-2 border border-slate-700/40">
                    {gumbelCasesGrouped.map((group) => (
                      <button key={group.dlc_number} onClick={() => toggleGumbelDlc(group.dlc_number)}
                        className={`flex items-center gap-2 w-full text-left px-2 py-1 rounded text-xs transition-colors ${gumbelSelectedDlcs.has(group.dlc_number) ? 'bg-amber-500/15 text-amber-300' : 'text-slate-400 hover:text-slate-200'}`}>
                        {gumbelSelectedDlcs.has(group.dlc_number) ? <CheckSquare className="w-3.5 h-3.5 text-amber-400" /> : <Square className="w-3.5 h-3.5" />}
                        <span className="font-mono">DLC {group.dlc_number}</span>
                        <span className="text-slate-500 ml-auto">{group.completed_cases}/{group.total_cases}</span>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {gumbelChannels.length > 0 && (
                <div>
                  <label className="block text-xs font-medium text-slate-400 mb-1">Channel</label>
                  <select value={gumbelSelectedChannel} onChange={(e) => setGumbelSelectedChannel(e.target.value)}
                    className="bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-sm text-slate-100 w-full focus:ring-1 focus:ring-amber-500 focus:border-amber-500">
                    {gumbelChannels.map((ch) => (
                      <option key={ch} value={ch}>{ch}</option>
                    ))}
                  </select>
                </div>
              )}

              <NumberInput label="Transient Skip" value={gumbelTStart} onChange={setGumbelTStart} step={5} min={0} max={120} unit="s" />
              <NumberInput label="Block Size" value={gumbelBlockSize} onChange={setGumbelBlockSize} step={60} min={10} max={3600} unit="s" />
              <NumberInput label="POT Threshold" value={gumbelThreshSigma} onChange={setGumbelThreshSigma} step={0.1} min={0.5} max={5.0} unit={"\u03C3"} />

              <button onClick={handleIecGumbel} disabled={gumbelLoading || !gumbelSimId || !gumbelSelectedChannel}
                className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-amber-600 hover:bg-amber-500 disabled:bg-slate-700 rounded-lg text-sm font-medium text-white transition-colors mt-3">
                {gumbelLoading ? <><Loader2 className="w-4 h-4 animate-spin" />Fitting Gumbel...</> : <><Zap className="w-4 h-4" />Run Gumbel Analysis</>}
              </button>
            </>}

            {/* Compute / Run buttons */}
            {!isIecTab && !isIecGumbelTab && (
              <button onClick={handleCompute} disabled={loading}
                className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-accent-600 hover:bg-accent-500 disabled:bg-slate-700 rounded-lg text-sm font-medium text-white transition-colors mt-3">
                {loading ? <><Loader2 className="w-4 h-4 animate-spin" />Computing...</> : 'Compute'}
              </button>
            )}

            {isIecTab && (
              <div className="space-y-2 mt-3">
                <button onClick={handleIecAnalysis} disabled={iecLoading || !iecSelectedSimId}
                  className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-amber-600 hover:bg-amber-500 disabled:bg-slate-700 rounded-lg text-sm font-medium text-white transition-colors">
                  {iecLoading ? <><Loader2 className="w-4 h-4 animate-spin" />Analyzing...</> : <><AlertTriangle className="w-4 h-4" />Run IEC Analysis</>}
                </button>
                <button onClick={handleIecExcel} disabled={iecExcelLoading || !iecSelectedSimId}
                  className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-green-700 hover:bg-green-600 disabled:bg-slate-700 rounded-lg text-sm font-medium text-white transition-colors">
                  {iecExcelLoading ? <><Loader2 className="w-4 h-4 animate-spin" />Generating...</> : <><Download className="w-4 h-4" />Download Excel</>}
                </button>
              </div>
            )}

            {error && <p className="text-xs text-red-400 mt-1">{error}</p>}

            {/* DEL results summary */}
            {activeTab === 'fatigue' && fResult && Object.keys(fResult.del_values).length > 0 && (
              <div className="mt-3 p-3 bg-slate-900/60 rounded-lg border border-slate-700/40">
                <h4 className="text-xs font-semibold text-slate-300 mb-2">Damage Equivalent Loads</h4>
                <div className="space-y-1">
                  {Object.entries(fResult.del_values).map(([k, v]) => (
                    <div key={k} className="flex justify-between text-xs">
                      <span className="text-slate-400">{k}</span>
                      <span className="text-accent-400 font-mono">{isNaN(v) ? 'N/A' : v.toFixed(2)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Stats results summary */}
            {activeTab === 'statistics' && sResult && (
              <div className="mt-3 p-3 bg-slate-900/60 rounded-lg border border-slate-700/40">
                <h4 className="text-xs font-semibold text-slate-300 mb-2">Statistics Summary</h4>
                <div className="space-y-1">
                  {Object.entries(sResult.stats).map(([k, v]) => (
                    <div key={k} className="flex justify-between text-xs">
                      <span className="text-slate-400 capitalize">{k}</span>
                      <span className="text-accent-400 font-mono">{v.toFixed(4)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Damping estimation results */}
            {activeTab === 'damping' && dResult && (
              <div className="mt-3 p-3 bg-slate-900/60 rounded-lg border border-slate-700/40">
                <h4 className="text-xs font-semibold text-slate-300 mb-2">Estimation Results</h4>
                <div className="space-y-1">
                  <div className="flex justify-between text-xs">
                    <span className="text-slate-400">f_n (true)</span>
                    <span className="text-slate-300 font-mono">{dResult.input_params.fn_true.toFixed(4)} Hz</span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span className="text-slate-400">f_n (est.)</span>
                    <span className="text-accent-400 font-mono">{dResult.estimated.fn.toFixed(4)} Hz</span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span className="text-slate-400">zeta (true)</span>
                    <span className="text-slate-300 font-mono">{dResult.input_params.zeta_true.toFixed(4)}</span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span className="text-slate-400">zeta (est.)</span>
                    <span className="text-accent-400 font-mono">{dResult.estimated.zeta.toFixed(4)}</span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span className="text-slate-400">zeta range</span>
                    <span className="text-slate-500 font-mono">[{dResult.estimated.zetaMin.toFixed(4)}, {dResult.estimated.zetaMax.toFixed(4)}]</span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span className="text-slate-400">f_n error</span>
                    <span className={`font-mono ${Math.abs(dResult.estimated.fn - dResult.input_params.fn_true) / dResult.input_params.fn_true < 0.01 ? 'text-green-400' : Math.abs(dResult.estimated.fn - dResult.input_params.fn_true) / dResult.input_params.fn_true < 0.05 ? 'text-amber-400' : 'text-red-400'}`}>
                      {(Math.abs(dResult.estimated.fn - dResult.input_params.fn_true) / dResult.input_params.fn_true * 100).toFixed(2)}%
                    </span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span className="text-slate-400">zeta error</span>
                    <span className={`font-mono ${Math.abs(dResult.estimated.zeta - dResult.input_params.zeta_true) / dResult.input_params.zeta_true < 0.01 ? 'text-green-400' : Math.abs(dResult.estimated.zeta - dResult.input_params.zeta_true) / dResult.input_params.zeta_true < 0.05 ? 'text-amber-400' : 'text-red-400'}`}>
                      {(Math.abs(dResult.estimated.zeta - dResult.input_params.zeta_true) / dResult.input_params.zeta_true * 100).toFixed(2)}%
                    </span>
                  </div>
                </div>
              </div>
            )}

            {/* Gumbel extrapolation results */}
            {activeTab === 'extremevalue' && evResult && Object.keys(evResult.extrapolated_loads).length > 0 && (
              <div className="mt-3 p-3 bg-slate-900/60 rounded-lg border border-slate-700/40">
                <h4 className="text-xs font-semibold text-slate-300 mb-2">Gumbel EV1 Parameters</h4>
                <div className="space-y-1 mb-3">
                  <div className="flex justify-between text-xs">
                    <span className="text-slate-400">&alpha; (scale)</span>
                    <span className="text-accent-400 font-mono">{evResult.gumbel_params.alpha.toFixed(6)}</span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span className="text-slate-400">&beta; (location)</span>
                    <span className="text-accent-400 font-mono">{evResult.gumbel_params.beta.toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span className="text-slate-400">&mu; extremes</span>
                    <span className="text-slate-300 font-mono">{evResult.gumbel_params.mu.toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span className="text-slate-400">&sigma; extremes</span>
                    <span className="text-slate-300 font-mono">{evResult.gumbel_params.sigma.toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span className="text-slate-400">N extremes</span>
                    <span className="text-slate-300 font-mono">{evResult.gumbel_params.n_extremes}</span>
                  </div>
                </div>
                <h4 className="text-xs font-semibold text-slate-300 mb-2">Extrapolated Loads</h4>
                <div className="space-y-1">
                  {Object.entries(evResult.extrapolated_loads).map(([k, v]) => (
                    <div key={k} className="flex justify-between text-xs">
                      <span className="text-slate-400">{k}</span>
                      <span className="text-accent-400 font-mono">{v.toFixed(1)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* IEC Gumbel results summary */}
            {isIecGumbelTab && gumbelResult && gumbelResult.n_blocks > 0 && (
              <div className="mt-3 p-3 bg-slate-900/60 rounded-lg border border-amber-700/30">
                <h4 className="text-xs font-semibold text-amber-300 mb-2">Gumbel EV1 Parameters</h4>
                <div className="space-y-1 mb-3">
                  <div className="flex justify-between text-xs">
                    <span className="text-slate-400">Channel</span>
                    <span className="text-amber-400 font-mono text-[10px]">{gumbelResult.channel}</span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span className="text-slate-400">&alpha; (scale)</span>
                    <span className="text-amber-300 font-mono">{gumbelResult.gumbel_params.alpha.toFixed(6)}</span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span className="text-slate-400">&beta; (location)</span>
                    <span className="text-amber-300 font-mono">{gumbelResult.gumbel_params.beta.toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span className="text-slate-400">&mu; extremes</span>
                    <span className="text-slate-300 font-mono">{gumbelResult.gumbel_params.mu.toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span className="text-slate-400">&sigma; extremes</span>
                    <span className="text-slate-300 font-mono">{gumbelResult.gumbel_params.sigma.toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span className="text-slate-400">N blocks</span>
                    <span className="text-slate-300 font-mono">{gumbelResult.n_blocks}</span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span className="text-slate-400">N cases</span>
                    <span className="text-slate-300 font-mono">{gumbelResult.n_cases}</span>
                  </div>
                </div>
                <h4 className="text-xs font-semibold text-amber-300 mb-2">Extrapolated Loads</h4>
                <div className="space-y-1">
                  {Object.entries(gumbelResult.extrapolated_loads).map(([k, v]) => (
                    <div key={k} className="flex justify-between text-xs">
                      <span className="text-slate-400">{k}</span>
                      <span className="text-amber-400 font-mono">{v.toFixed(1)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* IEC analysis summary */}
            {isIecTab && iecResult && (
              <div className="mt-3 p-3 bg-slate-900/60 rounded-lg border border-amber-700/30">
                <h4 className="text-xs font-semibold text-amber-300 mb-2">IEC Analysis Summary</h4>
                <div className="space-y-1">
                  <div className="flex justify-between text-xs">
                    <span className="text-slate-400">Simulation</span>
                    <span className="text-slate-200 font-mono text-[10px]">{iecResult.simulation_name}</span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span className="text-slate-400">Cases</span>
                    <span className="text-amber-400 font-mono">{iecResult.n_cases_analyzed}</span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span className="text-slate-400">Channels</span>
                    <span className="text-amber-400 font-mono">{iecResult.channels_analyzed.length}</span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span className="text-slate-400">Extreme rows</span>
                    <span className="text-slate-300 font-mono">{iecResult.extreme_loads.length}</span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span className="text-slate-400">DEL rows</span>
                    <span className="text-slate-300 font-mono">{iecResult.del_table.length}</span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span className="text-slate-400">DLCs</span>
                    <span className="text-slate-300 font-mono text-[10px]">{Array.from(new Set(iecResult.case_summary.map((c) => c.dlc_number))).sort().join(', ')}</span>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* -------- Right: Plots -------- */}
          <div className="xl:col-span-3 space-y-4">
            {/* FATIGUE */}
            {activeTab === 'fatigue' && fResult && (
              <>
                <div className="bg-slate-800/30 rounded-xl p-2 border border-slate-700/30">
                  <Plot data={fatigueSignalTrace as Plotly.Data[]} layout={makePlotLayout({ title: 'Load Time Series', xaxis: { title: 'Time [s]' }, yaxis: { title: 'Load [N]' } })} config={{ responsive: true }} style={{ width: '100%', height: 280 }} />
                </div>
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                  <div className="bg-slate-800/30 rounded-xl p-2 border border-slate-700/30">
                    <Plot data={rainflowTrace as Plotly.Data[]} layout={makePlotLayout({ title: 'Rainflow Range Histogram', xaxis: { title: 'Range [N]' }, yaxis: { title: 'Counts' } })} config={{ responsive: true }} style={{ width: '100%', height: 320 }} />
                  </div>
                  <div className="bg-slate-800/30 rounded-xl p-2 border border-slate-700/30">
                    <Plot data={markovTrace as Plotly.Data[]} layout={makePlotLayout({ title: 'Markov Cycle Matrix', xaxis: { title: 'Mean [N]' }, yaxis: { title: 'Amplitude [N]' }, showlegend: false })} config={{ responsive: true }} style={{ width: '100%', height: 320 }} />
                  </div>
                </div>
              </>
            )}

            {/* STATISTICS */}
            {activeTab === 'statistics' && sResult && (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <div className="bg-slate-800/30 rounded-xl p-2 border border-slate-700/30">
                  <Plot data={statsSignalTrace as Plotly.Data[]} layout={makePlotLayout({ title: 'Signal Time Series', xaxis: { title: 'Time [s]' }, yaxis: { title: 'Value' } })} config={{ responsive: true }} style={{ width: '100%', height: 350 }} />
                </div>
                <div className="bg-slate-800/30 rounded-xl p-2 border border-slate-700/30">
                  <Plot data={pdfTrace as Plotly.Data[]} layout={makePlotLayout({ title: 'Probability Density Function', xaxis: { title: 'Value' }, yaxis: { title: 'Density' } })} config={{ responsive: true }} style={{ width: '100%', height: 350 }} />
                </div>
              </div>
            )}

            {/* SPECTRAL */}
            {activeTab === 'spectral' && spResult && (
              <>
                <div className="bg-slate-800/30 rounded-xl p-2 border border-slate-700/30">
                  <Plot data={spectralTimeTrace as Plotly.Data[]} layout={makePlotLayout({ title: 'Signal Time Series', xaxis: { title: 'Time [s]' }, yaxis: { title: 'Value' } })} config={{ responsive: true }} style={{ width: '100%', height: 280 }} />
                </div>
                <div className="bg-slate-800/30 rounded-xl p-2 border border-slate-700/30">
                  <Plot data={spectralFreqTrace as Plotly.Data[]} layout={makePlotLayout({
                    title: `${spResult.output_type} Spectrum`,
                    xaxis: { title: 'Frequency [Hz]', type: spResult.output_type === 'amplitude' ? 'linear' : 'log' },
                    yaxis: { title: spResult.output_type === 'PSD' ? 'PSD [unit\u00B2/Hz]' : spResult.output_type === 'f x PSD' ? 'f \u00D7 PSD' : 'Amplitude', type: spResult.output_type === 'amplitude' ? 'linear' : 'log' },
                  })} config={{ responsive: true }} style={{ width: '100%', height: 350 }} />
                </div>
              </>
            )}

            {/* DAMPING */}
            {activeTab === 'damping' && dResult && (
              <div className="bg-slate-800/30 rounded-xl p-2 border border-slate-700/30">
                <Plot data={dampingTraces as Plotly.Data[]} layout={makePlotLayout({
                  title: 'Damping Estimation — Signal, Model & Envelope',
                  xaxis: { title: 'Time [s]' }, yaxis: { title: 'Value' },
                })} config={{ responsive: true }} style={{ width: '100%', height: 500 }} />
              </div>
            )}

            {/* GUMBEL EXTREME VALUE */}
            {activeTab === 'extremevalue' && evResult && (
              <>
                <div className="bg-slate-800/30 rounded-xl p-2 border border-slate-700/30">
                  <Plot data={evSignalTrace as Plotly.Data[]} layout={makePlotLayout({
                    title: 'Load Time Series — Peaks Over Threshold',
                    xaxis: { title: 'Time [s]' }, yaxis: { title: 'Load [N]' },
                  })} config={{ responsive: true }} style={{ width: '100%', height: 280 }} />
                </div>
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                  <div className="bg-slate-800/30 rounded-xl p-2 border border-slate-700/30">
                    <Plot data={evGumbelPlotTrace as Plotly.Data[]} layout={makePlotLayout({
                      title: 'Gumbel Probability Plot',
                      xaxis: { title: 'Load [N]' }, yaxis: { title: '-ln(-ln(F))  [reduced variate]' },
                    })} config={{ responsive: true }} style={{ width: '100%', height: 350 }} />
                  </div>
                  <div className="bg-slate-800/30 rounded-xl p-2 border border-slate-700/30">
                    <Plot data={evReturnPeriodTrace as Plotly.Data[]} layout={makePlotLayout({
                      title: 'Return Period Extrapolation (95% CI)',
                      xaxis: { title: 'Return Period', type: 'log' }, yaxis: { title: 'Extreme Load [N]' },
                    })} config={{ responsive: true }} style={{ width: '100%', height: 350 }} />
                  </div>
                </div>
              </>
            )}

            {/* ===== IEC GUMBEL EXTRAPOLATION ===== */}
            {isIecGumbelTab && gumbelResult && gumbelResult.n_blocks > 0 && (
              <>
                {/* ---- MAIN CHART: NREL-style Exceedance Probability Plot ---- */}
                <div className="bg-slate-800/30 rounded-xl p-2 border border-amber-700/20">
                  <Plot
                    data={iecExceedancePlotTrace as Plotly.Data[]}
                    layout={makePlotLayout({
                      title: `Exceedance Probability — ${gumbelResult.channel}  (${gumbelResult.n_peaks} POT peaks, threshold = ${gumbelResult.pot_threshold.toFixed(1)})`,
                      xaxis: { title: `Load Threshold — ${gumbelResult.channel}` },
                      yaxis: {
                        title: 'Probability of Exceedance',
                        type: 'log',
                        range: [-5, 0],
                        dtick: 1,
                      },
                      legend: { bgcolor: 'rgba(0,0,0,0.5)', font: { size: 11, color: '#e2e8f0' }, x: 0.72, y: 0.98 },
                    })}
                    config={{ responsive: true }}
                    style={{ width: '100%', height: 420 }}
                  />
                </div>

                {/* Gumbel probability plot + return period */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                  <div className="bg-slate-800/30 rounded-xl p-2 border border-amber-700/20">
                    <Plot data={iecGumbelProbPlotTrace as Plotly.Data[]} layout={makePlotLayout({
                      title: 'Gumbel Probability Plot (Block Maxima)',
                      xaxis: { title: `${gumbelResult.channel}` }, yaxis: { title: '-ln(-ln(F))  [reduced variate]' },
                    })} config={{ responsive: true }} style={{ width: '100%', height: 340 }} />
                  </div>
                  <div className="bg-slate-800/30 rounded-xl p-2 border border-amber-700/20">
                    <Plot data={iecGumbelReturnTrace as Plotly.Data[]} layout={makePlotLayout({
                      title: 'Return Period Extrapolation (95% CI)',
                      xaxis: { title: 'Return Period', type: 'log' }, yaxis: { title: `${gumbelResult.channel}` },
                    })} config={{ responsive: true }} style={{ width: '100%', height: 340 }} />
                  </div>
                </div>

                {/* Distribution Parameters Table */}
                <div className="bg-slate-800/30 rounded-xl border border-amber-700/20 overflow-hidden">
                  <div className="px-4 py-3 border-b border-slate-700/30">
                    <h3 className="text-sm font-semibold text-slate-200">Fitted Distribution Parameters</h3>
                    <p className="text-[10px] text-slate-500">Method of moments fits to {gumbelResult.n_peaks} peaks-over-threshold / {gumbelResult.n_blocks} block maxima</p>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead className="bg-slate-800/60">
                        <tr>
                          <th className="px-3 py-2 text-left text-slate-400 font-semibold">Distribution</th>
                          <th className="px-3 py-2 text-left text-slate-400 font-semibold">Parameters</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-700/30">
                        {gumbelResult.distribution_params.gumbel && (
                          <tr className="hover:bg-slate-800/40">
                            <td className="px-3 py-2 font-medium" style={{ color: '#f472b6' }}>Gumbel (EV1)</td>
                            <td className="px-3 py-2 font-mono text-slate-300">
                              &alpha; = {gumbelResult.distribution_params.gumbel.alpha?.toFixed(6)}, &beta; = {gumbelResult.distribution_params.gumbel.beta?.toFixed(2)}
                            </td>
                          </tr>
                        )}
                        {gumbelResult.distribution_params.weibull_2p && (
                          <tr className="hover:bg-slate-800/40">
                            <td className="px-3 py-2 font-medium" style={{ color: '#34d399' }}>Weibull (2P)</td>
                            <td className="px-3 py-2 font-mono text-slate-300">
                              k = {gumbelResult.distribution_params.weibull_2p.k?.toFixed(4)}, &lambda; = {gumbelResult.distribution_params.weibull_2p.lambda?.toFixed(2)}
                            </td>
                          </tr>
                        )}
                        {gumbelResult.distribution_params.weibull_3p && (
                          <tr className="hover:bg-slate-800/40">
                            <td className="px-3 py-2 font-medium" style={{ color: '#fbbf24' }}>Weibull (3P)</td>
                            <td className="px-3 py-2 font-mono text-slate-300">
                              k = {gumbelResult.distribution_params.weibull_3p.k?.toFixed(4)}, &lambda; = {gumbelResult.distribution_params.weibull_3p.lambda?.toFixed(2)}, &gamma; = {gumbelResult.distribution_params.weibull_3p.gamma?.toFixed(2)}
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* Extrapolated loads table */}
                <div className="bg-slate-800/30 rounded-xl border border-amber-700/20 overflow-hidden">
                  <div className="px-4 py-3 border-b border-slate-700/30">
                    <h3 className="text-sm font-semibold text-slate-200">
                      Extrapolated Extreme Loads — {gumbelResult.channel}
                    </h3>
                    <p className="text-[10px] text-slate-500">
                      Gumbel (EV1) fit from {gumbelResult.n_blocks} block maxima across {gumbelResult.n_cases} cases
                    </p>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead className="bg-slate-800/60 sticky top-0">
                        <tr>
                          <th className="px-3 py-2 text-left text-slate-400 font-semibold">Return Period</th>
                          <th className="px-3 py-2 text-right text-amber-400 font-semibold">Extrapolated Load</th>
                          <th className="px-3 py-2 text-right text-slate-400 font-semibold">95% CI Lower</th>
                          <th className="px-3 py-2 text-right text-slate-400 font-semibold">95% CI Upper</th>
                          <th className="px-3 py-2 text-right text-slate-400 font-semibold">CI Width</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-700/30">
                        {gumbelResult.return_periods.map((rp) => {
                          const load = gumbelResult.extrapolated_loads[rp];
                          const lower = gumbelResult.confidence_95_lower[rp];
                          const upper = gumbelResult.confidence_95_upper[rp];
                          return (
                            <tr key={rp} className="hover:bg-slate-800/40">
                              <td className="px-3 py-2 font-mono text-slate-200">{rp}</td>
                              <td className="px-3 py-2 text-right font-mono text-amber-300 font-semibold">{load.toFixed(2)}</td>
                              <td className="px-3 py-2 text-right font-mono text-slate-400">{lower.toFixed(2)}</td>
                              <td className="px-3 py-2 text-right font-mono text-slate-400">{upper.toFixed(2)}</td>
                              <td className="px-3 py-2 text-right font-mono text-slate-500">{(upper - lower).toFixed(2)}</td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* Block maxima summary */}
                <div className="bg-slate-800/30 rounded-xl border border-amber-700/20 overflow-hidden">
                  <div className="px-4 py-3 border-b border-slate-700/30">
                    <h3 className="text-sm font-semibold text-slate-200">Block Maxima Details</h3>
                    <p className="text-[10px] text-slate-500">Individual block maximum values extracted from each case</p>
                  </div>
                  <div className="overflow-x-auto max-h-64 overflow-y-auto">
                    <table className="w-full text-xs">
                      <thead className="bg-slate-800/60 sticky top-0">
                        <tr>
                          <th className="px-3 py-2 text-left text-slate-400 font-semibold">#</th>
                          <th className="px-3 py-2 text-left text-slate-400 font-semibold">Case ID</th>
                          <th className="px-3 py-2 text-center text-slate-400 font-semibold">DLC</th>
                          <th className="px-3 py-2 text-right text-slate-400 font-semibold">Vhub (m/s)</th>
                          <th className="px-3 py-2 text-right text-slate-400 font-semibold">Block</th>
                          <th className="px-3 py-2 text-right text-amber-400 font-semibold">Block Max</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-700/30">
                        {gumbelResult.block_maxima.map((bm, idx) => {
                          const info = gumbelResult.case_block_info[idx];
                          return (
                            <tr key={idx} className="hover:bg-slate-800/40">
                              <td className="px-3 py-1.5 text-slate-500">{idx + 1}</td>
                              <td className="px-3 py-1.5 font-mono text-slate-300 text-[10px]">{info?.case_id?.slice(0, 8) || '-'}</td>
                              <td className="px-3 py-1.5 text-center text-amber-400">{info?.dlc || '-'}</td>
                              <td className="px-3 py-1.5 text-right text-slate-300">{info?.vhub?.toFixed(1) || '-'}</td>
                              <td className="px-3 py-1.5 text-right text-slate-400">{info?.block ?? '-'}</td>
                              <td className="px-3 py-1.5 text-right font-mono text-amber-300 font-semibold">{bm.toFixed(2)}</td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              </>
            )}

            {/* IEC Gumbel empty state */}
            {isIecGumbelTab && !gumbelResult && !gumbelLoading && (
              <div className="flex flex-col items-center justify-center h-64 text-slate-500 text-sm gap-2">
                <Zap className="w-8 h-8 text-slate-600" />
                <span>Select a simulation, choose DLCs & channel, then click <span className="text-amber-400 font-medium">Run Gumbel Analysis</span></span>
                <span className="text-[10px] text-slate-600">Typically used with DLC 1.1 for 50-year return period extrapolation</span>
              </div>
            )}

            {/* ===== IEC EXTREME LOADS TABLE ===== */}
            {activeTab === 'iec-extreme' && iecResult && iecResult.extreme_loads.length > 0 && (
              <div className="bg-slate-800/30 rounded-xl border border-slate-700/30 overflow-hidden">
                <div className="px-4 py-3 border-b border-slate-700/30 flex items-center justify-between">
                  <h3 className="text-sm font-semibold text-slate-200">IEC Extreme Loads Table — {iecResult.n_cases_analyzed} cases</h3>
                  <span className="text-[10px] text-slate-500">{iecResult.channels_analyzed.length} channels</span>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead className="bg-slate-800/60 sticky top-0">
                      <tr>
                        <th className="px-3 py-2 text-left text-slate-400 font-semibold">Channel</th>
                        <th className="px-2 py-2 text-left text-slate-400 font-semibold">Unit</th>
                        <th className="px-2 py-2 text-right text-green-400 font-semibold">Max Char.</th>
                        <th className="px-2 py-2 text-right text-green-400 font-semibold">Max Design</th>
                        <th className="px-2 py-2 text-center text-green-400 font-semibold">Max DLC</th>
                        <th className="px-2 py-2 text-right text-green-400 font-semibold">Vhub</th>
                        <th className="px-2 py-2 text-right text-red-400 font-semibold">Min Char.</th>
                        <th className="px-2 py-2 text-right text-red-400 font-semibold">Min Design</th>
                        <th className="px-2 py-2 text-center text-red-400 font-semibold">Min DLC</th>
                        <th className="px-2 py-2 text-right text-red-400 font-semibold">Vhub</th>
                        <th className="px-2 py-2 text-right text-slate-400 font-semibold">SF</th>
                        <th className="px-2 py-2 text-center text-slate-400 font-semibold" />
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-700/30">
                      {iecResult.extreme_loads.map((row) => {
                        const rowKey = row.channel;
                        const isExpanded = iecExpandedRows.has(rowKey);
                        const concMax = iecResult.concurrent_loads.find(
                          (cl) => cl.governing_channel === row.channel && cl.extreme_type === 'max'
                        );
                        return (
                          <>
                            <tr key={rowKey} className="hover:bg-slate-800/40 cursor-pointer" onClick={() => toggleExpandRow(rowKey)}>
                              <td className="px-3 py-2 font-mono text-slate-200">{row.channel}</td>
                              <td className="px-2 py-2 text-slate-400">{row.unit}</td>
                              <td className="px-2 py-2 text-right font-mono text-green-300">{row.max_characteristic.toFixed(2)}</td>
                              <td className="px-2 py-2 text-right font-mono text-green-400 font-semibold">{row.max_design.toFixed(2)}</td>
                              <td className="px-2 py-2 text-center text-amber-400">{row.max_dlc}</td>
                              <td className="px-2 py-2 text-right text-slate-300">{row.max_vhub.toFixed(1)}</td>
                              <td className="px-2 py-2 text-right font-mono text-red-300">{row.min_characteristic.toFixed(2)}</td>
                              <td className="px-2 py-2 text-right font-mono text-red-400 font-semibold">{row.min_design.toFixed(2)}</td>
                              <td className="px-2 py-2 text-center text-amber-400">{row.min_dlc}</td>
                              <td className="px-2 py-2 text-right text-slate-300">{row.min_vhub.toFixed(1)}</td>
                              <td className="px-2 py-2 text-right text-slate-400">{row.safety_factor_max.toFixed(2)}</td>
                              <td className="px-2 py-2 text-center">
                                {isExpanded ? <ChevronDown className="w-3 h-3 text-slate-500" /> : <ChevronRight className="w-3 h-3 text-slate-500" />}
                              </td>
                            </tr>
                            {isExpanded && concMax && (
                              <tr key={`${rowKey}-conc`} className="bg-slate-900/40">
                                <td colSpan={12} className="px-6 py-2">
                                  <div className="text-[10px] text-slate-500 mb-1">Concurrent loads at max of {row.channel}:</div>
                                  <div className="flex flex-wrap gap-x-4 gap-y-1">
                                    {Object.entries(concMax.timestep_values).slice(0, 20).map(([ch, val]) => (
                                      <span key={ch} className="text-[10px]">
                                        <span className="text-slate-400">{ch}:</span>{' '}
                                        <span className="text-slate-200 font-mono">{val.toFixed(2)}</span>
                                      </span>
                                    ))}
                                  </div>
                                </td>
                              </tr>
                            )}
                          </>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* ===== IEC FATIGUE DEL TABLE ===== */}
            {activeTab === 'iec-fatigue' && iecResult && iecResult.del_table.length > 0 && (
              <div className="bg-slate-800/30 rounded-xl border border-slate-700/30 overflow-hidden">
                <div className="px-4 py-3 border-b border-slate-700/30">
                  <h3 className="text-sm font-semibold text-slate-200">IEC Fatigue DEL Table</h3>
                  <p className="text-[10px] text-slate-500">Damage Equivalent Loads combined across fatigue DLC cases with probability weighting</p>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead className="bg-slate-800/60 sticky top-0">
                      <tr>
                        <th className="px-3 py-2 text-left text-slate-400 font-semibold">Channel</th>
                        <th className="px-2 py-2 text-left text-slate-400 font-semibold">Unit</th>
                        {iecResult.del_table[0] && Object.keys(iecResult.del_table[0].del_values)
                          .sort((a, b) => parseFloat(a.split('=')[1]) - parseFloat(b.split('=')[1]))
                          .map((mk) => (
                            <th key={mk} className="px-2 py-2 text-right text-accent-400 font-semibold">{mk}</th>
                          ))}
                        <th className="px-2 py-2 text-right text-slate-400 font-semibold">N_eq</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-700/30">
                      {iecResult.del_table.map((row) => (
                        <tr key={row.channel} className="hover:bg-slate-800/40">
                          <td className="px-3 py-2 font-mono text-slate-200">{row.channel}</td>
                          <td className="px-2 py-2 text-slate-400">{row.unit}</td>
                          {Object.keys(row.del_values)
                            .sort((a, b) => parseFloat(a.split('=')[1]) - parseFloat(b.split('=')[1]))
                            .map((mk) => (
                              <td key={mk} className="px-2 py-2 text-right font-mono text-accent-300">
                                {isNaN(row.del_values[mk]) ? 'N/A' : row.del_values[mk].toFixed(4)}
                              </td>
                            ))}
                          <td className="px-2 py-2 text-right font-mono text-slate-400">{row.n_equivalent.toExponential(1)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* ===== IEC STATISTICS TABLE ===== */}
            {activeTab === 'iec-statistics' && iecResult && iecResult.statistics_table.length > 0 && (
              <div className="bg-slate-800/30 rounded-xl border border-slate-700/30 overflow-hidden">
                <div className="px-4 py-3 border-b border-slate-700/30">
                  <h3 className="text-sm font-semibold text-slate-200">IEC Statistics Summary</h3>
                  <p className="text-[10px] text-slate-500">Aggregated across {iecResult.n_cases_analyzed} simulation cases</p>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead className="bg-slate-800/60 sticky top-0">
                      <tr>
                        <th className="px-3 py-2 text-left text-slate-400 font-semibold">Channel</th>
                        <th className="px-2 py-2 text-left text-slate-400 font-semibold">Unit</th>
                        <th className="px-2 py-2 text-right text-slate-400 font-semibold">Mean</th>
                        <th className="px-2 py-2 text-right text-slate-400 font-semibold">Std</th>
                        <th className="px-2 py-2 text-right text-blue-400 font-semibold">Min</th>
                        <th className="px-2 py-2 text-right text-green-400 font-semibold">Max</th>
                        <th className="px-2 py-2 text-right text-amber-400 font-semibold">|Max|</th>
                        <th className="px-2 py-2 text-right text-slate-400 font-semibold">Cases</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-700/30">
                      {iecResult.statistics_table.map((row) => (
                        <tr key={row.channel} className="hover:bg-slate-800/40">
                          <td className="px-3 py-2 font-mono text-slate-200">{row.channel}</td>
                          <td className="px-2 py-2 text-slate-400">{row.unit}</td>
                          <td className="px-2 py-2 text-right font-mono text-slate-300">{row.mean.toFixed(4)}</td>
                          <td className="px-2 py-2 text-right font-mono text-slate-300">{row.std.toFixed(4)}</td>
                          <td className="px-2 py-2 text-right font-mono text-blue-300">{row.min_val.toFixed(4)}</td>
                          <td className="px-2 py-2 text-right font-mono text-green-300">{row.max_val.toFixed(4)}</td>
                          <td className="px-2 py-2 text-right font-mono text-amber-300">{row.abs_max.toFixed(4)}</td>
                          <td className="px-2 py-2 text-right text-slate-400">{row.n_cases}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* IEC empty state */}
            {isIecTab && !iecResult && !iecLoading && (
              <div className="flex flex-col items-center justify-center h-64 text-slate-500 text-sm gap-2">
                <AlertTriangle className="w-8 h-8 text-slate-600" />
                <span>Select a simulation, choose DLCs, and click <span className="text-amber-400 font-medium">Run IEC Analysis</span></span>
              </div>
            )}

            {/* Empty state */}
            {!isIecTab && !isIecGumbelTab && !fResult && !sResult && !spResult && !dResult && !evResult && !loading && (
              <div className="flex items-center justify-center h-64 text-slate-500 text-sm">
                Configure parameters and click <span className="text-accent-400 font-medium ml-1">Compute</span> to generate results.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
