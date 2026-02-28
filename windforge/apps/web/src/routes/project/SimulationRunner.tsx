import { useEffect, useState, useCallback, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { simulationsApi, dlcDefinitionsApi, turbineModelsApi } from '@/api/client';
import type { Simulation, SimulationCase, DLCDefinition, TurbineModel } from '@/types';
import type { SimulationCreate } from '@/api/client';
import { useAuthStore } from '@/stores/authStore';
import {
  Play,
  Plus,
  Loader2,
  StopCircle,
  CheckCircle2,
  XCircle,
  Clock,
  X,
  FolderOpen,
  AlertTriangle,
  Terminal,
  ChevronDown,
  ChevronRight,
  RefreshCw,
  Wifi,
  WifiOff,
  FileText,
} from 'lucide-react';
import clsx from 'clsx';
import toast from 'react-hot-toast';

interface LogEntry {
  timestamp: string;
  level: 'info' | 'warning' | 'error' | 'success';
  message: string;
}

export default function SimulationRunner() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const token = useAuthStore((s) => s.token);
  const [simulations, setSimulations] = useState<Simulation[]>([]);
  const [dlcDefs, setDlcDefs] = useState<DLCDefinition[]>([]);
  const [turbineModels, setTurbineModels] = useState<TurbineModel[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedSim, setSelectedSim] = useState<Simulation | null>(null);
  const [cases, setCases] = useState<SimulationCase[]>([]);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newName, setNewName] = useState('');
  const [newDlcId, setNewDlcId] = useState('');
  const [newTurbineModelId, setNewTurbineModelId] = useState('');
  const [isCreating, setIsCreating] = useState(false);
  const refreshRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // WebSocket & log state
  const wsRef = useRef<WebSocket | null>(null);
  const [wsConnected, setWsConnected] = useState(false);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [showLogs, setShowLogs] = useState(true);
  const [expandedErrors, setExpandedErrors] = useState<Set<string>>(new Set());
  const logEndRef = useRef<HTMLDivElement>(null);

  const addLog = useCallback((level: LogEntry['level'], message: string) => {
    const entry: LogEntry = {
      timestamp: new Date().toLocaleTimeString(),
      level,
      message,
    };
    setLogs((prev) => [...prev.slice(-200), entry]);
  }, []);

  // WebSocket connection
  useEffect(() => {
    if (!selectedSim || !token) return;
    const isActive = selectedSim.status === 'generating_wind' || selectedSim.status === 'running';
    if (!isActive) {
      // Close existing connection if sim is not active
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
        setWsConnected(false);
      }
      return;
    }

    // Build WebSocket URL
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsHost = window.location.hostname;
    const wsUrl = `${wsProtocol}//${wsHost}:8000/ws/${selectedSim.id}?token=${token}`;

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      setWsConnected(true);
      addLog('info', 'Connected to simulation monitor');
      // Subscribe to progress and logs
      ws.send(JSON.stringify({ action: 'subscribe', channels: ['progress', 'logs'] }));
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);

        switch (msg.type) {
          case 'connected':
            addLog('info', `Monitoring simulation ${msg.simulation_id}`);
            break;

          case 'generation_started':
            addLog('info', `Starting file generation for ${msg.total_cases} cases...`);
            break;

          case 'case_progress':
            if (msg.message) {
              addLog('info', msg.message);
            }
            // Update case status in local state
            if (msg.case_id) {
              setCases((prev) =>
                prev.map((c) =>
                  c.id === msg.case_id
                    ? { ...c, status: 'running' as SimulationCase['status'], progress_percent: msg.progress || c.progress_percent }
                    : c,
                ),
              );
            }
            break;

          case 'case_complete':
            addLog('success', `Case completed — ${msg.files_generated?.length || 0} files generated`);
            if (msg.case_id) {
              setCases((prev) =>
                prev.map((c) =>
                  c.id === msg.case_id
                    ? { ...c, status: 'completed' as SimulationCase['status'], progress_percent: 100 }
                    : c,
                ),
              );
              // Update simulation counters
              setSelectedSim((prev) =>
                prev ? { ...prev, completed_cases: prev.completed_cases + 1 } : prev,
              );
              setSimulations((prev) =>
                prev.map((s) =>
                  s.id === selectedSim.id
                    ? { ...s, completed_cases: s.completed_cases + 1 }
                    : s,
                ),
              );
            }
            break;

          case 'case_error':
            addLog('error', `Case failed: ${msg.error}`);
            if (msg.case_id) {
              setCases((prev) =>
                prev.map((c) =>
                  c.id === msg.case_id
                    ? { ...c, status: 'failed' as SimulationCase['status'], error_message: msg.error }
                    : c,
                ),
              );
              setSelectedSim((prev) =>
                prev ? { ...prev, failed_cases: prev.failed_cases + 1 } : prev,
              );
            }
            break;

          // Multi-phase simulation events
          case 'generate_only_mode':
            addLog('warning', `Generate-only mode: ${msg.message}`);
            break;

          case 'turbsim_started':
            addLog('info', `Running TurbSim for case ${msg.case_index ?? ''}...`);
            break;

          case 'turbsim_complete':
            addLog('success', `TurbSim complete — wind field generated`);
            break;

          case 'turbsim_error':
            addLog('error', `TurbSim failed: ${msg.error}`);
            break;

          case 'openfast_started':
            addLog('info', `Running OpenFAST for case ${msg.case_index ?? ''}...`);
            break;

          case 'openfast_complete':
            addLog('success', `OpenFAST complete — output generated`);
            break;

          case 'openfast_error':
            addLog('error', `OpenFAST failed: ${msg.error}`);
            break;

          case 'parsing_results':
            addLog('info', 'Parsing output files and computing statistics...');
            break;

          case 'results_persisted':
            addLog('success', `Results saved for ${msg.cases_with_results ?? 0} cases`);
            break;

          case 'simulation_complete':
            addLog(
              msg.failed > 0 ? 'warning' : 'success',
              `Simulation complete: ${msg.completed}/${msg.total} cases in ${msg.elapsed_seconds}s${msg.failed > 0 ? ` (${msg.failed} failed)` : ''}`,
            );
            // Refresh full state from server
            if (projectId) {
              simulationsApi.get(projectId, selectedSim.id).then((updated) => {
                setSelectedSim(updated);
                setSimulations((prev) => prev.map((s) => (s.id === updated.id ? updated : s)));
              });
              simulationsApi.getCases(projectId, selectedSim.id).then(setCases);
            }
            break;

          case 'simulation_error':
            addLog('error', `Simulation error: ${msg.error}`);
            if (projectId) {
              simulationsApi.get(projectId, selectedSim.id).then((updated) => {
                setSelectedSim(updated);
                setSimulations((prev) => prev.map((s) => (s.id === updated.id ? updated : s)));
              });
            }
            break;

          case 'subscribed':
            break; // ignore ack

          default:
            addLog('info', `Event: ${msg.type}`);
        }
      } catch {
        // ignore parse errors
      }
    };

    ws.onclose = () => {
      setWsConnected(false);
      addLog('info', 'Disconnected from simulation monitor');
    };

    ws.onerror = () => {
      addLog('warning', 'WebSocket connection error');
    };

    return () => {
      ws.close();
      wsRef.current = null;
      setWsConnected(false);
    };
  }, [selectedSim?.id, selectedSim?.status, token, addLog, projectId]);

  // Auto-scroll logs
  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  const loadSimulations = useCallback(async () => {
    if (!projectId) return;
    try {
      const data = await simulationsApi.list(projectId);
      setSimulations(data);
      return data;
    } catch {
      toast.error('Failed to load simulations');
      return [];
    }
  }, [projectId]);

  const loadSupportData = useCallback(async () => {
    if (!projectId) return;
    try {
      const [defs, models] = await Promise.all([
        dlcDefinitionsApi.list(projectId),
        turbineModelsApi.list(projectId),
      ]);
      setDlcDefs(defs);
      setTurbineModels(models);
    } catch {
      // non-critical
    }
  }, [projectId]);

  useEffect(() => {
    setIsLoading(true);
    Promise.all([loadSimulations(), loadSupportData()])
      .then(([sims]) => {
        if (sims && sims.length > 0) {
          setSelectedSim(sims[0]);
        }
      })
      .finally(() => setIsLoading(false));
  }, [loadSimulations, loadSupportData]);

  // Load cases when selection changes
  useEffect(() => {
    if (!projectId || !selectedSim) {
      setCases([]);
      return;
    }
    simulationsApi
      .getCases(projectId, selectedSim.id)
      .then(setCases)
      .catch(() => setCases([]));
  }, [projectId, selectedSim?.id]);

  // Auto-refresh while running/generating
  useEffect(() => {
    if (refreshRef.current) {
      clearInterval(refreshRef.current);
      refreshRef.current = null;
    }

    const isActive = selectedSim?.status === 'running' || selectedSim?.status === 'generating_wind';
    if (isActive && projectId) {
      refreshRef.current = setInterval(async () => {
        try {
          const [updatedSim, updatedCases] = await Promise.all([
            simulationsApi.get(projectId, selectedSim!.id),
            simulationsApi.getCases(projectId, selectedSim!.id),
          ]);
          setSelectedSim(updatedSim);
          setCases(updatedCases);
          setSimulations((prev) =>
            prev.map((s) => (s.id === updatedSim.id ? updatedSim : s)),
          );
          // Stop refreshing if no longer active
          const stillActive = updatedSim.status === 'running' || updatedSim.status === 'generating_wind';
          if (!stillActive && refreshRef.current) {
            clearInterval(refreshRef.current);
            refreshRef.current = null;
          }
        } catch {
          // ignore refresh errors
        }
      }, 2000);
    }

    return () => {
      if (refreshRef.current) {
        clearInterval(refreshRef.current);
        refreshRef.current = null;
      }
    };
  }, [selectedSim?.id, selectedSim?.status, projectId]);

  const handleSelect = (sim: Simulation) => {
    setSelectedSim(sim);
    setLogs([]); // Clear logs when switching
  };

  const handleCreate = async () => {
    if (!projectId || !newName.trim() || !newDlcId || !newTurbineModelId) return;
    setIsCreating(true);
    try {
      const payload: SimulationCreate = {
        name: newName.trim(),
        dlc_definition_id: newDlcId,
        turbine_model_id: newTurbineModelId,
      };
      const created = await simulationsApi.create(projectId, payload);
      toast.success('Simulation created');
      setShowCreateModal(false);
      setNewName('');
      setNewDlcId('');
      setNewTurbineModelId('');
      const data = await loadSimulations();
      if (data) {
        const found = data.find((s) => s.id === created.id);
        if (found) setSelectedSim(found);
      }
    } catch {
      toast.error('Failed to create simulation');
    } finally {
      setIsCreating(false);
    }
  };

  const handleStart = async () => {
    if (!projectId || !selectedSim) return;
    try {
      const updated = await simulationsApi.start(projectId, selectedSim.id);
      toast.success('Simulation started');
      setSelectedSim(updated);
      setSimulations((prev) =>
        prev.map((s) => (s.id === updated.id ? updated : s)),
      );
      addLog('info', 'Simulation started — generating files → TurbSim → OpenFAST...');
    } catch {
      toast.error('Failed to start simulation');
    }
  };

  const handleCancel = async () => {
    if (!projectId || !selectedSim) return;
    try {
      const updated = await simulationsApi.cancel(projectId, selectedSim.id);
      toast.success('Simulation cancelled');
      setSelectedSim(updated);
      setSimulations((prev) =>
        prev.map((s) => (s.id === updated.id ? updated : s)),
      );
    } catch {
      toast.error('Failed to cancel simulation');
    }
  };

  const toggleErrorExpanded = (caseId: string) => {
    setExpandedErrors((prev) => {
      const next = new Set(prev);
      if (next.has(caseId)) next.delete(caseId);
      else next.add(caseId);
      return next;
    });
  };

  const statusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle2 className="h-4 w-4 text-success-500" />;
      case 'failed':
        return <XCircle className="h-4 w-4 text-danger-500" />;
      case 'running':
      case 'generating_wind':
        return <Loader2 className="h-4 w-4 text-accent-500 animate-spin" />;
      case 'cancelled':
        return <StopCircle className="h-4 w-4 text-warning-500" />;
      default:
        return <Clock className="h-4 w-4 text-slate-400" />;
    }
  };

  const statusLabel = (status: string) => {
    switch (status) {
      case 'generating_wind':
        return 'Generating Files';
      case 'running':
        return 'Running';
      case 'completed':
        return 'Completed';
      case 'failed':
        return 'Failed';
      case 'cancelled':
        return 'Cancelled';
      default:
        return 'Pending';
    }
  };

  const statusBadge = (status: string) => {
    const colors: Record<string, string> = {
      pending: 'bg-surface-dark-tertiary text-slate-200',
      generating_wind: 'bg-accent-900/40 text-accent-300 border border-accent-700',
      running: 'bg-accent-900/40 text-accent-300 border border-accent-700',
      completed: 'bg-success-900/40 text-success-300 border border-success-700',
      failed: 'bg-danger-900/40 text-danger-300 border border-danger-700',
      cancelled: 'bg-warning-900/40 text-warning-300 border border-warning-700',
    };
    return (
      <span
        className={clsx(
          'inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium',
          colors[status] || colors.pending,
        )}
      >
        {statusIcon(status)}
        {statusLabel(status)}
      </span>
    );
  };

  const progressPercent = selectedSim
    ? selectedSim.total_cases > 0
      ? Math.round(((selectedSim.completed_cases + selectedSim.failed_cases) / selectedSim.total_cases) * 100)
      : 0
    : 0;

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-24">
        <Loader2 className="h-8 w-8 animate-spin text-accent-500" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-slate-100">Simulation Runner</h2>
          <p className="text-sm text-slate-400">
            Run TurbSim + OpenFAST simulations and monitor progress
          </p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="btn-primary flex items-center gap-2"
        >
          <Plus className="h-4 w-4" />
          New Simulation
        </button>
      </div>

      {/* Create Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-surface-dark-secondary rounded-xl shadow-xl p-6 w-full max-w-md">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-slate-100">New Simulation</h3>
              <button onClick={() => setShowCreateModal(false)} className="text-slate-400 hover:text-slate-300">
                <X className="h-5 w-5" />
              </button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-200 mb-1">Name</label>
                <input
                  type="text"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  placeholder="e.g., Run 001"
                  className="w-full rounded-lg border border-slate-600 bg-surface-dark-secondary px-3 py-2 text-sm text-slate-100 placeholder-slate-400 focus:border-accent-500 focus:ring-1 focus:ring-accent-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-200 mb-1">DLC Definition</label>
                <select
                  value={newDlcId}
                  onChange={(e) => setNewDlcId(e.target.value)}
                  className="w-full rounded-lg border border-slate-600 bg-surface-dark-secondary px-3 py-2 text-sm text-slate-100 focus:border-accent-500 focus:ring-1 focus:ring-accent-500"
                >
                  <option value="">-- Select --</option>
                  {dlcDefs.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.name} ({d.total_case_count} cases)
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-200 mb-1">Turbine Model</label>
                <select
                  value={newTurbineModelId}
                  onChange={(e) => setNewTurbineModelId(e.target.value)}
                  className="w-full rounded-lg border border-slate-600 bg-surface-dark-secondary px-3 py-2 text-sm text-slate-100 focus:border-accent-500 focus:ring-1 focus:ring-accent-500"
                >
                  <option value="">-- Select --</option>
                  {turbineModels.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.name}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <div className="flex justify-end gap-3 mt-6">
              <button
                onClick={() => setShowCreateModal(false)}
                className="px-4 py-2 text-sm font-medium text-slate-200 bg-surface-dark-tertiary rounded-lg hover:bg-slate-600"
              >
                Cancel
              </button>
              <button
                onClick={handleCreate}
                disabled={isCreating || !newName.trim() || !newDlcId || !newTurbineModelId}
                className="px-4 py-2 text-sm font-medium text-white bg-accent-600 rounded-lg hover:bg-accent-700 disabled:opacity-50 flex items-center gap-2"
              >
                {isCreating && <Loader2 className="h-4 w-4 animate-spin" />}
                Create
              </button>
            </div>
          </div>
        </div>
      )}

      {simulations.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-600 py-16">
          <Play className="h-12 w-12 text-slate-300 mb-3" />
          <h3 className="text-base font-semibold text-slate-200">No simulations</h3>
          <p className="mt-1 text-sm text-slate-400 max-w-sm text-center">
            Create a simulation by selecting a turbine model and DLC definition.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Simulation list */}
          <div className="space-y-2">
            {simulations.map((sim) => (
              <button
                key={sim.id}
                onClick={() => handleSelect(sim)}
                className={clsx(
                  'w-full rounded-lg border p-4 text-left transition-all',
                  selectedSim?.id === sim.id
                    ? 'border-accent-500 bg-accent-950/30 shadow-sm'
                    : 'border-slate-600 bg-surface-dark-secondary hover:border-slate-500',
                )}
              >
                <div className="flex items-center justify-between">
                  <span className="font-medium text-slate-100 truncate">{sim.name}</span>
                  {statusIcon(sim.status)}
                </div>
                <div className="mt-1 text-xs text-slate-400">
                  {sim.completed_cases}/{sim.total_cases} cases &middot; {statusLabel(sim.status)}
                </div>
                {(sim.status === 'running' || sim.status === 'generating_wind') && (
                  <div className="mt-2 h-1.5 w-full rounded-full bg-slate-600">
                    <div
                      className="h-full rounded-full bg-accent-500 transition-all duration-500"
                      style={{
                        width: `${sim.total_cases > 0 ? ((sim.completed_cases + sim.failed_cases) / sim.total_cases) * 100 : 0}%`,
                      }}
                    />
                  </div>
                )}
              </button>
            ))}
          </div>

          {/* Simulation detail */}
          {selectedSim && (
            <div className="lg:col-span-2 space-y-4">
              {/* Header + controls */}
              <div className="rounded-xl border border-slate-600 bg-surface-dark-secondary p-6">
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <h3 className="text-lg font-semibold text-slate-100">{selectedSim.name}</h3>
                    <div className="mt-1 flex items-center gap-3">
                      {statusBadge(selectedSim.status)}
                      {wsConnected && (
                        <span className="inline-flex items-center gap-1 text-xs text-green-400">
                          <Wifi className="h-3 w-3" /> Live
                        </span>
                      )}
                      {(selectedSim.status === 'generating_wind' || selectedSim.status === 'running') && !wsConnected && (
                        <span className="inline-flex items-center gap-1 text-xs text-slate-500">
                          <WifiOff className="h-3 w-3" /> Polling
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {selectedSim.status === 'pending' && (
                      <button
                        onClick={handleStart}
                        className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-accent-600 rounded-lg hover:bg-accent-700 transition-colors"
                      >
                        <Play className="h-4 w-4" />
                        Run Simulation
                      </button>
                    )}
                    {(selectedSim.status === 'running' || selectedSim.status === 'generating_wind') && (
                      <button
                        onClick={handleCancel}
                        className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-danger-600 rounded-lg hover:bg-danger-700 transition-colors"
                      >
                        <StopCircle className="h-4 w-4" />
                        Cancel
                      </button>
                    )}
                    {selectedSim.status === 'completed' && (
                      <button
                        onClick={() => navigate(`/projects/${projectId}/files`)}
                        className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-slate-100 bg-surface-dark-tertiary rounded-lg hover:bg-slate-600 border border-slate-600 transition-colors"
                      >
                        <FolderOpen className="h-4 w-4" />
                        View Files
                      </button>
                    )}
                    <button
                      onClick={() => {
                        if (projectId && selectedSim) {
                          Promise.all([
                            simulationsApi.get(projectId, selectedSim.id).then(setSelectedSim),
                            simulationsApi.getCases(projectId, selectedSim.id).then(setCases),
                          ]);
                        }
                      }}
                      className="p-2 text-slate-400 hover:text-slate-200 transition-colors"
                      title="Refresh"
                    >
                      <RefreshCw className="h-4 w-4" />
                    </button>
                  </div>
                </div>

                {/* Overall progress */}
                <div className="rounded-lg bg-surface-dark-tertiary p-4">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium text-slate-200">Overall Progress</span>
                    <span className="text-sm font-mono text-slate-300">
                      {selectedSim.completed_cases + selectedSim.failed_cases}/{selectedSim.total_cases}
                      <span className="text-slate-500 ml-2">({progressPercent}%)</span>
                    </span>
                  </div>
                  <div className="h-2.5 w-full rounded-full bg-slate-600 overflow-hidden">
                    {/* Success portion */}
                    <div className="h-full flex">
                      <div
                        className="h-full bg-success-500 transition-all duration-500"
                        style={{
                          width: `${selectedSim.total_cases > 0 ? (selectedSim.completed_cases / selectedSim.total_cases) * 100 : 0}%`,
                        }}
                      />
                      <div
                        className="h-full bg-danger-500 transition-all duration-500"
                        style={{
                          width: `${selectedSim.total_cases > 0 ? (selectedSim.failed_cases / selectedSim.total_cases) * 100 : 0}%`,
                        }}
                      />
                    </div>
                  </div>
                  <div className="flex items-center gap-4 mt-2 text-xs text-slate-400">
                    <span className="flex items-center gap-1">
                      <span className="inline-block w-2 h-2 rounded-full bg-success-500" />
                      {selectedSim.completed_cases} completed
                    </span>
                    {selectedSim.failed_cases > 0 && (
                      <span className="flex items-center gap-1">
                        <span className="inline-block w-2 h-2 rounded-full bg-danger-500" />
                        {selectedSim.failed_cases} failed
                      </span>
                    )}
                    <span className="flex items-center gap-1">
                      <span className="inline-block w-2 h-2 rounded-full bg-slate-500" />
                      {selectedSim.total_cases - selectedSim.completed_cases - selectedSim.failed_cases} pending
                    </span>
                  </div>
                </div>

                {/* Completion summary */}
                {selectedSim.status === 'completed' && (
                  <div className="mt-4 rounded-lg border border-success-700/30 bg-success-950/20 p-3 flex items-center gap-3">
                    <CheckCircle2 className="h-5 w-5 text-success-400 flex-shrink-0" />
                    <div>
                      <p className="text-sm font-medium text-success-300">
                        Simulation complete
                      </p>
                      <p className="text-xs text-success-400/70 mt-0.5">
                        {selectedSim.completed_cases} case{selectedSim.completed_cases !== 1 ? 's' : ''} completed successfully.
                        View results in the Results tab or files in the Files tab.
                      </p>
                    </div>
                  </div>
                )}

                {selectedSim.status === 'failed' && (
                  <div className="mt-4 rounded-lg border border-danger-700/30 bg-danger-950/20 p-3 flex items-center gap-3">
                    <AlertTriangle className="h-5 w-5 text-danger-400 flex-shrink-0" />
                    <div>
                      <p className="text-sm font-medium text-danger-300">
                        Simulation failed
                      </p>
                      <p className="text-xs text-danger-400/70 mt-0.5">
                        Check the error messages below for details.
                      </p>
                    </div>
                  </div>
                )}
              </div>

              {/* Cases table */}
              {cases.length > 0 && (
                <div className="rounded-xl border border-slate-600 bg-surface-dark-secondary overflow-hidden">
                  <div className="px-4 py-3 border-b border-slate-700 bg-surface-dark-tertiary flex items-center justify-between">
                    <h4 className="text-sm font-semibold text-slate-200">
                      Simulation Cases ({cases.length})
                    </h4>
                    <span className="text-xs text-slate-400">
                      <FileText className="h-3.5 w-3.5 inline mr-1" />
                      Each case runs TurbSim → OpenFAST → results parsing
                    </span>
                  </div>
                  <div className="overflow-x-auto max-h-72 overflow-y-auto">
                    <table className="min-w-full text-sm">
                      <thead className="bg-surface-dark-tertiary sticky top-0">
                        <tr>
                          <th className="px-3 py-2 text-left text-xs font-medium text-slate-400 uppercase">DLC</th>
                          <th className="px-3 py-2 text-left text-xs font-medium text-slate-400 uppercase">Wind (m/s)</th>
                          <th className="px-3 py-2 text-left text-xs font-medium text-slate-400 uppercase">Seed</th>
                          <th className="px-3 py-2 text-left text-xs font-medium text-slate-400 uppercase">Yaw</th>
                          <th className="px-3 py-2 text-left text-xs font-medium text-slate-400 uppercase">Status</th>
                          <th className="px-3 py-2 text-left text-xs font-medium text-slate-400 uppercase">Progress</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-700">
                        {cases.map((c) => (
                          <>
                            <tr key={c.id} className="hover:bg-surface-dark-tertiary">
                              <td className="px-3 py-2 font-medium text-slate-100">{c.dlc_number}</td>
                              <td className="px-3 py-2 text-slate-200">{c.wind_speed}</td>
                              <td className="px-3 py-2 text-slate-200">{c.seed_number}</td>
                              <td className="px-3 py-2 text-slate-200">{c.yaw_misalignment}°</td>
                              <td className="px-3 py-2">
                                <div className="flex items-center gap-1.5">
                                  {statusIcon(c.status)}
                                  <span className="text-slate-200">{statusLabel(c.status)}</span>
                                  {c.status === 'failed' && c.error_message && (
                                    <button
                                      onClick={() => toggleErrorExpanded(c.id)}
                                      className="ml-1 text-danger-400 hover:text-danger-300"
                                      title="View error"
                                    >
                                      {expandedErrors.has(c.id) ? (
                                        <ChevronDown className="h-3.5 w-3.5" />
                                      ) : (
                                        <ChevronRight className="h-3.5 w-3.5" />
                                      )}
                                    </button>
                                  )}
                                </div>
                              </td>
                              <td className="px-3 py-2">
                                <div className="flex items-center gap-2">
                                  <div className="h-1.5 w-20 rounded-full bg-slate-600">
                                    <div
                                      className={clsx(
                                        'h-full rounded-full transition-all duration-300',
                                        c.status === 'completed'
                                          ? 'bg-success-500'
                                          : c.status === 'failed'
                                            ? 'bg-danger-500'
                                            : 'bg-accent-500',
                                      )}
                                      style={{ width: `${c.progress_percent}%` }}
                                    />
                                  </div>
                                  <span className="text-xs font-mono text-slate-400 w-8">
                                    {c.progress_percent}%
                                  </span>
                                </div>
                              </td>
                            </tr>
                            {c.status === 'failed' && c.error_message && expandedErrors.has(c.id) && (
                              <tr key={`${c.id}-error`}>
                                <td colSpan={6} className="px-3 py-2">
                                  <div className="rounded-lg bg-danger-950/30 border border-danger-800/30 p-3">
                                    <pre className="text-xs text-danger-300 font-mono whitespace-pre-wrap break-words">
                                      {c.error_message}
                                    </pre>
                                  </div>
                                </td>
                              </tr>
                            )}
                          </>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* Console log */}
              <div className="rounded-xl border border-slate-600 bg-surface-dark-secondary overflow-hidden">
                <button
                  onClick={() => setShowLogs(!showLogs)}
                  className="w-full px-4 py-3 border-b border-slate-700 bg-surface-dark-tertiary flex items-center justify-between hover:bg-slate-700/50 transition-colors"
                >
                  <div className="flex items-center gap-2">
                    <Terminal className="h-4 w-4 text-slate-400" />
                    <h4 className="text-sm font-semibold text-slate-200">Console</h4>
                    {logs.length > 0 && (
                      <span className="text-xs text-slate-500">({logs.length} entries)</span>
                    )}
                  </div>
                  {showLogs ? (
                    <ChevronDown className="h-4 w-4 text-slate-400" />
                  ) : (
                    <ChevronRight className="h-4 w-4 text-slate-400" />
                  )}
                </button>
                {showLogs && (
                  <div className="max-h-48 overflow-y-auto p-3 font-mono text-xs">
                    {logs.length === 0 ? (
                      <p className="text-slate-500 text-center py-4">
                        Console output will appear here when a simulation is running...
                      </p>
                    ) : (
                      logs.map((log, i) => (
                        <div
                          key={i}
                          className={clsx(
                            'py-0.5 flex gap-2',
                            log.level === 'error' && 'text-danger-400',
                            log.level === 'warning' && 'text-warning-400',
                            log.level === 'success' && 'text-success-400',
                            log.level === 'info' && 'text-slate-300',
                          )}
                        >
                          <span className="text-slate-500 flex-shrink-0">[{log.timestamp}]</span>
                          <span>{log.message}</span>
                        </div>
                      ))
                    )}
                    <div ref={logEndRef} />
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
