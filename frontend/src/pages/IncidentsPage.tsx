import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '../services/api'
import { Badge, Loading, Panel } from '../components/ui'

export default function IncidentsPage() {
  const { data, isLoading } = useQuery({
    queryKey: ['incidents'],
    queryFn: api.incidents,
    refetchInterval: 3000,
  })

  if (isLoading || !data) return <Loading />

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold">Incidents</h1>
        <p className="text-sm text-slate-400">Correlated anomalies grouped into actionable incidents.</p>
      </div>
      <Panel>
        <div className="overflow-x-auto">
          <table className="min-w-full text-left text-sm">
            <thead className="text-xs uppercase text-slate-500">
              <tr>
                <th className="pb-2 pr-3">ID</th>
                <th className="pb-2 pr-3">Title</th>
                <th className="pb-2 pr-3">Severity</th>
                <th className="pb-2 pr-3">Status</th>
                <th className="pb-2 pr-3">Started</th>
                <th className="pb-2 pr-3">Services</th>
                <th className="pb-2 pr-3">Confidence</th>
                <th className="pb-2 pr-3">Root cause</th>
                <th className="pb-2 pr-3">Anomalies</th>
                <th className="pb-2">Evidence</th>
              </tr>
            </thead>
            <tbody>
              {data.map((inc) => (
                <tr key={inc.id} className="border-t border-[#1f2a3d] hover:bg-slate-800/40">
                  <td className="py-2 pr-3">
                    <Link className="text-indigo-300 hover:underline" to={`/incidents/${inc.incident_id}`}>
                      {inc.incident_id}
                    </Link>
                  </td>
                  <td className="py-2 pr-3">{inc.title}</td>
                  <td className="py-2 pr-3">
                    <Badge tone={inc.severity}>{inc.severity}</Badge>
                  </td>
                  <td className="py-2 pr-3">
                    <Badge tone={inc.status}>{inc.status}</Badge>
                  </td>
                  <td className="py-2 pr-3 text-xs text-slate-400">{new Date(inc.started_at).toLocaleString()}</td>
                  <td className="py-2 pr-3 text-xs">{(inc.affected_services || []).join(', ')}</td>
                  <td className="py-2 pr-3">{inc.confidence != null ? `${inc.confidence.toFixed(0)}%` : '—'}</td>
                  <td className="py-2 pr-3 text-xs">{inc.current_root_cause || '—'}</td>
                  <td className="py-2 pr-3">{inc.anomaly_count}</td>
                  <td className="py-2">{inc.evidence_count}</td>
                </tr>
              ))}
              {!data.length && (
                <tr>
                  <td colSpan={10} className="py-8 text-center text-slate-500">
                    No incidents yet. Start a scenario in Simulation Center.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  )
}
