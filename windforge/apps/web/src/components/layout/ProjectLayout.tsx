import { Outlet, NavLink, useParams } from 'react-router-dom';
import { useEffect } from 'react';
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
} from 'lucide-react';

const tabs = [
  { path: 'tower', label: 'Tower', icon: Building2 },
  { path: 'blade', label: 'Blade', icon: Fan },
  { path: 'controller', label: 'Controller', icon: Gauge },
  { path: 'assembly', label: 'Assembly', icon: Boxes },
  { path: 'bem', label: 'BEM & Rotor', icon: Target },
  { path: 'campbell', label: 'Frequencies', icon: Activity },
  { path: 'hydro', label: 'Hydro', icon: Droplets },
  { path: 'modeshapes', label: 'Mode Shapes', icon: Spline },
  { path: 'wind', label: 'Wind', icon: CloudRain },
  { path: 'airfoils', label: 'Airfoils', icon: Feather },
  { path: 'dynamics', label: 'Dynamics', icon: Orbit },
  { path: 'stochastic', label: 'Stochastic', icon: Shuffle },
  { path: 'potential-flow', label: 'Potential Flow', icon: Waves },
  { path: 'particles', label: 'Particles', icon: Atom },
  { path: 'dlc', label: 'DLC', icon: Table2 },
  { path: 'simulate', label: 'Simulate', icon: Play },
  { path: 'results', label: 'Results', icon: BarChart3 },
  { path: 'properties', label: 'Properties', icon: Wind },
  { path: 'files', label: 'Files', icon: FolderOpen },
];

export default function ProjectLayout() {
  const { projectId } = useParams<{ projectId: string }>();
  const currentProject = useProjectStore((s) => s.currentProject);
  const selectProject = useProjectStore((s) => s.selectProject);

  useEffect(() => {
    if (projectId) {
      selectProject(projectId);
    }
  }, [projectId, selectProject]);

  return (
    <div className="flex h-full flex-col">
      {/* Project header */}
      <div className="border-b border-slate-700 bg-surface-dark-secondary px-6 py-4">
        <div className="flex items-center gap-2 text-sm text-slate-400 mb-1">
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
            <span>
              {currentProject.rotor_diameter}m rotor
            </span>
            <span className="inline-block w-1 h-1 rounded-full bg-slate-600" />
            <span>
              {currentProject.rated_power} kW rated
            </span>
          </div>
        )}
      </div>

      {/* Horizontal tab navigation */}
      <div className="border-b border-slate-700 bg-surface-dark-secondary px-6">
        <nav className="flex gap-1 -mb-px">
          {tabs.map((tab) => (
            <NavLink
              key={tab.path}
              to={tab.path}
              className={({ isActive }) =>
                clsx(
                  'group flex items-center gap-2 border-b-2 px-4 py-3 text-sm font-medium transition-all duration-200',
                  isActive
                    ? 'border-accent-500 text-accent-400'
                    : 'border-transparent text-slate-400 hover:border-slate-500 hover:text-slate-200',
                )
              }
            >
              <tab.icon className="h-4 w-4" />
              {tab.label}
            </NavLink>
          ))}
        </nav>
      </div>

      {/* Page content */}
      <div className="flex-1 overflow-auto p-6">
        <Outlet />
      </div>
    </div>
  );
}
