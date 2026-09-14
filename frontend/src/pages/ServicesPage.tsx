import { useQuery } from '@tanstack/react-query'
import { api } from '../services/api'
import { Badge, Loading, Panel } from '../components/ui'

export default function ServicesPage() {
  const { data, isLoading } = useQuery({ queryKey: ['services'], queryFn: api.services, refetchInterval: 4000 })
  if (isLoading || !data) return <Loading />
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold">Services</h1>
        <p className="text-sm text-slate-400">Service catalog with dependency topology and live health.</p>
      </div>
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {data.map((s) => (
          <Panel key={s.id} title={s.display_name}>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-slate-500">Status</span>
                <Badge tone={s.status}>{s.status}</Badge>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Tier</span>
                <span>{s.tier}</span>
              </div>
              <div>
                <div className="text-slate-500">Depends on</div>
                <div className="mt-1 text-xs">{(s.dependencies || []).join(', ') || '—'}</div>
              </div>
            </div>
          </Panel>
        ))}
      </div>
    </div>
  )
}
