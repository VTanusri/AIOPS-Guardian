import clsx from 'clsx'
import {
  Activity,
  BookOpen,
  Brain,
  FlaskConical,
  Gauge,
  FolderGit,
  LayoutDashboard,
  ListTree,
  Network,
  ScrollText,
  Server,
  Settings,
  ShieldAlert,
  Sparkles,
} from 'lucide-react'
import { NavLink, Outlet } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '../services/api'

const nav = [
  { to: '/', label: 'Overview', icon: LayoutDashboard },
  { to: '/project', label: 'GitHub Project', icon: FolderGit },
  { to: '/incidents', label: 'Incidents', icon: ShieldAlert },
  { to: '/metrics', label: 'Live Metrics', icon: Gauge },
  { to: '/logs', label: 'Logs', icon: ScrollText },
  { to: '/traces', label: 'Traces', icon: Network },
  { to: '/investigation', label: 'AI Investigation', icon: Brain },
  { to: '/knowledge', label: 'Knowledge Base', icon: BookOpen },
  { to: '/services', label: 'Services', icon: Server },
  { to: '/simulation', label: 'Simulation Center', icon: Sparkles },
  { to: '/evaluation', label: 'Evaluation', icon: FlaskConical },
  { to: '/health', label: 'System Health', icon: Activity },
  { to: '/settings', label: 'Settings', icon: Settings },
  { to: '/about', label: 'About', icon: ListTree },
]

function statusColor(s?: string) {
  if (!s) return 'bg-slate-500'
  if (s === 'HEALTHY' || s === 'healthy') return 'bg-emerald-500'
  if (s === 'DEGRADED' || s === 'degraded' || s === 'WARNING') return 'bg-amber-500'
  return 'bg-rose-500'
}

export default function AppLayout() {
  const { data } = useQuery({
    queryKey: ['dashboard'],
    queryFn: api.dashboard,
    refetchInterval: 4000,
  })

  return (
    <div className="flex h-full min-h-screen bg-[#0b1220] text-slate-100">
      <aside className="flex w-60 shrink-0 flex-col border-r border-[#1f2a3d] bg-[#0f172a]">
        <div className="border-b border-[#1f2a3d] px-4 py-4">
          <div className="text-xs uppercase tracking-[0.2em] text-indigo-300">AIOps</div>
          <div className="text-lg font-semibold">Guardian</div>
          <div className="mt-3 flex items-center gap-2 text-xs text-slate-400">
            <span className={clsx('h-2 w-2 rounded-full', statusColor(data?.system_status))} />
            {data?.system_status || '…'}
          </div>
        </div>
        <nav className="flex-1 space-y-0.5 overflow-y-auto p-2">
          {nav.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) =>
                clsx(
                  'flex items-center gap-2 rounded-md px-3 py-2 text-sm text-slate-300 hover:bg-slate-800/70',
                  isActive && 'bg-slate-800 text-white',
                )
              }
            >
              <item.icon size={16} />
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="border-t border-[#1f2a3d] p-3 text-[11px] text-slate-500">
          Academic AIOps platform · explainable RCA
        </div>
      </aside>
      <main className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-[#1f2a3d] bg-[#0f172a]/70 px-6 py-3">
          <div className="text-sm text-slate-400">Observability · Detection · Investigation</div>
          <div className="flex gap-4 text-xs text-slate-400">
            <span>Incidents: {data?.active_incidents ?? 0}</span>
            <span>Anomalies: {data?.active_anomalies ?? 0}</span>
            <span>Risk: {data?.overall_risk_score ?? 0}</span>
          </div>
        </header>
        <div className="flex-1 overflow-auto p-6">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
