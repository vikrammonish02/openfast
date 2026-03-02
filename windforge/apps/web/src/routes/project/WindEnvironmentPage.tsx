import { useState, useCallback, useMemo } from 'react';
import { useParams } from 'react-router-dom';
import api from '@/api/client';
import { CloudRain, Loader2, Play } from 'lucide-react';
import toast from 'react-hot-toast';
import Plot from 'react-plotly.js';
import clsx from 'clsx';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const TABS = [
  { key: 'kaimal', label: 'Kaimal Spectrum' },
  { key: 'turbulence', label: 'Turbulence Classes' },
  { key: 'eog', label: 'Extreme Gust (EOG)' },
  { key: 'shear', label: 'Wind Shear' },
] as const;

type TabKey = (typeof TABS)[number]['key'];

const COMPONENT_COLORS = {
  u: '#10b981',
  v: '#3b82f6',
  w: '#f59e0b',
};

const TURB_COLORS: Record<string, string> = {
  'NTM-A': '#ef4444',
  'NTM-B': '#f59e0b',
  'NTM-C': '#10b981',
  'ETM-A': '#ef4444',
  'ETM-B': '#f59e0b',
  'ETM-C': '#10b981',
};

const TURB_DASHES: Record<string, string> = {
  'NTM-A': 'solid',
  'NTM-B': 'solid',
  'NTM-C': 'solid',
  'ETM-A': 'dash',
  'ETM-B': 'dash',
  'ETM-C': 'dash',
};

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface KaimalResult {
  frequencies: number[];
  Su: number[];
  Sv: number[];
  Sw: number[];
}

interface TurbulenceEnvelopeResult {
  wind_speeds: number[];
  ntm_A: number[];
  ntm_B: number[];
  ntm_C: number[];
  etm_A: number[];
  etm_B: number[];
  etm_C: number[];
}

interface EOGResult {
  time: number[];
  wind_speed: number[];
  gust_component: number[];
  gust_peak: number;
}

interface WindShearResult {
  heights: number[];
  velocity_powerlaw: number[];
  velocity_loglaw: number[];
}

// ---------------------------------------------------------------------------
// Base Plotly layout
// ---------------------------------------------------------------------------

const basePlotLayout: Partial<Plotly.Layout> = {
  paper_bgcolor: 'transparent',
  plot_bgcolor: 'rgba(17,24,39,0.8)',
  font: { family: 'ui-monospace, monospace', size: 10, color: '#9ca3af' },
  margin: { t: 40, r: 30, b: 60, l: 70 },
  showlegend: true,
  legend: { bgcolor: 'rgba(0,0,0,0.3)', font: { size: 9, color: '#9ca3af' } },
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function WindEnvironmentPage() {
  const { projectId } = useParams<{ projectId: string }>();

  // Tab state
  const [activeTab, setActiveTab] = useState<TabKey>('kaimal');

  // --- Kaimal Spectrum state ---
  const [kaimalVHub, setKaimalVHub] = useState(12);
  const [kaimalResult, setKaimalResult] = useState<KaimalResult | null>(null);
  const [kaimalLoading, setKaimalLoading] = useState(false);

  // --- Turbulence Classes state ---
  const [turbResult, setTurbResult] = useState<TurbulenceEnvelopeResult | null>(null);
  const [turbLoading, setTurbLoading] = useState(false);

  // --- EOG state ---
  const [eogVHub, setEogVHub] = useState(12);
  const [eogResult, setEogResult] = useState<EOGResult | null>(null);
  const [eogLoading, setEogLoading] = useState(false);

  // --- Wind Shear state ---
  const [shearVHub, setShearVHub] = useState(12);
  const [shearExp, setShearExp] = useState(0.2);
  const [shearResult, setShearResult] = useState<WindShearResult | null>(null);
  const [shearLoading, setShearLoading] = useState(false);

  // General error
  const [error, setError] = useState<string | null>(null);

  // ── API handlers ────────────────────────────────────────────────────────

  const handleKaimal = useCallback(async () => {
    if (!projectId) return;
    setKaimalLoading(true);
    setError(null);
    try {
      const res = await api.post<KaimalResult>(
        `/projects/${projectId}/wind/kaimal-spectrum`,
        { V_hub: kaimalVHub },
      );
      setKaimalResult(res.data);
      toast.success('Kaimal spectrum computed');
    } catch (err: any) {
      const msg = err?.response?.data?.detail || 'Kaimal spectrum computation failed';
      setError(msg);
      toast.error(msg);
    } finally {
      setKaimalLoading(false);
    }
  }, [projectId, kaimalVHub]);

  const handleTurbulence = useCallback(async () => {
    if (!projectId) return;
    setTurbLoading(true);
    setError(null);
    try {
      const res = await api.post<TurbulenceEnvelopeResult>(
        `/projects/${projectId}/wind/turbulence-envelope`,
        {},
      );
      setTurbResult(res.data);
      toast.success('Turbulence envelope computed');
    } catch (err: any) {
      const msg = err?.response?.data?.detail || 'Turbulence envelope computation failed';
      setError(msg);
      toast.error(msg);
    } finally {
      setTurbLoading(false);
    }
  }, [projectId]);

  const handleEOG = useCallback(async () => {
    if (!projectId) return;
    setEogLoading(true);
    setError(null);
    try {
      const res = await api.post<EOGResult>(
        `/projects/${projectId}/wind/eog`,
        { V_hub: eogVHub, rotor_diameter: 126, hub_height: 90 },
      );
      setEogResult(res.data);
      toast.success('EOG computed');
    } catch (err: any) {
      const msg = err?.response?.data?.detail || 'EOG computation failed';
      setError(msg);
      toast.error(msg);
    } finally {
      setEogLoading(false);
    }
  }, [projectId, eogVHub]);

  const handleShear = useCallback(async () => {
    if (!projectId) return;
    setShearLoading(true);
    setError(null);
    try {
      const res = await api.post<WindShearResult>(
        `/projects/${projectId}/wind/wind-shear`,
        { V_hub: shearVHub, hub_height: 90, shear_exp: shearExp },
      );
      setShearResult(res.data);
      toast.success('Wind shear profile computed');
    } catch (err: any) {
      const msg = err?.response?.data?.detail || 'Wind shear computation failed';
      setError(msg);
      toast.error(msg);
    } finally {
      setShearLoading(false);
    }
  }, [projectId, shearVHub, shearExp]);

  // ── Kaimal chart data ──────────────────────────────────────────────────

  const kaimalTraces = useMemo(() => {
    if (!kaimalResult) return [];
    return [
      {
        x: kaimalResult.frequencies,
        y: kaimalResult.Su,
        type: 'scatter' as const,
        mode: 'lines' as const,
        name: 'Su (u-component)',
        line: { color: COMPONENT_COLORS.u, width: 2 },
      },
      {
        x: kaimalResult.frequencies,
        y: kaimalResult.Sv,
        type: 'scatter' as const,
        mode: 'lines' as const,
        name: 'Sv (v-component)',
        line: { color: COMPONENT_COLORS.v, width: 2 },
      },
      {
        x: kaimalResult.frequencies,
        y: kaimalResult.Sw,
        type: 'scatter' as const,
        mode: 'lines' as const,
        name: 'Sw (w-component)',
        line: { color: COMPONENT_COLORS.w, width: 2 },
      },
    ];
  }, [kaimalResult]);

  const kaimalLayout = useMemo(
    () => ({
      ...basePlotLayout,
      title: {
        text: `Kaimal Turbulence Spectrum (V_hub = ${kaimalVHub} m/s)`,
        font: { size: 12, color: '#e2e8f0' },
      },
      xaxis: {
        title: 'Frequency (Hz)',
        type: 'log' as const,
        gridcolor: 'rgba(100,116,139,0.2)',
        zeroline: false,
      },
      yaxis: {
        title: 'Power Spectral Density S(f) (m\u00b2/s)',
        type: 'log' as const,
        gridcolor: 'rgba(100,116,139,0.2)',
        zeroline: false,
      },
    }),
    [kaimalVHub],
  );

  // ── Turbulence chart data ──────────────────────────────────────────────

  const turbTraces = useMemo(() => {
    if (!turbResult) return [];
    const curves = [
      { label: 'NTM-A', data: turbResult.ntm_A },
      { label: 'NTM-B', data: turbResult.ntm_B },
      { label: 'NTM-C', data: turbResult.ntm_C },
      { label: 'ETM-A', data: turbResult.etm_A },
      { label: 'ETM-B', data: turbResult.etm_B },
      { label: 'ETM-C', data: turbResult.etm_C },
    ];
    return curves.map((curve) => ({
      x: turbResult.wind_speeds,
      y: curve.data,
      type: 'scatter' as const,
      mode: 'lines' as const,
      name: curve.label,
      line: {
        color: TURB_COLORS[curve.label] || '#9ca3af',
        width: 2,
        dash: (TURB_DASHES[curve.label] || 'solid') as Plotly.Dash,
      },
    }));
  }, [turbResult]);

  const turbLayout = useMemo(
    () => ({
      ...basePlotLayout,
      title: {
        text: 'IEC Turbulence Intensity Envelope (NTM solid, ETM dashed)',
        font: { size: 12, color: '#e2e8f0' },
      },
      xaxis: {
        title: 'Wind Speed (m/s)',
        gridcolor: 'rgba(100,116,139,0.2)',
        zeroline: false,
      },
      yaxis: {
        title: 'Turbulence Std Dev \u03c3 (m/s)',
        gridcolor: 'rgba(100,116,139,0.2)',
        zeroline: false,
      },
    }),
    [turbResult],
  );

  // ── EOG chart data ─────────────────────────────────────────────────────

  const eogTraces = useMemo(() => {
    if (!eogResult) return [];
    return [
      {
        x: eogResult.time,
        y: eogResult.wind_speed,
        type: 'scatter' as const,
        mode: 'lines' as const,
        name: `EOG (peak gust = ${eogResult.gust_peak.toFixed(1)} m/s)`,
        line: { color: '#ef4444', width: 2 },
        fill: 'tozeroy' as const,
        fillcolor: 'rgba(239,68,68,0.1)',
      },
    ];
  }, [eogResult]);

  const eogLayout = useMemo(
    () => ({
      ...basePlotLayout,
      title: {
        text: `Extreme Operating Gust (V_hub = ${eogVHub} m/s)`,
        font: { size: 12, color: '#e2e8f0' },
      },
      xaxis: {
        title: 'Time (s)',
        gridcolor: 'rgba(100,116,139,0.2)',
        zeroline: false,
      },
      yaxis: {
        title: 'Wind Speed (m/s)',
        gridcolor: 'rgba(100,116,139,0.2)',
        zeroline: false,
      },
    }),
    [eogVHub],
  );

  // ── Wind Shear chart data ──────────────────────────────────────────────

  const shearTraces = useMemo(() => {
    if (!shearResult) return [];
    return [
      {
        x: shearResult.velocity_powerlaw,
        y: shearResult.heights,
        type: 'scatter' as const,
        mode: 'lines' as const,
        name: 'Power Law',
        line: { color: '#3b82f6', width: 2 },
      },
      {
        x: shearResult.velocity_loglaw,
        y: shearResult.heights,
        type: 'scatter' as const,
        mode: 'lines' as const,
        name: 'Log Law',
        line: { color: '#10b981', width: 2 },
      },
    ];
  }, [shearResult]);

  const shearShapes = useMemo(() => {
    if (!shearResult) return [];
    const xMax = Math.max(
      ...shearResult.velocity_powerlaw,
      ...shearResult.velocity_loglaw,
    ) * 1.1;
    return [
      {
        type: 'line' as const,
        x0: 0,
        x1: xMax,
        y0: 90,
        y1: 90,
        line: {
          color: '#f59e0b',
          width: 1.5,
          dash: 'dash' as const,
        },
      },
    ];
  }, [shearResult]);

  const shearAnnotations = useMemo(() => {
    if (!shearResult) return [];
    return [
      {
        x: 0.02,
        xref: 'paper' as const,
        y: 90,
        yref: 'y' as const,
        text: `Hub Height (${90} m)`,
        showarrow: false,
        font: { size: 10, color: '#f59e0b' },
        xanchor: 'left' as const,
        yanchor: 'bottom' as const,
      },
    ];
  }, [shearResult]);

  const shearLayout = useMemo(
    () => ({
      ...basePlotLayout,
      title: {
        text: `Wind Shear Profile (V_hub = ${shearVHub} m/s, \u03b1 = ${shearExp})`,
        font: { size: 12, color: '#e2e8f0' },
      },
      xaxis: {
        title: 'Wind Speed (m/s)',
        gridcolor: 'rgba(100,116,139,0.2)',
        zeroline: false,
      },
      yaxis: {
        title: 'Height (m)',
        gridcolor: 'rgba(100,116,139,0.2)',
        zeroline: false,
      },
      shapes: shearShapes,
      annotations: shearAnnotations,
    }),
    [shearVHub, shearExp, shearShapes, shearAnnotations],
  );

  const plotConfig = {
    displaylogo: false,
    responsive: true,
    displayModeBar: false,
  };

  // ── Render ─────────────────────────────────────────────────────────────

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-xl font-bold text-slate-100">Wind Environment</h2>
        <p className="text-sm text-slate-400">
          IEC wind condition analysis: spectra, turbulence classes, gusts, and shear profiles
        </p>
      </div>

      {/* Sub-tab navigation */}
      <div className="flex gap-1 rounded-lg bg-surface-dark-secondary border border-slate-700 p-1">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={clsx(
              'flex-1 rounded-md px-3 py-2 text-sm font-medium transition-all',
              activeTab === tab.key
                ? 'bg-accent-600 text-white shadow-sm'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800',
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Error display */}
      {error && (
        <div className="rounded-lg border border-red-800 bg-red-950/30 p-4 text-sm text-red-300">
          {error}
        </div>
      )}

      {/* ──────────────── Kaimal Spectrum Tab ──────────────── */}
      {activeTab === 'kaimal' && (
        <div className="space-y-6">
          <div className="border border-slate-700 bg-surface-dark-secondary rounded-xl p-6">
            <h3 className="text-sm font-semibold text-slate-200 uppercase tracking-wider mb-4">
              Kaimal Spectrum Parameters
            </h3>
            <div className="flex items-end gap-4">
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">
                  Hub Wind Speed (m/s)
                </label>
                <input
                  type="number"
                  value={kaimalVHub}
                  onChange={(e) => setKaimalVHub(Number(e.target.value))}
                  step={0.5}
                  min={1}
                  className="w-full rounded bg-slate-800 border border-slate-600 px-3 py-1.5 text-sm text-slate-100 focus:border-accent-500 focus:outline-none"
                />
              </div>
              <button
                onClick={handleKaimal}
                disabled={kaimalLoading}
                className="px-4 py-2 bg-accent-500 hover:bg-accent-600 text-white text-sm font-medium rounded transition-colors disabled:opacity-50 flex items-center gap-2"
              >
                {kaimalLoading ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Play className="h-4 w-4" />
                )}
                Compute
              </button>
            </div>
          </div>

          {kaimalResult && (
            <div className="border border-slate-700 bg-surface-dark-secondary rounded-xl p-6">
              <div className="min-h-[450px]">
                <Plot
                  data={kaimalTraces as any}
                  layout={kaimalLayout as any}
                  config={plotConfig}
                  style={{ width: '100%', height: '450px' }}
                  useResizeHandler
                />
              </div>
            </div>
          )}
        </div>
      )}

      {/* ──────────────── Turbulence Classes Tab ──────────────── */}
      {activeTab === 'turbulence' && (
        <div className="space-y-6">
          <div className="border border-slate-700 bg-surface-dark-secondary rounded-xl p-6">
            <h3 className="text-sm font-semibold text-slate-200 uppercase tracking-wider mb-4">
              Turbulence Class Envelope
            </h3>
            <p className="text-xs text-slate-400 mb-4">
              Computes NTM and ETM turbulence standard deviation envelopes for IEC classes A, B, C.
              The project's wind class is highlighted.
            </p>
            <button
              onClick={handleTurbulence}
              disabled={turbLoading}
              className="px-4 py-2 bg-accent-500 hover:bg-accent-600 text-white text-sm font-medium rounded transition-colors disabled:opacity-50 flex items-center gap-2"
            >
              {turbLoading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Play className="h-4 w-4" />
              )}
              Compute Envelope
            </button>
          </div>

          {turbResult && (
            <div className="border border-slate-700 bg-surface-dark-secondary rounded-xl p-6">
              <div className="min-h-[450px]">
                <Plot
                  data={turbTraces as any}
                  layout={turbLayout as any}
                  config={plotConfig}
                  style={{ width: '100%', height: '450px' }}
                  useResizeHandler
                />
              </div>
            </div>
          )}
        </div>
      )}

      {/* ──────────────── Extreme Gust (EOG) Tab ──────────────── */}
      {activeTab === 'eog' && (
        <div className="space-y-6">
          <div className="border border-slate-700 bg-surface-dark-secondary rounded-xl p-6">
            <h3 className="text-sm font-semibold text-slate-200 uppercase tracking-wider mb-4">
              Extreme Operating Gust Parameters
            </h3>
            <div className="flex items-end gap-4">
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">
                  Hub Wind Speed (m/s)
                </label>
                <input
                  type="number"
                  value={eogVHub}
                  onChange={(e) => setEogVHub(Number(e.target.value))}
                  step={0.5}
                  min={1}
                  className="w-full rounded bg-slate-800 border border-slate-600 px-3 py-1.5 text-sm text-slate-100 focus:border-accent-500 focus:outline-none"
                />
              </div>
              <button
                onClick={handleEOG}
                disabled={eogLoading}
                className="px-4 py-2 bg-accent-500 hover:bg-accent-600 text-white text-sm font-medium rounded transition-colors disabled:opacity-50 flex items-center gap-2"
              >
                {eogLoading ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Play className="h-4 w-4" />
                )}
                Compute
              </button>
            </div>
          </div>

          {eogResult && (
            <div className="border border-slate-700 bg-surface-dark-secondary rounded-xl p-6">
              <div className="min-h-[450px]">
                <Plot
                  data={eogTraces as any}
                  layout={eogLayout as any}
                  config={plotConfig}
                  style={{ width: '100%', height: '450px' }}
                  useResizeHandler
                />
              </div>
            </div>
          )}
        </div>
      )}

      {/* ──────────────── Wind Shear Tab ──────────────── */}
      {activeTab === 'shear' && (
        <div className="space-y-6">
          <div className="border border-slate-700 bg-surface-dark-secondary rounded-xl p-6">
            <h3 className="text-sm font-semibold text-slate-200 uppercase tracking-wider mb-4">
              Wind Shear Profile Parameters
            </h3>
            <div className="flex items-end gap-4 flex-wrap">
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">
                  Hub Wind Speed (m/s)
                </label>
                <input
                  type="number"
                  value={shearVHub}
                  onChange={(e) => setShearVHub(Number(e.target.value))}
                  step={0.5}
                  min={1}
                  className="w-full rounded bg-slate-800 border border-slate-600 px-3 py-1.5 text-sm text-slate-100 focus:border-accent-500 focus:outline-none"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">
                  Shear Exponent (&alpha;)
                </label>
                <input
                  type="number"
                  value={shearExp}
                  onChange={(e) => setShearExp(Number(e.target.value))}
                  step={0.01}
                  min={0}
                  max={1}
                  className="w-full rounded bg-slate-800 border border-slate-600 px-3 py-1.5 text-sm text-slate-100 focus:border-accent-500 focus:outline-none"
                />
              </div>
              <button
                onClick={handleShear}
                disabled={shearLoading}
                className="px-4 py-2 bg-accent-500 hover:bg-accent-600 text-white text-sm font-medium rounded transition-colors disabled:opacity-50 flex items-center gap-2"
              >
                {shearLoading ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Play className="h-4 w-4" />
                )}
                Compute
              </button>
            </div>
          </div>

          {shearResult && (
            <div className="border border-slate-700 bg-surface-dark-secondary rounded-xl p-6">
              <div className="min-h-[450px]">
                <Plot
                  data={shearTraces as any}
                  layout={shearLayout as any}
                  config={plotConfig}
                  style={{ width: '100%', height: '450px' }}
                  useResizeHandler
                />
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
