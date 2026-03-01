import { useState, useEffect, useCallback, useMemo } from 'react';
import { useParams } from 'react-router-dom';
import api from '@/api/client';
import { bladesApi } from '@/api/client';
import type { Blade, BladeAeroStation } from '@/types';
import { Feather, Loader2, Play } from 'lucide-react';
import toast from 'react-hot-toast';
import Plot from 'react-plotly.js';
import clsx from 'clsx';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const TABS = [
  { key: 'polar', label: 'Polar Viewer' },
  { key: 'correction3d', label: '3D Correction' },
  { key: 'naca', label: 'NACA Generator' },
] as const;

type TabKey = (typeof TABS)[number]['key'];

const POLAR_COLORS = {
  cl: '#10b981',
  cd: '#ef4444',
  clcd: '#3b82f6',
  cm: '#f59e0b',
};

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface PolarAnalysisResult {
  alpha_deg: number[];
  cl: number[];
  cd: number[];
  cm: number[];
  cl_cd: number[];
  cl_max: number;
  alpha_stall: number;
  cl_cd_max: number;
  alpha_0: number;
}

interface Correction3DResult {
  alpha_deg: number[];
  cl_original: number[];
  cd_original: number[];
  cl_corrected: number[];
  cd_corrected: number[];
}

interface NACAResult {
  x: number[];
  y_upper: number[];
  y_lower: number[];
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

export default function AirfoilToolsPage() {
  const { projectId } = useParams<{ projectId: string }>();

  // Tab state
  const [activeTab, setActiveTab] = useState<TabKey>('polar');

  // Blade / airfoil data for polar viewer
  const [blades, setBlades] = useState<Blade[]>([]);
  const [loadingBlades, setLoadingBlades] = useState(true);
  const [selectedAirfoilId, setSelectedAirfoilId] = useState<string>('');

  // Airfoil station list (flattened from all blades)
  const airfoilStations = useMemo(() => {
    const stationsMap = new Map<string, { id: string; label: string }>();
    blades.forEach((blade) => {
      if (blade.aero_stations) {
        blade.aero_stations.forEach((station: BladeAeroStation) => {
          if (station.airfoil_id && !stationsMap.has(station.airfoil_id)) {
            stationsMap.set(station.airfoil_id, {
              id: station.airfoil_id,
              label: `${station.airfoil_id} (r/R=${station.frac.toFixed(3)})`,
            });
          }
        });
      }
    });
    return Array.from(stationsMap.values());
  }, [blades]);

  // --- Polar Viewer state ---
  const [polarResult, setPolarResult] = useState<PolarAnalysisResult | null>(null);
  const [polarLoading, setPolarLoading] = useState(false);

  // --- 3D Correction state ---
  const [corrRR, setCorrRR] = useState(0.5);
  const [corrCR, setCorrCR] = useState(0.1);
  const [showOriginal, setShowOriginal] = useState(true);
  const [corrResult, setCorrResult] = useState<Correction3DResult | null>(null);
  const [corrLoading, setCorrLoading] = useState(false);

  // --- NACA Generator state ---
  const [nacaDigits, setNacaDigits] = useState('0012');
  const [nacaNPoints, setNacaNPoints] = useState(100);
  const [nacaResult, setNacaResult] = useState<NACAResult | null>(null);
  const [nacaLoading, setNacaLoading] = useState(false);

  // General error
  const [error, setError] = useState<string | null>(null);

  // ── Load blade data on mount ───────────────────────────────────────────

  useEffect(() => {
    if (!projectId) return;
    setLoadingBlades(true);
    bladesApi
      .list(projectId)
      .then((data) => {
        setBlades(data);
      })
      .catch(() => {
        toast.error('Failed to load blades');
      })
      .finally(() => setLoadingBlades(false));
  }, [projectId]);

  // Auto-select first airfoil when stations change
  useEffect(() => {
    if (airfoilStations.length > 0 && !selectedAirfoilId) {
      setSelectedAirfoilId(airfoilStations[0].id);
    }
  }, [airfoilStations, selectedAirfoilId]);

  // ── API handlers ────────────────────────────────────────────────────────

  const handlePolarAnalyze = useCallback(async () => {
    if (!projectId || !selectedAirfoilId) return;
    setPolarLoading(true);
    setError(null);
    try {
      const res = await api.post<PolarAnalysisResult>(
        `/projects/${projectId}/airfoil-tools/analyze`,
        { airfoil_id: selectedAirfoilId },
      );
      setPolarResult(res.data);
      toast.success('Polar analysis complete');
    } catch (err: any) {
      const msg = err?.response?.data?.detail || 'Polar analysis failed';
      setError(msg);
      toast.error(msg);
    } finally {
      setPolarLoading(false);
    }
  }, [projectId, selectedAirfoilId]);

  const handleCorrection3D = useCallback(async () => {
    if (!projectId || !selectedAirfoilId) return;
    setCorrLoading(true);
    setError(null);
    try {
      const res = await api.post<Correction3DResult>(
        `/projects/${projectId}/airfoil-tools/correction-3d`,
        {
          airfoil_id: selectedAirfoilId,
          r_over_R: corrRR,
          c_over_R: corrCR,
        },
      );
      setCorrResult(res.data);
      toast.success('3D correction computed');
    } catch (err: any) {
      const msg = err?.response?.data?.detail || '3D correction failed';
      setError(msg);
      toast.error(msg);
    } finally {
      setCorrLoading(false);
    }
  }, [projectId, selectedAirfoilId, corrRR, corrCR]);

  const handleGenerateNACA = useCallback(async () => {
    if (!projectId || !nacaDigits.trim()) return;
    setNacaLoading(true);
    setError(null);
    try {
      const res = await api.post<NACAResult>(
        `/projects/${projectId}/airfoil-tools/generate-naca`,
        {
          digits: nacaDigits.trim(),
          n_points: nacaNPoints,
        },
      );
      setNacaResult(res.data);
      toast.success(`NACA ${nacaDigits} generated`);
    } catch (err: any) {
      const msg = err?.response?.data?.detail || 'NACA generation failed';
      setError(msg);
      toast.error(msg);
    } finally {
      setNacaLoading(false);
    }
  }, [projectId, nacaDigits, nacaNPoints]);

  // ── Polar Viewer chart data ────────────────────────────────────────────

  const polarClTraces = useMemo(() => {
    if (!polarResult) return [];
    return [
      {
        x: polarResult.alpha_deg,
        y: polarResult.cl,
        type: 'scatter' as const,
        mode: 'lines' as const,
        name: 'Cl',
        line: { color: POLAR_COLORS.cl, width: 2 },
      },
    ];
  }, [polarResult]);

  const polarCdTraces = useMemo(() => {
    if (!polarResult) return [];
    return [
      {
        x: polarResult.alpha_deg,
        y: polarResult.cd,
        type: 'scatter' as const,
        mode: 'lines' as const,
        name: 'Cd',
        line: { color: POLAR_COLORS.cd, width: 2 },
      },
    ];
  }, [polarResult]);

  const polarClCdTraces = useMemo(() => {
    if (!polarResult) return [];
    return [
      {
        x: polarResult.alpha_deg,
        y: polarResult.cl_cd,
        type: 'scatter' as const,
        mode: 'lines' as const,
        name: 'Cl/Cd',
        line: { color: POLAR_COLORS.clcd, width: 2 },
      },
    ];
  }, [polarResult]);

  const polarCmTraces = useMemo(() => {
    if (!polarResult) return [];
    return [
      {
        x: polarResult.alpha_deg,
        y: polarResult.cm,
        type: 'scatter' as const,
        mode: 'lines' as const,
        name: 'Cm',
        line: { color: POLAR_COLORS.cm, width: 2 },
      },
    ];
  }, [polarResult]);

  const makePolarSubLayout = useCallback(
    (title: string, yLabel: string) => ({
      ...basePlotLayout,
      title: { text: title, font: { size: 11, color: '#e2e8f0' } },
      xaxis: { title: '\u03b1 (deg)', ...gridStyle },
      yaxis: { title: yLabel, ...gridStyle },
      showlegend: false,
      margin: { t: 35, r: 20, b: 50, l: 60 },
    }),
    [],
  );

  // ── 3D Correction chart data ───────────────────────────────────────────

  const corrTraces = useMemo(() => {
    if (!corrResult) return [];
    const traces: any[] = [];

    // Corrected Cl (solid)
    traces.push({
      x: corrResult.alpha_deg,
      y: corrResult.cl_corrected,
      type: 'scatter' as const,
      mode: 'lines' as const,
      name: 'Cl corrected',
      line: { color: POLAR_COLORS.cl, width: 2 },
    });

    // Corrected Cd (solid)
    traces.push({
      x: corrResult.alpha_deg,
      y: corrResult.cd_corrected,
      type: 'scatter' as const,
      mode: 'lines' as const,
      name: 'Cd corrected',
      line: { color: POLAR_COLORS.cd, width: 2 },
    });

    // Original (dashed) if toggled on
    if (showOriginal) {
      traces.push({
        x: corrResult.alpha_deg,
        y: corrResult.cl_original,
        type: 'scatter' as const,
        mode: 'lines' as const,
        name: 'Cl original',
        line: { color: POLAR_COLORS.cl, width: 1.5, dash: 'dash' as const },
      });
      traces.push({
        x: corrResult.alpha_deg,
        y: corrResult.cd_original,
        type: 'scatter' as const,
        mode: 'lines' as const,
        name: 'Cd original',
        line: { color: POLAR_COLORS.cd, width: 1.5, dash: 'dash' as const },
      });
    }

    return traces;
  }, [corrResult, showOriginal]);

  const corrLayout = useMemo(
    () => ({
      ...basePlotLayout,
      title: {
        text: `3D Rotational Correction (r/R=${corrRR}, c/R=${corrCR})`,
        font: { size: 12, color: '#e2e8f0' },
      },
      xaxis: { title: '\u03b1 (deg)', ...gridStyle },
      yaxis: { title: 'Coefficient', ...gridStyle },
    }),
    [corrRR, corrCR],
  );

  // ── NACA Generator chart data ──────────────────────────────────────────

  const nacaTraces = useMemo(() => {
    if (!nacaResult) return [];
    return [
      {
        x: nacaResult.x,
        y: nacaResult.y_upper,
        type: 'scatter' as const,
        mode: 'lines' as const,
        name: 'Upper surface',
        line: { color: '#3b82f6', width: 2 },
      },
      {
        x: nacaResult.x,
        y: nacaResult.y_lower,
        type: 'scatter' as const,
        mode: 'lines' as const,
        name: 'Lower surface',
        line: { color: '#10b981', width: 2 },
      },
    ];
  }, [nacaResult]);

  const nacaLayout = useMemo(
    () => ({
      ...basePlotLayout,
      title: {
        text: nacaResult ? `NACA ${nacaDigits}` : 'NACA Airfoil',
        font: { size: 12, color: '#e2e8f0' },
      },
      xaxis: {
        title: 'x/c',
        ...gridStyle,
        scaleanchor: 'y' as const,
        scaleratio: 1,
      },
      yaxis: {
        title: 'y/c',
        ...gridStyle,
      },
    }),
    [nacaResult, nacaDigits],
  );

  const plotConfig = {
    displaylogo: false,
    responsive: true,
    displayModeBar: false,
  };

  // ── Loading state ──────────────────────────────────────────────────────

  if (loadingBlades) {
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
        <h2 className="text-xl font-bold text-slate-100">Airfoil Tools</h2>
        <p className="text-sm text-slate-400">
          Polar analysis, 3D rotational corrections, and NACA airfoil generation
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

      {/* ──────────────── Polar Viewer Tab ──────────────── */}
      {activeTab === 'polar' && (
        <div className="space-y-6">
          <div className="border border-slate-700 bg-surface-dark-secondary rounded-xl p-6">
            <h3 className="text-sm font-semibold text-slate-200 uppercase tracking-wider mb-4">
              Airfoil Polar Analysis
            </h3>

            {airfoilStations.length === 0 ? (
              <div className="flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-600 py-12">
                <Feather className="h-10 w-10 text-slate-300 mb-3" />
                <p className="text-sm text-slate-400">
                  No airfoils found. Define aero stations on a blade first.
                </p>
              </div>
            ) : (
              <div className="flex items-end gap-4">
                <div className="flex-1 max-w-sm">
                  <label className="block text-xs font-medium text-slate-400 mb-1">
                    Airfoil
                  </label>
                  <select
                    value={selectedAirfoilId}
                    onChange={(e) => setSelectedAirfoilId(e.target.value)}
                    className="w-full rounded bg-slate-800 border border-slate-600 px-3 py-1.5 text-sm text-slate-100 focus:border-accent-500 focus:outline-none"
                  >
                    {airfoilStations.map((station) => (
                      <option key={station.id} value={station.id}>
                        {station.label}
                      </option>
                    ))}
                  </select>
                </div>
                <button
                  onClick={handlePolarAnalyze}
                  disabled={polarLoading || !selectedAirfoilId}
                  className="px-4 py-2 bg-accent-500 hover:bg-accent-600 text-white text-sm font-medium rounded transition-colors disabled:opacity-50 flex items-center gap-2"
                >
                  {polarLoading ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Play className="h-4 w-4" />
                  )}
                  Analyze
                </button>
              </div>
            )}
          </div>

          {polarResult && (
            <>
              {/* Key parameters */}
              <div className="border border-slate-700 bg-surface-dark-secondary rounded-xl p-6">
                <h3 className="text-sm font-semibold text-slate-200 uppercase tracking-wider mb-4">
                  Key Parameters
                </h3>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                  <div className="rounded-lg border border-slate-700 bg-slate-800/50 p-3 text-center">
                    <div className="text-xs text-slate-400 mb-1">Cl_max</div>
                    <div className="text-lg font-bold text-emerald-400 font-mono">
                      {polarResult.cl_max.toFixed(3)}
                    </div>
                  </div>
                  <div className="rounded-lg border border-slate-700 bg-slate-800/50 p-3 text-center">
                    <div className="text-xs text-slate-400 mb-1">&alpha;_stall</div>
                    <div className="text-lg font-bold text-blue-400 font-mono">
                      {polarResult.alpha_stall.toFixed(1)}&deg;
                    </div>
                  </div>
                  <div className="rounded-lg border border-slate-700 bg-slate-800/50 p-3 text-center">
                    <div className="text-xs text-slate-400 mb-1">(Cl/Cd)_max</div>
                    <div className="text-lg font-bold text-amber-400 font-mono">
                      {polarResult.cl_cd_max.toFixed(1)}
                    </div>
                  </div>
                  <div className="rounded-lg border border-slate-700 bg-slate-800/50 p-3 text-center">
                    <div className="text-xs text-slate-400 mb-1">&alpha;_0</div>
                    <div className="text-lg font-bold text-rose-400 font-mono">
                      {polarResult.alpha_0.toFixed(2)}&deg;
                    </div>
                  </div>
                </div>
              </div>

              {/* Four subplot charts */}
              <div className="border border-slate-700 bg-surface-dark-secondary rounded-xl p-6">
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                  <div className="min-h-[300px]">
                    <Plot
                      data={polarClTraces as any}
                      layout={makePolarSubLayout('Cl vs \u03b1', 'Cl') as any}
                      config={plotConfig}
                      style={{ width: '100%', height: '300px' }}
                      useResizeHandler
                    />
                  </div>
                  <div className="min-h-[300px]">
                    <Plot
                      data={polarCdTraces as any}
                      layout={makePolarSubLayout('Cd vs \u03b1', 'Cd') as any}
                      config={plotConfig}
                      style={{ width: '100%', height: '300px' }}
                      useResizeHandler
                    />
                  </div>
                  <div className="min-h-[300px]">
                    <Plot
                      data={polarClCdTraces as any}
                      layout={makePolarSubLayout('Cl/Cd vs \u03b1', 'Cl/Cd') as any}
                      config={plotConfig}
                      style={{ width: '100%', height: '300px' }}
                      useResizeHandler
                    />
                  </div>
                  <div className="min-h-[300px]">
                    <Plot
                      data={polarCmTraces as any}
                      layout={makePolarSubLayout('Cm vs \u03b1', 'Cm') as any}
                      config={plotConfig}
                      style={{ width: '100%', height: '300px' }}
                      useResizeHandler
                    />
                  </div>
                </div>
              </div>
            </>
          )}
        </div>
      )}

      {/* ──────────────── 3D Correction Tab ──────────────── */}
      {activeTab === 'correction3d' && (
        <div className="space-y-6">
          <div className="border border-slate-700 bg-surface-dark-secondary rounded-xl p-6">
            <h3 className="text-sm font-semibold text-slate-200 uppercase tracking-wider mb-4">
              3D Rotational Correction
            </h3>

            {airfoilStations.length === 0 ? (
              <div className="flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-600 py-12">
                <Feather className="h-10 w-10 text-slate-300 mb-3" />
                <p className="text-sm text-slate-400">
                  No airfoils found. Define aero stations on a blade first.
                </p>
              </div>
            ) : (
              <div className="space-y-4">
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                  <div>
                    <label className="block text-xs font-medium text-slate-400 mb-1">
                      Airfoil
                    </label>
                    <select
                      value={selectedAirfoilId}
                      onChange={(e) => setSelectedAirfoilId(e.target.value)}
                      className="w-full rounded bg-slate-800 border border-slate-600 px-3 py-1.5 text-sm text-slate-100 focus:border-accent-500 focus:outline-none"
                    >
                      {airfoilStations.map((station) => (
                        <option key={station.id} value={station.id}>
                          {station.label}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-400 mb-1">
                      r/R (radial position)
                    </label>
                    <input
                      type="number"
                      value={corrRR}
                      onChange={(e) => setCorrRR(Number(e.target.value))}
                      step={0.05}
                      min={0}
                      max={1}
                      className="w-full rounded bg-slate-800 border border-slate-600 px-3 py-1.5 text-sm text-slate-100 focus:border-accent-500 focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-400 mb-1">
                      c/R (chord ratio)
                    </label>
                    <input
                      type="number"
                      value={corrCR}
                      onChange={(e) => setCorrCR(Number(e.target.value))}
                      step={0.01}
                      min={0}
                      max={1}
                      className="w-full rounded bg-slate-800 border border-slate-600 px-3 py-1.5 text-sm text-slate-100 focus:border-accent-500 focus:outline-none"
                    />
                  </div>
                </div>

                <div className="flex items-center gap-4">
                  <label className="flex items-center gap-2 text-sm text-slate-300 cursor-pointer select-none">
                    <input
                      type="checkbox"
                      checked={showOriginal}
                      onChange={(e) => setShowOriginal(e.target.checked)}
                      className="rounded border-slate-600 bg-slate-800 text-accent-500 focus:ring-accent-500 focus:ring-offset-0"
                    />
                    Show original polars (dashed)
                  </label>
                  <button
                    onClick={handleCorrection3D}
                    disabled={corrLoading || !selectedAirfoilId}
                    className="px-4 py-2 bg-accent-500 hover:bg-accent-600 text-white text-sm font-medium rounded transition-colors disabled:opacity-50 flex items-center gap-2"
                  >
                    {corrLoading ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Play className="h-4 w-4" />
                    )}
                    Compute Correction
                  </button>
                </div>
              </div>
            )}
          </div>

          {corrResult && (
            <div className="border border-slate-700 bg-surface-dark-secondary rounded-xl p-6">
              <div className="min-h-[450px]">
                <Plot
                  data={corrTraces as any}
                  layout={corrLayout as any}
                  config={plotConfig}
                  style={{ width: '100%', height: '450px' }}
                  useResizeHandler
                />
              </div>
            </div>
          )}
        </div>
      )}

      {/* ──────────────── NACA Generator Tab ──────────────── */}
      {activeTab === 'naca' && (
        <div className="space-y-6">
          <div className="border border-slate-700 bg-surface-dark-secondary rounded-xl p-6">
            <h3 className="text-sm font-semibold text-slate-200 uppercase tracking-wider mb-4">
              NACA Airfoil Generator
            </h3>

            <div className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-slate-400 mb-1">
                    NACA Digits (e.g. 0012, 4412, 23015)
                  </label>
                  <input
                    type="text"
                    value={nacaDigits}
                    onChange={(e) => setNacaDigits(e.target.value)}
                    placeholder="0012"
                    className="w-full rounded bg-slate-800 border border-slate-600 px-3 py-1.5 text-sm text-slate-100 focus:border-accent-500 focus:outline-none font-mono"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-400 mb-1">
                    Number of Points: {nacaNPoints}
                  </label>
                  <input
                    type="range"
                    min={50}
                    max={200}
                    value={nacaNPoints}
                    onChange={(e) => setNacaNPoints(Number(e.target.value))}
                    className="w-full accent-accent-500"
                  />
                  <div className="flex justify-between text-[10px] text-slate-500 mt-0.5">
                    <span>50</span>
                    <span>100</span>
                    <span>150</span>
                    <span>200</span>
                  </div>
                </div>
              </div>

              <button
                onClick={handleGenerateNACA}
                disabled={nacaLoading || !nacaDigits.trim()}
                className="px-4 py-2 bg-accent-500 hover:bg-accent-600 text-white text-sm font-medium rounded transition-colors disabled:opacity-50 flex items-center gap-2"
              >
                {nacaLoading ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Play className="h-4 w-4" />
                )}
                Generate Airfoil
              </button>
            </div>
          </div>

          {nacaResult && (
            <div className="border border-slate-700 bg-surface-dark-secondary rounded-xl p-6">
              <div className="min-h-[400px]">
                <Plot
                  data={nacaTraces as any}
                  layout={nacaLayout as any}
                  config={plotConfig}
                  style={{ width: '100%', height: '400px' }}
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
