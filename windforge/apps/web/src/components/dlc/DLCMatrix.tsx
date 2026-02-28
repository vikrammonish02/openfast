import { useState, useEffect, useMemo, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Save,
  FolderOpen,
  ChevronDown,
  ChevronRight,
  Zap,
  Shield,
  Wind,
  Settings2,
  Hash,
  RotateCcw,
  Plus,
  X,
  AlertTriangle,
  Play,
  Square,
  AlertOctagon,
  ParkingCircle,
  ShieldAlert,
  Truck,
  ListFilter,
  Target,
  Crosshair,
  ArrowRight,
} from 'lucide-react';
import clsx from 'clsx';
import toast from 'react-hot-toast';
import apiClient from '@/api/client';
import StatusBadge from '@/components/common/StatusBadge';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface DLCCaseSpec {
  dlc_number: string;
  wind_speeds: number[];
  seeds: number;
  yaw_misalignments: number[];
  wind_condition: string;
  partial_safety_factor: number;
  analysis_type: string;
  simulation_length: number;
  init_length: number;
  description: string;
  is_custom: boolean;
}

interface TurbSimParams {
  turbulence_model: string;
  iec_standard: string;
  iec_turbc: string;
  grid_height: number;
  grid_width: number;
  num_grid_z: number;
  num_grid_y: number;
  time_step: number;
  analysis_time: number;
  ref_height: number;
}

interface DLCDefinition {
  id: string;
  project_id: string;
  turbine_model_id: string;
  name: string;
  dlc_cases: DLCCaseSpec[] | null;
  turbsim_params: TurbSimParams | null;
  total_case_count: number;
  status: string;
  created_at: string;
}

interface TurbineModel {
  id: string;
  name: string;
}

// ---------------------------------------------------------------------------
// DLC metadata — IEC 61400-1 Ed.4 Table 2
// ---------------------------------------------------------------------------

type DLCGroup =
  | 'power_production'
  | 'power_prod_fault'
  | 'startup'
  | 'normal_shutdown'
  | 'emergency_shutdown'
  | 'parked'
  | 'parked_fault'
  | 'transport';

interface DLCMeta {
  number: string;
  group: DLCGroup;
  description: string;
  windModel: string;
  analysisType: 'fatigue' | 'ultimate';
  partialSafetyFactor: number;
  defaultSeeds: number;
  defaultYaw: number[];
  defaultWindSpeeds: string;
  faultCondition: string;
  simulationLength: number;
  initLength: number;
}

const DLC_CATALOG: DLCMeta[] = [
  // 1. Power production
  { number: '1.1', group: 'power_production', description: 'Normal turbulence', windModel: 'NTM', analysisType: 'ultimate', partialSafetyFactor: 1.25, defaultSeeds: 6, defaultYaw: [-8, 0, 8], defaultWindSpeeds: 'Vin:Vout', faultCondition: 'none', simulationLength: 600, initLength: 200 },
  { number: '1.2', group: 'power_production', description: 'Normal turbulence (fatigue)', windModel: 'NTM', analysisType: 'fatigue', partialSafetyFactor: 1.0, defaultSeeds: 6, defaultYaw: [-8, 0, 8], defaultWindSpeeds: 'Vin:Vout', faultCondition: 'none', simulationLength: 600, initLength: 200 },
  { number: '1.3', group: 'power_production', description: 'Extreme turbulence model', windModel: 'ETM', analysisType: 'ultimate', partialSafetyFactor: 1.35, defaultSeeds: 6, defaultYaw: [-8, 0, 8], defaultWindSpeeds: 'Vin:Vout', faultCondition: 'none', simulationLength: 600, initLength: 200 },
  { number: '1.4', group: 'power_production', description: 'Extreme coherent gust + dir change', windModel: 'ECD', analysisType: 'ultimate', partialSafetyFactor: 1.35, defaultSeeds: 1, defaultYaw: [0], defaultWindSpeeds: 'Vr-2,Vr,Vr+2', faultCondition: 'none', simulationLength: 60, initLength: 0 },
  { number: '1.5', group: 'power_production', description: 'Extreme wind shear', windModel: 'EWS', analysisType: 'ultimate', partialSafetyFactor: 1.35, defaultSeeds: 1, defaultYaw: [0], defaultWindSpeeds: 'Vin:Vout', faultCondition: 'none', simulationLength: 60, initLength: 0 },
  // 2. Power production + fault
  { number: '2.1', group: 'power_prod_fault', description: 'Control system fault', windModel: 'NTM', analysisType: 'ultimate', partialSafetyFactor: 1.35, defaultSeeds: 6, defaultYaw: [0], defaultWindSpeeds: 'Vin:Vout', faultCondition: 'control', simulationLength: 600, initLength: 200 },
  { number: '2.2', group: 'power_prod_fault', description: 'Protection / internal electrical fault', windModel: 'NTM', analysisType: 'ultimate', partialSafetyFactor: 1.1, defaultSeeds: 6, defaultYaw: [0], defaultWindSpeeds: 'Vin:Vout', faultCondition: 'protection', simulationLength: 600, initLength: 200 },
  { number: '2.3', group: 'power_prod_fault', description: 'EOG + external electrical fault', windModel: 'EOG', analysisType: 'ultimate', partialSafetyFactor: 1.1, defaultSeeds: 1, defaultYaw: [0], defaultWindSpeeds: 'Vr-2,Vr,Vr+2,Vout', faultCondition: 'electrical', simulationLength: 60, initLength: 0 },
  { number: '2.4', group: 'power_prod_fault', description: 'NTM with fault (fatigue)', windModel: 'NTM', analysisType: 'fatigue', partialSafetyFactor: 1.0, defaultSeeds: 6, defaultYaw: [0], defaultWindSpeeds: 'Vin:Vout', faultCondition: 'control', simulationLength: 600, initLength: 200 },
  // 3. Start-up
  { number: '3.1', group: 'startup', description: 'Normal wind profile', windModel: 'NWP', analysisType: 'fatigue', partialSafetyFactor: 1.0, defaultSeeds: 1, defaultYaw: [0], defaultWindSpeeds: 'Vin,Vr,Vout', faultCondition: 'none', simulationLength: 60, initLength: 0 },
  { number: '3.2', group: 'startup', description: 'Extreme operating gust', windModel: 'EOG', analysisType: 'ultimate', partialSafetyFactor: 1.35, defaultSeeds: 1, defaultYaw: [0], defaultWindSpeeds: 'Vin,Vr-2,Vr,Vr+2', faultCondition: 'none', simulationLength: 60, initLength: 0 },
  { number: '3.3', group: 'startup', description: 'Extreme direction change', windModel: 'EDC', analysisType: 'ultimate', partialSafetyFactor: 1.35, defaultSeeds: 1, defaultYaw: [0], defaultWindSpeeds: 'Vin,Vr-2,Vr,Vr+2', faultCondition: 'none', simulationLength: 60, initLength: 0 },
  // 4. Normal shutdown
  { number: '4.1', group: 'normal_shutdown', description: 'Normal wind profile', windModel: 'NWP', analysisType: 'fatigue', partialSafetyFactor: 1.0, defaultSeeds: 1, defaultYaw: [0], defaultWindSpeeds: 'Vr-2,Vr,Vr+2,Vout', faultCondition: 'none', simulationLength: 60, initLength: 0 },
  { number: '4.2', group: 'normal_shutdown', description: 'Extreme operating gust', windModel: 'EOG', analysisType: 'ultimate', partialSafetyFactor: 1.35, defaultSeeds: 1, defaultYaw: [0], defaultWindSpeeds: 'Vr-2,Vr,Vr+2,Vout', faultCondition: 'none', simulationLength: 60, initLength: 0 },
  // 5. Emergency shutdown
  { number: '5.1', group: 'emergency_shutdown', description: 'Emergency shutdown', windModel: 'NTM', analysisType: 'ultimate', partialSafetyFactor: 1.35, defaultSeeds: 6, defaultYaw: [0], defaultWindSpeeds: 'Vr-2,Vr,Vr+2', faultCondition: 'none', simulationLength: 60, initLength: 0 },
  // 6. Parked
  { number: '6.1', group: 'parked', description: 'EWM 50-yr recurrence', windModel: 'EWM 50-yr', analysisType: 'ultimate', partialSafetyFactor: 1.35, defaultSeeds: 6, defaultYaw: [-8, 0, 8], defaultWindSpeeds: 'Ve50', faultCondition: 'none', simulationLength: 600, initLength: 200 },
  { number: '6.2', group: 'parked', description: 'EWM 50-yr + grid loss', windModel: 'EWM 50-yr', analysisType: 'ultimate', partialSafetyFactor: 1.1, defaultSeeds: 6, defaultYaw: [-180, -30, 0, 30, 180], defaultWindSpeeds: 'Ve50', faultCondition: 'grid_loss', simulationLength: 600, initLength: 200 },
  { number: '6.3', group: 'parked', description: 'EWM 1-yr recurrence', windModel: 'EWM 1-yr', analysisType: 'ultimate', partialSafetyFactor: 1.35, defaultSeeds: 6, defaultYaw: [-20, 0, 20], defaultWindSpeeds: 'Ve1', faultCondition: 'none', simulationLength: 600, initLength: 200 },
  { number: '6.4', group: 'parked', description: 'Normal turbulence (fatigue)', windModel: 'NTM', analysisType: 'fatigue', partialSafetyFactor: 1.0, defaultSeeds: 6, defaultYaw: [-8, 0, 8], defaultWindSpeeds: 'Vin:Vout', faultCondition: 'none', simulationLength: 600, initLength: 200 },
  // 7. Parked + fault
  { number: '7.1', group: 'parked_fault', description: 'EWM 1-yr + yaw system fault', windModel: 'EWM 1-yr', analysisType: 'ultimate', partialSafetyFactor: 1.1, defaultSeeds: 6, defaultYaw: [-180, -30, 0, 30, 180], defaultWindSpeeds: 'Ve1', faultCondition: 'yaw_system', simulationLength: 600, initLength: 200 },
  // 8. Transport / installation
  { number: '8.1', group: 'transport', description: 'Transport, assembly, maintenance', windModel: 'EWM', analysisType: 'ultimate', partialSafetyFactor: 1.5, defaultSeeds: 1, defaultYaw: [0], defaultWindSpeeds: 'Vmaint', faultCondition: 'none', simulationLength: 600, initLength: 200 },
];

// ---------------------------------------------------------------------------
// Group definitions
// ---------------------------------------------------------------------------

interface GroupDef {
  key: DLCGroup;
  label: string;
  dlcRange: string;
  icon: React.FC<{ size?: number; className?: string }>;
}

const DLC_GROUPS: GroupDef[] = [
  { key: 'power_production', label: '1. Power Production', dlcRange: '1.1 \u2013 1.5', icon: Zap },
  { key: 'power_prod_fault', label: '2. Power Production + Fault', dlcRange: '2.1 \u2013 2.4', icon: AlertTriangle },
  { key: 'startup', label: '3. Start-up', dlcRange: '3.1 \u2013 3.3', icon: Play },
  { key: 'normal_shutdown', label: '4. Normal Shutdown', dlcRange: '4.1 \u2013 4.2', icon: Square },
  { key: 'emergency_shutdown', label: '5. Emergency Shutdown', dlcRange: '5.1', icon: AlertOctagon },
  { key: 'parked', label: '6. Parked (Standstill or Idling)', dlcRange: '6.1 \u2013 6.4', icon: ParkingCircle },
  { key: 'parked_fault', label: '7. Parked + Fault Conditions', dlcRange: '7.1', icon: ShieldAlert },
  { key: 'transport', label: '8. Transport / Installation', dlcRange: '8.1', icon: Truck },
];

// ---------------------------------------------------------------------------
// Wind condition options
// ---------------------------------------------------------------------------

const WIND_CONDITIONS = [
  { value: 'NTM', label: 'NTM' },
  { value: 'NTM_Ieff', label: 'NTM I_eff' },
  { value: 'NTM_Ichar', label: "NTM I'_char" },
  { value: 'ETM', label: 'ETM' },
  { value: 'EWM', label: 'EWM' },
  { value: 'EOG', label: 'EOG' },
  { value: 'ECD', label: 'ECD' },
  { value: 'EDC', label: 'EDC' },
  { value: 'EWS', label: 'EWS' },
  { value: 'NWP', label: 'NWP' },
];

// ---------------------------------------------------------------------------
// Preset definitions
// ---------------------------------------------------------------------------

interface Preset {
  name: string;
  icon: React.FC<{ size?: number; className?: string }>;
  description: string;
  dlcNumbers: string[];
}

const PRESETS: Preset[] = [
  { name: 'IEC Minimum', icon: Target, description: 'Minimal cert set for quick assessment', dlcNumbers: ['1.1', '1.3', '2.1', '5.1', '6.1', '6.3'] },
  { name: 'Full Certification', icon: Shield, description: 'All 20 IEC DLCs with standard parameters', dlcNumbers: DLC_CATALOG.map((d) => d.number) },
  { name: 'Fatigue Focus', icon: RotateCcw, description: 'All fatigue-type DLCs', dlcNumbers: DLC_CATALOG.filter((d) => d.analysisType === 'fatigue').map((d) => d.number) },
  { name: 'Ultimate Focus', icon: Crosshair, description: 'All ultimate-type DLCs', dlcNumbers: DLC_CATALOG.filter((d) => d.analysisType === 'ultimate').map((d) => d.number) },
];

// ---------------------------------------------------------------------------
// Per-DLC row state (enhanced)
// ---------------------------------------------------------------------------

interface DLCRowState {
  enabled: boolean;
  expanded: boolean;
  windSpeedMin: number;
  windSpeedMax: number;
  windSpeedStep: number;
  seeds: number;
  yawMisalignments: number[];
  windCondition: string;
  partialSafetyFactor: number;
  analysisType: 'fatigue' | 'ultimate';
  simulationLength: number;
  initLength: number;
  description: string;
  isCustom: boolean;
}

function defaultRowState(meta?: DLCMeta): DLCRowState {
  return {
    enabled: false,
    expanded: false,
    windSpeedMin: 4,
    windSpeedMax: 24,
    windSpeedStep: 2,
    seeds: meta?.defaultSeeds ?? 6,
    yawMisalignments: meta?.defaultYaw ?? [0],
    windCondition: meta?.windModel ?? 'NTM',
    partialSafetyFactor: meta?.partialSafetyFactor ?? 1.35,
    analysisType: meta?.analysisType ?? 'ultimate',
    simulationLength: meta?.simulationLength ?? 600,
    initLength: meta?.initLength ?? 200,
    description: meta?.description ?? '',
    isCustom: false,
  };
}

function generateWindSpeeds(min: number, max: number, step: number): number[] {
  const speeds: number[] = [];
  for (let v = min; v <= max + 0.001; v += step) {
    speeds.push(parseFloat(v.toFixed(1)));
  }
  return speeds;
}

function countCases(row: DLCRowState): number {
  if (!row.enabled) return 0;
  const speeds = generateWindSpeeds(row.windSpeedMin, row.windSpeedMax, row.windSpeedStep);
  return speeds.length * row.seeds * row.yawMisalignments.length;
}

// ---------------------------------------------------------------------------
// Default TurbSim params
// ---------------------------------------------------------------------------

function defaultTurbSimParams(): TurbSimParams {
  return {
    turbulence_model: 'IECKAI',
    iec_standard: '1-ED3',
    iec_turbc: 'B',
    grid_height: 180,
    grid_width: 180,
    num_grid_z: 25,
    num_grid_y: 25,
    time_step: 0.05,
    analysis_time: 660,
    ref_height: 119,
  };
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

export default function DLCMatrix() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();

  const [name, setName] = useState('Default DLC Matrix');
  const [showNextStep, setShowNextStep] = useState(false);
  const [turbineModels, setTurbineModels] = useState<TurbineModel[]>([]);
  const [selectedTurbineId, setSelectedTurbineId] = useState('');
  const [existingDefinitions, setExistingDefinitions] = useState<DLCDefinition[]>([]);
  const [activeDefinitionId, setActiveDefinitionId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [expandedGroups, setExpandedGroups] = useState<Record<DLCGroup, boolean>>(() => {
    const init: Record<string, boolean> = {};
    DLC_GROUPS.forEach((g) => { init[g.key] = true; });
    return init as Record<DLCGroup, boolean>;
  });

  const [allDLCs, setAllDLCs] = useState<DLCMeta[]>([...DLC_CATALOG]);
  const [rows, setRows] = useState<Record<string, DLCRowState>>(() => {
    const init: Record<string, DLCRowState> = {};
    DLC_CATALOG.forEach((dlc) => { init[dlc.number] = defaultRowState(dlc); });
    return init;
  });
  const [turbSimParams, setTurbSimParams] = useState<TurbSimParams>(defaultTurbSimParams());

  // ---- Fetch turbine models & existing definitions ----
  useEffect(() => {
    if (!projectId) return;
    apiClient.get(`/projects/${projectId}/turbine-models`).then((res) => {
      const models = res.data as TurbineModel[];
      setTurbineModels(models);
      if (models.length > 0 && !selectedTurbineId) setSelectedTurbineId(models[0].id);
    }).catch(() => {});
    apiClient.get(`/projects/${projectId}/dlc-definitions`).then((res) => {
      setExistingDefinitions(res.data as DLCDefinition[]);
    }).catch(() => {});
  }, [projectId]);

  // ---- Load an existing definition ----
  const loadDefinition = useCallback((def: DLCDefinition) => {
    setName(def.name);
    setSelectedTurbineId(def.turbine_model_id);
    setActiveDefinitionId(def.id);
    if (def.turbsim_params) setTurbSimParams(def.turbsim_params);

    const catalogNumbers = new Set(DLC_CATALOG.map((d) => d.number));
    const customMetas: DLCMeta[] = [];
    const newRows: Record<string, DLCRowState> = {};
    DLC_CATALOG.forEach((dlc) => { newRows[dlc.number] = defaultRowState(dlc); });

    if (def.dlc_cases) {
      def.dlc_cases.forEach((c) => {
        if (!catalogNumbers.has(c.dlc_number)) {
          const baseNum = c.dlc_number.replace(/[a-zA-Z]+$/, '');
          const baseMeta = DLC_CATALOG.find((d) => d.number === baseNum);
          customMetas.push({
            number: c.dlc_number,
            group: baseMeta?.group ?? 'power_production',
            description: c.description || `Custom: ${c.dlc_number}`,
            windModel: c.wind_condition || baseMeta?.windModel || 'NTM',
            analysisType: (c.analysis_type as 'fatigue' | 'ultimate') || 'ultimate',
            partialSafetyFactor: c.partial_safety_factor ?? 1.35,
            defaultSeeds: c.seeds,
            defaultYaw: c.yaw_misalignments,
            defaultWindSpeeds: 'Vin:Vout',
            faultCondition: baseMeta?.faultCondition ?? 'none',
            simulationLength: c.simulation_length ?? 600,
            initLength: c.init_length ?? 200,
          });
        }
        const speeds = [...c.wind_speeds].sort((a, b) => a - b);
        const step = speeds.length > 1 ? parseFloat((speeds[1] - speeds[0]).toFixed(1)) : 2;
        newRows[c.dlc_number] = {
          enabled: true, expanded: false,
          windSpeedMin: speeds[0] ?? 4, windSpeedMax: speeds[speeds.length - 1] ?? 24, windSpeedStep: step,
          seeds: c.seeds, yawMisalignments: c.yaw_misalignments,
          windCondition: c.wind_condition || 'NTM',
          partialSafetyFactor: c.partial_safety_factor ?? 1.35,
          analysisType: (c.analysis_type as 'fatigue' | 'ultimate') || 'ultimate',
          simulationLength: c.simulation_length ?? 600, initLength: c.init_length ?? 200,
          description: c.description || '',
          isCustom: c.is_custom ?? !catalogNumbers.has(c.dlc_number),
        };
      });
    }
    setAllDLCs([...DLC_CATALOG, ...customMetas]);
    setRows(newRows);
    toast.success(`Loaded "${def.name}"`);
  }, []);

  // ---- Apply preset ----
  const applyPreset = useCallback((preset: Preset) => {
    const enabledSet = new Set(preset.dlcNumbers);
    const newRows: Record<string, DLCRowState> = {};
    DLC_CATALOG.forEach((dlc) => {
      newRows[dlc.number] = { ...defaultRowState(dlc), enabled: enabledSet.has(dlc.number) };
    });
    setAllDLCs([...DLC_CATALOG]);
    setRows(newRows);
    setActiveDefinitionId(null);
    toast.success(`Applied preset: ${preset.name}`);
  }, []);

  // ---- Add custom sub-DLC ----
  const addCustomDLC = useCallback((group: DLCGroup, baseDlcNumber: string, suffix: string, desc: string) => {
    const newNumber = `${baseDlcNumber}${suffix}`;
    if (rows[newNumber]) { toast.error(`DLC ${newNumber} already exists`); return; }
    const baseMeta = DLC_CATALOG.find((d) => d.number === baseDlcNumber);
    if (!baseMeta) return;
    setAllDLCs((prev) => [...prev, { ...baseMeta, number: newNumber, description: desc || `Custom: ${newNumber}` }]);
    setRows((prev) => ({ ...prev, [newNumber]: { ...defaultRowState(baseMeta), enabled: true, isCustom: true, description: desc } }));
    toast.success(`Added DLC ${newNumber}`);
  }, [rows]);

  const removeCustomDLC = useCallback((dlcNumber: string) => {
    setAllDLCs((prev) => prev.filter((d) => d.number !== dlcNumber));
    setRows((prev) => { const next = { ...prev }; delete next[dlcNumber]; return next; });
    toast.success(`Removed DLC ${dlcNumber}`);
  }, []);

  // ---- Row helpers ----
  const updateRow = useCallback((dlcNum: string, patch: Partial<DLCRowState>) => {
    setRows((prev) => ({ ...prev, [dlcNum]: { ...prev[dlcNum], ...patch } }));
  }, []);

  const toggleYaw = useCallback((dlcNum: string, yaw: number) => {
    setRows((prev) => {
      const cur = prev[dlcNum];
      const yaws = cur.yawMisalignments.includes(yaw)
        ? cur.yawMisalignments.filter((y) => y !== yaw)
        : [...cur.yawMisalignments, yaw].sort((a, b) => a - b);
      return { ...prev, [dlcNum]: { ...cur, yawMisalignments: yaws.length > 0 ? yaws : [0] } };
    });
  }, []);

  // ---- Derived totals ----
  const caseCountByDLC = useMemo(() => {
    const counts: Record<string, number> = {};
    allDLCs.forEach((dlc) => { if (rows[dlc.number]) counts[dlc.number] = countCases(rows[dlc.number]); });
    return counts;
  }, [rows, allDLCs]);

  const totalCases = useMemo(() => Object.values(caseCountByDLC).reduce((s, c) => s + c, 0), [caseCountByDLC]);
  const enabledCount = useMemo(() => allDLCs.filter((d) => rows[d.number]?.enabled).length, [rows, allDLCs]);

  const groupSummary = useMemo(() => {
    const summary: Record<DLCGroup, { enabled: number; cases: number }> = {} as any;
    DLC_GROUPS.forEach((g) => {
      const dlcs = allDLCs.filter((d) => d.group === g.key);
      summary[g.key] = {
        enabled: dlcs.filter((d) => rows[d.number]?.enabled).length,
        cases: dlcs.reduce((s, d) => s + (caseCountByDLC[d.number] || 0), 0),
      };
    });
    return summary;
  }, [rows, caseCountByDLC, allDLCs]);

  // ---- Build API payload ----
  const buildPayload = useCallback(() => {
    const dlcCases: DLCCaseSpec[] = allDLCs.filter((d) => rows[d.number]?.enabled).map((d) => {
      const r = rows[d.number];
      return {
        dlc_number: d.number,
        wind_speeds: generateWindSpeeds(r.windSpeedMin, r.windSpeedMax, r.windSpeedStep),
        seeds: r.seeds, yaw_misalignments: r.yawMisalignments,
        wind_condition: r.windCondition, partial_safety_factor: r.partialSafetyFactor,
        analysis_type: r.analysisType, simulation_length: r.simulationLength,
        init_length: r.initLength, description: r.description, is_custom: r.isCustom,
      };
    });
    return { name, turbine_model_id: selectedTurbineId, dlc_cases: dlcCases, turbsim_params: turbSimParams };
  }, [name, selectedTurbineId, rows, turbSimParams, allDLCs]);

  const handleSave = useCallback(async () => {
    if (!projectId) return;
    setSaving(true);
    try {
      const payload = buildPayload();
      if (activeDefinitionId) {
        await apiClient.put(`/projects/${projectId}/dlc-definitions/${activeDefinitionId}`, payload);
        toast.success('DLC definition updated');
      } else {
        const res = await apiClient.post(`/projects/${projectId}/dlc-definitions`, payload);
        setActiveDefinitionId(res.data.id);
        toast.success('DLC definition created');
      }
      const res = await apiClient.get(`/projects/${projectId}/dlc-definitions`);
      setExistingDefinitions(res.data as DLCDefinition[]);
    } catch (err: any) {
      toast.error(err?.response?.data?.detail ?? 'Failed to save');
    } finally { setSaving(false); }
  }, [projectId, activeDefinitionId, buildPayload]);

  const handleGenerateCases = useCallback(async () => {
    if (enabledCount === 0) { toast.error('Enable at least one DLC'); return; }
    await handleSave();
    setShowNextStep(true);
    toast.success(`${totalCases} cases saved — go to Simulate to run them`);
  }, [enabledCount, totalCases, handleSave]);

  const updateTurbSim = useCallback((patch: Partial<TurbSimParams>) => {
    setTurbSimParams((prev) => ({ ...prev, ...patch }));
  }, []);

  const toggleGroup = useCallback((groupKey: DLCGroup) => {
    setExpandedGroups((prev) => ({ ...prev, [groupKey]: !prev[groupKey] }));
  }, []);

  // ---- Render ----
  return (
    <div className="flex h-full gap-6 overflow-hidden">
      {/* ====== Main area ====== */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Top bar */}
        <div className="mb-3 flex flex-wrap items-center gap-3">
          <input type="text" value={name} onChange={(e) => setName(e.target.value)} className="input-field max-w-xs" placeholder="DLC Definition Name" />
          <select value={selectedTurbineId} onChange={(e) => setSelectedTurbineId(e.target.value)} className="input-field max-w-[200px]">
            <option value="">Select Turbine</option>
            {turbineModels.map((m) => (<option key={m.id} value={m.id}>{m.name}</option>))}
          </select>
          <span className="inline-flex items-center gap-1.5 rounded-full bg-accent-500/20 px-3 py-1 text-xs font-semibold text-accent-300 ring-1 ring-inset ring-accent-500/30">
            <Hash size={12} />{totalCases.toLocaleString()} cases
          </span>
          <div className="ml-auto flex gap-2">
            {existingDefinitions.length > 0 && (
              <div className="relative group">
                <button className="btn-secondary text-xs"><FolderOpen size={14} />Load</button>
                <div className="invisible absolute right-0 z-20 mt-1 w-64 rounded-lg border border-slate-600 bg-surface-dark-secondary shadow-xl group-hover:visible">
                  {existingDefinitions.map((def) => (
                    <button key={def.id} onClick={() => loadDefinition(def)} className="flex w-full items-center justify-between px-4 py-2 text-left text-sm text-slate-200 hover:bg-surface-dark-tertiary first:rounded-t-lg last:rounded-b-lg">
                      <span>{def.name}</span><StatusBadge status={def.status} size="sm" />
                    </button>
                  ))}
                </div>
              </div>
            )}
            <button onClick={handleSave} disabled={saving} className="btn-secondary text-xs">
              <Save size={14} />{saving ? 'Saving...' : 'Save'}
            </button>
          </div>
        </div>

        {/* Preset buttons */}
        <div className="mb-3 flex flex-wrap gap-2">
          <span className="flex items-center gap-1.5 text-xs font-medium text-slate-400"><ListFilter size={13} />Presets:</span>
          {PRESETS.map((preset) => (
            <button key={preset.name} onClick={() => applyPreset(preset)} title={preset.description}
              className="inline-flex items-center gap-1.5 rounded-lg border border-slate-600/50 bg-surface-dark-secondary px-3 py-1.5 text-xs font-medium text-slate-300 ring-1 ring-inset ring-transparent transition-all hover:border-accent-500/40 hover:text-accent-300 hover:ring-accent-500/20">
              <preset.icon size={13} />{preset.name}
            </button>
          ))}
        </div>

        {/* DLC Accordion Groups */}
        <div className="flex-1 overflow-auto space-y-2">
          {DLC_GROUPS.map((group) => {
            const isExpanded = expandedGroups[group.key];
            const dlcsInGroup = allDLCs.filter((d) => d.group === group.key);
            const gs = groupSummary[group.key];
            return (
              <div key={group.key} className="rounded-xl border border-slate-700/50 bg-surface-dark-secondary overflow-hidden">
                {/* Group header */}
                <button onClick={() => toggleGroup(group.key)}
                  className="flex w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-surface-dark-tertiary/30">
                  {isExpanded ? <ChevronDown size={16} className="text-slate-400 shrink-0" /> : <ChevronRight size={16} className="text-slate-400 shrink-0" />}
                  <group.icon size={16} className="text-accent-400 shrink-0" />
                  <span className="text-sm font-semibold text-slate-100">{group.label}</span>
                  <span className="text-xs text-slate-500">({group.dlcRange})</span>
                  <div className="ml-auto flex items-center gap-3">
                    {gs.enabled > 0 && (
                      <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/15 px-2 py-0.5 text-[10px] font-semibold text-emerald-300 ring-1 ring-inset ring-emerald-500/25">
                        {gs.enabled} enabled
                      </span>
                    )}
                    {gs.cases > 0 && <span className="text-xs font-mono font-semibold text-accent-300">{gs.cases.toLocaleString()}</span>}
                  </div>
                </button>

                {isExpanded && (
                  <div className="border-t border-slate-700/50">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-slate-700/30 text-slate-500">
                          <th className="w-8 px-3 py-2" />
                          <th className="w-10 px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wider">En</th>
                          <th className="px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wider">DLC</th>
                          <th className="px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wider">Description</th>
                          <th className="px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wider">Wind</th>
                          <th className="px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wider">Type</th>
                          <th className="px-3 py-2 text-center text-[10px] font-semibold uppercase tracking-wider">&gamma;<sub>f</sub></th>
                          <th className="px-3 py-2 text-right text-[10px] font-semibold uppercase tracking-wider">Cases</th>
                          <th className="w-8 px-2 py-2" />
                        </tr>
                      </thead>
                      <tbody>
                        {dlcsInGroup.map((dlc) => {
                          const row = rows[dlc.number];
                          if (!row) return null;
                          return (
                            <DLCRow key={dlc.number} dlc={dlc} row={row} cases={caseCountByDLC[dlc.number] || 0} isFatigue={row.analysisType === 'fatigue'}
                              onToggleEnabled={() => updateRow(dlc.number, { enabled: !row.enabled })}
                              onToggleExpand={() => updateRow(dlc.number, { expanded: !row.expanded })}
                              onUpdateRow={(patch) => updateRow(dlc.number, patch)}
                              onToggleYaw={(yaw) => toggleYaw(dlc.number, yaw)}
                              onRemove={row.isCustom ? () => removeCustomDLC(dlc.number) : undefined}
                            />
                          );
                        })}
                      </tbody>
                    </table>
                    <AddSubDLCButton group={group.key} dlcsInGroup={dlcsInGroup} onAdd={addCustomDLC} />
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* ====== Right sidebar ====== */}
      <div className="w-80 shrink-0 overflow-y-auto rounded-xl border border-slate-700/50 bg-surface-dark-secondary p-5">
        <div className="mb-6">
          <h3 className="mb-4 flex items-center gap-2 text-sm font-semibold text-slate-100"><Settings2 size={16} className="text-accent-400" />TurbSim Parameters</h3>
          <div className="space-y-3">
            <div>
              <label className="label">Turbulence Model</label>
              <select value={turbSimParams.turbulence_model} onChange={(e) => updateTurbSim({ turbulence_model: e.target.value })} className="input-field">
                <option value="IECKAI">IECKAI (Kaimal)</option><option value="IECVKM">IECVKM (von Karman)</option><option value="GP_LLJ">GP_LLJ (Great Plains LLJ)</option>
              </select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="label">IEC Standard</label>
                <select value={turbSimParams.iec_standard} onChange={(e) => updateTurbSim({ iec_standard: e.target.value })} className="input-field">
                  <option value="1-ED3">IEC 61400-1 Ed.3</option><option value="1-ED4">IEC 61400-1 Ed.4</option>
                </select>
              </div>
              <div>
                <label className="label">Turb. Category</label>
                <select value={turbSimParams.iec_turbc} onChange={(e) => updateTurbSim({ iec_turbc: e.target.value })} className="input-field">
                  <option value="A">A (high)</option><option value="B">B (medium)</option><option value="C">C (low)</option>
                </select>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <TurbSimField label="Grid Height" unit="m" value={turbSimParams.grid_height} onChange={(v) => updateTurbSim({ grid_height: v })} />
              <TurbSimField label="Grid Width" unit="m" value={turbSimParams.grid_width} onChange={(v) => updateTurbSim({ grid_width: v })} />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <TurbSimField label="Z Points" value={turbSimParams.num_grid_z} onChange={(v) => updateTurbSim({ num_grid_z: v })} step={1} min={3} />
              <TurbSimField label="Y Points" value={turbSimParams.num_grid_y} onChange={(v) => updateTurbSim({ num_grid_y: v })} step={1} min={3} />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <TurbSimField label="Time Step" unit="s" value={turbSimParams.time_step} onChange={(v) => updateTurbSim({ time_step: v })} step={0.01} min={0.01} />
              <TurbSimField label="Analysis Time" unit="s" value={turbSimParams.analysis_time} onChange={(v) => updateTurbSim({ analysis_time: v })} step={10} min={60} />
            </div>
            <TurbSimField label="Reference Height" unit="m" value={turbSimParams.ref_height} onChange={(v) => updateTurbSim({ ref_height: v })} min={10} />
          </div>
        </div>
        <div className="my-5 border-t border-slate-700" />
        <div className="mb-6">
          <h3 className="mb-3 text-sm font-semibold text-slate-100">Case Breakdown</h3>
          <div className="space-y-1.5 max-h-64 overflow-y-auto">
            {allDLCs.filter((d) => rows[d.number]?.enabled).map((dlc) => (
              <div key={dlc.number} className="flex items-center justify-between rounded-md bg-surface-dark px-3 py-1.5 text-xs">
                <span className="font-mono text-slate-300">DLC {dlc.number}</span>
                <span className="font-semibold text-slate-100">{(caseCountByDLC[dlc.number] || 0).toLocaleString()}</span>
              </div>
            ))}
            {enabledCount === 0 && <p className="py-4 text-center text-xs text-slate-500">No DLCs enabled</p>}
          </div>
        </div>
        <div className="my-5 border-t border-slate-700" />
        <div className="space-y-3">
          <div className="flex items-center justify-between text-sm"><span className="text-slate-400">Enabled DLCs</span><span className="font-semibold text-slate-100">{enabledCount}</span></div>
          <div className="flex items-center justify-between text-sm"><span className="text-slate-400">Total Cases</span><span className="font-semibold text-accent-300">{totalCases.toLocaleString()}</span></div>
          <button onClick={handleGenerateCases} disabled={enabledCount === 0 || saving} className="btn-primary w-full"><Zap size={16} />Generate Cases</button>
          {showNextStep && activeDefinitionId && (
            <div className="rounded-lg border border-emerald-600/40 bg-emerald-950/20 p-3 space-y-2">
              <p className="text-xs text-emerald-300 font-medium">
                ✓ {totalCases.toLocaleString()} cases saved to "{name}"
              </p>
              <p className="text-[10px] text-emerald-400/70">
                Next: Create a simulation from this DLC definition to start running cases.
              </p>
              <button
                onClick={() => navigate(`/projects/${projectId}/simulate`)}
                className="w-full flex items-center justify-center gap-2 rounded-lg bg-emerald-600 px-3 py-2 text-sm font-medium text-white hover:bg-emerald-700 transition-colors"
              >
                <Play size={14} />Go to Simulate
                <ArrowRight size={14} />
              </button>
            </div>
          )}
          <button onClick={() => {
            const init: Record<string, DLCRowState> = {};
            DLC_CATALOG.forEach((d) => { init[d.number] = defaultRowState(d); });
            setAllDLCs([...DLC_CATALOG]); setRows(init); setTurbSimParams(defaultTurbSimParams()); setActiveDefinitionId(null); setShowNextStep(false); toast('Reset to defaults');
          }} className="btn-secondary w-full text-xs"><RotateCcw size={14} />Reset All</button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function TurbSimField({ label, unit, value, onChange, step = 1, min = 0 }: {
  label: string; unit?: string; value: number; onChange: (v: number) => void; step?: number; min?: number;
}) {
  return (
    <div>
      <label className="label">{label}{unit && <span className="ml-1 text-slate-500">[{unit}]</span>}</label>
      <input type="number" value={value} onChange={(e) => { const v = parseFloat(e.target.value); if (!isNaN(v) && v >= min) onChange(v); }}
        step={step} min={min} className="input-field font-mono text-xs" />
    </div>
  );
}

const DEFAULT_YAW_OPTIONS = [-180, -30, -20, -8, -4, 0, 4, 8, 20, 30, 180];

interface DLCRowProps {
  dlc: DLCMeta; row: DLCRowState; cases: number; isFatigue: boolean;
  onToggleEnabled: () => void; onToggleExpand: () => void;
  onUpdateRow: (patch: Partial<DLCRowState>) => void; onToggleYaw: (yaw: number) => void;
  onRemove?: () => void;
}

function DLCRow({ dlc, row, cases, isFatigue, onToggleEnabled, onToggleExpand, onUpdateRow, onToggleYaw, onRemove }: DLCRowProps) {
  return (
    <>
      <tr className={clsx('border-b border-slate-700/30 transition-colors',
        row.enabled ? 'bg-surface-dark hover:bg-surface-dark-tertiary/30' : 'bg-surface-dark-secondary/50 opacity-60 hover:opacity-80',
        row.enabled && isFatigue && 'border-l-2 border-l-emerald-500/50',
        row.enabled && !isFatigue && 'border-l-2 border-l-red-500/50')}>
        <td className="px-3 py-2.5">{row.enabled && (
          <button onClick={onToggleExpand} className="text-slate-400 hover:text-slate-200 transition-colors">
            {row.expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          </button>
        )}</td>
        <td className="px-3 py-2.5">
          <input type="checkbox" checked={row.enabled} onChange={onToggleEnabled}
            className="h-4 w-4 rounded border-slate-500 bg-surface-dark text-accent-500 focus:ring-accent-500 focus:ring-offset-0" />
        </td>
        <td className="px-3 py-2.5">
          <span className="font-mono font-semibold text-slate-100">{dlc.number}</span>
          {row.isCustom && <span className="ml-1.5 rounded bg-violet-500/15 px-1.5 py-0.5 text-[9px] font-medium text-violet-300 ring-1 ring-inset ring-violet-500/25">CUSTOM</span>}
        </td>
        <td className="px-3 py-2.5 text-slate-300 text-xs max-w-[180px] truncate" title={row.description || dlc.description}>{row.description || dlc.description}</td>
        <td className="px-3 py-2.5">
          <span className="inline-flex items-center gap-1 rounded-md bg-blue-500/15 px-2 py-0.5 text-[10px] font-medium text-blue-300 ring-1 ring-inset ring-blue-500/25">
            <Wind size={10} />{row.windCondition || dlc.windModel}
          </span>
        </td>
        <td className="px-3 py-2.5">
          <span className={clsx('inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-[10px] font-medium ring-1 ring-inset',
            isFatigue ? 'bg-emerald-500/15 text-emerald-300 ring-emerald-500/25' : 'bg-red-500/15 text-red-300 ring-red-500/25')}>
            {isFatigue ? <RotateCcw size={10} /> : <Shield size={10} />}{row.analysisType.charAt(0).toUpperCase()}
          </span>
        </td>
        <td className="px-3 py-2.5 text-center"><span className="font-mono text-xs text-slate-300">{row.partialSafetyFactor.toFixed(2)}</span></td>
        <td className="px-3 py-2.5 text-right font-mono text-xs text-slate-300">{row.enabled ? cases.toLocaleString() : '\u2013'}</td>
        <td className="px-2 py-2.5">{onRemove && (
          <button onClick={onRemove} className="text-slate-500 hover:text-red-400 transition-colors" title="Remove custom DLC"><X size={14} /></button>
        )}</td>
      </tr>

      {row.enabled && row.expanded && (
        <tr className="border-b border-slate-700/30 bg-surface-dark/80">
          <td colSpan={9} className="px-6 py-4">
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2 xl:grid-cols-3">
              {/* Wind speed range */}
              <div>
                <p className="mb-2 text-[10px] font-semibold text-slate-400 uppercase tracking-wider">Wind Speed Range</p>
                <div className="flex items-center gap-2">
                  <div>
                    <label className="text-[10px] text-slate-500">V<sub>in</sub> (m/s)</label>
                    <input type="number" value={row.windSpeedMin} onChange={(e) => { const v = parseFloat(e.target.value); if (!isNaN(v) && v >= 0) onUpdateRow({ windSpeedMin: v }); }}
                      step={1} min={0} className="input-field w-16 text-xs font-mono" />
                  </div>
                  <span className="mt-4 text-slate-500 text-xs">to</span>
                  <div>
                    <label className="text-[10px] text-slate-500">V<sub>out</sub> (m/s)</label>
                    <input type="number" value={row.windSpeedMax} onChange={(e) => { const v = parseFloat(e.target.value); if (!isNaN(v) && v > row.windSpeedMin) onUpdateRow({ windSpeedMax: v }); }}
                      step={1} min={row.windSpeedMin + 1} className="input-field w-16 text-xs font-mono" />
                  </div>
                  <div>
                    <label className="text-[10px] text-slate-500">Step</label>
                    <input type="number" value={row.windSpeedStep} onChange={(e) => { const v = parseFloat(e.target.value); if (!isNaN(v) && v > 0) onUpdateRow({ windSpeedStep: v }); }}
                      step={0.5} min={0.5} className="input-field w-16 text-xs font-mono" />
                  </div>
                </div>
                <p className="mt-1 text-[10px] text-slate-500">
                  {generateWindSpeeds(row.windSpeedMin, row.windSpeedMax, row.windSpeedStep).length} speeds: {generateWindSpeeds(row.windSpeedMin, row.windSpeedMax, row.windSpeedStep).map((v) => v.toFixed(0)).join(', ')}
                </p>
              </div>

              {/* Seeds + Wind Condition */}
              <div className="space-y-3">
                <div>
                  <p className="mb-2 text-[10px] font-semibold text-slate-400 uppercase tracking-wider">Seeds</p>
                  <div className="flex items-center gap-2">
                    <button onClick={() => onUpdateRow({ seeds: Math.max(1, row.seeds - 1) })}
                      className="flex h-7 w-7 items-center justify-center rounded-md border border-slate-600 bg-surface-dark-tertiary text-slate-300 hover:bg-slate-600 transition-colors text-xs">-</button>
                    <span className="w-6 text-center font-mono font-semibold text-slate-100 text-sm">{row.seeds}</span>
                    <button onClick={() => onUpdateRow({ seeds: Math.min(30, row.seeds + 1) })}
                      className="flex h-7 w-7 items-center justify-center rounded-md border border-slate-600 bg-surface-dark-tertiary text-slate-300 hover:bg-slate-600 transition-colors text-xs">+</button>
                  </div>
                </div>
                <div>
                  <p className="mb-1 text-[10px] font-semibold text-slate-400 uppercase tracking-wider">Wind Condition</p>
                  <select value={row.windCondition} onChange={(e) => onUpdateRow({ windCondition: e.target.value })} className="input-field text-xs w-full">
                    {WIND_CONDITIONS.map((wc) => (<option key={wc.value} value={wc.value}>{wc.label}</option>))}
                  </select>
                </div>
              </div>

              {/* Simulation parameters */}
              <div className="space-y-3">
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <p className="mb-1 text-[10px] font-semibold text-slate-400 uppercase tracking-wider">Sim Length (s)</p>
                    <input type="number" value={row.simulationLength} onChange={(e) => { const v = parseFloat(e.target.value); if (!isNaN(v) && v > 0) onUpdateRow({ simulationLength: v }); }}
                      step={10} min={10} className="input-field w-full text-xs font-mono" />
                  </div>
                  <div>
                    <p className="mb-1 text-[10px] font-semibold text-slate-400 uppercase tracking-wider">Init Length (s)</p>
                    <input type="number" value={row.initLength} onChange={(e) => { const v = parseFloat(e.target.value); if (!isNaN(v) && v >= 0) onUpdateRow({ initLength: v }); }}
                      step={10} min={0} className="input-field w-full text-xs font-mono" />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <p className="mb-1 text-[10px] font-semibold text-slate-400 uppercase tracking-wider">Safety Factor</p>
                    <input type="number" value={row.partialSafetyFactor} onChange={(e) => { const v = parseFloat(e.target.value); if (!isNaN(v) && v >= 0) onUpdateRow({ partialSafetyFactor: v }); }}
                      step={0.05} min={0} className="input-field w-full text-xs font-mono" />
                  </div>
                  <div>
                    <p className="mb-1 text-[10px] font-semibold text-slate-400 uppercase tracking-wider">Analysis Type</p>
                    <select value={row.analysisType} onChange={(e) => onUpdateRow({ analysisType: e.target.value as 'fatigue' | 'ultimate' })} className="input-field text-xs w-full">
                      <option value="ultimate">Ultimate</option><option value="fatigue">Fatigue</option>
                    </select>
                  </div>
                </div>
              </div>

              {/* Yaw misalignment */}
              <div className="col-span-full">
                <p className="mb-2 text-[10px] font-semibold text-slate-400 uppercase tracking-wider">Yaw Misalignment</p>
                <div className="flex flex-wrap gap-1.5">
                  {DEFAULT_YAW_OPTIONS.map((yaw) => (
                    <button key={yaw} onClick={() => onToggleYaw(yaw)}
                      className={clsx('rounded-md px-2 py-1 text-[10px] font-mono font-medium transition-colors ring-1 ring-inset',
                        row.yawMisalignments.includes(yaw) ? 'bg-accent-500/20 text-accent-300 ring-accent-500/40' : 'bg-surface-dark-tertiary text-slate-400 ring-slate-600 hover:ring-slate-500')}>
                      {yaw > 0 ? `+${yaw}` : yaw}&deg;
                    </button>
                  ))}
                </div>
              </div>

              {/* Description */}
              <div className="col-span-full">
                <p className="mb-1 text-[10px] font-semibold text-slate-400 uppercase tracking-wider">Description / Notes</p>
                <input type="text" value={row.description} onChange={(e) => onUpdateRow({ description: e.target.value })}
                  placeholder="e.g., NTM_ControllerOverspeed, RepTurbEQP..." className="input-field w-full text-xs" />
              </div>

              {/* Case preview */}
              <div className="col-span-full">
                <p className="text-[10px] text-slate-500">
                  Preview: {generateWindSpeeds(row.windSpeedMin, row.windSpeedMax, row.windSpeedStep).length} wind speeds &times; {row.seeds} seeds &times; {row.yawMisalignments.length} yaw = <span className="font-semibold text-accent-300">{cases.toLocaleString()} cases</span> &bull; Sim: {row.simulationLength}s + {row.initLength}s init
                </p>
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

// ---------------------------------------------------------------------------
// Add Sub-DLC Button
// ---------------------------------------------------------------------------

function AddSubDLCButton({ group, dlcsInGroup, onAdd }: {
  group: DLCGroup; dlcsInGroup: DLCMeta[];
  onAdd: (group: DLCGroup, baseDlcNumber: string, suffix: string, desc: string) => void;
}) {
  const [isAdding, setIsAdding] = useState(false);
  const [baseDlc, setBaseDlc] = useState('');
  const [suffix, setSuffix] = useState('');
  const [desc, setDesc] = useState('');
  const catalogInGroup = dlcsInGroup.filter((d) => DLC_CATALOG.some((c) => c.number === d.number));

  if (!isAdding) {
    return (
      <div className="px-4 py-2 border-t border-slate-700/30">
        <button onClick={() => { setIsAdding(true); if (catalogInGroup.length > 0) setBaseDlc(catalogInGroup[0].number); }}
          className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-accent-300 transition-colors">
          <Plus size={13} />Add sub-DLC variant
        </button>
      </div>
    );
  }

  return (
    <div className="px-4 py-3 border-t border-slate-700/30 bg-surface-dark/50">
      <div className="flex flex-wrap items-end gap-3">
        <div>
          <label className="text-[10px] text-slate-500">Base DLC</label>
          <select value={baseDlc} onChange={(e) => setBaseDlc(e.target.value)} className="input-field text-xs w-24">
            {catalogInGroup.map((d) => (<option key={d.number} value={d.number}>{d.number}</option>))}
          </select>
        </div>
        <div>
          <label className="text-[10px] text-slate-500">Suffix</label>
          <input type="text" value={suffix} onChange={(e) => setSuffix(e.target.value.replace(/[^a-zA-Z]/g, '').slice(0, 3))}
            placeholder="c, g, y..." className="input-field text-xs w-16 font-mono" maxLength={3} />
        </div>
        <div className="flex-1 min-w-[150px]">
          <label className="text-[10px] text-slate-500">Description</label>
          <input type="text" value={desc} onChange={(e) => setDesc(e.target.value)}
            placeholder="e.g., NTM_GridDrop" className="input-field text-xs w-full" />
        </div>
        <button onClick={() => {
          if (baseDlc && suffix) { onAdd(group, baseDlc, suffix, desc); setSuffix(''); setDesc(''); setIsAdding(false); }
          else toast.error('Base DLC and suffix are required');
        }} className="btn-primary text-xs h-8"><Plus size={12} />Add</button>
        <button onClick={() => { setIsAdding(false); setSuffix(''); setDesc(''); }} className="btn-secondary text-xs h-8">Cancel</button>
      </div>
      {baseDlc && suffix && <p className="mt-1.5 text-[10px] text-slate-500">Will create: <span className="font-mono font-semibold text-slate-300">DLC {baseDlc}{suffix}</span></p>}
    </div>
  );
}
