import { useEffect, useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { useProjectStore } from '@/stores/projectStore';
import { templatesApi } from '@/api/client';
import type { ProjectCreate, WindClass, TurbulenceClass, ReferenceTemplate, PlatformType } from '@/types';
import {
  Plus,
  Wind,
  Calendar,
  Ruler,
  Zap,
  X,
  Loader2,
  FolderOpen,
  FileText,
  Waves,
  ArrowLeft,
} from 'lucide-react';
import clsx from 'clsx';

const WIND_CLASSES: WindClass[] = ['I', 'II', 'III', 'S'];
const TURBULENCE_CLASSES: TurbulenceClass[] = ['A', 'B', 'C'];
const PLATFORM_TYPES: { value: PlatformType; label: string }[] = [
  { value: 'onshore', label: 'Onshore' },
  { value: 'monopile', label: 'Monopile' },
  { value: 'jacket', label: 'Jacket' },
  { value: 'spar', label: 'Spar buoy' },
  { value: 'semi_submersible', label: 'Semi-submersible' },
  { value: 'tlp', label: 'TLP' },
];

const defaultFormData: ProjectCreate = {
  name: '',
  description: '',
  wind_class: 'II',
  turbulence_class: 'B',
  rated_power: 5000,
  rotor_diameter: 126,
  hub_height: 90,
  cut_in_speed: 3,
  rated_speed: 11.4,
  cut_out_speed: 25,
  dt: 0.0125,
  t_max: 660,
  platform_type: 'onshore',
};

type ModalStep = 'choose' | 'template' | 'scratch';

export default function Dashboard() {
  const projects = useProjectStore((s) => s.projects);
  const isLoading = useProjectStore((s) => s.isLoading);
  const fetchProjects = useProjectStore((s) => s.fetchProjects);
  const createProject = useProjectStore((s) => s.createProject);
  const createProjectFromTemplate = useProjectStore((s) => s.createProjectFromTemplate);
  const navigate = useNavigate();

  const [showModal, setShowModal] = useState(false);
  const [modalStep, setModalStep] = useState<ModalStep>('choose');
  const [formData, setFormData] = useState<ProjectCreate>(defaultFormData);
  const [isCreating, setIsCreating] = useState(false);

  // Template state
  const [templates, setTemplates] = useState<ReferenceTemplate[]>([]);
  const [selectedTemplate, setSelectedTemplate] = useState<string | null>(null);
  const [templateName, setTemplateName] = useState('');
  const [templateDesc, setTemplateDesc] = useState('');
  const [templatePlatform, setTemplatePlatform] = useState<string | null>(null);
  const [loadingTemplates, setLoadingTemplates] = useState(false);

  useEffect(() => {
    fetchProjects();
  }, [fetchProjects]);

  const openModal = () => {
    setShowModal(true);
    setModalStep('choose');
    setFormData(defaultFormData);
    setSelectedTemplate(null);
    setTemplateName('');
    setTemplateDesc('');
    setTemplatePlatform(null);
  };

  const closeModal = () => {
    setShowModal(false);
  };

  const handleChooseTemplate = async () => {
    setModalStep('template');
    if (templates.length === 0) {
      setLoadingTemplates(true);
      try {
        const list = await templatesApi.list();
        setTemplates(list);
      } catch {
        // Handled silently
      } finally {
        setLoadingTemplates(false);
      }
    }
  };

  const handleCreateFromTemplate = async (e: FormEvent) => {
    e.preventDefault();
    if (!selectedTemplate || !templateName.trim()) return;

    setIsCreating(true);
    try {
      const project = await createProjectFromTemplate({
        template_id: selectedTemplate,
        name: templateName.trim(),
        description: templateDesc.trim() || undefined,
        platform_type: templatePlatform || undefined,
      });
      closeModal();
      navigate(`/projects/${project.id}/tower`);
    } catch {
      // Error handled in store
    } finally {
      setIsCreating(false);
    }
  };

  const handleCreateProject = async (e: FormEvent) => {
    e.preventDefault();
    if (!formData.name.trim()) return;

    setIsCreating(true);
    try {
      const project = await createProject(formData);
      closeModal();
      navigate(`/projects/${project.id}/tower`);
    } catch {
      // Error handled in store
    } finally {
      setIsCreating(false);
    }
  };

  const updateForm = <K extends keyof ProjectCreate>(
    key: K,
    value: ProjectCreate[K],
  ) => {
    setFormData((prev) => ({ ...prev, [key]: value }));
  };

  const selectedTemplateData = templates.find((t) => t.id === selectedTemplate);

  return (
    <div className="p-8">
      {/* Header */}
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Your Projects</h1>
          <p className="mt-1 text-sm text-slate-400">
            Manage and design your wind turbine configurations
          </p>
        </div>
        <button onClick={openModal} className="btn-primary">
          <Plus className="h-4 w-4" />
          New Project
        </button>
      </div>

      {/* Loading state */}
      {isLoading && projects.length === 0 && (
        <div className="flex items-center justify-center py-24">
          <Loader2 className="h-8 w-8 animate-spin text-accent-500" />
        </div>
      )}

      {/* Empty state */}
      {!isLoading && projects.length === 0 && (
        <div className="flex flex-col items-center justify-center rounded-2xl border-2 border-dashed border-slate-600 py-24">
          <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-surface-dark-tertiary">
            <FolderOpen className="h-8 w-8 text-slate-400" />
          </div>
          <h3 className="text-lg font-semibold text-slate-200">
            No projects yet
          </h3>
          <p className="mt-1 text-sm text-slate-400 max-w-sm text-center">
            Create your first wind turbine project to start designing towers,
            blades, and controllers.
          </p>
          <button
            onClick={openModal}
            className="btn-primary mt-6"
          >
            <Plus className="h-4 w-4" />
            Create your first project
          </button>
        </div>
      )}

      {/* Project grid */}
      {projects.length > 0 && (
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {projects.map((project) => (
            <button
              key={project.id}
              onClick={() => navigate(`/projects/${project.id}/tower`)}
              className="group rounded-xl border border-slate-700 bg-surface-dark-secondary p-6 text-left shadow-sm transition-all duration-200 hover:border-accent-500/50 hover:shadow-md hover:shadow-accent-500/5"
            >
              {/* Project header */}
              <div className="mb-4 flex items-start justify-between">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-accent-500/10 transition-colors group-hover:bg-accent-500/20">
                  <Wind className="h-5 w-5 text-accent-400" />
                </div>
                <div className="flex items-center gap-2">
                  {project.platform_type && project.platform_type !== 'onshore' && (
                    <span className="inline-flex items-center gap-1 rounded-full bg-sky-500/10 px-2 py-0.5 text-xs font-medium text-sky-400">
                      <Waves className="h-3 w-3" />
                      {project.platform_type}
                    </span>
                  )}
                  <span
                    className={clsx(
                      'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium',
                      project.status === 'active'
                        ? 'bg-success-500/10 text-success-400'
                        : project.status === 'completed'
                          ? 'bg-accent-500/10 text-accent-400'
                          : 'bg-slate-700 text-slate-300',
                    )}
                  >
                    {project.status || 'Draft'}
                  </span>
                </div>
              </div>

              {/* Name & description */}
              <h3 className="text-base font-semibold text-slate-100 group-hover:text-accent-400 transition-colors">
                {project.name}
              </h3>
              {project.description && (
                <p className="mt-1 text-sm text-slate-400 line-clamp-2">
                  {project.description}
                </p>
              )}

              {/* Specs */}
              <div className="mt-4 grid grid-cols-2 gap-3">
                <div className="flex items-center gap-1.5 text-xs text-slate-400">
                  <Wind className="h-3.5 w-3.5 text-slate-500" />
                  <span>
                    Class {project.wind_class}
                    {project.turbulence_class}
                  </span>
                </div>
                <div className="flex items-center gap-1.5 text-xs text-slate-400">
                  <Ruler className="h-3.5 w-3.5 text-slate-500" />
                  <span>{project.rotor_diameter}m rotor</span>
                </div>
                <div className="flex items-center gap-1.5 text-xs text-slate-400">
                  <Zap className="h-3.5 w-3.5 text-slate-500" />
                  <span>{project.rated_power} kW</span>
                </div>
                <div className="flex items-center gap-1.5 text-xs text-slate-400">
                  <Ruler className="h-3.5 w-3.5 text-slate-500" />
                  <span>{project.hub_height}m hub</span>
                </div>
              </div>

              {/* Date */}
              <div className="mt-4 flex items-center gap-1.5 text-xs text-slate-500 border-t border-slate-700 pt-3">
                <Calendar className="h-3.5 w-3.5" />
                <span>
                  Created{' '}
                  {new Date(project.created_at).toLocaleDateString('en-US', {
                    month: 'short',
                    day: 'numeric',
                    year: 'numeric',
                  })}
                </span>
              </div>
            </button>
          ))}
        </div>
      )}

      {/* New Project Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          {/* Backdrop */}
          <div
            className="absolute inset-0 bg-black/50 backdrop-blur-sm"
            onClick={closeModal}
          />

          {/* Modal */}
          <div className="relative z-10 w-full max-w-2xl max-h-[90vh] overflow-y-auto rounded-2xl border border-slate-700/50 bg-surface-dark-secondary p-8 shadow-2xl mx-4">
            {/* Close button */}
            <button
              onClick={closeModal}
              className="absolute right-4 top-4 flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 hover:bg-slate-700 hover:text-slate-200 transition-colors"
            >
              <X className="h-5 w-5" />
            </button>

            {/* Step: Choose */}
            {modalStep === 'choose' && (
              <div>
                <h2 className="text-xl font-bold text-white mb-1">
                  Create New Project
                </h2>
                <p className="text-sm text-slate-400 mb-6">
                  Choose how to start your wind turbine project
                </p>

                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  <button
                    onClick={handleChooseTemplate}
                    className="group flex flex-col items-center gap-3 rounded-xl border border-slate-700 bg-surface-dark p-6 text-center transition-all hover:border-accent-500/50 hover:bg-surface-dark-tertiary"
                  >
                    <div className="flex h-14 w-14 items-center justify-center rounded-xl bg-accent-500/10 group-hover:bg-accent-500/20 transition-colors">
                      <FileText className="h-7 w-7 text-accent-400" />
                    </div>
                    <h3 className="text-base font-semibold text-slate-100">
                      Start from Template
                    </h3>
                    <p className="text-xs text-slate-400">
                      Use a pre-configured reference turbine (NREL 5MW, DTU
                      10MW, IEA 15MW) with all components populated
                    </p>
                  </button>

                  <button
                    onClick={() => setModalStep('scratch')}
                    className="group flex flex-col items-center gap-3 rounded-xl border border-slate-700 bg-surface-dark p-6 text-center transition-all hover:border-accent-500/50 hover:bg-surface-dark-tertiary"
                  >
                    <div className="flex h-14 w-14 items-center justify-center rounded-xl bg-slate-700/50 group-hover:bg-slate-700 transition-colors">
                      <Plus className="h-7 w-7 text-slate-300" />
                    </div>
                    <h3 className="text-base font-semibold text-slate-100">
                      Start from Scratch
                    </h3>
                    <p className="text-xs text-slate-400">
                      Define your own turbine parameters manually
                    </p>
                  </button>
                </div>
              </div>
            )}

            {/* Step: Template Selection */}
            {modalStep === 'template' && (
              <div>
                <button
                  onClick={() => setModalStep('choose')}
                  className="mb-4 flex items-center gap-1.5 text-sm text-slate-400 hover:text-slate-200 transition-colors"
                >
                  <ArrowLeft className="h-4 w-4" />
                  Back
                </button>

                <h2 className="text-xl font-bold text-white mb-1">
                  Select Reference Turbine
                </h2>
                <p className="text-sm text-slate-400 mb-6">
                  Choose a reference turbine to pre-populate all components
                </p>

                {loadingTemplates ? (
                  <div className="flex items-center justify-center py-12">
                    <Loader2 className="h-6 w-6 animate-spin text-accent-500" />
                  </div>
                ) : (
                  <form onSubmit={handleCreateFromTemplate} className="space-y-6">
                    {/* Template cards */}
                    <div className="grid grid-cols-1 gap-3">
                      {templates.map((tmpl) => (
                        <button
                          key={tmpl.id}
                          type="button"
                          onClick={() => {
                            setSelectedTemplate(tmpl.id);
                            if (!templateName) {
                              setTemplateName(`My ${tmpl.name}`);
                            }
                            if (tmpl.is_offshore) {
                              setTemplatePlatform(tmpl.platform_type);
                            }
                          }}
                          className={clsx(
                            'flex items-start gap-4 rounded-xl border p-4 text-left transition-all',
                            selectedTemplate === tmpl.id
                              ? 'border-accent-500 bg-accent-500/5 ring-1 ring-accent-500/30'
                              : 'border-slate-700 bg-surface-dark hover:border-slate-600',
                          )}
                        >
                          <div
                            className={clsx(
                              'mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-lg transition-colors',
                              selectedTemplate === tmpl.id
                                ? 'bg-accent-500/20'
                                : 'bg-surface-dark-tertiary',
                            )}
                          >
                            <Wind
                              className={clsx(
                                'h-5 w-5',
                                selectedTemplate === tmpl.id
                                  ? 'text-accent-400'
                                  : 'text-slate-400',
                              )}
                            />
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2">
                              <h4 className="text-sm font-semibold text-slate-100">
                                {tmpl.name}
                              </h4>
                              {tmpl.is_offshore && (
                                <span className="inline-flex items-center gap-1 rounded-full bg-sky-500/10 px-2 py-0.5 text-xs font-medium text-sky-400">
                                  <Waves className="h-3 w-3" />
                                  Offshore
                                </span>
                              )}
                            </div>
                            <p className="mt-0.5 text-xs text-slate-400">
                              {tmpl.description}
                            </p>
                            <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">
                              <span>{tmpl.rated_power_kw} kW</span>
                              <span>{tmpl.rotor_diameter}m rotor</span>
                              <span>{tmpl.hub_height}m hub</span>
                              <span>Class {tmpl.wind_class}{tmpl.turbulence_class}</span>
                            </div>
                          </div>
                          <div
                            className={clsx(
                              'mt-1 h-5 w-5 shrink-0 rounded-full border-2 transition-colors',
                              selectedTemplate === tmpl.id
                                ? 'border-accent-500 bg-accent-500'
                                : 'border-slate-600',
                            )}
                          >
                            {selectedTemplate === tmpl.id && (
                              <svg className="h-full w-full text-white" viewBox="0 0 20 20" fill="currentColor">
                                <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                              </svg>
                            )}
                          </div>
                        </button>
                      ))}
                    </div>

                    {/* Project name & description for template */}
                    {selectedTemplate && (
                      <div className="space-y-4 border-t border-slate-700 pt-4">
                        <div>
                          <label htmlFor="tmpl-name" className="label">
                            Project name
                          </label>
                          <input
                            id="tmpl-name"
                            type="text"
                            value={templateName}
                            onChange={(e) => setTemplateName(e.target.value)}
                            className="input-field"
                            placeholder="e.g., My NREL 5MW Project"
                            required
                            autoFocus
                          />
                        </div>
                        <div>
                          <label htmlFor="tmpl-desc" className="label">
                            Description{' '}
                            <span className="text-slate-500 font-normal">
                              (optional)
                            </span>
                          </label>
                          <textarea
                            id="tmpl-desc"
                            value={templateDesc}
                            onChange={(e) => setTemplateDesc(e.target.value)}
                            className="input-field resize-none"
                            rows={2}
                            placeholder="Brief project description..."
                          />
                        </div>

                        {/* Platform type for offshore templates */}
                        {selectedTemplateData?.is_offshore && (
                          <div>
                            <label htmlFor="tmpl-platform" className="label">
                              Platform type
                            </label>
                            <select
                              id="tmpl-platform"
                              value={templatePlatform || selectedTemplateData.platform_type}
                              onChange={(e) => setTemplatePlatform(e.target.value)}
                              className="input-field"
                            >
                              {PLATFORM_TYPES.filter((p) => p.value !== 'onshore').map((p) => (
                                <option key={p.value} value={p.value}>
                                  {p.label}
                                </option>
                              ))}
                            </select>
                          </div>
                        )}
                      </div>
                    )}

                    {/* Actions */}
                    <div className="flex items-center justify-end gap-3 pt-2 border-t border-slate-700">
                      <button
                        type="button"
                        onClick={closeModal}
                        className="btn-secondary"
                      >
                        Cancel
                      </button>
                      <button
                        type="submit"
                        disabled={isCreating || !selectedTemplate || !templateName.trim()}
                        className="btn-primary"
                      >
                        {isCreating ? (
                          <>
                            <Loader2 className="h-4 w-4 animate-spin" />
                            Creating...
                          </>
                        ) : (
                          <>
                            <Plus className="h-4 w-4" />
                            Create from Template
                          </>
                        )}
                      </button>
                    </div>
                  </form>
                )}
              </div>
            )}

            {/* Step: Manual / Scratch */}
            {modalStep === 'scratch' && (
              <div>
                <button
                  onClick={() => setModalStep('choose')}
                  className="mb-4 flex items-center gap-1.5 text-sm text-slate-400 hover:text-slate-200 transition-colors"
                >
                  <ArrowLeft className="h-4 w-4" />
                  Back
                </button>

                <h2 className="text-xl font-bold text-white mb-1">
                  Create New Project
                </h2>
                <p className="text-sm text-slate-400 mb-6">
                  Define your wind turbine project parameters
                </p>

                <form onSubmit={handleCreateProject} className="space-y-6">
                  {/* Basic Info */}
                  <div className="space-y-4">
                    <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-wider">
                      General
                    </h3>

                    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                      <div className="sm:col-span-2">
                        <label htmlFor="proj-name" className="label">
                          Project name
                        </label>
                        <input
                          id="proj-name"
                          type="text"
                          value={formData.name}
                          onChange={(e) => updateForm('name', e.target.value)}
                          className="input-field"
                          placeholder="e.g., NREL 5MW Reference"
                          required
                          autoFocus
                        />
                      </div>

                      <div className="sm:col-span-2">
                        <label htmlFor="proj-desc" className="label">
                          Description{' '}
                          <span className="text-slate-500 font-normal">
                            (optional)
                          </span>
                        </label>
                        <textarea
                          id="proj-desc"
                          value={formData.description || ''}
                          onChange={(e) =>
                            updateForm('description', e.target.value)
                          }
                          className="input-field resize-none"
                          rows={2}
                          placeholder="Brief project description..."
                        />
                      </div>

                      <div>
                        <label htmlFor="wind-class" className="label">
                          IEC Wind Class
                        </label>
                        <select
                          id="wind-class"
                          value={formData.wind_class}
                          onChange={(e) =>
                            updateForm('wind_class', e.target.value as WindClass)
                          }
                          className="input-field"
                        >
                          {WIND_CLASSES.map((wc) => (
                            <option key={wc} value={wc}>
                              Class {wc}
                            </option>
                          ))}
                        </select>
                      </div>

                      <div>
                        <label htmlFor="turb-class" className="label">
                          Turbulence Class
                        </label>
                        <select
                          id="turb-class"
                          value={formData.turbulence_class}
                          onChange={(e) =>
                            updateForm(
                              'turbulence_class',
                              e.target.value as TurbulenceClass,
                            )
                          }
                          className="input-field"
                        >
                          {TURBULENCE_CLASSES.map((tc) => (
                            <option key={tc} value={tc}>
                              {tc}
                            </option>
                          ))}
                        </select>
                      </div>
                    </div>
                  </div>

                  {/* Platform Type */}
                  <div className="space-y-4">
                    <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-wider">
                      Platform
                    </h3>
                    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                      <div>
                        <label htmlFor="platform-type" className="label">
                          Platform type
                        </label>
                        <select
                          id="platform-type"
                          value={formData.platform_type || 'onshore'}
                          onChange={(e) =>
                            updateForm('platform_type', e.target.value as PlatformType)
                          }
                          className="input-field"
                        >
                          {PLATFORM_TYPES.map((p) => (
                            <option key={p.value} value={p.value}>
                              {p.label}
                            </option>
                          ))}
                        </select>
                      </div>

                      {formData.platform_type && formData.platform_type !== 'onshore' && (
                        <div>
                          <label htmlFor="water-depth" className="label">
                            Water depth (m)
                          </label>
                          <input
                            id="water-depth"
                            type="number"
                            value={formData.water_depth || ''}
                            onChange={(e) =>
                              updateForm('water_depth', Number(e.target.value))
                            }
                            className="input-field"
                            min={0}
                            step={1}
                            placeholder="e.g., 30"
                          />
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Turbine parameters */}
                  <div className="space-y-4">
                    <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-wider">
                      Turbine Parameters
                    </h3>

                    <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                      <div>
                        <label htmlFor="rated-power" className="label">
                          Rated power (kW)
                        </label>
                        <input
                          id="rated-power"
                          type="number"
                          value={formData.rated_power}
                          onChange={(e) =>
                            updateForm('rated_power', Number(e.target.value))
                          }
                          className="input-field"
                          min={0}
                          step={100}
                          required
                        />
                      </div>

                      <div>
                        <label htmlFor="rotor-diam" className="label">
                          Rotor diameter (m)
                        </label>
                        <input
                          id="rotor-diam"
                          type="number"
                          value={formData.rotor_diameter}
                          onChange={(e) =>
                            updateForm('rotor_diameter', Number(e.target.value))
                          }
                          className="input-field"
                          min={0}
                          step={1}
                          required
                        />
                      </div>

                      <div>
                        <label htmlFor="hub-height" className="label">
                          Hub height (m)
                        </label>
                        <input
                          id="hub-height"
                          type="number"
                          value={formData.hub_height}
                          onChange={(e) =>
                            updateForm('hub_height', Number(e.target.value))
                          }
                          className="input-field"
                          min={0}
                          step={1}
                          required
                        />
                      </div>
                    </div>
                  </div>

                  {/* Wind speed parameters */}
                  <div className="space-y-4">
                    <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-wider">
                      Operating Conditions
                    </h3>

                    <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                      <div>
                        <label htmlFor="cut-in" className="label">
                          Cut-in speed (m/s)
                        </label>
                        <input
                          id="cut-in"
                          type="number"
                          value={formData.cut_in_speed}
                          onChange={(e) =>
                            updateForm('cut_in_speed', Number(e.target.value))
                          }
                          className="input-field"
                          min={0}
                          step={0.1}
                          required
                        />
                      </div>

                      <div>
                        <label htmlFor="rated-speed" className="label">
                          Rated speed (m/s)
                        </label>
                        <input
                          id="rated-speed"
                          type="number"
                          value={formData.rated_speed}
                          onChange={(e) =>
                            updateForm('rated_speed', Number(e.target.value))
                          }
                          className="input-field"
                          min={0}
                          step={0.1}
                          required
                        />
                      </div>

                      <div>
                        <label htmlFor="cut-out" className="label">
                          Cut-out speed (m/s)
                        </label>
                        <input
                          id="cut-out"
                          type="number"
                          value={formData.cut_out_speed}
                          onChange={(e) =>
                            updateForm('cut_out_speed', Number(e.target.value))
                          }
                          className="input-field"
                          min={0}
                          step={0.1}
                          required
                        />
                      </div>
                    </div>
                  </div>

                  {/* Simulation defaults */}
                  <div className="space-y-4">
                    <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-wider">
                      Simulation Defaults
                    </h3>

                    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                      <div>
                        <label htmlFor="dt" className="label">
                          Time step - dt (s)
                        </label>
                        <input
                          id="dt"
                          type="number"
                          value={formData.dt}
                          onChange={(e) =>
                            updateForm('dt', Number(e.target.value))
                          }
                          className="input-field"
                          min={0.001}
                          step={0.0001}
                          required
                        />
                      </div>

                      <div>
                        <label htmlFor="t-max" className="label">
                          Max time - t_max (s)
                        </label>
                        <input
                          id="t-max"
                          type="number"
                          value={formData.t_max}
                          onChange={(e) =>
                            updateForm('t_max', Number(e.target.value))
                          }
                          className="input-field"
                          min={0}
                          step={10}
                          required
                        />
                      </div>
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="flex items-center justify-end gap-3 pt-2 border-t border-slate-700">
                    <button
                      type="button"
                      onClick={closeModal}
                      className="btn-secondary"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      disabled={isCreating || !formData.name.trim()}
                      className="btn-primary"
                    >
                      {isCreating ? (
                        <>
                          <Loader2 className="h-4 w-4 animate-spin" />
                          Creating...
                        </>
                      ) : (
                        <>
                          <Plus className="h-4 w-4" />
                          Create Project
                        </>
                      )}
                    </button>
                  </div>
                </form>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
