import { useState, useCallback, useMemo } from 'react';
import { useParams } from 'react-router-dom';
import { Activity, BarChart3, TrendingUp, Loader2 } from 'lucide-react';
import toast from 'react-hot-toast';
import Plot from 'react-plotly.js';
import axios from 'axios';

const API_BASE = (window as unknown as Record<string, string>).__WINDFORGE_API_URL__
  ? `${(window as unknown as Record<string, string>).__WINDFORGE_API_URL__}/api/v1` : '/api/v1';

function dynPost<T>(projectId: string, endpoint: string, data: unknown): Promise<T> {
  const token = localStorage.getItem('windforge_token');
  return axios.post<T>(`${API_BASE}/projects/${projectId}/dynamics/${endpoint}`, data, {
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
  }).then((res) => res.data);
}

const TABS = [
  { key: 'forced', label: 'Forced Vibrations', icon: Activity },
  { key: 'bode', label: 'Bode Plot', icon: BarChart3 },
  { key: 'step', label: 'Step/Impulse', icon: TrendingUp },
  { key: 'lorenz', label: 'Lorenz Attractor', icon: Activity },
  { key: 'pendulum', label: 'Pendulum', icon: Activity },
] as const;
type TabKey = (typeof TABS)[number]['key'];

interface ForcedResult { frequency_ratios: number[]; amplitude_curves: Record<string, number[]>; phase_curves: Record<string, number[]>; }
interface BodeResult { frequencies: number[]; magnitude_db: number[]; phase_deg: number[]; }
interface StepResult { time: number[]; displacement: number[]; velocity: number[]; }
interface LorenzResult { time: number[]; x: number[]; y: number[]; z: number[]; }
interface PendulumResult { time: number[]; theta_deg: number[]; omega_deg_s: number[]; x_pos: number[]; y_pos: number[]; }

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

export default function DynamicsPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const [activeTab, setActiveTab] = useState<TabKey>('forced');
  const [error, setError] = useState<string | null>(null);

  // Forced Vibration
  const [fvResult, setFvResult] = useState<ForcedResult | null>(null);
  const [fvLoading, setFvLoading] = useState(false);

  // Bode
  const [bMass, setBMass] = useState(1.0);
  const [bDamp, setBDamp] = useState(0.5);
  const [bStiff, setBStiff] = useState(10.0);
  const [bResult, setBResult] = useState<BodeResult | null>(null);
  const [bLoading, setBLoading] = useState(false);

  // Step/Impulse
  const [sMass, setSMass] = useState(1.0);
  const [sDamp, setSDamp] = useState(0.5);
  const [sStiff, setSStiff] = useState(10.0);
  const [sType, setSType] = useState('step');
  const [sTmax, setSTmax] = useState(10.0);
  const [sResult, setSResult] = useState<StepResult | null>(null);
  const [sLoading, setSLoading] = useState(false);

  // Lorenz
  const [lSigma, setLSigma] = useState(10.0);
  const [lRho, setLRho] = useState(28.0);
  const [lBeta, setLBeta] = useState(2.667);
  const [lTmax, setLTmax] = useState(50.0);
  const [lResult, setLResult] = useState<LorenzResult | null>(null);
  const [lLoading, setLLoading] = useState(false);

  // Pendulum
  const [pLen, setPLen] = useState(1.0);
  const [pDamp, setPDamp] = useState(0.0);
  const [pTheta, setPTheta] = useState(30.0);
  const [pTmax, setPTmax] = useState(20.0);
  const [pResult, setPResult] = useState<PendulumResult | null>(null);
  const [pLoading, setPLoading] = useState(false);

  const handleForced = useCallback(async () => {
    if (!projectId) return;
    setFvLoading(true); setError(null); setFvResult(null);
    try { setFvResult(await dynPost<ForcedResult>(projectId, 'forced-vibration', {})); toast.success('Forced vibration computed'); }
    catch { setError('Forced vibration failed'); toast.error('Failed'); }
    finally { setFvLoading(false); }
  }, [projectId]);

  const handleBode = useCallback(async () => {
    if (!projectId) return;
    setBLoading(true); setError(null); setBResult(null);
    try { setBResult(await dynPost<BodeResult>(projectId, 'bode-plot', { mass: bMass, damping: bDamp, stiffness: bStiff })); toast.success('Bode plot computed'); }
    catch { setError('Bode plot failed'); toast.error('Failed'); }
    finally { setBLoading(false); }
  }, [projectId, bMass, bDamp, bStiff]);

  const handleStep = useCallback(async () => {
    if (!projectId) return;
    setSLoading(true); setError(null); setSResult(null);
    try { setSResult(await dynPost<StepResult>(projectId, 'step-impulse', { mass: sMass, damping: sDamp, stiffness: sStiff, response_type: sType, t_max: sTmax })); toast.success(`${sType} response computed`); }
    catch { setError('Step response failed'); toast.error('Failed'); }
    finally { setSLoading(false); }
  }, [projectId, sMass, sDamp, sStiff, sType, sTmax]);

  const handleLorenz = useCallback(async () => {
    if (!projectId) return;
    setLLoading(true); setError(null); setLResult(null);
    try { setLResult(await dynPost<LorenzResult>(projectId, 'lorenz', { sigma: lSigma, rho: lRho, beta: lBeta, t_max: lTmax })); toast.success('Lorenz attractor computed'); }
    catch { setError('Lorenz failed'); toast.error('Failed'); }
    finally { setLLoading(false); }
  }, [projectId, lSigma, lRho, lBeta, lTmax]);

  const handlePendulum = useCallback(async () => {
    if (!projectId) return;
    setPLoading(true); setError(null); setPResult(null);
    try { setPResult(await dynPost<PendulumResult>(projectId, 'pendulum', { length: pLen, damping_ratio: pDamp, theta0: pTheta, t_max: pTmax })); toast.success('Pendulum simulated'); }
    catch { setError('Pendulum failed'); toast.error('Failed'); }
    finally { setPLoading(false); }
  }, [projectId, pLen, pDamp, pTheta, pTmax]);

  // Plot traces
  const forcedTraces = useMemo(() => {
    if (!fvResult) return [];
    const colors = ['#22d3ee', '#f97316', '#a78bfa', '#34d399', '#f472b6'];
    return Object.entries(fvResult.amplitude_curves).map(([label, vals], i) => ({
      x: fvResult.frequency_ratios, y: vals, name: label, type: 'scatter' as const, line: { color: colors[i % colors.length] },
    }));
  }, [fvResult]);

  const bodeTraces = useMemo(() => bResult ? [
    { x: bResult.frequencies, y: bResult.magnitude_db, name: 'Magnitude', type: 'scatter' as const, line: { color: '#22d3ee' } },
  ] : [], [bResult]);

  const bodePhaseTraces = useMemo(() => bResult ? [
    { x: bResult.frequencies, y: bResult.phase_deg, name: 'Phase', type: 'scatter' as const, line: { color: '#f97316' } },
  ] : [], [bResult]);

  const stepTraces = useMemo(() => sResult ? [
    { x: sResult.time, y: sResult.displacement, name: 'Displacement', type: 'scatter' as const, line: { color: '#22d3ee' } },
    { x: sResult.time, y: sResult.velocity, name: 'Velocity', type: 'scatter' as const, line: { color: '#f97316', dash: 'dash' as const } },
  ] : [], [sResult]);

  const lorenzTraces = useMemo(() => lResult ? [{
    x: lResult.x, y: lResult.y, z: lResult.z, type: 'scatter3d' as const, mode: 'lines' as const,
    line: { color: lResult.time, colorscale: 'Viridis', width: 1.5 }, name: 'Lorenz',
  }] : [], [lResult]);

  const pendulumTraces = useMemo(() => pResult ? [
    { x: pResult.time, y: pResult.theta_deg, name: 'θ (deg)', type: 'scatter' as const, line: { color: '#22d3ee' } },
  ] : [], [pResult]);

  const pendulumPhaseTraces = useMemo(() => pResult ? [
    { x: pResult.theta_deg, y: pResult.omega_deg_s, name: 'Phase portrait', type: 'scatter' as const, mode: 'lines' as const, line: { color: '#a78bfa' } },
  ] : [], [pResult]);

  const isLoading = { forced: fvLoading, bode: bLoading, step: sLoading, lorenz: lLoading, pendulum: pLoading }[activeTab];
  const handleCompute = { forced: handleForced, bode: handleBode, step: handleStep, lorenz: handleLorenz, pendulum: handlePendulum }[activeTab];

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <Activity className="h-6 w-6 text-purple-400" />
        <h2 className="text-lg font-semibold text-white">System Dynamics</h2>
        <span className="text-xs text-slate-500 bg-slate-800 px-2 py-0.5 rounded">welib.system</span>
      </div>

      <div className="flex flex-wrap gap-1">
        {TABS.map((tab) => { const Icon = tab.icon; return (
          <button key={tab.key} onClick={() => setActiveTab(tab.key)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              activeTab === tab.key ? 'bg-purple-500/20 text-purple-300 ring-1 ring-purple-500/40' : 'bg-slate-800 text-slate-400 hover:text-slate-200 hover:bg-slate-700'}`}>
            <Icon className="h-3.5 w-3.5" />{tab.label}
          </button>
        ); })}
      </div>

      {error && <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3 text-sm text-red-300">{error}</div>}

      <div className="grid grid-cols-1 xl:grid-cols-4 gap-4">
        <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-700/50 space-y-3">
          <h3 className="text-sm font-medium text-slate-300 mb-2">Parameters</h3>

          {activeTab === 'forced' && <p className="text-xs text-slate-500">Compares amplitude ratio xk/F₀ vs frequency ratio f/fₙ for damping ratios ζ = 0, 0.1, 0.2, 0.5, 1.0</p>}

          {activeTab === 'bode' && (<>
            <NumberInput label="Mass" value={bMass} onChange={setBMass} unit="kg" step={0.1} min={0.01} />
            <NumberInput label="Damping" value={bDamp} onChange={setBDamp} unit="Ns/m" step={0.1} min={0} />
            <NumberInput label="Stiffness" value={bStiff} onChange={setBStiff} unit="N/m" step={1} min={0.1} />
          </>)}

          {activeTab === 'step' && (<>
            <NumberInput label="Mass" value={sMass} onChange={setSMass} unit="kg" step={0.1} min={0.01} />
            <NumberInput label="Damping" value={sDamp} onChange={setSDamp} unit="Ns/m" step={0.1} min={0} />
            <NumberInput label="Stiffness" value={sStiff} onChange={setSStiff} unit="N/m" step={1} min={0.1} />
            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1">Response Type</label>
              <select value={sType} onChange={(e) => setSType(e.target.value)}
                className="bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-sm text-slate-100 w-full">
                <option value="step">Step</option><option value="impulse">Impulse</option><option value="ramp">Ramp</option>
              </select>
            </div>
            <NumberInput label="Duration" value={sTmax} onChange={setSTmax} unit="s" step={1} min={1} />
          </>)}

          {activeTab === 'lorenz' && (<>
            <NumberInput label="σ" value={lSigma} onChange={setLSigma} step={1} />
            <NumberInput label="ρ" value={lRho} onChange={setLRho} step={1} />
            <NumberInput label="β" value={lBeta} onChange={setLBeta} step={0.1} />
            <NumberInput label="Duration" value={lTmax} onChange={setLTmax} unit="s" step={10} min={10} />
          </>)}

          {activeTab === 'pendulum' && (<>
            <NumberInput label="Length" value={pLen} onChange={setPLen} unit="m" step={0.1} min={0.1} />
            <NumberInput label="Damping ratio" value={pDamp} onChange={setPDamp} step={0.05} min={0} max={2} />
            <NumberInput label="Initial angle" value={pTheta} onChange={setPTheta} unit="°" step={5} />
            <NumberInput label="Duration" value={pTmax} onChange={setPTmax} unit="s" step={5} min={5} />
          </>)}

          <button onClick={handleCompute} disabled={isLoading}
            className="w-full mt-2 flex items-center justify-center gap-2 px-4 py-2 rounded-lg bg-purple-600 text-white text-sm font-medium hover:bg-purple-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors">
            {isLoading ? <><Loader2 className="h-4 w-4 animate-spin" />Computing…</> : 'Compute'}
          </button>
        </div>

        <div className="xl:col-span-3 space-y-4">
          {activeTab === 'forced' && fvResult && (
            <div className="bg-slate-800/30 rounded-xl border border-slate-700/30 p-2">
              <Plot data={forcedTraces as Plotly.Data[]} layout={makePlotLayout({ title: 'Forced Vibration — Amplitude Ratio vs Frequency Ratio', xaxis: { title: 'f/fₙ' }, yaxis: { title: 'xk/F₀' }, height: 450 }) as Partial<Plotly.Layout>} config={{ responsive: true }} className="w-full" />
            </div>
          )}

          {activeTab === 'bode' && bResult && (
            <div className="space-y-4">
              <div className="bg-slate-800/30 rounded-xl border border-slate-700/30 p-2">
                <Plot data={bodeTraces as Plotly.Data[]} layout={makePlotLayout({ title: 'Bode Plot — Magnitude', xaxis: { title: 'Frequency (Hz)', type: 'log' }, yaxis: { title: 'Magnitude (dB)' }, height: 350 }) as Partial<Plotly.Layout>} config={{ responsive: true }} className="w-full" />
              </div>
              <div className="bg-slate-800/30 rounded-xl border border-slate-700/30 p-2">
                <Plot data={bodePhaseTraces as Plotly.Data[]} layout={makePlotLayout({ title: 'Bode Plot — Phase', xaxis: { title: 'Frequency (Hz)', type: 'log' }, yaxis: { title: 'Phase (°)' }, height: 300 }) as Partial<Plotly.Layout>} config={{ responsive: true }} className="w-full" />
              </div>
            </div>
          )}

          {activeTab === 'step' && sResult && (
            <div className="bg-slate-800/30 rounded-xl border border-slate-700/30 p-2">
              <Plot data={stepTraces as Plotly.Data[]} layout={makePlotLayout({ title: `${sType.charAt(0).toUpperCase() + sType.slice(1)} Response`, xaxis: { title: 'Time (s)' }, yaxis: { title: 'Response' }, height: 450 }) as Partial<Plotly.Layout>} config={{ responsive: true }} className="w-full" />
            </div>
          )}

          {activeTab === 'lorenz' && lResult && (
            <div className="bg-slate-800/30 rounded-xl border border-slate-700/30 p-2">
              <Plot data={lorenzTraces as Plotly.Data[]} layout={{
                ...makePlotLayout({ title: 'Lorenz Attractor' }),
                scene: { xaxis: { title: 'x', color: '#9ca3af' }, yaxis: { title: 'y', color: '#9ca3af' }, zaxis: { title: 'z', color: '#9ca3af' }, bgcolor: 'rgba(17,24,39,0.8)' },
                margin: { t: 50, r: 10, b: 10, l: 10 }, height: 550,
              } as Partial<Plotly.Layout>} config={{ responsive: true }} className="w-full" />
            </div>
          )}

          {activeTab === 'pendulum' && pResult && (
            <div className="space-y-4">
              <div className="bg-slate-800/30 rounded-xl border border-slate-700/30 p-2">
                <Plot data={pendulumTraces as Plotly.Data[]} layout={makePlotLayout({ title: 'Pendulum Angle vs Time', xaxis: { title: 'Time (s)' }, yaxis: { title: 'θ (°)' }, height: 350 }) as Partial<Plotly.Layout>} config={{ responsive: true }} className="w-full" />
              </div>
              <div className="bg-slate-800/30 rounded-xl border border-slate-700/30 p-2">
                <Plot data={pendulumPhaseTraces as Plotly.Data[]} layout={makePlotLayout({ title: 'Phase Portrait', xaxis: { title: 'θ (°)' }, yaxis: { title: 'ω (°/s)' }, height: 350 }) as Partial<Plotly.Layout>} config={{ responsive: true }} className="w-full" />
              </div>
            </div>
          )}

          {/* Empty states */}
          {((activeTab === 'forced' && !fvResult && !fvLoading) ||
            (activeTab === 'bode' && !bResult && !bLoading) ||
            (activeTab === 'step' && !sResult && !sLoading) ||
            (activeTab === 'lorenz' && !lResult && !lLoading) ||
            (activeTab === 'pendulum' && !pResult && !pLoading)) && (
            <div className="bg-slate-800/20 rounded-xl border border-slate-700/30 p-12 text-center text-slate-500">
              Click <span className="text-purple-400">Compute</span> to generate the visualization
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
