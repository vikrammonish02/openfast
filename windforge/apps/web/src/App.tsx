import { Routes, Route, Navigate } from 'react-router-dom';
import { useEffect } from 'react';
import { useAuthStore } from '@/stores/authStore';
import MainLayout from '@/components/layout/MainLayout';
import ProjectLayout from '@/components/layout/ProjectLayout';
import ProtectedRoute from '@/components/layout/ProtectedRoute';
import LoginPage from '@/routes/LoginPage';
import RegisterPage from '@/routes/RegisterPage';
import Dashboard from '@/routes/Dashboard';

// Lazy placeholders for project sub-pages (stubs for now)
import TowerDesigner from '@/routes/project/TowerDesigner';
import BladeDesigner from '@/routes/project/BladeDesigner';
import ControllerDesigner from '@/routes/project/ControllerDesigner';
import TurbineAssembly from '@/routes/project/TurbineAssembly';
import DLCMatrix from '@/routes/project/DLCMatrix';
import SimulationRunner from '@/routes/project/SimulationRunner';
import ResultsDashboard from '@/components/results/ResultsDashboard';
import TurbineProperties from '@/components/turbine/TurbineProperties';
import FileBrowser from '@/routes/project/FileBrowser';
import MetoceanPage from '@/routes/MetoceanPage';
import CampbellDiagram from '@/routes/project/CampbellDiagram';
import HydroPage from '@/routes/project/HydroPage';
import ModeShapePage from '@/routes/project/ModeShapePage';
import WindEnvironmentPage from '@/routes/project/WindEnvironmentPage';
import AirfoilToolsPage from '@/routes/project/AirfoilToolsPage';

function App() {
  const loadUser = useAuthStore((s) => s.loadUser);
  const isDesktopMode = useAuthStore((s) => s.isDesktopMode);

  useEffect(() => {
    loadUser();
  }, [loadUser]);

  return (
    <Routes>
      {/* In desktop mode, redirect login/register to dashboard */}
      {isDesktopMode ? (
        <>
          <Route path="/login" element={<Navigate to="/" replace />} />
          <Route path="/register" element={<Navigate to="/" replace />} />
        </>
      ) : (
        <>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
        </>
      )}
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <MainLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<Dashboard />} />
        <Route path="metocean" element={<MetoceanPage />} />
        <Route path="projects/:projectId" element={<ProjectLayout />}>
          <Route index element={<Navigate to="tower" replace />} />
          <Route path="tower" element={<TowerDesigner />} />
          <Route path="blade" element={<BladeDesigner />} />
          <Route path="controller" element={<ControllerDesigner />} />
          <Route path="assembly" element={<TurbineAssembly />} />
          <Route path="campbell" element={<CampbellDiagram />} />
          <Route path="hydro" element={<HydroPage />} />
          <Route path="modeshapes" element={<ModeShapePage />} />
          <Route path="wind" element={<WindEnvironmentPage />} />
          <Route path="airfoils" element={<AirfoilToolsPage />} />
          <Route path="dlc" element={<DLCMatrix />} />
          <Route path="simulate" element={<SimulationRunner />} />
          <Route path="results" element={<ResultsDashboard />} />
          <Route path="properties" element={<TurbineProperties />} />
          <Route path="files" element={<FileBrowser />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default App;
