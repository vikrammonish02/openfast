import { useState, useEffect, useCallback, useMemo } from 'react';
import { useParams } from 'react-router-dom';
import { frequencyApi, turbineModelsApi } from '@/api/client';
import type { CampbellResult, MultiStageResult } from '@/api/client';
import type { TurbineModel } from '@/types';
import { Activity, Loader2, BarChart3, LineChart } from 'lucide-react';
import toast from 'react-hot-toast';
import Plot from 'react-plotly.js';

// ---------------------------------------------------------------------------
// Stage definitions
// ---------------------------------------------------------------------------

const STAGES = [
  { key: 'blade_alone', label: 'Blade Alone' },
  { key: 'tower_alone', label: 'Tower Alone' },
  { key: 'tower_rna', label: 'Tower + RNA' },
  { key: 'monopile_tower', label: 'Monopile + Tower' },
  { key: 'full_operation', label: 'Full System (Operation)' },
  { key: 'transport_blade', label: 'Transport (Blade)' },
  { key: 'transport_tower', label: 'Transport (Tower)' },
  { key: 'installation', label: 'Installation' },
] as const;

// ---------------------------------------------------------------------------
// Color palettes
// ---------------------------------------------------------------------------

const COMPONENT_COLORS: Record<string, string[]> = {
  blade: ['#10b981', '#34d399', '#6ee7b7'],
  tower: ['#3b82f6', '#60a5fa', '#93c5fd'],
  drivetrain: ['#f59e0b', '#fbbf24'],
};

const MODE_PALETTE = [
  '#10b981', '#3b82f6', '#f59e0b', '#ef4444', '#8b5cf6',
  '#ec4899', '#06b6d4', '#84cc16', '#f97316', '#6366f1',
  '#14b8a6', '#e11d48', '#a855f7', '#22d3ee', '#eab308',
];

const EXCITATION_STYLES: Record<string, { color: string; label: string }> = {
  '1P': { color: '#6b7280', label: '1P' },
  '3P': { color: '#3b82f6', label: '3P' },
  '6P': { color: '#f59e0b', label: '6P' },
  '9P': { color: '#ef4444', label: '9P' },
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function getComponentColor(modeDesc: string, index: number): string {
  const lower = modeDesc.toLowerCase();
  if (lower.includes('blade') || lower.includes('flap') || lower.includes('edge')) {
    const colors = COMPONENT_COLORS.blade;
    return colors[index % colors.length];
  }
  if (lower.includes('tower') || lower.includes('fore-aft') || lower.includes('side')) {
    const colors = COMPONENT_COLORS.tower;
    return colors[index % colors.length];
  }
  if (lower.includes('drive') || lower.includes('shaft') || lower.includes('generator')) {
    const colors = COMPONENT_COLORS.drivetrain;
    return colors[index % colors.length];
  }
  return MODE_PALETTE[index % MODE_PALETTE.length];
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function CampbellDiagram() {
  const { projectId } = useParams<{ projectId: string }>();

  // Turbine model state
  const [turbineModels, setTurbineModels] = useState<TurbineModel[]>([]);
  const [selectedModelId, setSelectedModelId] = useState<string>('');

  // Stage selection
  const [selectedStages, setSelectedStages] = useState<string[]>([
    'blade_alone',
    'tower_alone',
    'full_operation',
  ]);

  // Campbell parameters
  const [rpmMin, setRpmMin] = useState(0);
  const [rpmMax, setRpmMax] = useState(15);
  const [rpmSteps, setRpmSteps] = useState(30);
  const [nModes, setNModes] = useState(10);

  // Results
  const [stageResults, setStageResults] = useState<MultiStageResult | null>(null);
  const [campbellData, setCampbellData] = useState<CampbellResult | null>(null);

  // Loading
  const [loadingFreq, setLoadingFreq] = useState(false);
  const [loadingCampbell, setLoadingCampbell] = useState(false);
  const [loadingModels, setLoadingModels] = useState(true);

  // ── Fetch turbine models on mount ──────────────────────────────────────────

  useEffect(() => {
    if (!projectId) return;
    setLoadingModels(true);
    turbineModelsApi
      .list(projectId)
      .then((models) => {
        setTurbineModels(models);
        if (models.length > 0 && !selectedModelId) {
          setSelectedModelId(models[0].id);
        }
      })
      .catch(() => {
        toast.error('Failed to load turbine models');
      })
      .finally(() => setLoadingModels(false));
  }, [projectId]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Stage toggle ───────────────────────────────────────────────────────────

  const toggleStage = useCallback((stage: string) => {
    setSelectedStages((prev) =>
      prev.includes(stage) ? prev.filter((s) => s !== stage) : [...prev, stage],
    );
  }, []);

  // ── Compute multi-stage frequencies ────────────────────────────────────────

  const handleComputeFrequencies = useCallback(async () => {
    if (!projectId || !selectedModelId) return;
    if (selectedStages.length === 0) {
      toast.error('Select at least one analysis stage');
      return;
    }
    setLoadingFreq(true);
    setStageResults(null);
    try {
      const result = await frequencyApi.computeMultiStage(projectId, {
        turbine_model_id: selectedModelId,
        stages: selectedStages,
        rotor_speed_rpm: 0,
      });
      setStageResults(result);
      toast.success('Frequency analysis complete');
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Frequency computation failed');
    } finally {
      setLoadingFreq(false);
    }
  }, [projectId, selectedModelId, selectedStages]);

  // ── Generate Campbell diagram ──────────────────────────────────────────────

  const handleGenerateCampbell = useCallback(async () => {
    if (!projectId || !selectedModelId) return;
    setLoadingCampbell(true);
    setCampbellData(null);
    try {
      const result = await frequencyApi.computeCampbell(projectId, {
        turbine_model_id: selectedModelId,
        rpm_min: rpmMin,
        rpm_max: rpmMax,
        rpm_steps: rpmSteps,
        n_modes: nModes,
      });
      setCampbellData(result);
      toast.success('Campbell diagram generated');
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Campbell computation failed');
    } finally {
      setLoadingCampbell(false);
    }
  }, [projectId, selectedModelId, rpmMin, rpmMax, rpmSteps, nModes]);

  // ── Frequency table data ───────────────────────────────────────────────────

  const { modeRows, stageLabels } = useMemo(() => {
    if (!stageResults) return { modeRows: [], stageLabels: [] };

    const stages = stageResults.stages;
    const labels = stages.map((s) => s.stage_label);

    // Build union of all mode descriptions preserving order
    const modeSet = new Map<string, number[]>();
    const modeOrder: string[] = [];

    stages.forEach((stage, stageIdx) => {
      stage.mode_descriptions.forEach((desc, modeIdx) => {
        if (!modeSet.has(desc)) {
          modeSet.set(desc, new Array(stages.length).fill(NaN));
          modeOrder.push(desc);
        }
        modeSet.get(desc)![stageIdx] = stage.frequencies_hz[modeIdx];
      });
    });

    const rows = modeOrder.map((desc) => ({
      description: desc,
      frequencies: modeSet.get(desc)!,
    }));

    return { modeRows: rows, stageLabels: labels };
  }, [stageResults]);

  // ── Frequency bar chart data ───────────────────────────────────────────────

  const freqBarData = useMemo(() => {
    if (!stageResults || modeRows.length === 0) return [];

    // Counter per component type for color cycling
    const componentCounters: Record<string, number> = {};

    return modeRows.map((row) => {
      const lower = row.description.toLowerCase();
      let component = 'other';
      if (lower.includes('blade') || lower.includes('flap') || lower.includes('edge')) {
        component = 'blade';
      } else if (lower.includes('tower') || lower.includes('fore-aft') || lower.includes('side')) {
        component = 'tower';
      } else if (lower.includes('drive') || lower.includes('shaft') || lower.includes('generator')) {
        component = 'drivetrain';
      }

      const idx = componentCounters[component] ?? 0;
      componentCounters[component] = idx + 1;

      return {
        x: stageLabels,
        y: row.frequencies.map((f) => (isNaN(f) ? null : f)),
        type: 'bar' as const,
        name: row.description,
        marker: {
          color: getComponentColor(row.description, idx),
        },
      };
    });
  }, [stageResults, modeRows, stageLabels]);

  const freqBarLayout = useMemo(
    () => ({
      paper_bgcolor: 'transparent',
      plot_bgcolor: 'rgba(17,24,39,0.8)',
      font: { family: 'ui-monospace, monospace', size: 10, color: '#9ca3af' },
      margin: { t: 40, r: 30, b: 80, l: 60 },
      barmode: 'group' as const,
      xaxis: {
        title: 'Stage',
        gridcolor: 'rgba(100,116,139,0.2)',
        zeroline: false,
        tickangle: -30,
      },
      yaxis: {
        title: 'Frequency (Hz)',
        gridcolor: 'rgba(100,116,139,0.2)',
        zeroline: false,
      },
      legend: {
        bgcolor: 'rgba(0,0,0,0.3)',
        font: { size: 9, color: '#9ca3af' },
      },
      showlegend: true,
    }),
    [],
  );

  // ── Campbell diagram traces ────────────────────────────────────────────────

  const campbellTraces = useMemo(() => {
    if (!campbellData) return [];

    const traces: any[] = [];

    // Mode lines
    campbellData.modes.forEach((mode, i) => {
      traces.push({
        x: campbellData.rpm_values,
        y: mode.frequencies,
        type: 'scatter' as const,
        mode: 'lines' as const,
        name: mode.name,
        line: {
          color: MODE_PALETTE[i % MODE_PALETTE.length],
          width: 2,
        },
      });
    });

    // Excitation lines
    Object.entries(campbellData.excitation_lines).forEach(([key, line]) => {
      const style = EXCITATION_STYLES[key] || { color: '#9ca3af', label: key };
      traces.push({
        x: line.rpm,
        y: line.freq,
        type: 'scatter' as const,
        mode: 'lines' as const,
        name: style.label,
        line: {
          color: style.color,
          width: 1.5,
          dash: 'dash' as const,
        },
      });
    });

    // Rated RPM vertical line - find the selected model
    const selectedModel = turbineModels.find((m) => m.id === selectedModelId);
    if (selectedModel?.rotor_speed_rated) {
      const ratedRpm = selectedModel.rotor_speed_rated;
      const yMax = Math.max(
        ...campbellData.modes.flatMap((m) => m.frequencies),
        ...Object.values(campbellData.excitation_lines).flatMap((l) => l.freq),
      );
      traces.push({
        x: [ratedRpm, ratedRpm],
        y: [0, yMax * 1.05],
        type: 'scatter' as const,
        mode: 'lines' as const,
        name: 'Rated RPM',
        line: {
          color: '#ef4444',
          width: 1.5,
          dash: 'dash' as const,
        },
        showlegend: true,
      });
    }

    return traces;
  }, [campbellData, turbineModels, selectedModelId]);

  const campbellLayout = useMemo(
    () => ({
      paper_bgcolor: 'transparent',
      plot_bgcolor: 'rgba(17,24,39,0.8)',
      font: { family: 'ui-monospace, monospace', size: 10, color: '#9ca3af' },
      margin: { t: 40, r: 30, b: 60, l: 70 },
      xaxis: {
        title: 'Rotor Speed (RPM)',
        gridcolor: 'rgba(100,116,139,0.2)',
        zeroline: false,
      },
      yaxis: {
        title: 'Frequency (Hz)',
        gridcolor: 'rgba(100,116,139,0.2)',
        zeroline: false,
      },
      legend: {
        bgcolor: 'rgba(0,0,0,0.3)',
        font: { size: 9, color: '#9ca3af' },
      },
      showlegend: true,
    }),
    [],
  );

  // ── Loading state ──────────────────────────────────────────────────────────

  if (loadingModels) {
    return (
      <div className="flex items-center justify-center py-24">
        <Loader2 className="h-8 w-8 animate-spin text-accent-500" />
      </div>
    );
  }

  // ── Empty state ────────────────────────────────────────────────────────────

  if (turbineModels.length === 0) {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-xl font-bold text-slate-100">Campbell Diagram</h2>
          <p className="text-sm text-slate-400">
            Structural frequency analysis and Campbell diagrams
          </p>
        </div>
        <div className="flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-600 py-16">
          <Activity className="h-12 w-12 text-slate-300 mb-3" />
          <h3 className="text-base font-semibold text-slate-200">
            No turbine models available
          </h3>
          <p className="mt-1 text-sm text-slate-400">
            Create a turbine model in the Assembly tab to start frequency analysis.
          </p>
        </div>
      </div>
    );
  }

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-xl font-bold text-slate-100">Campbell Diagram</h2>
        <p className="text-sm text-slate-400">
          Structural frequency analysis and Campbell diagrams
        </p>
      </div>

      {/* Section 1 — Configuration Panel */}
      <div className="border border-slate-700 bg-surface-dark-secondary rounded-xl p-6">
        <h3 className="text-sm font-semibold text-slate-200 uppercase tracking-wider mb-4">
          Analysis Configuration
        </h3>

        {/* Row 1: Turbine model */}
        <div className="mb-4">
          <label className="block text-xs font-medium text-slate-400 mb-1">
            Turbine Model
          </label>
          <select
            value={selectedModelId}
            onChange={(e) => setSelectedModelId(e.target.value)}
            className="bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-sm text-slate-200 w-full max-w-md"
          >
            {turbineModels.map((model) => (
              <option key={model.id} value={model.id}>
                {model.name}
              </option>
            ))}
          </select>
        </div>

        {/* Row 2: Stage checkboxes */}
        <div className="mb-4">
          <label className="block text-xs font-medium text-slate-400 mb-2">
            Analysis Stages
          </label>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            {STAGES.map((stage) => (
              <label
                key={stage.key}
                className="flex items-center gap-2 text-sm text-slate-300 cursor-pointer select-none"
              >
                <input
                  type="checkbox"
                  checked={selectedStages.includes(stage.key)}
                  onChange={() => toggleStage(stage.key)}
                  className="rounded border-slate-600 bg-slate-800 text-accent-500 focus:ring-accent-500 focus:ring-offset-0"
                />
                {stage.label}
              </label>
            ))}
          </div>
        </div>

        {/* Row 3: Campbell parameters */}
        <div className="mb-5">
          <label className="block text-xs font-medium text-slate-400 mb-2">
            Campbell Parameters
          </label>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div>
              <label className="block text-xs text-slate-500 mb-1">RPM Min</label>
              <input
                type="number"
                value={rpmMin}
                onChange={(e) => setRpmMin(Number(e.target.value))}
                className="bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-sm text-slate-200 w-full"
              />
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">RPM Max</label>
              <input
                type="number"
                value={rpmMax}
                onChange={(e) => setRpmMax(Number(e.target.value))}
                className="bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-sm text-slate-200 w-full"
              />
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">Steps</label>
              <input
                type="number"
                value={rpmSteps}
                onChange={(e) => setRpmSteps(Number(e.target.value))}
                min={2}
                className="bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-sm text-slate-200 w-full"
              />
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">Modes</label>
              <input
                type="number"
                value={nModes}
                onChange={(e) => setNModes(Number(e.target.value))}
                min={1}
                className="bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-sm text-slate-200 w-full"
              />
            </div>
          </div>
        </div>

        {/* Row 4: Action buttons */}
        <div className="flex items-center gap-3">
          <button
            onClick={handleComputeFrequencies}
            disabled={loadingFreq || !selectedModelId || selectedStages.length === 0}
            className="bg-accent-600 hover:bg-accent-500 text-white rounded-lg px-4 py-2 text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          >
            {loadingFreq ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <BarChart3 className="h-4 w-4" />
            )}
            Compute Frequencies
          </button>
          <button
            onClick={handleGenerateCampbell}
            disabled={loadingCampbell || !selectedModelId}
            className="bg-slate-700 hover:bg-slate-600 text-slate-200 rounded-lg px-4 py-2 text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          >
            {loadingCampbell ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <LineChart className="h-4 w-4" />
            )}
            Generate Campbell Diagram
          </button>
        </div>
      </div>

      {/* Section 2 — Natural Frequency Results */}
      {stageResults && modeRows.length > 0 && (
        <div className="border border-slate-700 bg-surface-dark-secondary rounded-xl p-6">
          <h3 className="text-sm font-semibold text-slate-200 uppercase tracking-wider mb-4">
            Natural Frequency Results
          </h3>

          <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
            {/* Left: Table */}
            <div className="overflow-x-auto rounded-lg border border-slate-700">
              <table className="min-w-full text-sm">
                <thead className="bg-slate-800">
                  <tr>
                    <th className="px-3 py-2 text-left text-xs font-medium text-slate-400 uppercase whitespace-nowrap">
                      Mode Description
                    </th>
                    {stageLabels.map((label) => (
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
                  {modeRows.map((row, i) => (
                    <tr
                      key={row.description}
                      className={i % 2 === 0 ? 'bg-slate-800/50' : ''}
                    >
                      <td className="px-3 py-2 text-slate-200 whitespace-nowrap font-mono text-xs">
                        {row.description}
                      </td>
                      {row.frequencies.map((freq, j) => (
                        <td
                          key={j}
                          className="px-3 py-2 text-right text-slate-300 font-mono text-xs"
                        >
                          {isNaN(freq) ? '--' : freq.toFixed(3)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Right: Bar chart */}
            <div className="min-h-[350px]">
              <Plot
                data={freqBarData as any}
                layout={freqBarLayout}
                config={{
                  displaylogo: false,
                  responsive: true,
                  displayModeBar: false,
                }}
                style={{ width: '100%', height: '350px' }}
                useResizeHandler
              />
            </div>
          </div>
        </div>
      )}

      {/* Section 3 — Campbell Diagram */}
      {campbellData && campbellTraces.length > 0 && (
        <div className="border border-slate-700 bg-surface-dark-secondary rounded-xl p-6">
          <h3 className="text-sm font-semibold text-slate-200 uppercase tracking-wider mb-4">
            Campbell Diagram
          </h3>
          <div className="min-h-[500px]">
            <Plot
              data={campbellTraces}
              layout={campbellLayout}
              config={{
                displaylogo: false,
                responsive: true,
                modeBarButtonsToRemove: [
                  'select2d',
                  'lasso2d',
                  'autoScale2d',
                ],
                displayModeBar: false,
              }}
              style={{ width: '100%', height: '500px' }}
              useResizeHandler
            />
          </div>
        </div>
      )}
    </div>
  );
}
