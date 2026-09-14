import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { api } from '../services/api'
import { Badge, Loading, Panel, StatCard } from '../components/ui'

export default function IncidentDetailPage() {
  const { id = '' } = useParams()
  const qc = useQueryClient()
  const { data, isLoading } = useQuery({
    queryKey: ['incident', id],
    queryFn: () => api.incident(id),
    enabled: !!id,
    refetchInterval: 3000,
  })

  const investigate = useMutation({
    mutationFn: () => api.investigate(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['incident', id] })
      qc.invalidateQueries({ queryKey: ['incidents'] })
      qc.invalidateQueries({ queryKey: ['dashboard'] })
    },
  })

  if (isLoading || !data) return <Loading />

  const started = new Date(data.started_at).getTime()
  const durationMin = Math.max(1, Math.round((Date.now() - started) / 60000))
  const rca = data.rca

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-xs text-slate-500">{data.incident_id}</div>
          <h1 className="text-xl font-semibold">{data.title}</h1>
          <div className="mt-2 flex flex-wrap gap-2">
            <Badge tone={data.severity}>{data.severity}</Badge>
            <Badge tone={data.status}>{data.status}</Badge>
            <span className="text-xs text-slate-500">Started {new Date(data.started_at).toLocaleString()}</span>
            <span className="text-xs text-slate-500">Duration {durationMin}m</span>
          </div>
          <div className="mt-2 text-sm text-slate-400">
            Affected: {(data.affected_services || []).join(', ') || '—'}
          </div>
        </div>
        <button
          onClick={() => investigate.mutate()}
          disabled={investigate.isPending}
          className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium hover:bg-indigo-500 disabled:opacity-50"
        >
          {investigate.isPending ? 'Investigating…' : 'Run AI Investigation'}
        </button>
      </div>

      <div className="grid gap-4 xl:grid-cols-3">
        <Panel title="Root cause" className="xl:col-span-1">
          {rca ? (
            <div>
              <div className="text-lg font-semibold text-indigo-200">{rca.root_cause}</div>
              <div className="mt-3 text-4xl font-semibold">{rca.confidence.toFixed(0)}%</div>
              <div className="mt-1 text-sm text-slate-400">{rca.confidence_label}</div>
              {rca.score_breakdown && (
                <div className="mt-4 space-y-1 text-xs text-slate-400">
                  {Object.entries(rca.score_breakdown).map(([k, v]) => (
                    <div key={k} className="flex justify-between gap-2">
                      <span>{k}</span>
                      <span>{Number(v) > 0 ? `+${v}` : v}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <div className="text-sm text-slate-500">No RCA yet. Trigger AI investigation.</div>
          )}
        </Panel>

        <Panel title="Evidence" className="xl:col-span-2">
          <div className="grid gap-2 sm:grid-cols-2">
            {data.evidence.map((e) => (
              <div key={e.id} className="rounded-md border border-[#1f2a3d] p-3 text-sm">
                <div className="font-medium">{e.metric}</div>
                <div className="text-2xl">{e.value}</div>
                <div className="text-xs text-slate-500">Expected: {e.expected_value || 'n/a'}</div>
                <div className="mt-1 flex justify-between text-xs">
                  <span>Anomaly: {e.anomaly_status ? 'YES' : 'NO'}</span>
                  <span>{e.service}</span>
                </div>
              </div>
            ))}
            {!data.evidence.length && <div className="text-sm text-slate-500">Evidence appears after investigation.</div>}
          </div>
        </Panel>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <Panel title="Correlated signals">
          <div className="font-mono text-sm text-slate-300">
            {(data.correlated_signals || []).map((s, i) => (
              <div key={s}>
                {i === 0 ? s : `  |`}
                {i > 0 && (
                  <>
                    <br />
                    {`  +---- ${s}`}
                  </>
                )}
              </div>
            ))}
            {!data.correlated_signals?.length && <span className="text-slate-500">No signals yet.</span>}
          </div>
        </Panel>
        <Panel title="Timeline">
          <div className="max-h-64 space-y-2 overflow-auto">
            {data.events.map((ev) => (
              <div key={ev.id} className="border-l-2 border-indigo-500/40 pl-3 text-sm">
                <div className="text-xs text-slate-500">{new Date(ev.timestamp).toLocaleString()}</div>
                <div>{ev.message}</div>
              </div>
            ))}
          </div>
        </Panel>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <Panel title="AI Investigation">
          {rca ? (
            <div className="space-y-3 text-sm text-slate-300">
              <p>{rca.reasoning_summary}</p>
              <div>
                <div className="mb-1 text-xs uppercase text-slate-500">Supporting evidence</div>
                <ul className="list-disc space-y-1 pl-5">
                  {rca.supporting_evidence.map((s, i) => (
                    <li key={i}>{s}</li>
                  ))}
                </ul>
              </div>
              <div>
                <div className="mb-1 text-xs uppercase text-slate-500">Contradictory evidence</div>
                {rca.contradicting_evidence?.length ? (
                  <ul className="list-disc space-y-1 pl-5">
                    {rca.contradicting_evidence.map((s, i) => (
                      <li key={i}>{s}</li>
                    ))}
                  </ul>
                ) : (
                  <div className="text-slate-500">None observed.</div>
                )}
              </div>
              <div>
                <div className="mb-1 text-xs uppercase text-slate-500">Retrieved runbooks</div>
                <div className="flex flex-wrap gap-2">
                  {(rca.retrieved_knowledge || []).map((k) => (
                    <Badge key={k} tone="Investigating">
                      {k}
                    </Badge>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <div className="text-sm text-slate-500">Run investigation to populate this panel.</div>
          )}
        </Panel>
        <Panel title="Recommendations">
          <ul className="space-y-2 text-sm">
            {(data.recommendations.length ? data.recommendations : rca?.recommendations || []).map((r, i) => (
              <li key={i} className="rounded-md border border-[#1f2a3d] px-3 py-2">
                {r}
              </li>
            ))}
            {!data.recommendations.length && !rca?.recommendations?.length && (
              <li className="text-slate-500">No recommendations yet.</li>
            )}
          </ul>
          <p className="mt-3 text-xs text-amber-400/90">
            Guardian never auto-executes destructive remediation.
          </p>
          <Link to="/investigation" className="mt-3 inline-block text-sm text-indigo-300 hover:underline">
            Open AI Investigation console →
          </Link>
        </Panel>
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        <StatCard label="Anomalies" value={data.anomaly_count} />
        <StatCard label="Evidence signals" value={data.evidence_count} />
        <StatCard label="Confidence" value={data.confidence != null ? `${data.confidence.toFixed(0)}%` : '—'} tone="ai" />
      </div>
    </div>
  )
}
