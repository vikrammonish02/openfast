import { Outlet, NavLink, useParams, useLocation } from 'react-router-dom';
import { useEffect, useState } from 'react';
import { useProjectStore } from '@/stores/projectStore';
import clsx from 'clsx';
import {
  Building2,
  Fan,
  Gauge,
  Boxes,
  Activity,
  Table2,
  Play,
  BarChart3,
  Wind,
  FolderOpen,
  ChevronRight,
  Droplets,
  Spline,
  CloudRain,
  Feather,
  Target,
  Orbit,
  Shuffle,
  Waves,
  Atom,
  ChevronDown,
  TrendingDown,
} from 'lucide-react';

// ---------------------------------------------------------------------------
// Sidebar groups — "define & run" pages
// ---------------------------------------------------------------------------

interface SidebarItem {
  path: string;
  label: string;
  icon: typeof Building2;
}

interface SidebarGroup {
  label: string;
  items: SidebarItem[];
}

const sidebarGroups: SidebarGroup[] = [
  {
    label: 'DESIGN',
    items: [
      { path: 'tower', label: 'Tower', icon: Building2 },
      { path: 'blade', label: 'Blade', icon: Fan },
      { path: 'controller', label: 'Controller', icon: Gauge },
      { path: 'assembly', label: 'Assembly', icon: Boxes },
    ],
  },
  {
    label: 'ENVIRONMENT',
    items: [
      { path: 'wind', label: 'Wind', icon: CloudRain },
      { path: 'hydro', label: 'Hydro', icon: Droplets },
    ],
  },
  {
    label: 'SIMULATION',
    items: [
      { path: 'dlc', label: 'DLC Matrix', icon: Table2 },
      { path: 'simulate', label: 'Simulate', icon: Play },
      { path: 'results', label: 'Results', icon: BarChart3 },
    ],
  },
  {
    label: 'PROJECT',
    items: [
      { path: 'properties', label: 'Properties', icon: Wind },
      { path: 'files', label: 'Files', icon: FolderOpen },
    ],
  },
];

// ---------------------------------------------------------------------------
// Horizontal analysis tabs — "compute & visualize" pages
// ---------------------------------------------------------------------------

const analysisTabs = [
  { path: 'bem', label: 'BEM & Rotor', icon: Target },
  { path: 'campbell', label: 'Frequencies', icon: Activity },
  { path: 'modeshapes', label: 'Mode Shapes', icon: Spline },
  { path: 'airfoils', label: 'Airfoils', icon: Feather },
  { path: 'dynamics', label: 'Dynamics', icon: Orbit },
  { path: 'stochastic', label: 'Stochastic', icon: Shuffle },
  { path: 'potential-flow', label: 'Potential Flow', icon: Waves },
  { path: 'particles', label: 'Particles', icon: Atom },
];

// All analysis paths for checking if we're on an analysis page
const analysisPathSet = new Set(analysisTabs.map((t) => t.path));

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function ProjectLayout() {
  const { projectId } = useParams<{ projectId: string }>();
  const location = useLocation();
  const currentProject = useProjectStore((s) => s.currentProject);
  const selectProject = useProjectStore((s) => s.selectProject);

  // Track collapsed sidebar groups
  const [collapsedGroups, setCollapsedGroups] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (projectId) {
      selectProject(projectId);
    }
  }, [projectId, selectProject]);

  // Determine if we're currently on an analysis tab
  const currentPath = location.pathname.split('/').pop() || '';
  const isAnalysisPage = analysisPathSet.has(currentPath);

  const toggleGroup = (label: string) => {
    setCollapsedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(label)) {
        next.delete(label);
      } else {
        next.add(label);
      }
      return next;
    });
  };

  return (
    <div className="flex h-full flex-col">
      {/* Project header breadcrumb */}
      <div className="border-b border-slate-700 bg-surface-dark-secondary px-6 py-3">
        <div className="flex items-center gap-2 text-sm text-slate-400 mb-0.5">
          <NavLink to="/" className="hover:text-accent-400 transition-colors">
            Projects
          </NavLink>
          <ChevronRight className="h-3.5 w-3.5" />
          <span className="text-slate-100 font-medium">
            {currentProject?.name || 'Loading...'}
          </span>
        </div>
        {currentProject && (
          <div className="flex items-center gap-4 text-xs text-slate-500">
            <span>
              Wind Class {currentProject.wind_class}
              {currentProject.turbulence_class}
            </span>
            <span className="inline-block w-1 h-1 rounded-full bg-slate-600" />
            <span>{currentProject.rotor_diameter}m rotor</span>
            <span className="inline-block w-1 h-1 rounded-full bg-slate-600" />
            <span>{currentProject.rated_power} kW rated</span>
          </div>
        )}
      </div>

      {/* Main body: sidebar + content */}
      <div className="flex flex-1 overflow-hidden">
        {/* ── Left sidebar ────────────────────────────────────── */}
        <aside className="w-[220px] flex-shrink-0 border-r border-slate-700/60 bg-surface-dark overflow-y-auto">
          <nav className="py-3 px-2 space-y-4">
            {sidebarGroups.map((group) => {
              const isCollapsed = collapsedGroups.has(group.label);
              return (
                <div key={group.label}>
                  {/* Group header */}
                  <button
                    onClick={() => toggleGroup(group.label)}
                    className="flex w-full items-center justify-between px-2 mb-1 group"
                  >
                    <span className="text-[10px] font-semibold uppercase tracking-widest text-slate-500 group-hover:text-slate-400 transition-colors">
                      {group.label}
                    </span>
                    <ChevronDown
                      className={clsx(
                        'h-3 w-3 text-slate-600 transition-transform duration-200',
                        isCollapsed && '-rotate-90',
                      )}
                    />
                  </button>

                  {/* Group items */}
                  {!isCollapsed && (
                    <div className="space-y-0.5">
                      {group.items.map((item) => (
                        <NavLink
                          key={item.path}
                          to={item.path}
                          className={({ isActive }) =>
                            clsx(
                              'flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-[13px] font-medium transition-all duration-150',
                              isActive
                                ? 'bg-accent-500/10 text-accent-400'
                                : 'text-slate-400 hover:bg-slate-800/60 hover:text-slate-200',
                            )
                          }
                        >
                          <item.icon className="h-4 w-4 flex-shrink-0" />
                          {item.label}
                        </NavLink>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}

            {/* Analysis section link in sidebar */}
            <div>
              <span className="flex items-center gap-1.5 px-2 mb-1">
                <span className="text-[10px] font-semibold uppercase tracking-widest text-slate-500">
                  ANALYSIS
                </span>
              </span>
              <div className="space-y-0.5">
                {analysisTabs.map((tab) => (
                  <NavLink
                    key={tab.path}
                    to={tab.path}
                    className={({ isActive }) =>
                      clsx(
                        'flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-[13px] font-medium transition-all duration-150',
                        isActive
                          ? 'bg-accent-500/10 text-accent-400'
                          : 'text-slate-400 hover:bg-slate-800/60 hover:text-slate-200',
                      )
                    }
                  >
                    <tab.icon className="h-4 w-4 flex-shrink-0" />
                    {tab.label}
                  </NavLink>
                ))}
              </div>
            </div>

            {/* Post Processing section */}
            <div>
              <span className="flex items-center gap-1.5 px-2 mb-1">
                <span className="text-[10px] font-semibold uppercase tracking-widest text-slate-500">
                  POST PROCESSING
                </span>
              </span>
              <div className="space-y-0.5">
                <NavLink
                  to="postprocessing"
                  className={({ isActive }) =>
                    clsx(
                      'flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-[13px] font-medium transition-all duration-150',
                      isActive
                        ? 'bg-accent-500/10 text-accent-400'
                        : 'text-slate-400 hover:bg-slate-800/60 hover:text-slate-200',
                    )
                  }
                >
                  <TrendingDown className="h-4 w-4 flex-shrink-0" />
                  Post Processing
                </NavLink>
              </div>
            </div>
          </nav>
        </aside>

        {/* ── Right content area ──────────────────────────────── */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {/* Horizontal analysis tabs — shown only when on analysis pages */}
          {isAnalysisPage && (
            <div className="border-b border-slate-700 bg-surface-dark-secondary px-4 flex-shrink-0">
              <nav className="flex gap-0.5 -mb-px overflow-x-auto scrollbar-thin scrollbar-track-transparent scrollbar-thumb-slate-700">
                {analysisTabs.map((tab) => (
                  <NavLink
                    key={tab.path}
                    to={tab.path}
                    className={({ isActive }) =>
                      clsx(
                        'group flex items-center gap-1.5 border-b-2 px-3 py-2.5 text-sm font-medium transition-all duration-200 whitespace-nowrap',
                        isActive
                          ? 'border-accent-500 text-accent-400'
                          : 'border-transparent text-slate-400 hover:border-slate-500 hover:text-slate-200',
                      )
                    }
                  >
                    <tab.icon className="h-3.5 w-3.5" />
                    {tab.label}
                  </NavLink>
                ))}
              </nav>
            </div>
          )}

          {/* Page content */}
          <div className="flex-1 overflow-auto p-6">
            <Outlet />
          </div>
        </div>
      </div>
    </div>
  );
}
