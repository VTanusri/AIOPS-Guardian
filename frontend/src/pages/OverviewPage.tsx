import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { api } from '../services/api'
import { Badge, Loading, Panel, StatCard } from '../components/ui'

export default function OverviewPage() {
  const { data, isLoading } = useQuery({
    queryKey: ['dashboard'],
    queryFn: api.dashboard,
    refetchInterval: 3000,
  })

  if (isLoading || !data) return <Loading />

  const m = data.metrics
  const tone =
    data.system_status === 'HEALTHY' ? 'ok' : data.system_status === 'CRITICAL' ? 'crit' : 'warn'
  const project = (data as any).active_project

  return (
    <div className="space-y-4">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold">Overview</h1>
          <p className="text-sm text-slate-400">System health, active risk, and what changed recently.</p>
        </div>
        <Badge tone={data.system_status === 'HEALTHY' ? 'healthy' : data.system_status}>{data.system_status}</Badge>
      </div>

      <Panel title="GitHub project scope">
        {project?.active ? (
          <div className="flex flex-wrap items-center justify-between gap-3 text-sm">
            <div>
              <div className="font-medium text-indigo-200">{project.full_name}</div>
              <div className="text-xs text-slate-500">
                {project.service_count} services · mode {project.mode} · failed Actions{' '}
                {project.signals?.failed_workflow_count ?? 0}
              </div>
            </div>
            <Link to="/project" className="text-indigo-300 hover:underline">
              Manage project →
            </Link>
          </div>
        ) : (
          <div className="flex flex-wrap items-center justify-between gap-3 text-sm text-slate-400">
            <span>No GitHub repo imported — using default demo topology.</span>
            <Link to="/project" className="text-indigo-300 hover:underline">
              Import GitHub URL →
            </Link>
          </div>
        )}
      </Panel>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <StatCard label="System status" value={data.system_status} tone={tone} />
        <StatCard label="Services" value={data.service_count} />
        <StatCard label="Active incidents" value={data.active_incidents} tone={data.active_incidents ? 'warn' : 'ok'} />
        <StatCard label="Active anomalies" value={data.active_anomalies} tone={data.active_anomalies ? 'warn' : 'ok'} />
        <StatCard label="Risk score" value={data.overall_risk_score} tone={data.overall_risk_score > 60 ? 'crit' : 'neutral'} />
      </div>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="CPU" value={`${m.cpu?.toFixed?.(1) ?? m.cpu}%`} />
        <StatCard label="Memory" value={`${m.memory?.toFixed?.(1) ?? m.memory}%`} />
        <StatCard label="Request rate" value={`${m.request_rate?.toFixed?.(0) ?? 0} rps`} />
        <StatCard label="Error rate" value={`${m.error_rate?.toFixed?.(2) ?? 0}%`} tone={m.error_rate > 5 ? 'crit' : 'ok'} />
        <StatCard label="API latency" value={`${m.api_latency?.toFixed?.(0) ?? 0} ms`} tone={m.api_latency > 300 ? 'warn' : 'neutral'} />
        <StatCard label="DB connections" value={`${m.db_connections?.toFixed?.(1) ?? 0}%`} tone={m.db_connections > 80 ? 'crit' : 'neutral'} />
        <StatCard label="Disk" value={`${m.disk?.toFixed?.(1) ?? 0}%`} />
        <StatCard label="Network" value={`${m.network?.toFixed?.(1) ?? 0}%`} />
      </div>

      <div className="grid gap-4 xl:grid-cols-3">
        <Panel title="System health timeline" className="xl:col-span-2">
          <div className="h-48">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={data.health_timeline}>
                <CartesianGrid stroke="#1f2a3d" strokeDasharray="3 3" />
                <XAxis dataKey="t" hide />
                <YAxis domain={[0, 100]} stroke="#64748b" fontSize={11} />
                <Tooltip contentStyle={{ background: '#111827', border: '1px solid #1f2a3d' }} />
                <Area type="monotone" dataKey="risk" stroke="#6366f1" fill="#6366f133" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </Panel>
        <Panel title="AI incident summary">
          <p className="text-sm leading-relaxed text-slate-300">{data.ai_summary}</p>
        </Panel>
      </div>

      <div className="grid gap-4 xl:grid-cols-3">
        <Panel title="Active incidents" className="xl:col-span-2">
          <div className="space-y-2">
            {data.active_incident_list.length === 0 && (
              <div className="text-sm text-slate-500">No active incidents.</div>
            )}
            {data.active_incident_list.map((inc) => (
              <Link
                key={inc.id}
                to={`/incidents/${inc.incident_id}`}
                className="flex items-center justify-between rounded-md border border-[#1f2a3d] px-3 py-2 hover:bg-slate-800/50"
              >
                <div>
                  <div className="text-sm font-medium">{inc.title}</div>
                  <div className="text-xs text-slate-500">
                    {inc.incident_id} · {inc.status}
                    {inc.current_root_cause ? ` · ${inc.current_root_cause}` : ''}
                  </div>
                </div>
                <Badge tone={inc.severity}>{inc.severity}</Badge>
              </Link>
            ))}
          </div>
        </Panel>
        <Panel title="Service health">
          <div className="space-y-2">
            {data.service_health.map((s) => (
              <div key={s.name} className="flex items-center justify-between text-sm">
                <span>{s.display_name}</span>
                <Badge tone={s.status}>{s.status}</Badge>
              </div>
            ))}
          </div>
        </Panel>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <Panel title="Recent alerts">
          <div className="space-y-2">
            {data.recent_alerts.map((a) => (
              <div key={a.id} className="flex items-center justify-between text-sm">
                <span className="truncate pr-3 text-slate-300">{a.message}</span>
                <Badge tone={a.severity}>{a.severity}</Badge>
              </div>
            ))}
            {!data.recent_alerts.length && <div className="text-sm text-slate-500">No recent anomalies.</div>}
          </div>
        </Panel>
        <Panel title="Anomaly timeline">
          <div className="max-h-56 space-y-1 overflow-auto text-xs text-slate-400">
            {data.anomaly_timeline.map((a, i) => (
              <div key={i} className="flex justify-between gap-2 border-b border-[#1f2a3d]/60 py-1">
                <span>
                  {a.service}/{a.metric}
                </span>
                <span>{a.severity}</span>
              </div>
            ))}
            {!data.anomaly_timeline.length && <div>No anomalies in the last 15 minutes.</div>}
          </div>
        </Panel>
      </div>
    </div>
  )
}
