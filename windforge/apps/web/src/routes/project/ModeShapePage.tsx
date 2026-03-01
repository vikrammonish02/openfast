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

export default function ModeShapePage() {
  const { projectId } = useParams<{ projectId: string }>();

  // Turbine model state
  const [turbineModels, setTurbineModels] = useState<TurbineModel[]>([]);
  const [turbineModelId, setTurbineModelId] = useState<string>('');
  const [loadingModels, setLoadingModels] = useState(true);

  // Config state
  const [component, setComponent] = useState<'tower' | 'blade'>('tower');
  const [nModes, setNModes] = useState(5);
  const [includeTipMass, setIncludeTipMass] = useState(true);

  // Results
  const [result, setResult] = useState<ModeShapeResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

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

  // ── Compute mode shapes ─────────────────────────────────────────────────

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
        gridcolor: 'rgba(100,116,139,0.2)',
        zeroline: false,
      },
      yaxis: {
        title: 'Normalized Displacement',
        gridcolor: 'rgba(100,116,139,0.2)',
        zeroline: true,
        zerolinecolor: 'rgba(100,116,139,0.4)',
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
        gridcolor: 'rgba(100,116,139,0.2)',
        zeroline: false,
      },
      yaxis: {
        title: 'Normalized Displacement',
        gridcolor: 'rgba(100,116,139,0.2)',
        zeroline: true,
        zerolinecolor: 'rgba(100,116,139,0.4)',
      },
    }),
    [],
  );

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

  if (turbineModels.length === 0) {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-xl font-bold text-slate-100">Mode Shapes</h2>
          <p className="text-sm text-slate-400">
            Visualize structural mode shapes for tower and blade components
          </p>
        </div>
        <div className="flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-600 py-16">
          <Spline className="h-12 w-12 text-slate-300 mb-3" />
          <h3 className="text-base font-semibold text-slate-200">
            No turbine models available
          </h3>
          <p className="mt-1 text-sm text-slate-400">
            Create a turbine model in the Assembly tab to compute mode shapes.
          </p>
        </div>
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
          Visualize structural mode shapes for tower and blade components
        </p>
      </div>

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

      {/* Error display */}
      {error && (
        <div className="rounded-lg border border-red-800 bg-red-950/30 p-4 text-sm text-red-300">
          {error}
        </div>
      )}

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
    </div>
  );
}
