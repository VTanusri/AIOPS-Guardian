import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import AppLayout from './layouts/AppLayout'
import OverviewPage from './pages/OverviewPage'
import IncidentsPage from './pages/IncidentsPage'
import IncidentDetailPage from './pages/IncidentDetailPage'
import MetricsPage from './pages/MetricsPage'
import LogsPage from './pages/LogsPage'
import TracesPage from './pages/TracesPage'
import AIInvestigationPage from './pages/AIInvestigationPage'
import KnowledgePage from './pages/KnowledgePage'
import ServicesPage from './pages/ServicesPage'
import SimulationPage from './pages/SimulationPage'
import EvaluationPage from './pages/EvaluationPage'
import SystemHealthPage from './pages/SystemHealthPage'
import SettingsPage from './pages/SettingsPage'
import AboutPage from './pages/AboutPage'

import ProjectImportPage from './pages/ProjectImportPage'

const qc = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } },
})

export default function App() {
  return (
    <QueryClientProvider client={qc}>
      <BrowserRouter>
        <Routes>
          <Route element={<AppLayout />}>
            <Route index element={<OverviewPage />} />
            <Route path="project" element={<ProjectImportPage />} />
            <Route path="incidents" element={<IncidentsPage />} />
            <Route path="incidents/:id" element={<IncidentDetailPage />} />
            <Route path="metrics" element={<MetricsPage />} />
            <Route path="logs" element={<LogsPage />} />
            <Route path="traces" element={<TracesPage />} />
            <Route path="investigation" element={<AIInvestigationPage />} />
            <Route path="knowledge" element={<KnowledgePage />} />
            <Route path="services" element={<ServicesPage />} />
            <Route path="simulation" element={<SimulationPage />} />
            <Route path="evaluation" element={<EvaluationPage />} />
            <Route path="health" element={<SystemHealthPage />} />
            <Route path="settings" element={<SettingsPage />} />
            <Route path="about" element={<AboutPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
