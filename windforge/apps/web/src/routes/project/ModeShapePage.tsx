import { useState, useEffect, useCallback, useMemo } from 'react';
import { useParams } from 'react-router-dom';
import { turbineModelsApi } from '@/api/client';
import api from '@/api/client';
import type { TurbineModel } from '@/types';
import { Spline, Loader2, Play } from 'lucide-react';
import toast from 'react-hot-toast';
import Plot from 'react-plotly.js';
import clsx from 'clsx';

// ---------------------------------------------------------------------------
// Color palette
// ---------------------------------------------------------------------------

const MODE_PALETTE = [
  '#10b981', '#3b82f6', '#f59e0b', '#ef4444', '#8b5cf6',
  '#ec4899', '#06b6d4', '#84cc16', '#f97316', '#6366f1',
];

// ---------------------------------------------------------------------------
// Sub-tabs
// ---------------------------------------------------------------------------

const TABS = [
  { key: 'component', label: 'Component Modes' },
  { key: 'beam', label: 'Beam Theory' },
  { key: 'fem', label: 'FEM vs Theory' },
] as const;

type TabKey = (typeof TABS)[number]['key'];

const BC_OPTIONS = [
  { value: 'unloaded-clamped-free', label: 'Clamped-Free (cantilever)' },
  { value: 'unloaded-clamped-clamped', label: 'Clamped-Clamped' },
  { value: 'unloaded-hinged-hinged', label: 'Hinged-Hinged (simply supported)' },
  { value: 'unloaded-clamped-hinged', label: 'Clamped-Hinged' },
  { value: 'unloaded-hinged-free', label: 'Hinged-Free' },
  { value: 'unloaded-free-free', label: 'Free-Free' },
];

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ModeShape {
  frequency: number;
  label: string;
  shape_values: number[];
  shape_values_edge?: number[];
}

interface ModeShapeResult {
  span_positions: number[];
  modes: ModeShape[];
}

interface BeamTheoryMode {
  frequency: number;
  label: string;
  shape_values: number[];
}

interface BeamTheoryResult {
  x: number[];
  frequencies: number[];
  modes: BeamTheoryMode[];
}

interface FemCompareResult {
  x_theory: number[];
  x_fem: number[];
  frequencies_theory: number[];
  frequencies_fem: number[];
  modes_theory: BeamTheoryMode[];
  modes_fem: BeamTheoryMode[];
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

const gridStyle = {
  gridcolor: 'rgba(100,116,139,0.2)',
  zeroline: true,
  zerolinecolor: 'rgba(100,116,139,0.4)',
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function ModeShapePage() {
  const { projectId } = useParams<{ projectId: string }>();

  // Tab state
  const [activeTab, setActiveTab] = useState<TabKey>('component');

  // Turbine model state
  const [turbineModels, setTurbineModels] = useState<TurbineModel[]>([]);
  const [turbineModelId, setTurbineModelId] = useState<string>('');
  const [loadingModels, setLoadingModels] = useState(true);

  // Config state (component modes)
  const [component, setComponent] = useState<'tower' | 'blade'>('tower');
  const [nModes, setNModes] = useState(5);
  const [includeTipMass, setIncludeTipMass] = useState(true);

  // Results (component modes)
  const [result, setResult] = useState<ModeShapeResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Beam Theory state
  const [btBC, setBtBC] = useState('unloaded-clamped-free');
  const [btEI, setBtEI] = useState(2.1e8);
  const [btRho, setBtRho] = useState(7850);
  const [btA, setBtA] = useState(0.01);
  const [btL, setBtL] = useState(10);
  const [btNModes, setBtNModes] = useState(4);
  const [btMtop, setBtMtop] = useState(0);
  const [btResult, setBtResult] = useState<BeamTheoryResult | null>(null);
  const [btLoading, setBtLoading] = useState(false);

  // FEM Compare state
  const [femEI, setFemEI] = useState(2.1e8);
  const [femRho, setFemRho] = useState(7850);
  const [femA, setFemA] = useState(0.01);
  const [femL, setFemL] = useState(10);
  const [femNModes, setFemNModes] = useState(4);
  const [femNElements, setFemNElements] = useState(20);
  const [femResult, setFemResult] = useState<FemCompareResult | null>(null);
  const [femLoading, setFemLoading] = useState(false);

  // ── Fetch turbine models on mount ────────────────────────────────────────

  useEffect(() => {
    if (!projectId) return;
    setLoadingModels(true);
    turbineModelsApi
      .list(projectId)
      .then((models) => {
        setTurbineModels(models);
        if (models.length > 0 && !turbineModelId) {
          setTurbineModelId(models[0].id);
        }
      })
      .catch(() => {
        toast.error('Failed to load turbine models');
      })
      .finally(() => setLoadingModels(false));
  }, [projectId]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Compute component mode shapes ─────────────────────────────────────

  const handleCompute = useCallback(async () => {
    if (!projectId || !turbineModelId) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await api.post<ModeShapeResult>(
        `/projects/${projectId}/modeshape/compute`,
        {
          turbine_model_id: turbineModelId,
          component,
          n_modes: nModes,
          include_tip_mass: includeTipMass,
        },
      );
      setResult(res.data);
      toast.success('Mode shapes computed');
    } catch (err: any) {
      const msg = err?.response?.data?.detail || 'Mode shape computation failed';
      setError(msg);
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  }, [projectId, turbineModelId, component, nModes, includeTipMass]);

  // ── Beam Theory compute ───────────────────────────────────────────────

  const handleBeamTheory = useCallback(async () => {
    if (!projectId) return;
    setBtLoading(true);
    setError(null);
    setBtResult(null);
    try {
      const res = await api.post<BeamTheoryResult>(
        `/projects/${projectId}/modeshape/beam-theory`,
        { BC_type: btBC, EI: btEI, rho: btRho, A: btA, L: btL, n_modes: btNModes, Mtop: btMtop },
      );
      setBtResult(res.data);
      toast.success('Beam theory modes computed');
    } catch (err: any) {
      const msg = err?.response?.data?.detail || 'Beam theory computation failed';
      setError(msg);
      toast.error(msg);
    } finally {
      setBtLoading(false);
    }
  }, [projectId, btBC, btEI, btRho, btA, btL, btNModes, btMtop]);

  // ── FEM Compare compute ───────────────────────────────────────────────

  const handleFemCompare = useCallback(async () => {
    if (!projectId) return;
    setFemLoading(true);
    setError(null);
    setFemResult(null);
    try {
      const res = await api.post<FemCompareResult>(
        `/projects/${projectId}/modeshape/fem-compare`,
        { EI: femEI, rho: femRho, A: femA, L: femL, n_modes: femNModes, n_elements: femNElements },
      );
      setFemResult(res.data);
      toast.success('FEM vs Theory comparison computed');
    } catch (err: any) {
      const msg = err?.response?.data?.detail || 'FEM comparison failed';
      setError(msg);
      toast.error(msg);
    } finally {
      setFemLoading(false);
    }
  }, [projectId, femEI, femRho, femA, femL, femNModes, femNElements]);

  // ── Build Plotly traces: Flapwise / main chart ──────────────────────────

  const flapTraces = useMemo(() => {
    if (!result) return [];
    return result.modes.map((mode, i) => ({
      x: result.span_positions,
      y: mode.shape_values,
      type: 'scatter' as const,
      mode: 'lines' as const,
      name: mode.label,
      line: {
        color: MODE_PALETTE[i % MODE_PALETTE.length],
        width: 2,
      },
    }));
  }, [result]);

  // ── Build Plotly traces: Edgewise (blade only) ──────────────────────────

  const edgeTraces = useMemo(() => {
    if (!result || component !== 'blade') return [];
    return result.modes
      .filter((m) => m.shape_values_edge && m.shape_values_edge.length > 0)
      .map((mode, i) => ({
        x: result.span_positions,
        y: mode.shape_values_edge!,
        type: 'scatter' as const,
        mode: 'lines' as const,
        name: mode.label,
        line: {
          color: MODE_PALETTE[i % MODE_PALETTE.length],
          width: 2,
        },
      }));
  }, [result, component]);

  const hasBothCharts = component === 'blade' && edgeTraces.length > 0;

  // ── Chart layouts ───────────────────────────────────────────────────────

  const flapLayout = useMemo(
    () => ({
      ...basePlotLayout,
      title: {
        text: component === 'blade' ? 'Flapwise Mode Shapes' : 'Mode Shapes',
        font: { size: 12, color: '#e2e8f0' },
      },
      xaxis: {
        title: 'Span Position (m)',
        ...gridStyle,
      },
      yaxis: {
        title: 'Normalized Displacement',
        ...gridStyle,
      },
    }),
    [component],
  );

  const edgeLayout = useMemo(
    () => ({
      ...basePlotLayout,
      title: {
        text: 'Edgewise Mode Shapes',
        font: { size: 12, color: '#e2e8f0' },
      },
      xaxis: {
        title: 'Span Position (m)',
        ...gridStyle,
      },
      yaxis: {
        title: 'Normalized Displacement',
        ...gridStyle,
      },
    }),
    [],
  );

  // ── Beam Theory traces ────────────────────────────────────────────────

  const btTraces = useMemo(() => {
    if (!btResult) return [];
    return btResult.modes.map((mode, i) => ({
      x: btResult.x,
      y: mode.shape_values,
      type: 'scatter' as const,
      mode: 'lines' as const,
      name: `${mode.label} (${mode.frequency.toFixed(2)} Hz)`,
      line: { color: MODE_PALETTE[i % MODE_PALETTE.length], width: 2 },
    }));
  }, [btResult]);

  // ── FEM Compare traces ────────────────────────────────────────────────

  const femTraces = useMemo(() => {
    if (!femResult) return [];
    const traces: any[] = [];
    const nM = Math.min(femResult.modes_theory.length, femResult.modes_fem.length);
    for (let i = 0; i < nM; i++) {
      const color = MODE_PALETTE[i % MODE_PALETTE.length];
      traces.push({
        x: femResult.x_theory,
        y: femResult.modes_theory[i].shape_values,
        type: 'scatter' as const,
        mode: 'lines' as const,
        name: `Theory Mode ${i + 1}`,
        line: { color, width: 2 },
      });
      traces.push({
        x: femResult.x_fem,
        y: femResult.modes_fem[i].shape_values,
        type: 'scatter' as const,
        mode: 'markers' as const,
        name: `FEM Mode ${i + 1}`,
        marker: { color, size: 5, symbol: 'circle' },
      });
    }
    return traces;
  }, [femResult]);

  const plotConfig = {
    displaylogo: false,
    responsive: true,
    displayModeBar: false,
  };

  // ── Loading / empty states ──────────────────────────────────────────────

  if (loadingModels) {
    return (
      <div className="flex items-center justify-center py-24">
        <Loader2 className="h-8 w-8 animate-spin text-accent-500" />
      </div>
    );
  }

  // ── Render ─────────────────────────────────────────────────────────────

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-xl font-bold text-slate-100">Mode Shapes</h2>
        <p className="text-sm text-slate-400">
          Structural mode shapes, beam theory analysis, and FEM comparison
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

      {/* ──────────────── Component Modes Tab ──────────────── */}
      {activeTab === 'component' && (
        <>
          {turbineModels.length === 0 ? (
            <div className="flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-600 py-16">
              <Spline className="h-12 w-12 text-slate-300 mb-3" />
              <h3 className="text-base font-semibold text-slate-200">
                No turbine models available
              </h3>
              <p className="mt-1 text-sm text-slate-400">
                Create a turbine model in the Assembly tab to compute mode shapes.
              </p>
            </div>
          ) : (
            <>
              {/* Configuration panel */}
              <div className="border border-slate-700 bg-surface-dark-secondary rounded-xl p-6">
                <h3 className="text-sm font-semibold text-slate-200 uppercase tracking-wider mb-4">
                  Configuration
                </h3>

                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-5">
                  {/* Turbine model selector */}
                  <div>
                    <label className="block text-xs font-medium text-slate-400 mb-1">
                      Turbine Model
                    </label>
                    <select
                      value={turbineModelId}
                      onChange={(e) => setTurbineModelId(e.target.value)}
                      className="w-full rounded bg-slate-800 border border-slate-600 px-3 py-1.5 text-sm text-slate-100 focus:border-accent-500 focus:outline-none"
                    >
                      {turbineModels.map((model) => (
                        <option key={model.id} value={model.id}>
                          {model.name}
                        </option>
                      ))}
                    </select>
                  </div>

                  {/* Component toggle */}
                  <div>
                    <label className="block text-xs font-medium text-slate-400 mb-1">
                      Component
                    </label>
                    <div className="flex gap-1 rounded-lg bg-slate-800 p-1">
                      <button
                        onClick={() => setComponent('tower')}
                        className={clsx(
                          'flex-1 rounded-md px-3 py-1.5 text-sm font-medium transition-all',
                          component === 'tower'
                            ? 'bg-accent-600 text-white shadow-sm'
                            : 'text-slate-400 hover:text-slate-200',
                        )}
                      >
                        Tower
                      </button>
                      <button
                        onClick={() => setComponent('blade')}
                        className={clsx(
                          'flex-1 rounded-md px-3 py-1.5 text-sm font-medium transition-all',
                          component === 'blade'
                            ? 'bg-accent-600 text-white shadow-sm'
                            : 'text-slate-400 hover:text-slate-200',
                        )}
                      >
                        Blade
                      </button>
                    </div>
                  </div>

                  {/* Number of modes slider */}
                  <div>
                    <label className="block text-xs font-medium text-slate-400 mb-1">
                      Number of Modes: {nModes}
                    </label>
                    <input
                      type="range"
                      min={1}
                      max={10}
                      value={nModes}
                      onChange={(e) => setNModes(Number(e.target.value))}
                      className="w-full accent-accent-500"
                    />
                    <div className="flex justify-between text-[10px] text-slate-500 mt-0.5">
                      <span>1</span>
                      <span>5</span>
                      <span>10</span>
                    </div>
                  </div>

                  {/* Include tip mass */}
                  <div className="flex items-end pb-1">
                    {component === 'tower' && (
                      <label className="flex items-center gap-2 text-sm text-slate-300 cursor-pointer select-none">
                        <input
                          type="checkbox"
                          checked={includeTipMass}
                          onChange={(e) => setIncludeTipMass(e.target.checked)}
                          className="rounded border-slate-600 bg-slate-800 text-accent-500 focus:ring-accent-500 focus:ring-offset-0"
                        />
                        Include tip mass (RNA)
                      </label>
                    )}
                  </div>
                </div>

                {/* Compute button */}
                <button
                  onClick={handleCompute}
                  disabled={loading || !turbineModelId}
                  className="px-4 py-2 bg-accent-500 hover:bg-accent-600 text-white text-sm font-medium rounded transition-colors disabled:opacity-50 flex items-center gap-2"
                >
                  {loading ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Play className="h-4 w-4" />
                  )}
                  Compute Mode Shapes
                </button>
              </div>

              {/* Charts */}
              {result && (
                <div className="border border-slate-700 bg-surface-dark-secondary rounded-xl p-6">
                  <h3 className="text-sm font-semibold text-slate-200 uppercase tracking-wider mb-4">
                    Mode Shape Results
                  </h3>

                  <div className={clsx(hasBothCharts ? 'grid grid-cols-1 xl:grid-cols-2 gap-6' : '')}>
                    {/* Flapwise / main chart */}
                    <div className="min-h-[400px]">
                      <Plot
                        data={flapTraces as any}
                        layout={flapLayout as any}
                        config={plotConfig}
                        style={{ width: '100%', height: '400px' }}
                        useResizeHandler
                      />
                    </div>

                    {/* Edgewise chart (blade only) */}
                    {hasBothCharts && (
                      <div className="min-h-[400px]">
                        <Plot
                          data={edgeTraces as any}
                          layout={edgeLayout as any}
                          config={plotConfig}
                          style={{ width: '100%', height: '400px' }}
                          useResizeHandler
                        />
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Frequency table */}
              {result && result.modes.length > 0 && (
                <div className="border border-slate-700 bg-surface-dark-secondary rounded-xl p-6">
                  <h3 className="text-sm font-semibold text-slate-200 uppercase tracking-wider mb-4">
                    Natural Frequencies
                  </h3>
                  <div className="overflow-x-auto rounded-lg border border-slate-700">
                    <table className="min-w-full text-sm">
                      <thead className="bg-slate-800">
                        <tr>
                          <th className="px-3 py-2 text-left text-xs font-medium text-slate-400 uppercase whitespace-nowrap">
                            Mode #
                          </th>
                          <th className="px-3 py-2 text-left text-xs font-medium text-slate-400 uppercase whitespace-nowrap">
                            Label
                          </th>
                          <th className="px-3 py-2 text-right text-xs font-medium text-slate-400 uppercase whitespace-nowrap">
                            Frequency (Hz)
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {result.modes.map((mode, i) => (
                          <tr
                            key={i}
                            className={i % 2 === 0 ? 'bg-slate-800/50' : ''}
                          >
                            <td className="px-3 py-2 text-slate-200 font-mono text-xs">
                              {i + 1}
                            </td>
                            <td className="px-3 py-2 text-slate-200 text-xs">
                              <span className="flex items-center gap-2">
                                <span
                                  className="inline-block h-2.5 w-2.5 rounded-full"
                                  style={{ backgroundColor: MODE_PALETTE[i % MODE_PALETTE.length] }}
                                />
                                {mode.label}
                              </span>
                            </td>
                            <td className="px-3 py-2 text-right text-slate-300 font-mono text-xs">
                              {mode.frequency.toFixed(4)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </>
          )}
        </>
      )}

      {/* ──────────────── Beam Theory Tab ──────────────── */}
      {activeTab === 'beam' && (
        <div className="space-y-6">
          <div className="border border-slate-700 bg-surface-dark-secondary rounded-xl p-6">
            <h3 className="text-sm font-semibold text-slate-200 uppercase tracking-wider mb-4">
              Uniform Beam Bending Modes
            </h3>
            <p className="text-xs text-slate-500 mb-4">
              Analytical mode shapes for a uniform Euler-Bernoulli beam with various boundary conditions.
              Uses welib.beams.theory.UniformBeamBendingModes.
            </p>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
              <div className="sm:col-span-2">
                <label className="block text-xs font-medium text-slate-400 mb-1">
                  Boundary Condition
                </label>
                <select value={btBC} onChange={(e) => setBtBC(e.target.value)}
                  className="w-full rounded bg-slate-800 border border-slate-600 px-3 py-1.5 text-sm text-slate-100 focus:border-accent-500 focus:outline-none">
                  {BC_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">
                  EI <span className="text-slate-500">(Nm&sup2;)</span>
                </label>
                <input type="number" value={btEI} onChange={(e) => setBtEI(Number(e.target.value))}
                  step={1e7} min={1}
                  className="w-full rounded bg-slate-800 border border-slate-600 px-3 py-1.5 text-sm text-slate-100 focus:border-accent-500 focus:outline-none" />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">
                  Density <span className="text-slate-500">(kg/m&sup3;)</span>
                </label>
                <input type="number" value={btRho} onChange={(e) => setBtRho(Number(e.target.value))}
                  step={100} min={1}
                  className="w-full rounded bg-slate-800 border border-slate-600 px-3 py-1.5 text-sm text-slate-100 focus:border-accent-500 focus:outline-none" />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">
                  Area <span className="text-slate-500">(m&sup2;)</span>
                </label>
                <input type="number" value={btA} onChange={(e) => setBtA(Number(e.target.value))}
                  step={0.001} min={0.001}
                  className="w-full rounded bg-slate-800 border border-slate-600 px-3 py-1.5 text-sm text-slate-100 focus:border-accent-500 focus:outline-none" />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">
                  Length <span className="text-slate-500">(m)</span>
                </label>
                <input type="number" value={btL} onChange={(e) => setBtL(Number(e.target.value))}
                  step={1} min={0.1}
                  className="w-full rounded bg-slate-800 border border-slate-600 px-3 py-1.5 text-sm text-slate-100 focus:border-accent-500 focus:outline-none" />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Modes: {btNModes}</label>
                <input type="range" min={1} max={10} value={btNModes}
                  onChange={(e) => setBtNModes(Number(e.target.value))}
                  className="w-full accent-accent-500" />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">
                  Tip mass <span className="text-slate-500">(kg)</span>
                </label>
                <input type="number" value={btMtop} onChange={(e) => setBtMtop(Number(e.target.value))}
                  step={10} min={0}
                  className="w-full rounded bg-slate-800 border border-slate-600 px-3 py-1.5 text-sm text-slate-100 focus:border-accent-500 focus:outline-none" />
              </div>
            </div>

            <button onClick={handleBeamTheory} disabled={btLoading}
              className="px-4 py-2 bg-accent-500 hover:bg-accent-600 text-white text-sm font-medium rounded transition-colors disabled:opacity-50 flex items-center gap-2">
              {btLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
              Compute Beam Modes
            </button>
          </div>

          {btResult && (
            <>
              <div className="border border-slate-700 bg-surface-dark-secondary rounded-xl p-6">
                <div className="min-h-[450px]">
                  <Plot
                    data={btTraces as any}
                    layout={{
                      ...basePlotLayout,
                      title: { text: `Beam Mode Shapes (${btBC})`, font: { size: 12, color: '#e2e8f0' } },
                      xaxis: { title: 'x / L', ...gridStyle },
                      yaxis: { title: 'Normalized Displacement', ...gridStyle },
                    } as any}
                    config={plotConfig}
                    style={{ width: '100%', height: '450px' }}
                    useResizeHandler
                  />
                </div>
              </div>

              {/* Frequency table */}
              <div className="border border-slate-700 bg-surface-dark-secondary rounded-xl p-6">
                <h3 className="text-sm font-semibold text-slate-200 uppercase tracking-wider mb-4">
                  Natural Frequencies
                </h3>
                <div className="overflow-x-auto rounded-lg border border-slate-700">
                  <table className="min-w-full text-sm">
                    <thead className="bg-slate-800">
                      <tr>
                        <th className="px-3 py-2 text-left text-xs font-medium text-slate-400 uppercase">Mode</th>
                        <th className="px-3 py-2 text-left text-xs font-medium text-slate-400 uppercase">Label</th>
                        <th className="px-3 py-2 text-right text-xs font-medium text-slate-400 uppercase">Frequency (Hz)</th>
                      </tr>
                    </thead>
                    <tbody>
                      {btResult.modes.map((m, i) => (
                        <tr key={i} className={i % 2 === 0 ? 'bg-slate-800/50' : ''}>
                          <td className="px-3 py-2 text-slate-200 font-mono text-xs">{i + 1}</td>
                          <td className="px-3 py-2 text-slate-200 text-xs">
                            <span className="flex items-center gap-2">
                              <span className="inline-block h-2.5 w-2.5 rounded-full"
                                style={{ backgroundColor: MODE_PALETTE[i % MODE_PALETTE.length] }} />
                              {m.label}
                            </span>
                          </td>
                          <td className="px-3 py-2 text-right text-slate-300 font-mono text-xs">{m.frequency.toFixed(4)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          )}
        </div>
      )}

      {/* ──────────────── FEM vs Theory Tab ──────────────── */}
      {activeTab === 'fem' && (
        <div className="space-y-6">
          <div className="border border-slate-700 bg-surface-dark-secondary rounded-xl p-6">
            <h3 className="text-sm font-semibold text-slate-200 uppercase tracking-wider mb-4">
              FEM vs Analytical Comparison
            </h3>
            <p className="text-xs text-slate-500 mb-4">
              Compares clamped-free beam mode shapes from FEM (welib.FEM.fem_beam) with analytical solutions
              (welib.beams.theory). Solid lines = analytical, markers = FEM nodes.
            </p>

            <div className="grid grid-cols-1 sm:grid-cols-3 lg:grid-cols-6 gap-4 mb-4">
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">
                  EI <span className="text-slate-500">(Nm&sup2;)</span>
                </label>
                <input type="number" value={femEI} onChange={(e) => setFemEI(Number(e.target.value))}
                  step={1e7} min={1}
                  className="w-full rounded bg-slate-800 border border-slate-600 px-3 py-1.5 text-sm text-slate-100 focus:border-accent-500 focus:outline-none" />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">
                  Density <span className="text-slate-500">(kg/m&sup3;)</span>
                </label>
                <input type="number" value={femRho} onChange={(e) => setFemRho(Number(e.target.value))}
                  step={100} min={1}
                  className="w-full rounded bg-slate-800 border border-slate-600 px-3 py-1.5 text-sm text-slate-100 focus:border-accent-500 focus:outline-none" />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">
                  Area <span className="text-slate-500">(m&sup2;)</span>
                </label>
                <input type="number" value={femA} onChange={(e) => setFemA(Number(e.target.value))}
                  step={0.001} min={0.001}
                  className="w-full rounded bg-slate-800 border border-slate-600 px-3 py-1.5 text-sm text-slate-100 focus:border-accent-500 focus:outline-none" />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">
                  Length <span className="text-slate-500">(m)</span>
                </label>
                <input type="number" value={femL} onChange={(e) => setFemL(Number(e.target.value))}
                  step={1} min={0.1}
                  className="w-full rounded bg-slate-800 border border-slate-600 px-3 py-1.5 text-sm text-slate-100 focus:border-accent-500 focus:outline-none" />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Modes: {femNModes}</label>
                <input type="range" min={1} max={10} value={femNModes}
                  onChange={(e) => setFemNModes(Number(e.target.value))}
                  className="w-full accent-accent-500" />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Elements: {femNElements}</label>
                <input type="range" min={5} max={100} value={femNElements}
                  onChange={(e) => setFemNElements(Number(e.target.value))}
                  className="w-full accent-accent-500" />
              </div>
            </div>

            <button onClick={handleFemCompare} disabled={femLoading}
              className="px-4 py-2 bg-accent-500 hover:bg-accent-600 text-white text-sm font-medium rounded transition-colors disabled:opacity-50 flex items-center gap-2">
              {femLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
              Compare FEM vs Theory
            </button>
          </div>

          {femResult && (
            <>
              <div className="border border-slate-700 bg-surface-dark-secondary rounded-xl p-6">
                <div className="min-h-[450px]">
                  <Plot
                    data={femTraces as any}
                    layout={{
                      ...basePlotLayout,
                      title: { text: 'FEM vs Analytical Mode Shapes', font: { size: 12, color: '#e2e8f0' } },
                      xaxis: { title: 'x / L', ...gridStyle },
                      yaxis: { title: 'Normalized Displacement', ...gridStyle },
                    } as any}
                    config={plotConfig}
                    style={{ width: '100%', height: '450px' }}
                    useResizeHandler
                  />
                </div>
              </div>

              {/* Frequency comparison table */}
              <div className="border border-slate-700 bg-surface-dark-secondary rounded-xl p-6">
                <h3 className="text-sm font-semibold text-slate-200 uppercase tracking-wider mb-4">
                  Frequency Comparison
                </h3>
                <div className="overflow-x-auto rounded-lg border border-slate-700">
                  <table className="min-w-full text-sm">
                    <thead className="bg-slate-800">
                      <tr>
                        <th className="px-3 py-2 text-left text-xs font-medium text-slate-400 uppercase">Mode</th>
                        <th className="px-3 py-2 text-right text-xs font-medium text-slate-400 uppercase">Analytical (Hz)</th>
                        <th className="px-3 py-2 text-right text-xs font-medium text-slate-400 uppercase">FEM (Hz)</th>
                        <th className="px-3 py-2 text-right text-xs font-medium text-slate-400 uppercase">Error (%)</th>
                      </tr>
                    </thead>
                    <tbody>
                      {femResult.frequencies_theory.map((fTheory, i) => {
                        const fFem = femResult.frequencies_fem[i] ?? 0;
                        const errPct = fTheory > 0 ? ((fFem - fTheory) / fTheory * 100) : 0;
                        return (
                          <tr key={i} className={i % 2 === 0 ? 'bg-slate-800/50' : ''}>
                            <td className="px-3 py-2 text-slate-200 font-mono text-xs">
                              <span className="flex items-center gap-2">
                                <span className="inline-block h-2.5 w-2.5 rounded-full"
                                  style={{ backgroundColor: MODE_PALETTE[i % MODE_PALETTE.length] }} />
                                {i + 1}
                              </span>
                            </td>
                            <td className="px-3 py-2 text-right text-slate-300 font-mono text-xs">{fTheory.toFixed(4)}</td>
                            <td className="px-3 py-2 text-right text-slate-300 font-mono text-xs">{fFem.toFixed(4)}</td>
                            <td className={clsx(
                              'px-3 py-2 text-right font-mono text-xs',
                              Math.abs(errPct) < 1 ? 'text-emerald-400' : Math.abs(errPct) < 5 ? 'text-amber-400' : 'text-red-400',
                            )}>
                              {errPct >= 0 ? '+' : ''}{errPct.toFixed(3)}%
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
