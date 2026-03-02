import { useEffect, useState, useCallback, useMemo } from 'react';
import { metoceanApi } from '@/api/client';
import type { MetoceanSite, MetoceanSiteCreate } from '@/types';
import {
  Waves,
  Plus,
  Loader2,
  Trash2,
  Save,
  X,
  Zap,
  MinusCircle,
} from 'lucide-react';
import clsx from 'clsx';
import toast from 'react-hot-toast';
import Plot from 'react-plotly.js';
import type { Data, Layout } from 'plotly.js';

// ---------------------------------------------------------------------------
// Editable form state — mirrors MetoceanSite fields relevant for editing
// ---------------------------------------------------------------------------
interface EditableMetocean {
  name: string;
  description: string;
  water_depth: number;
  current_speed: number;
  latitude: number | null;
  longitude: number | null;
  wind_speeds: number[];
  wave_hs_nss: number[];
  wave_tp_nss: number[];
  wave_hs_sss: number[];
  wave_tp_sss: number[];
  wave_hs_ess: number[];
  wave_tp_ess: number[];
  wave_gamma: number[];
}

function siteToEditable(site: MetoceanSite): EditableMetocean {
  const n = site.wind_speeds?.length ?? 0;
  return {
    name: site.name,
    description: site.description ?? '',
    water_depth: site.water_depth,
    current_speed: site.current_speed,
    latitude: site.latitude,
    longitude: site.longitude,
    wind_speeds: site.wind_speeds ? [...site.wind_speeds] : [],
    wave_hs_nss: site.wave_hs_nss ? [...site.wave_hs_nss] : new Array(n).fill(0),
    wave_tp_nss: site.wave_tp_nss ? [...site.wave_tp_nss] : new Array(n).fill(0),
    wave_hs_sss: site.wave_hs_sss ? [...site.wave_hs_sss] : new Array(n).fill(0),
    wave_tp_sss: site.wave_tp_sss ? [...site.wave_tp_sss] : new Array(n).fill(0),
    wave_hs_ess: site.wave_hs_ess ? [...site.wave_hs_ess] : new Array(n).fill(0),
    wave_tp_ess: site.wave_tp_ess ? [...site.wave_tp_ess] : new Array(n).fill(0),
    wave_gamma: site.wave_gamma ? [...site.wave_gamma] : new Array(n).fill(3.3),
  };
}

// ---------------------------------------------------------------------------
// Plotly layout configuration
// ---------------------------------------------------------------------------
const plotLayout: Partial<Layout> = {
  paper_bgcolor: 'transparent',
  plot_bgcolor: 'rgba(17,24,39,0.8)',
  font: { family: 'ui-monospace, monospace', size: 10, color: '#9ca3af' },
  margin: { t: 30, r: 20, b: 50, l: 60 },
  xaxis: { title: 'Wind Speed (m/s)', gridcolor: 'rgba(100,116,139,0.2)' },
  yaxis: { title: 'Hs (m)', gridcolor: 'rgba(100,116,139,0.2)' },
  legend: { orientation: 'h' as const, y: -0.2 },
};

const inputCls =
  'w-full rounded-lg border border-slate-600 bg-slate-800 px-3 py-2 text-sm text-slate-200 placeholder-slate-400 focus:border-accent-500 focus:ring-1 focus:ring-accent-500';

const cellInputCls =
  'w-full rounded border border-slate-600 bg-slate-800 px-2 py-1 text-xs text-slate-200 text-right tabular-nums focus:border-accent-500 focus:ring-1 focus:ring-accent-500';

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
export default function MetoceanPage() {
  const [sites, setSites] = useState<MetoceanSite[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedSite, setSelectedSite] = useState<MetoceanSite | null>(null);
  const [editForm, setEditForm] = useState<EditableMetocean | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  // Create modal
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newName, setNewName] = useState('');
  const [newWaterDepth, setNewWaterDepth] = useState<number>(30);
  const [isCreating, setIsCreating] = useState(false);

  // Auto-generate
  const [isAutoGenerating, setIsAutoGenerating] = useState(false);

  // ─── Data fetching ──────────────────────────────────────────────────────────

  const loadSites = useCallback(async () => {
    try {
      const data = await metoceanApi.list();
      setSites(data);
      return data;
    } catch {
      toast.error('Failed to load metocean sites');
      return [];
    }
  }, []);

  useEffect(() => {
    setIsLoading(true);
    loadSites()
      .then((data) => {
        if (data && data.length > 0) {
          setSelectedSite(data[0]);
          setEditForm(siteToEditable(data[0]));
        }
      })
      .finally(() => setIsLoading(false));
  }, [loadSites]);

  // ─── Handlers ───────────────────────────────────────────────────────────────

  const handleSelect = (site: MetoceanSite) => {
    setSelectedSite(site);
    setEditForm(siteToEditable(site));
  };

  const handleCreate = async () => {
    if (!newName.trim()) return;
    setIsCreating(true);
    try {
      const payload: MetoceanSiteCreate = {
        name: newName.trim(),
        water_depth: newWaterDepth,
      };
      const created = await metoceanApi.create(payload);
      toast.success('Metocean site created');
      setShowCreateModal(false);
      setNewName('');
      setNewWaterDepth(30);
      const data = await loadSites();
      if (data) {
        const found = data.find((s) => s.id === created.id);
        if (found) {
          setSelectedSite(found);
          setEditForm(siteToEditable(found));
        }
      }
    } catch {
      toast.error('Failed to create metocean site');
    } finally {
      setIsCreating(false);
    }
  };

  const handleAutoGenerate = async () => {
    setIsAutoGenerating(true);
    try {
      const created = await metoceanApi.autoGenerate({
        wind_speeds: [4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24],
        water_depth: 30,
      });
      toast.success('IEC metocean site generated');
      const data = await loadSites();
      if (data) {
        const found = data.find((s) => s.id === created.id);
        if (found) {
          setSelectedSite(found);
          setEditForm(siteToEditable(found));
        }
      }
    } catch {
      toast.error('Failed to auto-generate metocean site');
    } finally {
      setIsAutoGenerating(false);
    }
  };

  const handleSave = async () => {
    if (!selectedSite || !editForm) return;
    setIsSaving(true);
    try {
      const payload: Partial<MetoceanSiteCreate> = {
        name: editForm.name,
        description: editForm.description || null,
        water_depth: editForm.water_depth,
        current_speed: editForm.current_speed,
        latitude: editForm.latitude,
        longitude: editForm.longitude,
        wind_speeds: editForm.wind_speeds.length > 0 ? editForm.wind_speeds : null,
        wave_hs_nss: editForm.wave_hs_nss.length > 0 ? editForm.wave_hs_nss : null,
        wave_tp_nss: editForm.wave_tp_nss.length > 0 ? editForm.wave_tp_nss : null,
        wave_hs_sss: editForm.wave_hs_sss.length > 0 ? editForm.wave_hs_sss : null,
        wave_tp_sss: editForm.wave_tp_sss.length > 0 ? editForm.wave_tp_sss : null,
        wave_hs_ess: editForm.wave_hs_ess.length > 0 ? editForm.wave_hs_ess : null,
        wave_tp_ess: editForm.wave_tp_ess.length > 0 ? editForm.wave_tp_ess : null,
        wave_gamma: editForm.wave_gamma.length > 0 ? editForm.wave_gamma : null,
      };
      const updated = await metoceanApi.update(selectedSite.id, payload);
      toast.success('Metocean site saved');
      setSelectedSite(updated);
      setEditForm(siteToEditable(updated));
      await loadSites();
    } catch {
      toast.error('Failed to save metocean site');
    } finally {
      setIsSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!selectedSite) return;
    if (!window.confirm(`Delete metocean site "${selectedSite.name}"?`)) return;
    try {
      await metoceanApi.delete(selectedSite.id);
      toast.success('Metocean site deleted');
      setSelectedSite(null);
      setEditForm(null);
      await loadSites();
    } catch {
      toast.error('Failed to delete metocean site');
    }
  };

  // ─── Form field helpers ─────────────────────────────────────────────────────

  const updateField = <K extends keyof EditableMetocean>(
    field: K,
    value: EditableMetocean[K],
  ) => {
    if (!editForm) return;
    setEditForm({ ...editForm, [field]: value });
  };

  const updateArrayCell = (
    field: keyof Pick<
      EditableMetocean,
      | 'wind_speeds'
      | 'wave_hs_nss'
      | 'wave_tp_nss'
      | 'wave_hs_sss'
      | 'wave_tp_sss'
      | 'wave_hs_ess'
      | 'wave_tp_ess'
      | 'wave_gamma'
    >,
    index: number,
    value: number,
  ) => {
    if (!editForm) return;
    const arr = [...editForm[field]];
    arr[index] = value;
    setEditForm({ ...editForm, [field]: arr });
  };

  const addRow = () => {
    if (!editForm) return;
    const n = editForm.wind_speeds.length;
    const lastWs = n > 0 ? editForm.wind_speeds[n - 1] + 2 : 4;
    setEditForm({
      ...editForm,
      wind_speeds: [...editForm.wind_speeds, lastWs],
      wave_hs_nss: [...editForm.wave_hs_nss, 0],
      wave_tp_nss: [...editForm.wave_tp_nss, 0],
      wave_hs_sss: [...editForm.wave_hs_sss, 0],
      wave_tp_sss: [...editForm.wave_tp_sss, 0],
      wave_hs_ess: [...editForm.wave_hs_ess, 0],
      wave_tp_ess: [...editForm.wave_tp_ess, 0],
      wave_gamma: [...editForm.wave_gamma, 3.3],
    });
  };

  const removeRow = (index: number) => {
    if (!editForm) return;
    const remove = <T,>(arr: T[]) => arr.filter((_, i) => i !== index);
    setEditForm({
      ...editForm,
      wind_speeds: remove(editForm.wind_speeds),
      wave_hs_nss: remove(editForm.wave_hs_nss),
      wave_tp_nss: remove(editForm.wave_tp_nss),
      wave_hs_sss: remove(editForm.wave_hs_sss),
      wave_tp_sss: remove(editForm.wave_tp_sss),
      wave_hs_ess: remove(editForm.wave_hs_ess),
      wave_tp_ess: remove(editForm.wave_tp_ess),
      wave_gamma: remove(editForm.wave_gamma),
    });
  };

  // ─── Plotly traces ──────────────────────────────────────────────────────────

  const plotTraces = useMemo((): Data[] => {
    if (!editForm || editForm.wind_speeds.length === 0) return [];
    const ws = editForm.wind_speeds;
    return [
      {
        x: ws,
        y: editForm.wave_hs_nss,
        name: 'Hs NSS',
        mode: 'lines+markers' as const,
        line: { color: '#3b82f6', width: 2 },
        marker: { size: 4 },
      },
      {
        x: ws,
        y: editForm.wave_hs_sss,
        name: 'Hs SSS',
        mode: 'lines+markers' as const,
        line: { color: '#f97316', width: 2 },
        marker: { size: 4 },
      },
      {
        x: ws,
        y: editForm.wave_hs_ess,
        name: 'Hs ESS',
        mode: 'lines+markers' as const,
        line: { color: '#ef4444', width: 2 },
        marker: { size: 4 },
      },
    ];
  }, [editForm]);

  // ─── Column definitions for the table ───────────────────────────────────────

  const columns: {
    label: string;
    field: keyof Pick<
      EditableMetocean,
      | 'wind_speeds'
      | 'wave_hs_nss'
      | 'wave_tp_nss'
      | 'wave_hs_sss'
      | 'wave_tp_sss'
      | 'wave_hs_ess'
      | 'wave_tp_ess'
      | 'wave_gamma'
    >;
    step: string;
  }[] = [
    { label: 'Wind Speed', field: 'wind_speeds', step: '0.1' },
    { label: 'Hs NSS', field: 'wave_hs_nss', step: '0.001' },
    { label: 'Tp NSS', field: 'wave_tp_nss', step: '0.001' },
    { label: 'Hs SSS', field: 'wave_hs_sss', step: '0.001' },
    { label: 'Tp SSS', field: 'wave_tp_sss', step: '0.001' },
    { label: 'Hs ESS', field: 'wave_hs_ess', step: '0.001' },
    { label: 'Tp ESS', field: 'wave_tp_ess', step: '0.001' },
    { label: '\u03B3', field: 'wave_gamma', step: '0.1' },
  ];

  // ─── Render ─────────────────────────────────────────────────────────────────

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-24">
        <Loader2 className="h-8 w-8 animate-spin text-accent-500" />
      </div>
    );
  }

  return (
    <div className="flex h-full gap-6">
      {/* ── Left panel: site list ─────────────────────────────────────────── */}
      <div className="w-80 shrink-0 space-y-3 overflow-y-auto">
        <div className="flex flex-col gap-2">
          <button
            onClick={() => setShowCreateModal(true)}
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-accent-600 px-4 py-2 text-sm font-medium text-white hover:bg-accent-500"
          >
            <Plus className="h-4 w-4" />
            Create New
          </button>
          <button
            onClick={handleAutoGenerate}
            disabled={isAutoGenerating}
            className="flex w-full items-center justify-center gap-2 rounded-lg border border-slate-600 bg-surface-dark-secondary px-4 py-2 text-sm font-medium text-slate-200 hover:border-slate-500 hover:bg-surface-dark-secondary/80 disabled:opacity-50"
          >
            {isAutoGenerating ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Zap className="h-4 w-4 text-amber-400" />
            )}
            Auto-Generate from IEC
          </button>
        </div>

        {sites.length === 0 ? (
          <div className="flex flex-col items-center rounded-xl border-2 border-dashed border-slate-600 py-10">
            <Waves className="mb-2 h-10 w-10 text-slate-500" />
            <p className="text-sm text-slate-400">No metocean sites</p>
          </div>
        ) : (
          sites.map((site) => (
            <button
              key={site.id}
              onClick={() => handleSelect(site)}
              className={clsx(
                'w-full rounded-xl border p-4 text-left transition-all',
                selectedSite?.id === site.id
                  ? 'border-accent-500 bg-accent-950/30 shadow-sm'
                  : 'border-slate-700 bg-surface-dark-secondary hover:border-slate-500',
              )}
            >
              <span className="block font-medium text-slate-100">
                {site.name}
              </span>
              <span className="mt-1 block text-xs text-slate-400">
                {site.water_depth}m depth &middot;{' '}
                {site.wind_speeds ? site.wind_speeds.length : 0} wind bins
              </span>
            </button>
          ))
        )}
      </div>

      {/* ── Right panel: detail editor ────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto">
        {selectedSite && editForm ? (
          <div className="space-y-6">
            {/* Header fields */}
            <div className="rounded-xl border border-slate-700 bg-surface-dark-secondary p-6">
              <div className="mb-6 flex items-center justify-between">
                <h3 className="text-lg font-semibold text-slate-100">
                  Site Details
                </h3>
                <div className="flex items-center gap-2">
                  <button
                    onClick={handleSave}
                    disabled={isSaving}
                    className="flex items-center gap-2 rounded-lg bg-accent-600 px-4 py-2 text-sm font-medium text-white hover:bg-accent-500 disabled:opacity-50"
                  >
                    {isSaving ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Save className="h-4 w-4" />
                    )}
                    Save
                  </button>
                  <button
                    onClick={handleDelete}
                    className="flex items-center gap-2 rounded-lg border border-red-800 px-4 py-2 text-sm font-medium text-red-400 hover:bg-red-950/30"
                  >
                    <Trash2 className="h-4 w-4" />
                    Delete
                  </button>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="col-span-2">
                  <label className="mb-1 block text-xs font-medium text-slate-400">
                    Name
                  </label>
                  <input
                    type="text"
                    value={editForm.name}
                    onChange={(e) => updateField('name', e.target.value)}
                    className={inputCls}
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs font-medium text-slate-400">
                    Water Depth (m)
                  </label>
                  <input
                    type="number"
                    step="0.1"
                    value={editForm.water_depth}
                    onChange={(e) =>
                      updateField('water_depth', parseFloat(e.target.value) || 0)
                    }
                    className={inputCls}
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs font-medium text-slate-400">
                    Current Speed (m/s)
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    value={editForm.current_speed}
                    onChange={(e) =>
                      updateField(
                        'current_speed',
                        parseFloat(e.target.value) || 0,
                      )
                    }
                    className={inputCls}
                  />
                </div>
              </div>
            </div>

            {/* Wave data table */}
            <div className="rounded-xl border border-slate-700 bg-surface-dark-secondary p-6">
              <div className="mb-4 flex items-center justify-between">
                <h4 className="text-sm font-semibold uppercase tracking-wider text-slate-300">
                  Wave Conditions ({editForm.wind_speeds.length} bins)
                </h4>
                <button
                  onClick={addRow}
                  className="flex items-center gap-1 rounded-lg bg-accent-950/30 px-3 py-1.5 text-xs font-medium text-accent-300 hover:bg-accent-950/50"
                >
                  <Plus className="h-3.5 w-3.5" />
                  Add Row
                </button>
              </div>

              {editForm.wind_speeds.length > 0 ? (
                <div className="overflow-x-auto rounded-lg border border-slate-700">
                  <table className="min-w-full text-sm">
                    <thead className="bg-slate-800/60">
                      <tr>
                        {columns.map((col) => (
                          <th
                            key={col.field}
                            className="px-3 py-2 text-right text-xs font-medium uppercase text-slate-400"
                          >
                            {col.label}
                          </th>
                        ))}
                        <th className="w-10 px-2 py-2" />
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-700/50">
                      {editForm.wind_speeds.map((_, rowIdx) => (
                        <tr
                          key={rowIdx}
                          className="hover:bg-slate-800/30"
                        >
                          {columns.map((col) => (
                            <td key={col.field} className="px-2 py-1">
                              <input
                                type="number"
                                step={col.step}
                                value={editForm[col.field][rowIdx] ?? 0}
                                onChange={(e) =>
                                  updateArrayCell(
                                    col.field,
                                    rowIdx,
                                    parseFloat(e.target.value) || 0,
                                  )
                                }
                                className={cellInputCls}
                              />
                            </td>
                          ))}
                          <td className="px-2 py-1 text-center">
                            <button
                              onClick={() => removeRow(rowIdx)}
                              className="text-slate-500 hover:text-red-400"
                              title="Remove row"
                            >
                              <MinusCircle className="h-3.5 w-3.5" />
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="rounded-lg border-2 border-dashed border-slate-600 p-8 text-center">
                  <p className="text-sm text-slate-400">
                    No wind speed bins defined. Click &ldquo;Add Row&rdquo; to
                    begin, or use &ldquo;Auto-Generate from IEC&rdquo; to
                    populate automatically.
                  </p>
                </div>
              )}
            </div>

            {/* Plotly chart */}
            {editForm.wind_speeds.length > 0 && (
              <div className="rounded-xl border border-slate-700 bg-surface-dark-secondary p-6">
                <h4 className="mb-4 text-sm font-semibold uppercase tracking-wider text-slate-300">
                  Hs vs Wind Speed
                </h4>
                <Plot
                  data={plotTraces}
                  layout={plotLayout}
                  config={{
                    displayModeBar: false,
                    responsive: true,
                  }}
                  useResizeHandler
                  style={{ width: '100%', height: 340 }}
                />
              </div>
            )}
          </div>
        ) : (
          <div className="flex h-full flex-col items-center justify-center">
            <Waves className="mb-3 h-12 w-12 text-slate-500" />
            <h3 className="text-base font-semibold text-slate-200">
              No site selected
            </h3>
            <p className="mt-1 text-sm text-slate-400">
              Select a metocean site from the list or create a new one.
            </p>
          </div>
        )}
      </div>

      {/* ── Create modal ──────────────────────────────────────────────────── */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="w-full max-w-md rounded-xl bg-surface-dark-secondary p-6 shadow-xl">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-lg font-semibold text-slate-100">
                New Metocean Site
              </h3>
              <button
                onClick={() => setShowCreateModal(false)}
                className="text-slate-400 hover:text-slate-300"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-200">
                  Name
                </label>
                <input
                  type="text"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  placeholder="e.g., North Sea 30m"
                  className={inputCls}
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-200">
                  Water Depth (m)
                </label>
                <input
                  type="number"
                  step="0.1"
                  value={newWaterDepth}
                  onChange={(e) =>
                    setNewWaterDepth(parseFloat(e.target.value) || 0)
                  }
                  className={inputCls}
                />
              </div>
            </div>
            <div className="mt-6 flex justify-end gap-3">
              <button
                onClick={() => setShowCreateModal(false)}
                className="rounded-lg bg-slate-700 px-4 py-2 text-sm font-medium text-slate-200 hover:bg-slate-600"
              >
                Cancel
              </button>
              <button
                onClick={handleCreate}
                disabled={isCreating || !newName.trim()}
                className="flex items-center gap-2 rounded-lg bg-accent-600 px-4 py-2 text-sm font-medium text-white hover:bg-accent-500 disabled:opacity-50"
              >
                {isCreating && <Loader2 className="h-4 w-4 animate-spin" />}
                Create
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
