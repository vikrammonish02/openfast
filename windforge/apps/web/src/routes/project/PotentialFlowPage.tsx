import { useState, useCallback, useMemo } from 'react';
import { useParams } from 'react-router-dom';
import { Waves, Circle, Feather, Loader2 } from 'lucide-react';
import toast from 'react-hot-toast';
import Plot from 'react-plotly.js';
import axios from 'axios';

const API_BASE = (window as unknown as Record<string, string>).__WINDFORGE_API_URL__
  ? `${(window as unknown as Record<string, string>).__WINDFORGE_API_URL__}/api/v1` : '/api/v1';

function pfPost<T>(projectId: string, endpoint: string, data: unknown): Promise<T> {
  const token = localStorage.getItem('windforge_token');
  return axios.post<T>(`${API_BASE}/projects/${projectId}/potential-flow/${endpoint}`, data, {
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
  }).then((res) => res.data);
}

const TABS = [
  { key: 'vortex', label: 'Vortex Point', icon: Waves },
  { key: 'cylinder', label: 'Cylinder Flow', icon: Circle },
  { key: 'kt', label: 'Karman-Trefftz', icon: Feather },
] as const;
type TabKey = (typeof TABS)[number]['key'];

/* ---- Result interfaces ---- */
interface VortexResult { x: number[]; y: number[]; U: number[][]; V: number[][]; speed: number[][]; psi: number[][]; }
interface CylinderResult {
  x: number[]; y: number[]; U: number[][]; V: number[][]; speed: number[][];
  xc: number[]; yc: number[]; stag_x: number[]; stag_y: number[];
  theta_deg: number[]; Cp_theta: number[];
}
interface KTResult {
  airfoil_x: number[]; airfoil_y: number[];
  wall_x: number[]; wall_y: number[]; wall_Cp: number[];
  x: number[]; y: number[];
  u_field: number[][]; v_field: number[][]; Cp_field: number[][]; speed_field: number[][];
}

function makePlotLayout(overrides: Record<string, unknown> = {}) {
  return {
    paper_bgcolor: 'transparent', plot_bgcolor: 'rgba(17,24,39,0.8)',
    font: { family: 'ui-monospace, monospace', size: 10, color: '#9ca3af' },
    margin: { t: 40, r: 30, b: 60, l: 70 },
    xaxis: { gridcolor: 'rgba(100,116,139,0.2)', zeroline: false, ...(overrides.xaxis as object || {}) },
    yaxis: { gridcolor: 'rgba(100,116,139,0.2)', zeroline: false, scaleanchor: 'x', scaleratio: 1, ...(overrides.yaxis as object || {}) },
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

export default function PotentialFlowPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const [activeTab, setActiveTab] = useState<TabKey>('vortex');
  const [error, setError] = useState<string | null>(null);

  /* ---- Vortex state ---- */
  const [vGamma, setVGamma] = useState(5.0);
  const [vResult, setVResult] = useState<VortexResult | null>(null);
  const [vLoading, setVLoading] = useState(false);

  /* ---- Cylinder state ---- */
  const [cU0, setCU0] = useState(1.0);
  const [cR, setCR] = useState(1.0);
  const [cGamma, setCGamma] = useState(0.0);
  const [cAlpha, setCAlpha] = useState(0.0);
  const [cResult, setCResult] = useState<CylinderResult | null>(null);
  const [cLoading, setCLoading] = useState(false);

  /* ---- KT state ---- */
  const [ktXC, setKtXC] = useState(-0.2);
  const [ktYC, setKtYC] = useState(0.1);
  const [ktTau, setKtTau] = useState(10.0);
  const [ktAlpha, setKtAlpha] = useState(5.0);
  const [ktResult, setKtResult] = useState<KTResult | null>(null);
  const [ktLoading, setKtLoading] = useState(false);

  /* ---- Handlers ---- */
  const handleVortex = useCallback(async () => {
    if (!projectId) return;
    setVLoading(true); setError(null); setVResult(null);
    try { setVResult(await pfPost<VortexResult>(projectId, 'vortex-point', { Gamma: vGamma })); toast.success('Vortex field computed'); }
    catch { setError('Vortex computation failed'); toast.error('Failed'); }
    finally { setVLoading(false); }
  }, [projectId, vGamma]);

  const handleCylinder = useCallback(async () => {
    if (!projectId) return;
    setCLoading(true); setError(null); setCResult(null);
    try {
      setCResult(await pfPost<CylinderResult>(projectId, 'cylinder-flow', {
        U0: cU0, R: cR, Gamma: cGamma, alpha_deg: cAlpha,
      }));
      toast.success('Cylinder flow computed');
    } catch { setError('Cylinder flow failed'); toast.error('Failed'); }
    finally { setCLoading(false); }
  }, [projectId, cU0, cR, cGamma, cAlpha]);

  const handleKT = useCallback(async () => {
    if (!projectId) return;
    setKtLoading(true); setError(null); setKtResult(null);
    try {
      setKtResult(await pfPost<KTResult>(projectId, 'karman-trefftz', {
        XC: ktXC, YC: ktYC, tau_deg: ktTau, alpha_deg: ktAlpha,
      }));
      toast.success('Karman-Trefftz computed');
    } catch { setError('KT computation failed'); toast.error('Failed'); }
    finally { setKtLoading(false); }
  }, [projectId, ktXC, ktYC, ktTau, ktAlpha]);

  /* ---- Plot traces ---- */
  const vortexTraces = useMemo((): Plotly.Data[] => {
    if (!vResult) return [];
    return [
      {
        z: vResult.speed, x: vResult.x, y: vResult.y,
        type: 'heatmap', colorscale: 'Viridis', showscale: true,
        colorbar: { title: '|V|', tickfont: { color: '#9ca3af' }, titlefont: { color: '#9ca3af' } },
      } as Plotly.Data,
      {
        z: vResult.psi, x: vResult.x, y: vResult.y,
        type: 'contour', showscale: false, ncontours: 30,
        line: { color: 'rgba(255,255,255,0.3)', width: 0.5 },
        contours: { coloring: 'none' },
      } as Plotly.Data,
    ];
  }, [vResult]);

  const cylinderFlowTraces = useMemo((): Plotly.Data[] => {
    if (!cResult) return [];
    const traces: Plotly.Data[] = [
      {
        z: cResult.speed, x: cResult.x, y: cResult.y,
        type: 'heatmap', colorscale: 'RdBu', showscale: true, reversescale: true, zmin: 0, zmax: 3,
        colorbar: { title: '|V|/U0', tickfont: { color: '#9ca3af' }, titlefont: { color: '#9ca3af' } },
      } as Plotly.Data,
      // Cylinder boundary
      {
        x: cResult.xc, y: cResult.yc, type: 'scatter', mode: 'lines',
        line: { color: '#f97316', width: 2 }, name: 'Cylinder', showlegend: false,
      } as Plotly.Data,
    ];
    // Stagnation points
    if (cResult.stag_x.length > 0) {
      traces.push({
        x: cResult.stag_x, y: cResult.stag_y, type: 'scatter', mode: 'markers',
        marker: { color: '#ef4444', size: 8, symbol: 'x' }, name: 'Stagnation', showlegend: false,
      } as Plotly.Data);
    }
    return traces;
  }, [cResult]);

  const cylinderCpTraces = useMemo((): Plotly.Data[] => {
    if (!cResult || cResult.theta_deg.length === 0) return [];
    return [{
      x: cResult.theta_deg, y: cResult.Cp_theta, type: 'scatter',
      line: { color: '#22d3ee' }, name: 'Cp(θ)',
    } as Plotly.Data];
  }, [cResult]);

  const ktFlowTraces = useMemo((): Plotly.Data[] => {
    if (!ktResult || ktResult.x.length === 0) return [];
    return [
      {
        z: ktResult.speed_field, x: ktResult.x, y: ktResult.y,
        type: 'heatmap', colorscale: 'Viridis', showscale: true, zmin: 0, zmax: 2.5,
        colorbar: { title: '|V|', tickfont: { color: '#9ca3af' }, titlefont: { color: '#9ca3af' } },
      } as Plotly.Data,
      // Airfoil boundary
      {
        x: ktResult.airfoil_x, y: ktResult.airfoil_y, type: 'scatter', mode: 'lines',
        line: { color: '#f97316', width: 2 }, name: 'Airfoil', showlegend: false,
        fill: 'toself', fillcolor: 'rgba(249,115,22,0.15)',
      } as Plotly.Data,
    ];
  }, [ktResult]);

  const ktCpTraces = useMemo((): Plotly.Data[] => {
    if (!ktResult || ktResult.wall_x.length === 0) return [];
    return [{
      x: ktResult.wall_x, y: ktResult.wall_Cp, type: 'scatter',
      line: { color: '#22d3ee' }, name: 'Cp',
    } as Plotly.Data];
  }, [ktResult]);

  const isLoading: Record<TabKey, boolean> = { vortex: vLoading, cylinder: cLoading, kt: ktLoading };
  const handleCompute: Record<TabKey, () => Promise<void>> = { vortex: handleVortex, cylinder: handleCylinder, kt: handleKT };

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <Waves className="h-6 w-6 text-sky-400" />
        <h2 className="text-lg font-semibold text-white">Potential Flow & Vortex Elements</h2>
        <span className="text-xs text-slate-500 bg-slate-800 px-2 py-0.5 rounded">welib.vortilib</span>
      </div>

      {/* Sub-tab pills */}
      <div className="flex flex-wrap gap-1">
        {TABS.map((tab) => { const Icon = tab.icon; return (
          <button key={tab.key} onClick={() => setActiveTab(tab.key)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              activeTab === tab.key ? 'bg-sky-500/20 text-sky-300 ring-1 ring-sky-500/40' : 'bg-slate-800 text-slate-400 hover:text-slate-200 hover:bg-slate-700'}`}>
            <Icon className="h-3.5 w-3.5" />{tab.label}
          </button>
        ); })}
      </div>

      {error && <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3 text-sm text-red-300">{error}</div>}

      <div className="grid grid-cols-1 xl:grid-cols-4 gap-4">
        {/* ---- Parameters panel ---- */}
        <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-700/50 space-y-3">
          <h3 className="text-sm font-medium text-slate-300 mb-2">Parameters</h3>

          {activeTab === 'vortex' && (<>
            <NumberInput label="Circulation Γ" value={vGamma} onChange={setVGamma} step={1} />
            <p className="text-xs text-slate-500">2D vortex point velocity field. + = counter-clockwise.</p>
          </>)}

          {activeTab === 'cylinder' && (<>
            <NumberInput label="Freestream U₀" value={cU0} onChange={setCU0} unit="m/s" step={0.5} min={0.1} />
            <NumberInput label="Radius R" value={cR} onChange={setCR} unit="m" step={0.1} min={0.1} />
            <NumberInput label="Circulation Γ" value={cGamma} onChange={setCGamma} step={1} />
            <NumberInput label="Angle of attack" value={cAlpha} onChange={setCAlpha} unit="deg" step={1} />
            <p className="text-xs text-slate-500">Set Γ = -4πU₀R ≈ {(-4 * Math.PI * cU0 * cR).toFixed(1)} for maximum lift.</p>
          </>)}

          {activeTab === 'kt' && (<>
            <NumberInput label="XC (cyl. center)" value={ktXC} onChange={setKtXC} step={0.05} />
            <NumberInput label="YC (cyl. center)" value={ktYC} onChange={setKtYC} step={0.05} />
            <NumberInput label="TE angle τ" value={ktTau} onChange={setKtTau} unit="deg" step={2} min={1} max={45} />
            <NumberInput label="Angle of attack" value={ktAlpha} onChange={setKtAlpha} unit="deg" step={1} />
            <p className="text-xs text-slate-500">Conformal-mapping airfoil. XC &lt; 0 adds camber, YC &gt; 0 adds thickness.</p>
          </>)}

          <button onClick={handleCompute[activeTab]} disabled={isLoading[activeTab]}
            className="w-full mt-2 flex items-center justify-center gap-2 px-4 py-2 rounded-lg bg-sky-600 text-white text-sm font-medium hover:bg-sky-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors">
            {isLoading[activeTab] ? <><Loader2 className="h-4 w-4 animate-spin" />Computing…</> : 'Compute'}
          </button>
        </div>

        {/* ---- Plots ---- */}
        <div className="xl:col-span-3 space-y-4">

          {/* Vortex point */}
          {activeTab === 'vortex' && vResult && (
            <div className="bg-slate-800/30 rounded-xl border border-slate-700/30 p-2">
              <Plot data={vortexTraces}
                layout={makePlotLayout({
                  title: `Vortex Point Flow (Γ = ${vGamma})`,
                  xaxis: { title: 'x' }, yaxis: { title: 'y' }, height: 550, showlegend: false,
                }) as Partial<Plotly.Layout>}
                config={{ responsive: true }} className="w-full" />
            </div>
          )}

          {/* Cylinder flow */}
          {activeTab === 'cylinder' && cResult && (
            <div className="space-y-4">
              <div className="bg-slate-800/30 rounded-xl border border-slate-700/30 p-2">
                <Plot data={cylinderFlowTraces}
                  layout={makePlotLayout({
                    title: `Cylinder Flow (Γ = ${cGamma.toFixed(1)})`,
                    xaxis: { title: 'x' }, yaxis: { title: 'y' }, height: 450, showlegend: false,
                  }) as Partial<Plotly.Layout>}
                  config={{ responsive: true }} className="w-full" />
              </div>
              {cylinderCpTraces.length > 0 && (
                <div className="bg-slate-800/30 rounded-xl border border-slate-700/30 p-2">
                  <Plot data={cylinderCpTraces}
                    layout={{
                      ...makePlotLayout({
                        title: 'Surface Pressure Coefficient',
                        xaxis: { title: 'θ (deg)' },
                        yaxis: { title: 'Cp', autorange: 'reversed' as const },
                        height: 300, showlegend: false,
                      }),
                      yaxis: { gridcolor: 'rgba(100,116,139,0.2)', zeroline: true, zerolinecolor: 'rgba(255,255,255,0.2)', autorange: 'reversed' as const, title: 'Cp' },
                    } as Partial<Plotly.Layout>}
                    config={{ responsive: true }} className="w-full" />
                </div>
              )}
            </div>
          )}

          {/* Karman-Trefftz */}
          {activeTab === 'kt' && ktResult && (
            <div className="space-y-4">
              <div className="bg-slate-800/30 rounded-xl border border-slate-700/30 p-2">
                <Plot data={ktFlowTraces}
                  layout={makePlotLayout({
                    title: `Karman-Trefftz Airfoil (τ = ${ktTau}°, α = ${ktAlpha}°)`,
                    xaxis: { title: 'x' }, yaxis: { title: 'y' }, height: 450, showlegend: false,
                  }) as Partial<Plotly.Layout>}
                  config={{ responsive: true }} className="w-full" />
              </div>
              {ktCpTraces.length > 0 && (
                <div className="bg-slate-800/30 rounded-xl border border-slate-700/30 p-2">
                  <Plot data={ktCpTraces}
                    layout={{
                      ...makePlotLayout({
                        title: 'Surface Cp Distribution',
                        xaxis: { title: 'x/c' },
                        height: 300, showlegend: false,
                      }),
                      yaxis: { gridcolor: 'rgba(100,116,139,0.2)', zeroline: true, zerolinecolor: 'rgba(255,255,255,0.2)', autorange: 'reversed' as const, title: 'Cp' },
                    } as Partial<Plotly.Layout>}
                    config={{ responsive: true }} className="w-full" />
                </div>
              )}
            </div>
          )}

          {/* Empty states */}
          {((activeTab === 'vortex' && !vResult && !vLoading) ||
            (activeTab === 'cylinder' && !cResult && !cLoading) ||
            (activeTab === 'kt' && !ktResult && !ktLoading)) && (
            <div className="bg-slate-800/20 rounded-xl border border-slate-700/30 p-12 text-center text-slate-500">
              Click <span className="text-sky-400">Compute</span> to generate the visualization
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
