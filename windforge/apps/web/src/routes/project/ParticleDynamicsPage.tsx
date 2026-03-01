import { useState, useCallback, useMemo } from 'react';
import { useParams } from 'react-router-dom';
import { Atom, MoveDown, Orbit, Loader2 } from 'lucide-react';
import toast from 'react-hot-toast';
import Plot from 'react-plotly.js';
import axios from 'axios';

const API_BASE = (window as unknown as Record<string, string>).__WINDFORGE_API_URL__
  ? `${(window as unknown as Record<string, string>).__WINDFORGE_API_URL__}/api/v1` : '/api/v1';

function partPost<T>(projectId: string, endpoint: string, data: unknown): Promise<T> {
  const token = localStorage.getItem('windforge_token');
  return axios.post<T>(`${API_BASE}/projects/${projectId}/particles/${endpoint}`, data, {
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
  }).then((res) => res.data);
}

const TABS = [
  { key: 'freefall', label: 'Free Fall', icon: MoveDown },
  { key: 'orbit', label: 'Orbits', icon: Orbit },
  { key: 'spring', label: 'Spring-Mass', icon: Atom },
] as const;
type TabKey = (typeof TABS)[number]['key'];

interface FreeFallResult { time: number[]; x: number[]; z: number[]; vx: number[]; vz: number[]; z_analytical: number[]; }
interface OrbitResult { time: number[]; x1: number[]; z1: number[]; x2: number[]; z2: number[]; energy_kinetic: number[]; energy_potential: number[]; }
interface SpringResult { time: number[]; z: number[]; vz: number[]; energy_kinetic: number[]; energy_spring: number[]; energy_total: number[]; }

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

export default function ParticleDynamicsPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const [activeTab, setActiveTab] = useState<TabKey>('freefall');
  const [error, setError] = useState<string | null>(null);

  /* ---- Free Fall ---- */
  const [ffZ0, setFfZ0] = useState(100);
  const [ffVx, setFfVx] = useState(5);
  const [ffVz, setFfVz] = useState(10);
  const [ffTmax, setFfTmax] = useState(5);
  const [ffResult, setFfResult] = useState<FreeFallResult | null>(null);
  const [ffLoading, setFfLoading] = useState(false);

  /* ---- Orbit ---- */
  const [orbEcc, setOrbEcc] = useState(0.0);
  const [orbNorbits, setOrbNorbits] = useState(2.0);
  const [orbResult, setOrbResult] = useState<OrbitResult | null>(null);
  const [orbLoading, setOrbLoading] = useState(false);

  /* ---- Spring-Mass ---- */
  const [spM, setSpM] = useState(10);
  const [spK, setSpK] = useState(100);
  const [spC, setSpC] = useState(1);
  const [spOffset, setSpOffset] = useState(2);
  const [spTmax, setSpTmax] = useState(10);
  const [spResult, setSpResult] = useState<SpringResult | null>(null);
  const [spLoading, setSpLoading] = useState(false);

  const handleFreeFall = useCallback(async () => {
    if (!projectId) return;
    setFfLoading(true); setError(null); setFfResult(null);
    try { setFfResult(await partPost<FreeFallResult>(projectId, 'free-fall', { z0: ffZ0, vx0: ffVx, vz0: ffVz, t_max: ffTmax })); toast.success('Free fall simulated'); }
    catch { setError('Free fall failed'); toast.error('Failed'); }
    finally { setFfLoading(false); }
  }, [projectId, ffZ0, ffVx, ffVz, ffTmax]);

  const handleOrbit = useCallback(async () => {
    if (!projectId) return;
    setOrbLoading(true); setError(null); setOrbResult(null);
    try { setOrbResult(await partPost<OrbitResult>(projectId, 'orbit', { eccentricity: orbEcc, n_orbits: orbNorbits })); toast.success('Orbit simulated'); }
    catch { setError('Orbit simulation failed'); toast.error('Failed'); }
    finally { setOrbLoading(false); }
  }, [projectId, orbEcc, orbNorbits]);

  const handleSpring = useCallback(async () => {
    if (!projectId) return;
    setSpLoading(true); setError(null); setSpResult(null);
    try { setSpResult(await partPost<SpringResult>(projectId, 'spring-mass', { m: spM, k: spK, c: spC, z0_offset: spOffset, t_max: spTmax })); toast.success('Spring-mass simulated'); }
    catch { setError('Spring-mass failed'); toast.error('Failed'); }
    finally { setSpLoading(false); }
  }, [projectId, spM, spK, spC, spOffset, spTmax]);

  /* ---- Traces ---- */
  const ffTrajectoryTraces = useMemo((): Plotly.Data[] => {
    if (!ffResult) return [];
    return [
      { x: ffResult.x, y: ffResult.z, name: 'Simulated', type: 'scatter', line: { color: '#22d3ee' } } as Plotly.Data,
      { x: ffResult.x, y: ffResult.z_analytical, name: 'Analytical', type: 'scatter', line: { color: '#f97316', dash: 'dash' } } as Plotly.Data,
    ];
  }, [ffResult]);

  const ffTimeTraces = useMemo((): Plotly.Data[] => {
    if (!ffResult) return [];
    return [
      { x: ffResult.time, y: ffResult.z, name: 'z(t)', type: 'scatter', line: { color: '#22d3ee' } } as Plotly.Data,
      { x: ffResult.time, y: ffResult.vz, name: 'vz(t)', type: 'scatter', line: { color: '#a78bfa', dash: 'dash' } } as Plotly.Data,
    ];
  }, [ffResult]);

  const orbitTraces = useMemo((): Plotly.Data[] => {
    if (!orbResult) return [];
    return [
      { x: orbResult.x1, y: orbResult.z1, name: 'Body 1 (Central)', type: 'scatter', mode: 'lines', line: { color: '#f97316', width: 2 } } as Plotly.Data,
      { x: orbResult.x2, y: orbResult.z2, name: 'Body 2 (Orbiting)', type: 'scatter', mode: 'lines', line: { color: '#22d3ee' } } as Plotly.Data,
    ];
  }, [orbResult]);

  const springTraces = useMemo((): Plotly.Data[] => {
    if (!spResult) return [];
    return [
      { x: spResult.time, y: spResult.z, name: 'z(t)', type: 'scatter', line: { color: '#22d3ee' } } as Plotly.Data,
      { x: spResult.time, y: spResult.vz, name: 'vz(t)', type: 'scatter', line: { color: '#a78bfa', dash: 'dash' } } as Plotly.Data,
    ];
  }, [spResult]);

  const springEnergyTraces = useMemo((): Plotly.Data[] => {
    if (!spResult) return [];
    return [
      { x: spResult.time, y: spResult.energy_kinetic, name: 'Kinetic', type: 'scatter', line: { color: '#22d3ee' } } as Plotly.Data,
      { x: spResult.time, y: spResult.energy_spring, name: 'Spring', type: 'scatter', line: { color: '#f97316' } } as Plotly.Data,
      { x: spResult.time, y: spResult.energy_total, name: 'Total', type: 'scatter', line: { color: '#34d399', dash: 'dash' } } as Plotly.Data,
    ];
  }, [spResult]);

  const isLoading: Record<TabKey, boolean> = { freefall: ffLoading, orbit: orbLoading, spring: spLoading };
  const handleCompute: Record<TabKey, () => Promise<void>> = { freefall: handleFreeFall, orbit: handleOrbit, spring: handleSpring };

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <Atom className="h-6 w-6 text-amber-400" />
        <h2 className="text-lg font-semibold text-white">Particle Dynamics</h2>
        <span className="text-xs text-slate-500 bg-slate-800 px-2 py-0.5 rounded">welib.yams.partdyn</span>
      </div>

      <div className="flex flex-wrap gap-1">
        {TABS.map((tab) => { const Icon = tab.icon; return (
          <button key={tab.key} onClick={() => setActiveTab(tab.key)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              activeTab === tab.key ? 'bg-amber-500/20 text-amber-300 ring-1 ring-amber-500/40' : 'bg-slate-800 text-slate-400 hover:text-slate-200 hover:bg-slate-700'}`}>
            <Icon className="h-3.5 w-3.5" />{tab.label}
          </button>
        ); })}
      </div>

      {error && <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3 text-sm text-red-300">{error}</div>}

      <div className="grid grid-cols-1 xl:grid-cols-4 gap-4">
        <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-700/50 space-y-3">
          <h3 className="text-sm font-medium text-slate-300 mb-2">Parameters</h3>

          {activeTab === 'freefall' && (<>
            <NumberInput label="Initial height" value={ffZ0} onChange={setFfZ0} unit="m" step={10} min={0} />
            <NumberInput label="Horizontal v₀" value={ffVx} onChange={setFfVx} unit="m/s" step={1} />
            <NumberInput label="Vertical v₀" value={ffVz} onChange={setFfVz} unit="m/s" step={1} />
            <NumberInput label="Duration" value={ffTmax} onChange={setFfTmax} unit="s" step={1} min={1} />
          </>)}

          {activeTab === 'orbit' && (<>
            <NumberInput label="Eccentricity" value={orbEcc} onChange={setOrbEcc} step={0.1} min={0} max={0.99} />
            <NumberInput label="Orbits" value={orbNorbits} onChange={setOrbNorbits} step={0.5} min={0.5} max={10} />
            <p className="text-xs text-slate-500">Earth-Moon system. e = 0 is circular.</p>
          </>)}

          {activeTab === 'spring' && (<>
            <NumberInput label="Mass" value={spM} onChange={setSpM} unit="kg" step={1} min={0.1} />
            <NumberInput label="Stiffness" value={spK} onChange={setSpK} unit="N/m" step={10} min={1} />
            <NumberInput label="Damping" value={spC} onChange={setSpC} unit="Ns/m" step={0.5} min={0} />
            <NumberInput label="Initial offset" value={spOffset} onChange={setSpOffset} unit="m" step={0.5} />
            <NumberInput label="Duration" value={spTmax} onChange={setSpTmax} unit="s" step={2} min={1} />
          </>)}

          <button onClick={handleCompute[activeTab]} disabled={isLoading[activeTab]}
            className="w-full mt-2 flex items-center justify-center gap-2 px-4 py-2 rounded-lg bg-amber-600 text-white text-sm font-medium hover:bg-amber-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors">
            {isLoading[activeTab] ? <><Loader2 className="h-4 w-4 animate-spin" />Computing…</> : 'Compute'}
          </button>
        </div>

        <div className="xl:col-span-3 space-y-4">
          {/* Free Fall */}
          {activeTab === 'freefall' && ffResult && (
            <div className="space-y-4">
              <div className="bg-slate-800/30 rounded-xl border border-slate-700/30 p-2">
                <Plot data={ffTrajectoryTraces}
                  layout={makePlotLayout({ title: 'Projectile Trajectory', xaxis: { title: 'x (m)' }, yaxis: { title: 'z (m)' }, height: 350 }) as Partial<Plotly.Layout>}
                  config={{ responsive: true }} className="w-full" />
              </div>
              <div className="bg-slate-800/30 rounded-xl border border-slate-700/30 p-2">
                <Plot data={ffTimeTraces}
                  layout={makePlotLayout({ title: 'Position & Velocity vs Time', xaxis: { title: 'Time (s)' }, yaxis: { title: 'z (m) / vz (m/s)' }, height: 300 }) as Partial<Plotly.Layout>}
                  config={{ responsive: true }} className="w-full" />
              </div>
            </div>
          )}

          {/* Orbits */}
          {activeTab === 'orbit' && orbResult && (
            <div className="bg-slate-800/30 rounded-xl border border-slate-700/30 p-2">
              <Plot data={orbitTraces}
                layout={makePlotLayout({
                  title: `Two-Body Orbital Motion (e = ${orbEcc})`,
                  xaxis: { title: 'x / r₀', scaleanchor: 'y', scaleratio: 1 },
                  yaxis: { title: 'y / r₀' },
                  height: 550,
                }) as Partial<Plotly.Layout>}
                config={{ responsive: true }} className="w-full" />
            </div>
          )}

          {/* Spring-Mass */}
          {activeTab === 'spring' && spResult && (
            <div className="space-y-4">
              <div className="bg-slate-800/30 rounded-xl border border-slate-700/30 p-2">
                <Plot data={springTraces}
                  layout={makePlotLayout({ title: 'Spring-Mass Oscillation', xaxis: { title: 'Time (s)' }, yaxis: { title: 'z (m) / vz (m/s)' }, height: 350 }) as Partial<Plotly.Layout>}
                  config={{ responsive: true }} className="w-full" />
              </div>
              <div className="bg-slate-800/30 rounded-xl border border-slate-700/30 p-2">
                <Plot data={springEnergyTraces}
                  layout={makePlotLayout({ title: 'Energy Balance', xaxis: { title: 'Time (s)' }, yaxis: { title: 'Energy (J)' }, height: 300 }) as Partial<Plotly.Layout>}
                  config={{ responsive: true }} className="w-full" />
              </div>
            </div>
          )}

          {/* Empty states */}
          {((activeTab === 'freefall' && !ffResult && !ffLoading) ||
            (activeTab === 'orbit' && !orbResult && !orbLoading) ||
            (activeTab === 'spring' && !spResult && !spLoading)) && (
            <div className="bg-slate-800/20 rounded-xl border border-slate-700/30 p-12 text-center text-slate-500">
              Click <span className="text-amber-400">Compute</span> to generate the visualization
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
