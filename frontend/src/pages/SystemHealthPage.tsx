import { useQuery } from '@tanstack/react-query'
import { api } from '../services/api'
import { Badge, Loading, Panel, StatCard } from '../components/ui'

export default function SystemHealthPage() {
  const { data, isLoading } = useQuery({ queryKey: ['dashboard'], queryFn: api.dashboard, refetchInterval: 3000 })
  const { data: health } = useQuery({ queryKey: ['health'], queryFn: api.health })
  if (isLoading || !data) return <Loading />
  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">System Health</h1>
      <div className="grid gap-3 sm:grid-cols-4">
        <StatCard label="Derived status" value={data.system_status} tone={data.system_status === 'HEALTHY' ? 'ok' : 'crit'} />
        <StatCard label="Risk" value={data.overall_risk_score} />
        <StatCard label="API" value={health?.status || '…'} tone="ok" />
        <StatCard label="LLM provider" value={health?.llm_provider || '…'} tone="ai" />
      </div>
      <Panel title="Service availability">
        <div className="space-y-2">
          {data.service_health.map((s) => (
            <div key={s.name} className="flex justify-between text-sm">
              <span>{s.display_name}</span>
              <Badge tone={s.status}>{s.status}</Badge>
            </div>
          ))}
        </div>
      </Panel>
    </div>
  )
}
