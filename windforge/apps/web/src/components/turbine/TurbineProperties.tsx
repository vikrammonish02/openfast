/**
 * TurbineProperties — WEIS-inspired turbine data visualization.
 *
 * Tabs: Airfoils | Blade | Tower | Cp-Ct-Cq | Cost Breakdown
 *
 * Data is loaded from the /api/v1/reference/{turbine}/... endpoints which
 * parse the validated NREL reference input files on the backend.
 */

import { useState, useEffect, useMemo } from 'react';
import {
  Wind,
  Cpu,
  Building2,
  Gauge,
  DollarSign,
} from 'lucide-react';
import clsx from 'clsx';
import Plot from 'react-plotly.js';
import apiClient from '@/api/client';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface Airfoil {
  name: string;
  alpha: number[];
  cl: number[];
  cd: number[];
  cm: number[];
  coords_x: number[];
  coords_y: number[];
}

interface BladeData {
  name: string;
  n_stations: number;
  bl_fract: number[];
  pitch_axis: number[];
  struct_twist: number[];
  b_mass_den: number[];
  flp_stff: number[];
  edg_stff: number[];
}

interface TowerData {
  name: string;
  n_stations: number;
  ht_fract: number[];
  t_mass_den: number[];
  tw_fa_stif: number[];
  tw_ss_stif: number[];
}

interface PerfData {
  pitch: number[];
  tsr: number[];
  cp: number[][];
  ct: number[][];
  cq: number[][];
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

type TabKey = 'airfoils' | 'blade' | 'tower' | 'performance' | 'cost';

const TABS: { key: TabKey; label: string; icon: React.ReactNode }[] = [
  { key: 'airfoils', label: 'Airfoils', icon: <Wind size={14} /> },
  { key: 'blade', label: 'Blade', icon: <Cpu size={14} /> },
  { key: 'tower', label: 'Tower', icon: <Building2 size={14} /> },
  { key: 'performance', label: 'Cp-Ct-Cq', icon: <Gauge size={14} /> },
  { key: 'cost', label: 'Cost', icon: <DollarSign size={14} /> },
];

const PLOT_BG = 'rgba(15,23,42,0.8)';
const GRID_COLOR = 'rgba(51,65,85,0.4)';
const FONT_COLOR = '#94a3b8';
const COLORS = [
  '#00b4d8', '#ef4444', '#22c55e', '#f59e0b', '#a855f7',
  '#ec4899', '#06b6d4', '#84cc16', '#f97316', '#6366f1',
];

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function TurbineProperties() {
  const [activeTab, setActiveTab] = useState<TabKey>('airfoils');
  const turbine = 'NREL-5MW'; // Currently only one reference turbine

  return (
    <div className="flex h-full flex-col overflow-hidden">
      {/* Header */}
      <div className="mb-4">
        <h2 className="text-lg font-bold text-slate-100">Turbine Properties</h2>
        <p className="text-xs text-slate-500">
          NREL 5MW Reference — validated data from ROSCO / OpenFAST reference inputs
        </p>
      </div>

      {/* Tabs */}
      <div className="mb-4 flex gap-1 overflow-x-auto rounded-lg bg-slate-800/50 p-1">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={clsx(
              'flex items-center gap-1.5 whitespace-nowrap rounded-md px-3 py-2 text-xs font-medium transition-colors',
              activeTab === tab.key
                ? 'bg-accent-500/20 text-accent-300'
                : 'text-slate-400 hover:text-slate-200',
            )}
          >
            {tab.icon}
            {tab.label}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        {activeTab === 'airfoils' && <AirfoilsTab turbine={turbine} />}
        {activeTab === 'blade' && <BladeTab turbine={turbine} />}
        {activeTab === 'tower' && <TowerTab turbine={turbine} />}
        {activeTab === 'performance' && <PerformanceTab turbine={turbine} />}
        {activeTab === 'cost' && <CostTab turbine={turbine} />}
      </div>
    </div>
  );
}


// ===========================================================================
// Airfoils Tab
// ===========================================================================

function AirfoilsTab({ turbine }: { turbine: string }) {
  const [airfoils, setAirfoils] = useState<Airfoil[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [showCd, setShowCd] = useState(true);
  const [showCm, setShowCm] = useState(false);

  useEffect(() => {
    apiClient.get(`/reference/${turbine}/airfoils`).then((res) => {
      setAirfoils(res.data.airfoils);
      // Select first two non-cylinder airfoils by default
      const defaults = res.data.airfoils
        .filter((a: Airfoil) => !a.name.toLowerCase().startsWith('cylinder'))
        .slice(0, 2)
        .map((a: Airfoil) => a.name);
      setSelected(defaults);
    });
  }, [turbine]);

  const toggleAirfoil = (name: string) => {
    setSelected((prev) =>
      prev.includes(name) ? prev.filter((n) => n !== name) : [...prev, name],
    );
  };

  const selectedAirfoils = airfoils.filter((a) => selected.includes(a.name));

  // Airfoil coordinate traces
  const coordTraces = selectedAirfoils
    .filter((a) => a.coords_x.length > 0)
    .map((a, i) => ({
      x: a.coords_x,
      y: a.coords_y,
      type: 'scatter' as const,
      mode: 'lines' as const,
      name: a.name,
      line: { color: COLORS[i % COLORS.length], width: 2 },
    }));

  // Polar subplot rows
  const polarChannels: { key: 'cl' | 'cd' | 'cm'; label: string; show: boolean }[] = [
    { key: 'cl', label: 'CL', show: true },
    { key: 'cd', label: 'CD', show: showCd },
    { key: 'cm', label: 'CM', show: showCm },
  ];
  const visiblePolars = polarChannels.filter((p) => p.show);

  const polarTraces = selectedAirfoils.flatMap((a, ai) =>
    visiblePolars.map((p, pi) => ({
      x: a.alpha,
      y: a[p.key],
      type: 'scatter' as const,
      mode: 'lines' as const,
      name: `${a.name}`,
      xaxis: pi === 0 ? 'x' : `x${pi + 1}`,
      yaxis: pi === 0 ? 'y' : `y${pi + 1}`,
      line: { color: COLORS[ai % COLORS.length], width: 1.5 },
      showlegend: pi === 0,
    })),
  );

  const gap = 0.06;
  const rowH = (1 - gap * (visiblePolars.length - 1)) / visiblePolars.length;
  const polarLayout: Record<string, any> = {};
  visiblePolars.forEach((p, i) => {
    const bottom = 1 - (i + 1) * rowH - i * gap;
    const ys = i === 0 ? '' : `${i + 1}`;
    const xs = i === 0 ? '' : `${i + 1}`;
    polarLayout[`yaxis${ys}`] = {
      domain: [Math.max(0, bottom), bottom + rowH],
      title: { text: p.label, font: { size: 11 } },
      gridcolor: GRID_COLOR,
    };
    polarLayout[`xaxis${xs}`] = {
      anchor: `y${ys}`,
      gridcolor: GRID_COLOR,
      ...(i === visiblePolars.length - 1 ? { title: { text: 'Alpha (deg)', font: { size: 11 } } } : { showticklabels: false }),
      matches: i === 0 ? undefined : 'x',
    };
  });

  return (
    <div className="space-y-4">
      {/* Airfoil selector */}
      <div className="rounded-xl border border-slate-700/50 bg-surface-dark p-3">
        <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
          Select Airfoils
        </p>
        <div className="flex flex-wrap gap-2">
          {airfoils.map((a) => {
            const isSel = selected.includes(a.name);
            const ci = selected.indexOf(a.name);
            return (
              <button
                key={a.name}
                onClick={() => toggleAirfoil(a.name)}
                className={clsx(
                  'flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium ring-1 ring-inset transition-colors',
                  isSel
                    ? 'bg-accent-500/20 text-accent-300 ring-accent-500/40'
                    : 'bg-surface-dark text-slate-400 ring-slate-700 hover:ring-slate-600',
                )}
              >
                {isSel && (
                  <span
                    className="inline-block h-2 w-2 rounded-full"
                    style={{ backgroundColor: COLORS[ci % COLORS.length] }}
                  />
                )}
                {a.name}
              </button>
            );
          })}
        </div>
      </div>

      {/* Charts */}
      <div className="grid grid-cols-2 gap-4">
        {/* Airfoil shape */}
        <div className="rounded-xl border border-slate-700/50 bg-surface-dark p-2">
          <p className="mb-1 px-2 text-xs font-semibold text-slate-400">Airfoil Coordinates</p>
          <Plot
            data={coordTraces}
            layout={{
              autosize: true,
              height: 350,
              margin: { l: 50, r: 20, t: 10, b: 40 },
              paper_bgcolor: 'rgba(0,0,0,0)',
              plot_bgcolor: PLOT_BG,
              font: { color: FONT_COLOR, size: 10 },
              xaxis: { title: { text: 'x/c', font: { size: 10 } }, gridcolor: GRID_COLOR, scaleanchor: 'y' },
              yaxis: { title: { text: 'y/c', font: { size: 10 } }, gridcolor: GRID_COLOR },
              legend: { orientation: 'h', y: -0.2, font: { size: 9 } },
              showlegend: true,
            }}
            config={{ displayModeBar: false, responsive: true }}
            style={{ width: '100%' }}
          />
        </div>

        {/* Polars */}
        <div className="rounded-xl border border-slate-700/50 bg-surface-dark p-2">
          <div className="mb-1 flex items-center justify-between px-2">
            <p className="text-xs font-semibold text-slate-400">Airfoil Polars</p>
            <div className="flex gap-2">
              {[
                { label: 'CD', val: showCd, set: setShowCd },
                { label: 'CM', val: showCm, set: setShowCm },
              ].map((sw) => (
                <label key={sw.label} className="flex items-center gap-1 text-[10px] text-slate-400 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={sw.val}
                    onChange={(e) => sw.set(e.target.checked)}
                    className="h-3 w-3 rounded border-slate-600 bg-slate-800 text-accent-500"
                  />
                  {sw.label}
                </label>
              ))}
            </div>
          </div>
          <Plot
            data={polarTraces}
            layout={{
              autosize: true,
              height: 350,
              margin: { l: 50, r: 20, t: 10, b: 40 },
              paper_bgcolor: 'rgba(0,0,0,0)',
              plot_bgcolor: PLOT_BG,
              font: { color: FONT_COLOR, size: 10 },
              showlegend: true,
              legend: { orientation: 'h', y: -0.15, font: { size: 9 } },
              ...polarLayout,
            }}
            config={{ displayModeBar: false, responsive: true }}
            style={{ width: '100%' }}
          />
        </div>
      </div>
    </div>
  );
}


// ===========================================================================
// Blade Tab
// ===========================================================================

function BladeTab({ turbine }: { turbine: string }) {
  const [blade, setBlade] = useState<BladeData | null>(null);

  useEffect(() => {
    apiClient.get(`/reference/${turbine}/blade`).then((res) => setBlade(res.data));
  }, [turbine]);

  if (!blade) return <p className="text-center text-sm text-slate-500 py-8">Loading blade data...</p>;

  const channels = [
    { key: 'struct_twist', label: 'Structural Twist (deg)', color: '#f59e0b' },
    { key: 'pitch_axis', label: 'Pitch Axis (-)', color: '#22c55e' },
    { key: 'b_mass_den', label: 'Mass Density (kg/m)', color: '#00b4d8' },
    { key: 'flp_stff', label: 'Flap Stiffness (Nm\u00b2)', color: '#a855f7' },
    { key: 'edg_stff', label: 'Edge Stiffness (Nm\u00b2)', color: '#ef4444' },
  ];

  const traces = channels.map((ch, i) => ({
    x: blade.bl_fract,
    y: (blade as any)[ch.key] as number[],
    type: 'scatter' as const,
    mode: 'lines+markers' as const,
    name: ch.label,
    xaxis: i === 0 ? 'x' : `x${i + 1}`,
    yaxis: i === 0 ? 'y' : `y${i + 1}`,
    line: { color: ch.color, width: 2 },
    marker: { size: 3, color: ch.color },
    showlegend: false,
  }));

  const n = channels.length;
  const gap = 0.04;
  const rowH = (1 - gap * (n - 1)) / n;
  const layout: Record<string, any> = {};
  channels.forEach((ch, i) => {
    const bottom = 1 - (i + 1) * rowH - i * gap;
    const ys = i === 0 ? '' : `${i + 1}`;
    const xs = i === 0 ? '' : `${i + 1}`;
    layout[`yaxis${ys}`] = {
      domain: [Math.max(0, bottom), bottom + rowH],
      title: { text: ch.label, font: { size: 9, color: ch.color } },
      gridcolor: GRID_COLOR,
      tickfont: { size: 8 },
    };
    layout[`xaxis${xs}`] = {
      anchor: `y${ys}`,
      gridcolor: GRID_COLOR,
      ...(i === n - 1 ? { title: { text: 'Blade Fraction (-)', font: { size: 10 } } } : { showticklabels: false }),
      matches: i === 0 ? undefined : 'x',
    };
  });

  return (
    <div className="rounded-xl border border-slate-700/50 bg-surface-dark p-2">
      <p className="mb-1 px-2 text-xs font-semibold text-slate-400">
        Blade Distributed Properties — {blade.name} ({blade.n_stations} stations)
      </p>
      <Plot
        data={traces}
        layout={{
          autosize: true,
          height: Math.max(600, n * 150),
          margin: { l: 80, r: 20, t: 10, b: 50 },
          paper_bgcolor: 'rgba(0,0,0,0)',
          plot_bgcolor: PLOT_BG,
          font: { color: FONT_COLOR, size: 10 },
          showlegend: false,
          ...layout,
        }}
        config={{ displayModeBar: false, responsive: true }}
        style={{ width: '100%' }}
      />
    </div>
  );
}


// ===========================================================================
// Tower Tab
// ===========================================================================

function TowerTab({ turbine }: { turbine: string }) {
  const [tower, setTower] = useState<TowerData | null>(null);

  useEffect(() => {
    apiClient.get(`/reference/${turbine}/tower`).then((res) => setTower(res.data));
  }, [turbine]);

  if (!tower) return <p className="text-center text-sm text-slate-500 py-8">Loading tower data...</p>;

  // Left: realistic tower profile (OD vs height)
  const profileTraces = [
    {
      x: tower.t_mass_den.map((_, i) => {
        // Approximate outer diameter from mass density (rough but visual)
        const rho_steel = 7850;
        const od_approx = Math.sqrt((4 * tower.t_mass_den[i]) / (Math.PI * rho_steel)) * 15;
        return od_approx;
      }),
      y: tower.ht_fract,
      type: 'scatter' as const,
      mode: 'lines+markers' as const,
      name: 'Tower Profile',
      line: { color: '#00b4d8', width: 2 },
      marker: { size: 4 },
    },
  ];

  // Right: stacked subplots for mass, FA stiff, SS stiff
  const channels = [
    { key: 't_mass_den', label: 'Mass Density (kg/m)', color: '#00b4d8' },
    { key: 'tw_fa_stif', label: 'FA Stiffness (Nm\u00b2)', color: '#f59e0b' },
    { key: 'tw_ss_stif', label: 'SS Stiffness (Nm\u00b2)', color: '#ef4444' },
  ];

  const propTraces = channels.map((ch, i) => ({
    x: tower.ht_fract,
    y: (tower as any)[ch.key] as number[],
    type: 'scatter' as const,
    mode: 'lines+markers' as const,
    name: ch.label,
    xaxis: i === 0 ? 'x' : `x${i + 1}`,
    yaxis: i === 0 ? 'y' : `y${i + 1}`,
    line: { color: ch.color, width: 2 },
    marker: { size: 4, color: ch.color },
    showlegend: false,
  }));

  const n = channels.length;
  const gap = 0.06;
  const rowH = (1 - gap * (n - 1)) / n;
  const propLayout: Record<string, any> = {};
  channels.forEach((ch, i) => {
    const bottom = 1 - (i + 1) * rowH - i * gap;
    const ys = i === 0 ? '' : `${i + 1}`;
    const xs = i === 0 ? '' : `${i + 1}`;
    propLayout[`yaxis${ys}`] = {
      domain: [Math.max(0, bottom), bottom + rowH],
      title: { text: ch.label, font: { size: 10, color: ch.color } },
      gridcolor: GRID_COLOR,
      tickfont: { size: 8 },
    };
    propLayout[`xaxis${xs}`] = {
      anchor: `y${ys}`,
      gridcolor: GRID_COLOR,
      ...(i === n - 1 ? { title: { text: 'Height Fraction (-)', font: { size: 10 } } } : { showticklabels: false }),
      matches: i === 0 ? undefined : 'x',
    };
  });

  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-slate-700/50 bg-surface-dark p-2">
        <p className="mb-1 px-2 text-xs font-semibold text-slate-400">
          Tower Distributed Properties — {tower.name} ({tower.n_stations} stations)
        </p>
        <Plot
          data={propTraces}
          layout={{
            autosize: true,
            height: 550,
            margin: { l: 80, r: 20, t: 10, b: 50 },
            paper_bgcolor: 'rgba(0,0,0,0)',
            plot_bgcolor: PLOT_BG,
            font: { color: FONT_COLOR, size: 10 },
            showlegend: false,
            ...propLayout,
          }}
          config={{ displayModeBar: false, responsive: true }}
          style={{ width: '100%' }}
        />
      </div>
    </div>
  );
}


// ===========================================================================
// Performance Tab (Cp-Ct-Cq)
// ===========================================================================

function PerformanceTab({ turbine }: { turbine: string }) {
  const [perf, setPerf] = useState<PerfData | null>(null);
  const [surface, setSurface] = useState<'cp' | 'ct' | 'cq'>('cp');

  useEffect(() => {
    apiClient.get(`/reference/${turbine}/performance`).then((res) => setPerf(res.data));
  }, [turbine]);

  if (!perf) return <p className="text-center text-sm text-slate-500 py-8">Loading performance data...</p>;

  const surfaceData = perf[surface];
  const labels = { cp: 'Power Coefficient (Cp)', ct: 'Thrust Coefficient (Ct)', cq: 'Torque Coefficient (Cq)' };

  return (
    <div className="space-y-4">
      {/* Surface selector */}
      <div className="flex items-center gap-1 rounded-lg bg-slate-800/50 p-1 w-fit">
        {(['cp', 'ct', 'cq'] as const).map((s) => (
          <button
            key={s}
            onClick={() => setSurface(s)}
            className={clsx(
              'rounded-md px-3 py-1.5 text-xs font-semibold uppercase tracking-wider transition-colors',
              surface === s
                ? 'bg-accent-500/30 text-accent-300'
                : 'text-slate-500 hover:text-slate-300',
            )}
          >
            {s}
          </button>
        ))}
      </div>

      {/* Contour plot */}
      <div className="rounded-xl border border-slate-700/50 bg-surface-dark p-2">
        <Plot
          data={[
            {
              z: surfaceData,
              x: perf.pitch,
              y: perf.tsr,
              type: 'contour' as const,
              colorscale: 'Viridis',
              contours: { coloring: 'heatmap' as const, showlines: true },
              colorbar: { title: { text: labels[surface], font: { size: 11, color: FONT_COLOR } }, tickfont: { color: FONT_COLOR } },
              line: { width: 0.5 },
            },
          ]}
          layout={{
            autosize: true,
            height: 550,
            margin: { l: 60, r: 100, t: 30, b: 50 },
            paper_bgcolor: 'rgba(0,0,0,0)',
            plot_bgcolor: PLOT_BG,
            font: { color: FONT_COLOR, size: 11 },
            title: { text: labels[surface], font: { size: 14, color: '#e2e8f0' } },
            xaxis: { title: { text: 'Pitch Angle (deg)', font: { size: 11 } }, gridcolor: GRID_COLOR },
            yaxis: { title: { text: 'Tip Speed Ratio (-)', font: { size: 11 } }, gridcolor: GRID_COLOR },
          }}
          config={{ displayModeBar: false, responsive: true }}
          style={{ width: '100%' }}
        />
      </div>
    </div>
  );
}


// ===========================================================================
// Cost Tab
// ===========================================================================

function CostTab({ turbine }: { turbine: string }) {
  const [costs, setCosts] = useState<any>(null);

  useEffect(() => {
    apiClient.get(`/reference/${turbine}/costs`).then((res) => setCosts(res.data));
  }, [turbine]);

  if (!costs) return <p className="text-center text-sm text-slate-500 py-8">Loading cost data...</p>;

  // Build sunburst data
  const labels: string[] = [];
  const parents: string[] = [];
  const values: number[] = [];

  const t = costs.turbine;
  labels.push('Turbine');
  parents.push('');
  values.push(t.total);

  for (const subsystem of ['rotor', 'nacelle', 'tower'] as const) {
    const sub = t[subsystem];
    labels.push(sub.label);
    parents.push('Turbine');
    values.push(sub.total);
    for (const [comp, cost] of Object.entries(sub.components)) {
      const displayName = comp.replace(/_/g, ' ').replace(/\b\w/g, (c: string) => c.toUpperCase());
      labels.push(displayName);
      parents.push(sub.label);
      values.push(cost as number);
    }
  }

  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-slate-700/50 bg-surface-dark p-2">
        <p className="mb-1 px-2 text-xs font-semibold text-slate-400">
          NREL Cost & Scaling Model — 5MW Reference Turbine
        </p>
        <Plot
          data={[
            {
              type: 'sunburst' as const,
              labels,
              parents,
              values,
              branchvalues: 'total' as const,
              textinfo: 'label+percent parent',
              hovertemplate: '<b>%{label}</b><br>Cost: $%{value:,.0f}<br>%{percentParent:.1%} of parent<extra></extra>',
              marker: {
                colors: labels.map((_, i) => COLORS[i % COLORS.length]),
              },
            },
          ]}
          layout={{
            autosize: true,
            height: 550,
            margin: { l: 10, r: 10, t: 40, b: 10 },
            paper_bgcolor: 'rgba(0,0,0,0)',
            font: { color: FONT_COLOR, size: 11 },
            title: { text: 'Turbine Cost Breakdown', font: { size: 14, color: '#e2e8f0' } },
          }}
          config={{ displayModeBar: false, responsive: true }}
          style={{ width: '100%' }}
        />
      </div>

      {/* Cost table */}
      <div className="rounded-xl border border-slate-700/50 bg-surface-dark p-3">
        <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-500">Cost Summary</p>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-700 text-slate-400">
              <th className="py-1 text-left font-semibold">Component</th>
              <th className="py-1 text-right font-semibold">Cost (k USD)</th>
            </tr>
          </thead>
          <tbody>
            {labels.slice(1).map((label, i) => (
              <tr key={i} className="border-b border-slate-800">
                <td className="py-1 text-slate-300">{label}</td>
                <td className="py-1 text-right text-slate-300 font-mono">
                  {(values[i + 1] / 1000).toFixed(0)}
                </td>
              </tr>
            ))}
            <tr className="font-bold">
              <td className="py-1 text-slate-100">Total Turbine</td>
              <td className="py-1 text-right text-accent-300 font-mono">
                {(t.total / 1000).toFixed(0)}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}
