import { useState, useCallback, useMemo } from 'react';
import { useParams } from 'react-router-dom';
import { Wind, Target, TrendingUp, Gauge, Activity, Loader2 } from 'lucide-react';
import toast from 'react-hot-toast';
import Plot from 'react-plotly.js';
import axios from 'axios';

// ---------------------------------------------------------------------------
// API helper
// ---------------------------------------------------------------------------

const API_BASE =
  (window as unknown as Record<string, string>).__WINDFORGE_API_URL__
    ? `${(window as unknown as Record<string, string>).__WINDFORGE_API_URL__}/api/v1`
    : '/api/v1';

function bemPost<T>(projectId: string, endpoint: string, data: unknown): Promise<T> {
  const token = localStorage.getItem('windforge_token');
  return axios
    .post<T>(`${API_BASE}/projects/${projectId}/bem/${endpoint}`, data, {
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    })
    .then((res) => res.data);
}

// ---------------------------------------------------------------------------
// Sub-tab definitions
// ---------------------------------------------------------------------------

const TABS = [
  { key: 'cpSurface', label: 'CP-λ-Pitch', icon: Target },
  { key: 'powerCurve', label: 'Power Curve', icon: TrendingUp },
  { key: 'idealRotor', label: 'Ideal Rotor', icon: Wind },
  { key: 'highThrust', label: 'High Thrust', icon: Gauge },
  { key: 'optimalCp', label: 'Optimal CP', icon: Target },
  { key: 'wakeExpansion', label: 'Wake Expansion', icon: Activity },
  { key: 'dynamicInflow', label: 'Dynamic Inflow', icon: Wind },
] as const;

type TabKey = (typeof TABS)[number]['key'];

// ---------------------------------------------------------------------------
// Result types
// ---------------------------------------------------------------------------

interface CpSurfaceResult {
  tsr_values: number[];
  pitch_values: number[];
  cp_matrix: number[][];
  ct_matrix: number[][];
  max_cp: number;
  optimal_tsr: number;
  optimal_pitch: number;
}

interface PowerCurveResult {
  wind_speeds: number[];
  power: number[];
  thrust: number[];
  torque: number[];
  cp: number[];
  ct: number[];
}

interface HighThrustResult {
  a_values: number[];
  ct_curves: Record<string, number[]>;
}

interface IdealRotorResult {
  r_over_R: number[];
  chord_wake: number[];
  twist_wake: number[];
  chord_nowake: number[];
  twist_nowake: number[];
  a_wake: number[];
  ap_wake: number[];
}

interface OptimalCpResult {
  tsr: number[];
  cp_optimal: number[];
  cp_betz: number[];
  a_optimal: number[];
  ap_optimal: number[];
}

interface WakeExpansionResult {
  x_over_D: number[];
  curves: Record<string, number[]>;
}

interface DynamicInflowResult {
  time: number[];
  a_dynamic: number[];
  a_quasi_steady: number[];
  tau1: number;
  tau2: number;
}

// ---------------------------------------------------------------------------
// Dark theme Plotly layout factory
// ---------------------------------------------------------------------------

function makePlotLayout(overrides: Record<string, unknown> = {}) {
  return {
    paper_bgcolor: 'transparent',
    plot_bgcolor: 'rgba(17,24,39,0.8)',
    font: { family: 'ui-monospace, monospace', size: 10, color: '#9ca3af' },
    margin: { t: 40, r: 30, b: 60, l: 70 },
    xaxis: {
      gridcolor: 'rgba(100,116,139,0.2)',
      zeroline: false,
      ...(overrides.xaxis as object || {}),
    },
    yaxis: {
      gridcolor: 'rgba(100,116,139,0.2)',
      zeroline: false,
      ...(overrides.yaxis as object || {}),
    },
    legend: {
      bgcolor: 'rgba(0,0,0,0.3)',
      font: { size: 9, color: '#9ca3af' },
    },
    showlegend: true,
    ...Object.fromEntries(
      Object.entries(overrides).filter(([k]) => k !== 'xaxis' && k !== 'yaxis'),
    ),
  };
}

// ---------------------------------------------------------------------------
// Shared input field component
// ---------------------------------------------------------------------------

function NumberInput({
  label,
  value,
  onChange,
  step,
  min,
  max,
  unit,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
  step?: number;
  min?: number;
  max?: number;
  unit?: string;
}) {
  return (
    <div>
      <label className="block text-xs font-medium text-slate-400 mb-1">
        {label}
        {unit && <span className="text-slate-500 ml-1">({unit})</span>}
      </label>
      <input
        type="number"
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        step={step ?? 0.1}
        min={min}
        max={max}
        className="bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-sm text-slate-100 w-full focus:ring-1 focus:ring-accent-500 focus:border-accent-500"
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Default NREL-5MW-like rotor data for quick testing
// ---------------------------------------------------------------------------
const DEFAULT_R_STATIONS = [2.87, 5.60, 8.33, 11.75, 15.85, 19.95, 24.05, 28.15, 32.25, 36.35, 40.45, 44.55, 48.65, 52.75, 56.17, 58.90, 61.63];
const DEFAULT_CHORD = [3.54, 3.85, 4.17, 4.56, 4.65, 4.46, 4.25, 4.01, 3.75, 3.50, 3.26, 3.01, 2.76, 2.52, 2.31, 2.09, 1.42];
const DEFAULT_TWIST = [13.31, 13.31, 13.31, 13.31, 11.48, 10.16, 9.01, 7.80, 6.54, 5.36, 4.19, 3.13, 2.32, 1.53, 0.86, 0.37, 0.11];
const DEFAULT_POLAR_ALPHA = [-10,-8,-6,-4,-2,0,2,4,6,8,10,12,14,16,18,20,22,24];
const DEFAULT_POLAR_CL = [-0.56,-0.64,-0.42,-0.21,0.05,0.25,0.50,0.73,0.90,1.08,1.20,1.35,1.40,1.30,1.15,1.00,0.88,0.75];
const DEFAULT_POLAR_CD = [0.025,0.020,0.014,0.011,0.009,0.008,0.009,0.010,0.012,0.016,0.022,0.030,0.045,0.070,0.100,0.135,0.165,0.200];

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function BemRotorPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const [activeTab, setActiveTab] = useState<TabKey>('cpSurface');
  const [error, setError] = useState<string | null>(null);

  // ── CP Surface state ─────────────────────────────────────────────────────
  const [cpV0, setCpV0] = useState(10.0);
  const [cpTsrMin, setCpTsrMin] = useState(1.0);
  const [cpTsrMax, setCpTsrMax] = useState(15.0);
  const [cpTsrSteps, setCpTsrSteps] = useState(25);
  const [cpPitchMin, setCpPitchMin] = useState(-5.0);
  const [cpPitchMax, setCpPitchMax] = useState(25.0);
  const [cpPitchSteps, setCpPitchSteps] = useState(20);
  const [cpResult, setCpResult] = useState<CpSurfaceResult | null>(null);
  const [cpLoading, setCpLoading] = useState(false);

  // ── Power Curve state ────────────────────────────────────────────────────
  const [pcRpm, setPcRpm] = useState(12.1);
  const [pcPitch, setPcPitch] = useState(0.0);
  const [pcResult, setPcResult] = useState<PowerCurveResult | null>(null);
  const [pcLoading, setPcLoading] = useState(false);

  // ── Ideal Rotor state ────────────────────────────────────────────────────
  const [irR, setIrR] = useState(63.0);
  const [irHub, setIrHub] = useState(1.5);
  const [irTsr, setIrTsr] = useState(7.0);
  const [irCl, setIrCl] = useState(1.0);
  const [irB, setIrB] = useState(3);
  const [irResult, setIrResult] = useState<IdealRotorResult | null>(null);
  const [irLoading, setIrLoading] = useState(false);

  // ── High Thrust state ────────────────────────────────────────────────────
  const [htResult, setHtResult] = useState<HighThrustResult | null>(null);
  const [htLoading, setHtLoading] = useState(false);

  // ── Optimal CP state ─────────────────────────────────────────────────────
  const [ocResult, setOcResult] = useState<OptimalCpResult | null>(null);
  const [ocLoading, setOcLoading] = useState(false);

  // ── Wake Expansion state ─────────────────────────────────────────────────
  const [weCt, setWeCt] = useState(0.8);
  const [weXmax, setWeXmax] = useState(20.0);
  const [weResult, setWeResult] = useState<WakeExpansionResult | null>(null);
  const [weLoading, setWeLoading] = useState(false);

  // ── Dynamic Inflow state ─────────────────────────────────────────────────
  const [diR, setDiR] = useState(63.0);
  const [diU0, setDiU0] = useState(10.0);
  const [diAInit, setDiAInit] = useState(0.2);
  const [diAFinal, setDiAFinal] = useState(0.35);
  const [diRbar, setDiRbar] = useState(0.7);
  const [diTmax, setDiTmax] = useState(30.0);
  const [diResult, setDiResult] = useState<DynamicInflowResult | null>(null);
  const [diLoading, setDiLoading] = useState(false);

  // ── Compute handlers ─────────────────────────────────────────────────────

  const handleComputeCpSurface = useCallback(async () => {
    if (!projectId) return;
    setCpLoading(true); setError(null); setCpResult(null);
    try {
      const result = await bemPost<CpSurfaceResult>(projectId, 'cp-surface', {
        r: DEFAULT_R_STATIONS, chord: DEFAULT_CHORD, twist: DEFAULT_TWIST,
        polar_alpha: DEFAULT_POLAR_ALPHA, polar_cl: DEFAULT_POLAR_CL, polar_cd: DEFAULT_POLAR_CD,
        V0: cpV0, nB: 3, cone: 0, tsr_min: cpTsrMin, tsr_max: cpTsrMax, tsr_steps: cpTsrSteps,
        pitch_min: cpPitchMin, pitch_max: cpPitchMax, pitch_steps: cpPitchSteps,
      });
      setCpResult(result);
      toast.success(`Max CP = ${result.max_cp.toFixed(4)} at λ=${result.optimal_tsr.toFixed(1)}, θ=${result.optimal_pitch.toFixed(1)}°`);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'CP surface computation failed';
      setError(msg); toast.error(msg);
    } finally { setCpLoading(false); }
  }, [projectId, cpV0, cpTsrMin, cpTsrMax, cpTsrSteps, cpPitchMin, cpPitchMax, cpPitchSteps]);

  const handleComputePowerCurve = useCallback(async () => {
    if (!projectId) return;
    setPcLoading(true); setError(null); setPcResult(null);
    try {
      const result = await bemPost<PowerCurveResult>(projectId, 'power-curve', {
        r: DEFAULT_R_STATIONS, chord: DEFAULT_CHORD, twist: DEFAULT_TWIST,
        polar_alpha: DEFAULT_POLAR_ALPHA, polar_cl: DEFAULT_POLAR_CL, polar_cd: DEFAULT_POLAR_CD,
        nB: 3, cone: 0, rpm: pcRpm, pitch: pcPitch,
      });
      setPcResult(result);
      const maxP = Math.max(...result.power) / 1e6;
      toast.success(`Max power = ${maxP.toFixed(2)} MW`);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Power curve computation failed';
      setError(msg); toast.error(msg);
    } finally { setPcLoading(false); }
  }, [projectId, pcRpm, pcPitch]);

  const handleComputeIdealRotor = useCallback(async () => {
    if (!projectId) return;
    setIrLoading(true); setError(null); setIrResult(null);
    try {
      const result = await bemPost<IdealRotorResult>(projectId, 'ideal-rotor', {
        R: irR, r_hub: irHub, TSR_design: irTsr, Cl_design: irCl, B: irB,
      });
      setIrResult(result);
      toast.success('Ideal rotor planform computed');
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Ideal rotor computation failed';
      setError(msg); toast.error(msg);
    } finally { setIrLoading(false); }
  }, [projectId, irR, irHub, irTsr, irCl, irB]);

  const handleComputeHighThrust = useCallback(async () => {
    if (!projectId) return;
    setHtLoading(true); setError(null); setHtResult(null);
    try {
      const result = await bemPost<HighThrustResult>(projectId, 'high-thrust', {});
      setHtResult(result);
      toast.success(`${Object.keys(result.ct_curves).length} methods compared`);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'High thrust computation failed';
      setError(msg); toast.error(msg);
    } finally { setHtLoading(false); }
  }, [projectId]);

  const handleComputeOptimalCp = useCallback(async () => {
    if (!projectId) return;
    setOcLoading(true); setError(null); setOcResult(null);
    try {
      const result = await bemPost<OptimalCpResult>(projectId, 'optimal-cp', {});
      setOcResult(result);
      toast.success('Optimal CP (Betz limit) computed');
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Optimal CP computation failed';
      setError(msg); toast.error(msg);
    } finally { setOcLoading(false); }
  }, [projectId]);

  const handleComputeWakeExpansion = useCallback(async () => {
    if (!projectId) return;
    setWeLoading(true); setError(null); setWeResult(null);
    try {
      const result = await bemPost<WakeExpansionResult>(projectId, 'wake-expansion', {
        CT: weCt, x_max_over_D: weXmax,
      });
      setWeResult(result);
      toast.success(`${Object.keys(result.curves).length} wake models computed`);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Wake expansion computation failed';
      setError(msg); toast.error(msg);
    } finally { setWeLoading(false); }
  }, [projectId, weCt, weXmax]);

  const handleComputeDynamicInflow = useCallback(async () => {
    if (!projectId) return;
    setDiLoading(true); setError(null); setDiResult(null);
    try {
      const result = await bemPost<DynamicInflowResult>(projectId, 'dynamic-inflow', {
        R: diR, U0: diU0, a_init: diAInit, a_final: diAFinal, r_bar: diRbar, t_max: diTmax,
      });
      setDiResult(result);
      toast.success(`τ₁ = ${result.tau1.toFixed(2)} s, τ₂ = ${result.tau2.toFixed(2)} s`);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Dynamic inflow computation failed';
      setError(msg); toast.error(msg);
    } finally { setDiLoading(false); }
  }, [projectId, diR, diU0, diAInit, diAFinal, diRbar, diTmax]);

  // ── Plot traces (memoized) ────────────────────────────────────────────────

  const cpSurfaceTraces = useMemo(() => {
    if (!cpResult) return [];
    return [{
      type: 'surface' as const,
      x: cpResult.pitch_values,
      y: cpResult.tsr_values,
      z: cpResult.cp_matrix,
      colorscale: 'Viridis',
      showscale: true,
      colorbar: { title: 'CP', titlefont: { color: '#9ca3af' }, tickfont: { color: '#9ca3af' } },
    }];
  }, [cpResult]);

  const powerCurveTraces = useMemo(() => {
    if (!pcResult) return [];
    return [
      { x: pcResult.wind_speeds, y: pcResult.power.map(p => p / 1e6), name: 'Power (MW)', type: 'scatter' as const, line: { color: '#22d3ee' } },
      { x: pcResult.wind_speeds, y: pcResult.thrust.map(t => t / 1e3), name: 'Thrust (kN)', type: 'scatter' as const, yaxis: 'y2', line: { color: '#f97316', dash: 'dash' as const } },
    ];
  }, [pcResult]);

  const idealRotorTraces = useMemo(() => {
    if (!irResult) return [];
    return [
      { x: irResult.r_over_R, y: irResult.chord_wake, name: 'Chord (wake rot.)', type: 'scatter' as const, line: { color: '#22d3ee' } },
      { x: irResult.r_over_R, y: irResult.chord_nowake, name: 'Chord (no wake rot.)', type: 'scatter' as const, line: { color: '#22d3ee', dash: 'dash' as const } },
      { x: irResult.r_over_R, y: irResult.twist_wake, name: 'Twist (wake rot.)', type: 'scatter' as const, yaxis: 'y2', line: { color: '#f97316' } },
      { x: irResult.r_over_R, y: irResult.twist_nowake, name: 'Twist (no wake rot.)', type: 'scatter' as const, yaxis: 'y2', line: { color: '#f97316', dash: 'dash' as const } },
    ];
  }, [irResult]);

  const highThrustTraces = useMemo(() => {
    if (!htResult) return [];
    const colors = ['#22d3ee', '#f97316', '#a78bfa', '#34d399', '#f472b6', '#fbbf24'];
    return Object.entries(htResult.ct_curves).map(([method, values], i) => ({
      x: htResult.a_values, y: values, name: method, type: 'scatter' as const,
      line: { color: colors[i % colors.length] },
    }));
  }, [htResult]);

  const optimalCpTraces = useMemo(() => {
    if (!ocResult) return [];
    return [
      { x: ocResult.tsr, y: ocResult.cp_optimal, name: 'CP optimal (ADMTO)', type: 'scatter' as const, line: { color: '#22d3ee', width: 2 } },
      { x: ocResult.tsr, y: ocResult.cp_betz, name: 'Betz limit (16/27)', type: 'scatter' as const, line: { color: '#f97316', dash: 'dash' as const } },
    ];
  }, [ocResult]);

  const wakeExpansionTraces = useMemo(() => {
    if (!weResult) return [];
    const colors = ['#22d3ee', '#f97316', '#a78bfa', '#34d399'];
    return Object.entries(weResult.curves).map(([model, values], i) => ({
      x: weResult.x_over_D, y: values, name: model, type: 'scatter' as const,
      line: { color: colors[i % colors.length] },
    }));
  }, [weResult]);

  const dynamicInflowTraces = useMemo(() => {
    if (!diResult) return [];
    return [
      { x: diResult.time, y: diResult.a_dynamic, name: 'Dynamic (Øye)', type: 'scatter' as const, line: { color: '#22d3ee', width: 2 } },
      { x: diResult.time, y: diResult.a_quasi_steady, name: 'Quasi-steady', type: 'scatter' as const, line: { color: '#f97316', dash: 'dash' as const } },
    ];
  }, [diResult]);

  // ── Loading/compute for current tab ───────────────────────────────────────
  const isLoading = {
    cpSurface: cpLoading, powerCurve: pcLoading, idealRotor: irLoading,
    highThrust: htLoading, optimalCp: ocLoading, wakeExpansion: weLoading,
    dynamicInflow: diLoading,
  }[activeTab];

  const handleCompute = {
    cpSurface: handleComputeCpSurface, powerCurve: handleComputePowerCurve,
    idealRotor: handleComputeIdealRotor, highThrust: handleComputeHighThrust,
    optimalCp: handleComputeOptimalCp, wakeExpansion: handleComputeWakeExpansion,
    dynamicInflow: handleComputeDynamicInflow,
  }[activeTab];

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Wind className="h-6 w-6 text-cyan-400" />
        <h2 className="text-lg font-semibold text-white">BEM & Rotor Aerodynamics</h2>
        <span className="text-xs text-slate-500 bg-slate-800 px-2 py-0.5 rounded">welib.BEM + wt_theory + dyninflow</span>
      </div>

      {/* Sub-tab pills */}
      <div className="flex flex-wrap gap-1">
        {TABS.map((tab) => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                activeTab === tab.key
                  ? 'bg-cyan-500/20 text-cyan-300 ring-1 ring-cyan-500/40'
                  : 'bg-slate-800 text-slate-400 hover:text-slate-200 hover:bg-slate-700'
              }`}
            >
              <Icon className="h-3.5 w-3.5" />
              {tab.label}
            </button>
          );
        })}
      </div>

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {/* Content: inputs + plots */}
      <div className="grid grid-cols-1 xl:grid-cols-4 gap-4">
        {/* Left: Inputs panel */}
        <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-700/50 space-y-3">
          <h3 className="text-sm font-medium text-slate-300 mb-2">Parameters</h3>

          {/* CP Surface inputs */}
          {activeTab === 'cpSurface' && (
            <>
              <NumberInput label="Wind Speed" value={cpV0} onChange={setCpV0} unit="m/s" min={1} step={1} />
              <div className="grid grid-cols-2 gap-2">
                <NumberInput label="TSR min" value={cpTsrMin} onChange={setCpTsrMin} step={0.5} />
                <NumberInput label="TSR max" value={cpTsrMax} onChange={setCpTsrMax} step={0.5} />
              </div>
              <NumberInput label="TSR steps" value={cpTsrSteps} onChange={setCpTsrSteps} step={1} min={5} />
              <div className="grid grid-cols-2 gap-2">
                <NumberInput label="Pitch min" value={cpPitchMin} onChange={setCpPitchMin} unit="°" step={1} />
                <NumberInput label="Pitch max" value={cpPitchMax} onChange={setCpPitchMax} unit="°" step={1} />
              </div>
              <NumberInput label="Pitch steps" value={cpPitchSteps} onChange={setCpPitchSteps} step={1} min={5} />
              <p className="text-xs text-slate-500 mt-1">Using default NREL-5MW rotor geometry & DU21 polar</p>
            </>
          )}

          {/* Power Curve inputs */}
          {activeTab === 'powerCurve' && (
            <>
              <NumberInput label="Rotor RPM" value={pcRpm} onChange={setPcRpm} unit="rpm" step={0.1} min={1} />
              <NumberInput label="Pitch angle" value={pcPitch} onChange={setPcPitch} unit="°" step={0.5} />
              <p className="text-xs text-slate-500 mt-1">Fixed RPM/pitch sweep (3-25 m/s)</p>
            </>
          )}

          {/* Ideal Rotor inputs */}
          {activeTab === 'idealRotor' && (
            <>
              <NumberInput label="Rotor radius" value={irR} onChange={setIrR} unit="m" step={1} min={5} />
              <NumberInput label="Hub radius" value={irHub} onChange={setIrHub} unit="m" step={0.1} min={0.5} />
              <NumberInput label="Design TSR" value={irTsr} onChange={setIrTsr} step={0.5} min={1} />
              <NumberInput label="Design Cl" value={irCl} onChange={setIrCl} step={0.1} min={0.1} />
              <NumberInput label="Blades" value={irB} onChange={setIrB} step={1} min={1} max={6} />
            </>
          )}

          {/* High Thrust - no inputs needed */}
          {activeTab === 'highThrust' && (
            <p className="text-xs text-slate-500">Compares 6 high-thrust correction methods: Momentum Theory, Glauert, Spera, Buhl, Leishman, Branlard</p>
          )}

          {/* Optimal CP - no inputs needed */}
          {activeTab === 'optimalCp' && (
            <p className="text-xs text-slate-500">Actuator Disc Momentum Theory optimal CP vs TSR with Betz limit (16/27) overlay</p>
          )}

          {/* Wake Expansion inputs */}
          {activeTab === 'wakeExpansion' && (
            <>
              <NumberInput label="Thrust coeff. CT" value={weCt} onChange={setWeCt} step={0.05} min={0.1} max={1.5} />
              <NumberInput label="Max x/D" value={weXmax} onChange={setWeXmax} step={5} min={5} max={100} />
              <p className="text-xs text-slate-500 mt-1">Models: momentum, vortex cylinder, Rathmann, Frandsen</p>
            </>
          )}

          {/* Dynamic Inflow inputs */}
          {activeTab === 'dynamicInflow' && (
            <>
              <NumberInput label="Rotor radius" value={diR} onChange={setDiR} unit="m" step={1} min={5} />
              <NumberInput label="Wind speed" value={diU0} onChange={setDiU0} unit="m/s" step={0.5} min={1} />
              <NumberInput label="Initial a" value={diAInit} onChange={setDiAInit} step={0.05} min={0} max={0.9} />
              <NumberInput label="Final a" value={diAFinal} onChange={setDiAFinal} step={0.05} min={0} max={0.9} />
              <NumberInput label="r/R" value={diRbar} onChange={setDiRbar} step={0.05} min={0.1} max={1.0} />
              <NumberInput label="Duration" value={diTmax} onChange={setDiTmax} unit="s" step={5} min={5} />
            </>
          )}

          {/* Compute button */}
          <button
            onClick={handleCompute}
            disabled={isLoading}
            className="w-full mt-2 flex items-center justify-center gap-2 px-4 py-2 rounded-lg bg-cyan-600 text-white text-sm font-medium hover:bg-cyan-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {isLoading ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Computing…
              </>
            ) : (
              'Compute'
            )}
          </button>
        </div>

        {/* Right: Plot area (3 cols) */}
        <div className="xl:col-span-3 space-y-4">

          {/* CP Surface 3D */}
          {activeTab === 'cpSurface' && cpResult && (
            <div className="bg-slate-800/30 rounded-xl border border-slate-700/30 p-2">
              <Plot
                data={cpSurfaceTraces as Plotly.Data[]}
                layout={{
                  ...makePlotLayout({ title: `CP Surface — Max CP = ${cpResult.max_cp.toFixed(4)} at λ=${cpResult.optimal_tsr.toFixed(1)}, θ=${cpResult.optimal_pitch.toFixed(1)}°` }),
                  scene: {
                    xaxis: { title: 'Pitch (°)', color: '#9ca3af', gridcolor: 'rgba(100,116,139,0.2)' },
                    yaxis: { title: 'TSR (λ)', color: '#9ca3af', gridcolor: 'rgba(100,116,139,0.2)' },
                    zaxis: { title: 'CP', color: '#9ca3af', gridcolor: 'rgba(100,116,139,0.2)' },
                    bgcolor: 'rgba(17,24,39,0.8)',
                  },
                  margin: { t: 50, r: 10, b: 10, l: 10 },
                  height: 500,
                } as Partial<Plotly.Layout>}
                config={{ responsive: true }}
                className="w-full"
              />
            </div>
          )}

          {/* Power Curve */}
          {activeTab === 'powerCurve' && pcResult && (
            <div className="bg-slate-800/30 rounded-xl border border-slate-700/30 p-2">
              <Plot
                data={powerCurveTraces as Plotly.Data[]}
                layout={makePlotLayout({
                  title: 'Aerodynamic Power Curve',
                  xaxis: { title: 'Wind Speed (m/s)' },
                  yaxis: { title: 'Power (MW)', titlefont: { color: '#22d3ee' } },
                  yaxis2: { title: 'Thrust (kN)', titlefont: { color: '#f97316' }, overlaying: 'y', side: 'right', gridcolor: 'rgba(100,116,139,0.1)' },
                  height: 450,
                }) as Partial<Plotly.Layout>}
                config={{ responsive: true }}
                className="w-full"
              />
            </div>
          )}

          {/* Ideal Rotor */}
          {activeTab === 'idealRotor' && irResult && (
            <div className="bg-slate-800/30 rounded-xl border border-slate-700/30 p-2">
              <Plot
                data={idealRotorTraces as Plotly.Data[]}
                layout={makePlotLayout({
                  title: 'Ideal Rotor Planform (Betz Optimal)',
                  xaxis: { title: 'r/R' },
                  yaxis: { title: 'Chord (m)', titlefont: { color: '#22d3ee' } },
                  yaxis2: { title: 'Twist (°)', titlefont: { color: '#f97316' }, overlaying: 'y', side: 'right', gridcolor: 'rgba(100,116,139,0.1)' },
                  height: 450,
                }) as Partial<Plotly.Layout>}
                config={{ responsive: true }}
                className="w-full"
              />
            </div>
          )}

          {/* High Thrust */}
          {activeTab === 'highThrust' && htResult && (
            <div className="bg-slate-800/30 rounded-xl border border-slate-700/30 p-2">
              <Plot
                data={highThrustTraces as Plotly.Data[]}
                layout={makePlotLayout({
                  title: 'Thrust Coefficient vs Axial Induction Factor',
                  xaxis: { title: 'Axial induction factor a' },
                  yaxis: { title: 'Ct' },
                  height: 450,
                }) as Partial<Plotly.Layout>}
                config={{ responsive: true }}
                className="w-full"
              />
            </div>
          )}

          {/* Optimal CP */}
          {activeTab === 'optimalCp' && ocResult && (
            <div className="space-y-4">
              <div className="bg-slate-800/30 rounded-xl border border-slate-700/30 p-2">
                <Plot
                  data={optimalCpTraces as Plotly.Data[]}
                  layout={makePlotLayout({
                    title: 'Optimal CP vs Tip-Speed Ratio (Betz Limit)',
                    xaxis: { title: 'Tip-Speed Ratio λ' },
                    yaxis: { title: 'CP' },
                    height: 400,
                  }) as Partial<Plotly.Layout>}
                  config={{ responsive: true }}
                  className="w-full"
                />
              </div>
              <div className="bg-slate-800/30 rounded-xl border border-slate-700/30 p-2">
                <Plot
                  data={[
                    { x: ocResult.tsr, y: ocResult.a_optimal, name: 'a (axial)', type: 'scatter', line: { color: '#22d3ee' } },
                    { x: ocResult.tsr, y: ocResult.ap_optimal, name: "a' (tangential)", type: 'scatter', line: { color: '#f97316' } },
                  ] as Plotly.Data[]}
                  layout={makePlotLayout({
                    title: 'Optimal Induction Factors',
                    xaxis: { title: 'Tip-Speed Ratio λ' },
                    yaxis: { title: 'Induction Factor' },
                    height: 350,
                  }) as Partial<Plotly.Layout>}
                  config={{ responsive: true }}
                  className="w-full"
                />
              </div>
            </div>
          )}

          {/* Wake Expansion */}
          {activeTab === 'wakeExpansion' && weResult && (
            <div className="bg-slate-800/30 rounded-xl border border-slate-700/30 p-2">
              <Plot
                data={wakeExpansionTraces as Plotly.Data[]}
                layout={makePlotLayout({
                  title: `Wake Expansion (CT = ${weCt})`,
                  xaxis: { title: 'Downstream distance x/D' },
                  yaxis: { title: 'Wake radius Rw/R' },
                  height: 450,
                }) as Partial<Plotly.Layout>}
                config={{ responsive: true }}
                className="w-full"
              />
            </div>
          )}

          {/* Dynamic Inflow */}
          {activeTab === 'dynamicInflow' && diResult && (
            <div className="bg-slate-800/30 rounded-xl border border-slate-700/30 p-2">
              <Plot
                data={dynamicInflowTraces as Plotly.Data[]}
                layout={makePlotLayout({
                  title: `Dynamic Inflow (Øye) — τ₁=${diResult.tau1.toFixed(2)}s, τ₂=${diResult.tau2.toFixed(2)}s`,
                  xaxis: { title: 'Time (s)' },
                  yaxis: { title: 'Axial induction a' },
                  height: 450,
                }) as Partial<Plotly.Layout>}
                config={{ responsive: true }}
                className="w-full"
              />
            </div>
          )}

          {/* Empty state */}
          {!cpResult && activeTab === 'cpSurface' && !cpLoading && (
            <div className="bg-slate-800/20 rounded-xl border border-slate-700/30 p-12 text-center text-slate-500">
              Click <span className="text-cyan-400">Compute</span> to generate the CP-λ-pitch surface
            </div>
          )}
          {!pcResult && activeTab === 'powerCurve' && !pcLoading && (
            <div className="bg-slate-800/20 rounded-xl border border-slate-700/30 p-12 text-center text-slate-500">
              Click <span className="text-cyan-400">Compute</span> to generate the power curve
            </div>
          )}
          {!irResult && activeTab === 'idealRotor' && !irLoading && (
            <div className="bg-slate-800/20 rounded-xl border border-slate-700/30 p-12 text-center text-slate-500">
              Click <span className="text-cyan-400">Compute</span> to compute the ideal rotor planform
            </div>
          )}
          {!htResult && activeTab === 'highThrust' && !htLoading && (
            <div className="bg-slate-800/20 rounded-xl border border-slate-700/30 p-12 text-center text-slate-500">
              Click <span className="text-cyan-400">Compute</span> to compare high-thrust correction methods
            </div>
          )}
          {!ocResult && activeTab === 'optimalCp' && !ocLoading && (
            <div className="bg-slate-800/20 rounded-xl border border-slate-700/30 p-12 text-center text-slate-500">
              Click <span className="text-cyan-400">Compute</span> to compute optimal CP vs TSR
            </div>
          )}
          {!weResult && activeTab === 'wakeExpansion' && !weLoading && (
            <div className="bg-slate-800/20 rounded-xl border border-slate-700/30 p-12 text-center text-slate-500">
              Click <span className="text-cyan-400">Compute</span> to compute wake expansion
            </div>
          )}
          {!diResult && activeTab === 'dynamicInflow' && !diLoading && (
            <div className="bg-slate-800/20 rounded-xl border border-slate-700/30 p-12 text-center text-slate-500">
              Click <span className="text-cyan-400">Compute</span> to simulate dynamic inflow response
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
