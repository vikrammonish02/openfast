import { useState, useCallback, useMemo } from 'react';
import { useParams } from 'react-router-dom';
import { Droplets, Waves, Anchor, Loader2 } from 'lucide-react';
import toast from 'react-hot-toast';
import Plot from 'react-plotly.js';
import axios from 'axios';

// ---------------------------------------------------------------------------
// API helper -- use the same token convention as client.ts but call directly
// so we don't need to modify client.ts right now.
// ---------------------------------------------------------------------------

const API_BASE =
  (window as unknown as Record<string, string>).__WINDFORGE_API_URL__
    ? `${(window as unknown as Record<string, string>).__WINDFORGE_API_URL__}/api/v1`
    : '/api/v1';

function hydroPost<T>(projectId: string, endpoint: string, data: unknown): Promise<T> {
  const token = localStorage.getItem('windforge_token');
  return axios
    .post<T>(`${API_BASE}/projects/${projectId}/hydro/${endpoint}`, data, {
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
  { key: 'jonswap', label: 'JONSWAP Spectrum', icon: Waves },
  { key: 'kinematics', label: 'Wave Kinematics', icon: Droplets },
  { key: 'morison', label: 'Morison Loads', icon: Anchor },
  { key: 'hydrostatic', label: 'Hydrostatics', icon: Droplets },
] as const;

type TabKey = (typeof TABS)[number]['key'];

// ---------------------------------------------------------------------------
// Result types
// ---------------------------------------------------------------------------

interface JonswapResult {
  frequencies: number[];
  spectral_density: number[];
}

interface WaveKinematicsResult {
  time: number[];
  elevation: number[];
  depths: number[];
  velocity_x: number[][];  // depths x time
}

interface MorisonResult {
  time: number[];
  base_shear: number[];
  overturning_moment: number[];
}

interface HydrostaticResult {
  stiffness_matrix: number[][];
  added_mass_matrix: number[][];
}

// ---------------------------------------------------------------------------
// Dark theme Plotly layout factory (matches CampbellDiagram.tsx)
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
  unit,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
  step?: number;
  min?: number;
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
        className="bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-sm text-slate-100 w-full focus:ring-1 focus:ring-accent-500 focus:border-accent-500"
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// 6-DOF labels for hydrostatic matrices
// ---------------------------------------------------------------------------

const DOF_LABELS = ['Surge', 'Sway', 'Heave', 'Roll', 'Pitch', 'Yaw'];

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function HydroPage() {
  const { projectId } = useParams<{ projectId: string }>();

  // Active sub-tab
  const [activeTab, setActiveTab] = useState<TabKey>('jonswap');

  // ── JONSWAP inputs & results ────────────────────────────────────────────
  const [jonswapHs, setJonswapHs] = useState(2.0);
  const [jonswapTp, setJonswapTp] = useState(8.0);
  const [jonswapResult, setJonswapResult] = useState<JonswapResult | null>(null);
  const [jonswapLoading, setJonswapLoading] = useState(false);

  // ── Wave Kinematics inputs & results ────────────────────────────────────
  const [kinHs, setKinHs] = useState(2.0);
  const [kinTp, setKinTp] = useState(8.0);
  const [kinDepth, setKinDepth] = useState(30);
  const [kinDuration, setKinDuration] = useState(60);
  const [kinResult, setKinResult] = useState<WaveKinematicsResult | null>(null);
  const [kinLoading, setKinLoading] = useState(false);

  // ── Morison inputs & results ────────────────────────────────────────────
  const [morHs, setMorHs] = useState(2.0);
  const [morTp, setMorTp] = useState(8.0);
  const [morDepth, setMorDepth] = useState(30);
  const [morDiameter, setMorDiameter] = useState(6.0);
  const [morCd, setMorCd] = useState(1.0);
  const [morCm, setMorCm] = useState(2.0);
  const [morResult, setMorResult] = useState<MorisonResult | null>(null);
  const [morLoading, setMorLoading] = useState(false);

  // ── Hydrostatic inputs & results ────────────────────────────────────────
  const [hsRadius, setHsRadius] = useState(5.0);
  const [hsZBottom, setHsZBottom] = useState(-30.0);
  const [hsZTop, setHsZTop] = useState(10.0);
  const [hsMass, setHsMass] = useState(500000);
  const [hsResult, setHsResult] = useState<HydrostaticResult | null>(null);
  const [hsLoading, setHsLoading] = useState(false);

  // ── Error state ─────────────────────────────────────────────────────────
  const [error, setError] = useState<string | null>(null);

  // ── Compute handlers ────────────────────────────────────────────────────

  const handleComputeJonswap = useCallback(async () => {
    if (!projectId) return;
    setJonswapLoading(true);
    setError(null);
    setJonswapResult(null);
    try {
      const result = await hydroPost<JonswapResult>(projectId, 'jonswap-spectrum', {
        hs: jonswapHs,
        tp: jonswapTp,
      });
      setJonswapResult(result);
      toast.success('JONSWAP spectrum computed');
    } catch (err: any) {
      const msg = err?.response?.data?.detail || 'JONSWAP computation failed';
      setError(msg);
      toast.error(msg);
    } finally {
      setJonswapLoading(false);
    }
  }, [projectId, jonswapHs, jonswapTp]);

  const handleComputeKinematics = useCallback(async () => {
    if (!projectId) return;
    setKinLoading(true);
    setError(null);
    setKinResult(null);
    try {
      const result = await hydroPost<WaveKinematicsResult>(projectId, 'wave-kinematics', {
        hs: kinHs,
        tp: kinTp,
        water_depth: kinDepth,
        duration: kinDuration,
      });
      setKinResult(result);
      toast.success('Wave kinematics computed');
    } catch (err: any) {
      const msg = err?.response?.data?.detail || 'Wave kinematics computation failed';
      setError(msg);
      toast.error(msg);
    } finally {
      setKinLoading(false);
    }
  }, [projectId, kinHs, kinTp, kinDepth, kinDuration]);

  const handleComputeMorison = useCallback(async () => {
    if (!projectId) return;
    setMorLoading(true);
    setError(null);
    setMorResult(null);
    try {
      const result = await hydroPost<MorisonResult>(projectId, 'morison-loads', {
        hs: morHs,
        tp: morTp,
        water_depth: morDepth,
        monopile_diameter: morDiameter,
        cd: morCd,
        cm: morCm,
      });
      setMorResult(result);
      toast.success('Morison loads computed');
    } catch (err: any) {
      const msg = err?.response?.data?.detail || 'Morison loads computation failed';
      setError(msg);
      toast.error(msg);
    } finally {
      setMorLoading(false);
    }
  }, [projectId, morHs, morTp, morDepth, morDiameter, morCd, morCm]);

  const handleComputeHydrostatic = useCallback(async () => {
    if (!projectId) return;
    setHsLoading(true);
    setError(null);
    setHsResult(null);
    try {
      const result = await hydroPost<HydrostaticResult>(projectId, 'hydrostatic', {
        radius: hsRadius,
        z_bottom: hsZBottom,
        z_top: hsZTop,
        mass: hsMass,
      });
      setHsResult(result);
      toast.success('Hydrostatic properties computed');
    } catch (err: any) {
      const msg = err?.response?.data?.detail || 'Hydrostatic computation failed';
      setError(msg);
      toast.error(msg);
    } finally {
      setHsLoading(false);
    }
  }, [projectId, hsRadius, hsZBottom, hsZTop, hsMass]);

  // ── Loading flag for current tab ────────────────────────────────────────

  const isLoading =
    (activeTab === 'jonswap' && jonswapLoading) ||
    (activeTab === 'kinematics' && kinLoading) ||
    (activeTab === 'morison' && morLoading) ||
    (activeTab === 'hydrostatic' && hsLoading);

  // ── JONSWAP plot traces ─────────────────────────────────────────────────

  const jonswapTraces = useMemo(() => {
    if (!jonswapResult) return [];
    return [
      {
        x: jonswapResult.frequencies,
        y: jonswapResult.spectral_density,
        type: 'scatter' as const,
        mode: 'lines' as const,
        name: 'S(f)',
        fill: 'tozeroy' as const,
        line: { color: '#3b82f6', width: 2 },
        fillcolor: 'rgba(59,130,246,0.15)',
      },
    ];
  }, [jonswapResult]);

  const jonswapLayout = useMemo(
    () =>
      makePlotLayout({
        xaxis: { title: 'Frequency (Hz)' },
        yaxis: { title: 'Spectral Density S(f) (m\u00b2/Hz)' },
        showlegend: false,
      }),
    [],
  );

  // ── Wave kinematics plot traces ─────────────────────────────────────────

  const elevationTraces = useMemo(() => {
    if (!kinResult) return [];
    return [
      {
        x: kinResult.time,
        y: kinResult.elevation,
        type: 'scatter' as const,
        mode: 'lines' as const,
        name: 'Surface Elevation',
        line: { color: '#06b6d4', width: 1.5 },
      },
    ];
  }, [kinResult]);

  const elevationLayout = useMemo(
    () =>
      makePlotLayout({
        xaxis: { title: 'Time (s)' },
        yaxis: { title: 'Elevation (m)' },
        showlegend: false,
        margin: { t: 30, r: 30, b: 50, l: 60 },
      }),
    [],
  );

  const velocityHeatmapTraces = useMemo(() => {
    if (!kinResult) return [];
    return [
      {
        x: kinResult.time,
        y: kinResult.depths,
        z: kinResult.velocity_x,
        type: 'heatmap' as const,
        colorscale: 'Viridis',
        colorbar: {
          title: 'u (m/s)',
          titlefont: { size: 10, color: '#9ca3af' },
          tickfont: { size: 9, color: '#9ca3af' },
        },
      },
    ];
  }, [kinResult]);

  const velocityLayout = useMemo(
    () =>
      makePlotLayout({
        xaxis: { title: 'Time (s)' },
        yaxis: { title: 'Depth (m)' },
        showlegend: false,
        margin: { t: 30, r: 80, b: 50, l: 60 },
      }),
    [],
  );

  // ── Morison plot traces ─────────────────────────────────────────────────

  const shearTraces = useMemo(() => {
    if (!morResult) return [];
    return [
      {
        x: morResult.time,
        y: morResult.base_shear,
        type: 'scatter' as const,
        mode: 'lines' as const,
        name: 'Base Shear',
        line: { color: '#f59e0b', width: 1.5 },
      },
    ];
  }, [morResult]);

  const shearLayout = useMemo(
    () =>
      makePlotLayout({
        xaxis: { title: 'Time (s)' },
        yaxis: { title: 'Base Shear (kN)' },
        showlegend: false,
        margin: { t: 30, r: 30, b: 50, l: 70 },
      }),
    [],
  );

  const momentTraces = useMemo(() => {
    if (!morResult) return [];
    return [
      {
        x: morResult.time,
        y: morResult.overturning_moment,
        type: 'scatter' as const,
        mode: 'lines' as const,
        name: 'Overturning Moment',
        line: { color: '#ef4444', width: 1.5 },
      },
    ];
  }, [morResult]);

  const momentLayout = useMemo(
    () =>
      makePlotLayout({
        xaxis: { title: 'Time (s)' },
        yaxis: { title: 'Overturning Moment (kN\u00b7m)' },
        showlegend: false,
        margin: { t: 30, r: 30, b: 50, l: 80 },
      }),
    [],
  );

  // ── Plotly config (shared) ──────────────────────────────────────────────

  const plotConfig = useMemo(
    () => ({
      displaylogo: false,
      responsive: true,
      displayModeBar: false,
    }),
    [],
  );

  // ── Render helpers ──────────────────────────────────────────────────────

  const renderComputeButton = (onClick: () => void, label: string) => (
    <button
      onClick={onClick}
      disabled={isLoading || !projectId}
      className="bg-accent-500 hover:bg-accent-600 text-white rounded-lg px-5 py-2.5 text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 mt-4 w-full justify-center"
    >
      {isLoading ? (
        <Loader2 className="h-4 w-4 animate-spin" />
      ) : (
        <Waves className="h-4 w-4" />
      )}
      {isLoading ? 'Computing...' : label}
    </button>
  );

  const renderMatrix = (matrix: number[][], title: string) => (
    <div>
      <h4 className="text-sm font-semibold text-slate-200 mb-3">{title}</h4>
      <div className="overflow-x-auto rounded-lg border border-slate-700">
        <table className="min-w-full text-sm">
          <thead className="bg-slate-800">
            <tr>
              <th className="px-3 py-2 text-left text-xs font-medium text-slate-400 uppercase" />
              {DOF_LABELS.map((label) => (
                <th
                  key={label}
                  className="px-3 py-2 text-right text-xs font-medium text-slate-400 uppercase whitespace-nowrap"
                >
                  {label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {matrix.map((row, i) => (
              <tr key={i} className={i % 2 === 0 ? 'bg-slate-800/50' : ''}>
                <td className="px-3 py-2 text-slate-200 font-mono text-xs font-medium whitespace-nowrap">
                  {DOF_LABELS[i]}
                </td>
                {row.map((val, j) => (
                  <td
                    key={j}
                    className="px-3 py-2 text-right text-slate-300 font-mono text-xs"
                  >
                    {val.toExponential(3)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );

  // ── Tab content renderers ───────────────────────────────────────────────

  const renderJonswapTab = () => (
    <div className="grid grid-cols-1 xl:grid-cols-4 gap-6">
      {/* Left: Inputs */}
      <div className="xl:col-span-1">
        <div className="border border-slate-700 bg-surface-dark-secondary rounded-xl p-5">
          <h3 className="text-sm font-semibold text-slate-200 uppercase tracking-wider mb-4">
            Spectrum Parameters
          </h3>
          <div className="space-y-4">
            <NumberInput
              label="Significant Wave Height"
              unit="m"
              value={jonswapHs}
              onChange={setJonswapHs}
              step={0.5}
              min={0.1}
            />
            <NumberInput
              label="Peak Period"
              unit="s"
              value={jonswapTp}
              onChange={setJonswapTp}
              step={0.5}
              min={1}
            />
          </div>
          {renderComputeButton(handleComputeJonswap, 'Compute Spectrum')}
        </div>
      </div>

      {/* Right: Plot */}
      <div className="xl:col-span-3">
        <div className="border border-slate-700 bg-surface-dark-secondary rounded-xl p-5">
          <h3 className="text-sm font-semibold text-slate-200 uppercase tracking-wider mb-4">
            JONSWAP Spectral Density
          </h3>
          {jonswapResult ? (
            <div className="min-h-[400px]">
              <Plot
                data={jonswapTraces as any}
                layout={jonswapLayout}
                config={plotConfig}
                style={{ width: '100%', height: '400px' }}
                useResizeHandler
              />
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center rounded-lg border-2 border-dashed border-slate-600 py-20">
              <Waves className="h-10 w-10 text-slate-500 mb-3" />
              <p className="text-sm text-slate-400">
                Configure parameters and compute the JONSWAP spectrum.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );

  const renderKinematicsTab = () => (
    <div className="grid grid-cols-1 xl:grid-cols-4 gap-6">
      {/* Left: Inputs */}
      <div className="xl:col-span-1">
        <div className="border border-slate-700 bg-surface-dark-secondary rounded-xl p-5">
          <h3 className="text-sm font-semibold text-slate-200 uppercase tracking-wider mb-4">
            Wave Parameters
          </h3>
          <div className="space-y-4">
            <NumberInput label="Significant Wave Height" unit="m" value={kinHs} onChange={setKinHs} step={0.5} min={0.1} />
            <NumberInput label="Peak Period" unit="s" value={kinTp} onChange={setKinTp} step={0.5} min={1} />
            <NumberInput label="Water Depth" unit="m" value={kinDepth} onChange={setKinDepth} step={5} min={1} />
            <NumberInput label="Duration" unit="s" value={kinDuration} onChange={setKinDuration} step={10} min={10} />
          </div>
          {renderComputeButton(handleComputeKinematics, 'Compute Kinematics')}
        </div>
      </div>

      {/* Right: Plots */}
      <div className="xl:col-span-3 space-y-6">
        {/* Elevation time series */}
        <div className="border border-slate-700 bg-surface-dark-secondary rounded-xl p-5">
          <h3 className="text-sm font-semibold text-slate-200 uppercase tracking-wider mb-4">
            Surface Elevation
          </h3>
          {kinResult ? (
            <div className="min-h-[250px]">
              <Plot
                data={elevationTraces as any}
                layout={elevationLayout}
                config={plotConfig}
                style={{ width: '100%', height: '250px' }}
                useResizeHandler
              />
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center rounded-lg border-2 border-dashed border-slate-600 py-12">
              <Droplets className="h-8 w-8 text-slate-500 mb-2" />
              <p className="text-sm text-slate-400">Elevation time series will appear here.</p>
            </div>
          )}
        </div>

        {/* Velocity heatmap */}
        <div className="border border-slate-700 bg-surface-dark-secondary rounded-xl p-5">
          <h3 className="text-sm font-semibold text-slate-200 uppercase tracking-wider mb-4">
            Horizontal Velocity (Depth vs Time)
          </h3>
          {kinResult ? (
            <div className="min-h-[300px]">
              <Plot
                data={velocityHeatmapTraces as any}
                layout={velocityLayout}
                config={plotConfig}
                style={{ width: '100%', height: '300px' }}
                useResizeHandler
              />
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center rounded-lg border-2 border-dashed border-slate-600 py-12">
              <Waves className="h-8 w-8 text-slate-500 mb-2" />
              <p className="text-sm text-slate-400">Velocity heatmap will appear here.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );

  const renderMorisonTab = () => (
    <div className="grid grid-cols-1 xl:grid-cols-4 gap-6">
      {/* Left: Inputs */}
      <div className="xl:col-span-1">
        <div className="border border-slate-700 bg-surface-dark-secondary rounded-xl p-5">
          <h3 className="text-sm font-semibold text-slate-200 uppercase tracking-wider mb-4">
            Morison Parameters
          </h3>
          <div className="space-y-4">
            <NumberInput label="Significant Wave Height" unit="m" value={morHs} onChange={setMorHs} step={0.5} min={0.1} />
            <NumberInput label="Peak Period" unit="s" value={morTp} onChange={setMorTp} step={0.5} min={1} />
            <NumberInput label="Water Depth" unit="m" value={morDepth} onChange={setMorDepth} step={5} min={1} />
            <NumberInput label="Monopile Diameter" unit="m" value={morDiameter} onChange={setMorDiameter} step={0.5} min={0.5} />
            <NumberInput label="Drag Coefficient Cd" value={morCd} onChange={setMorCd} step={0.1} min={0} />
            <NumberInput label="Inertia Coefficient Cm" value={morCm} onChange={setMorCm} step={0.1} min={0} />
          </div>
          {renderComputeButton(handleComputeMorison, 'Compute Loads')}
        </div>
      </div>

      {/* Right: Plots */}
      <div className="xl:col-span-3 space-y-6">
        {/* Base shear */}
        <div className="border border-slate-700 bg-surface-dark-secondary rounded-xl p-5">
          <h3 className="text-sm font-semibold text-slate-200 uppercase tracking-wider mb-4">
            Base Shear
          </h3>
          {morResult ? (
            <div className="min-h-[250px]">
              <Plot
                data={shearTraces as any}
                layout={shearLayout}
                config={plotConfig}
                style={{ width: '100%', height: '250px' }}
                useResizeHandler
              />
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center rounded-lg border-2 border-dashed border-slate-600 py-12">
              <Anchor className="h-8 w-8 text-slate-500 mb-2" />
              <p className="text-sm text-slate-400">Base shear time series will appear here.</p>
            </div>
          )}
        </div>

        {/* Overturning moment */}
        <div className="border border-slate-700 bg-surface-dark-secondary rounded-xl p-5">
          <h3 className="text-sm font-semibold text-slate-200 uppercase tracking-wider mb-4">
            Overturning Moment
          </h3>
          {morResult ? (
            <div className="min-h-[250px]">
              <Plot
                data={momentTraces as any}
                layout={momentLayout}
                config={plotConfig}
                style={{ width: '100%', height: '250px' }}
                useResizeHandler
              />
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center rounded-lg border-2 border-dashed border-slate-600 py-12">
              <Anchor className="h-8 w-8 text-slate-500 mb-2" />
              <p className="text-sm text-slate-400">Overturning moment time series will appear here.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );

  const renderHydrostaticTab = () => (
    <div className="grid grid-cols-1 xl:grid-cols-4 gap-6">
      {/* Left: Inputs */}
      <div className="xl:col-span-1">
        <div className="border border-slate-700 bg-surface-dark-secondary rounded-xl p-5">
          <h3 className="text-sm font-semibold text-slate-200 uppercase tracking-wider mb-4">
            Body Parameters
          </h3>
          <div className="space-y-4">
            <NumberInput label="Radius" unit="m" value={hsRadius} onChange={setHsRadius} step={0.5} min={0.1} />
            <NumberInput label="Z Bottom" unit="m" value={hsZBottom} onChange={setHsZBottom} step={5} />
            <NumberInput label="Z Top" unit="m" value={hsZTop} onChange={setHsZTop} step={5} />
            <NumberInput label="Mass" unit="kg" value={hsMass} onChange={setHsMass} step={10000} min={0} />
          </div>
          {renderComputeButton(handleComputeHydrostatic, 'Compute Properties')}
        </div>
      </div>

      {/* Right: Matrices */}
      <div className="xl:col-span-3 space-y-6">
        {hsResult ? (
          <>
            <div className="border border-slate-700 bg-surface-dark-secondary rounded-xl p-5">
              {renderMatrix(hsResult.stiffness_matrix, 'Hydrostatic Stiffness Matrix (6 x 6)')}
            </div>
            <div className="border border-slate-700 bg-surface-dark-secondary rounded-xl p-5">
              {renderMatrix(hsResult.added_mass_matrix, 'Added Mass Matrix (6 x 6)')}
            </div>
          </>
        ) : (
          <div className="border border-slate-700 bg-surface-dark-secondary rounded-xl p-5">
            <div className="flex flex-col items-center justify-center rounded-lg border-2 border-dashed border-slate-600 py-20">
              <Droplets className="h-10 w-10 text-slate-500 mb-3" />
              <p className="text-sm text-slate-400">
                Configure body parameters and compute hydrostatic properties.
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );

  // ── Main render ─────────────────────────────────────────────────────────

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-xl font-bold text-slate-100">Hydrodynamics</h2>
        <p className="text-sm text-slate-400">
          Wave spectra, kinematics, Morison loads, and hydrostatic analysis
        </p>
      </div>

      {/* Sub-tab selector (pill buttons) */}
      <div className="flex flex-wrap gap-2">
        {TABS.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.key;
          return (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={
                isActive
                  ? 'flex items-center gap-2 rounded-full px-4 py-2 text-sm font-medium bg-accent-500 text-white shadow-md transition-all'
                  : 'flex items-center gap-2 rounded-full px-4 py-2 text-sm font-medium bg-slate-800 text-slate-400 hover:bg-slate-700 hover:text-slate-200 border border-slate-700 transition-all'
              }
            >
              <Icon className="h-4 w-4" />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Inline error */}
      {error && (
        <div className="rounded-lg border border-red-700/50 bg-red-900/20 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {/* Tab content */}
      {activeTab === 'jonswap' && renderJonswapTab()}
      {activeTab === 'kinematics' && renderKinematicsTab()}
      {activeTab === 'morison' && renderMorisonTab()}
      {activeTab === 'hydrostatic' && renderHydrostaticTab()}
    </div>
  );
}
