import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, subscribeSSE } from '../services/api'
import { Badge, Panel, StatCard } from '../components/ui'

export default function SimulationPage() {
  const qc = useQueryClient()
  const { data: scenarios } = useQuery({ queryKey: ['scenarios'], queryFn: api.scenarios })
  const { data: status, refetch } = useQuery({
    queryKey: ['sim-status'],
    queryFn: api.simStatus,
    refetchInterval: 2000,
  })
  const [events, setEvents] = useState<string[]>([])
  const [selected, setSelected] = useState('db_pool_exhaustion')

  useEffect(() => {
    return subscribeSSE('simulation', (msg) => {
      setEvents((prev) => [`${msg.type}: ${msg.message || msg.scenario || ''}`.trim(), ...prev].slice(0, 30))
      refetch()
      qc.invalidateQueries({ queryKey: ['dashboard'] })
      qc.invalidateQueries({ queryKey: ['incidents'] })
      qc.invalidateQueries({ queryKey: ['metrics'] })
    })
  }, [qc, refetch])

  const start = useMutation({
    mutationFn: () => api.simStart(selected),
    onSuccess: () => refetch(),
  })
  const stop = useMutation({ mutationFn: api.simStop, onSuccess: () => refetch() })
  const reset = useMutation({ mutationFn: api.simReset, onSuccess: () => refetch() })

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold">Simulation Center</h1>
        <p className="text-sm text-slate-400">
          Drive the full demo loop: healthy → simulate → anomalies → incident → RCA.
        </p>
      </div>
      <div className="grid gap-3 sm:grid-cols-4">
        <StatCard label="Running" value={status?.running ? 'YES' : 'NO'} tone={status?.running ? 'warn' : 'ok'} />
        <StatCard label="Scenario" value={status?.scenario || '—'} />
        <StatCard label="Step" value={`${status?.step ?? 0}/${status?.total_steps ?? 0}`} />
        <StatCard label="Message" value={status?.message || 'idle'} />
      </div>
      <Panel title="Scenarios">
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {(scenarios || []).map((s) => (
            <button
              key={s.key}
              onClick={() => setSelected(s.key)}
              className={`rounded-lg border p-3 text-left ${
                selected === s.key ? 'border-indigo-500 bg-slate-800/80' : 'border-[#1f2a3d]'
              }`}
            >
              <div className="font-medium">{s.name}</div>
              <div className="mt-1 text-xs text-slate-500">{s.description}</div>
            </button>
          ))}
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          <button
            onClick={() => start.mutate()}
            disabled={status?.running || start.isPending}
            className="rounded-md bg-rose-600 px-4 py-2 text-sm hover:bg-rose-500 disabled:opacity-50"
          >
            Start simulation
          </button>
          <button
            onClick={() => stop.mutate()}
            className="rounded-md border border-[#1f2a3d] px-4 py-2 text-sm hover:bg-slate-800"
          >
            Stop
          </button>
          <button
            onClick={() => reset.mutate()}
            className="rounded-md border border-[#1f2a3d] px-4 py-2 text-sm hover:bg-slate-800"
          >
            Reset
          </button>
          <Link to="/incidents" className="rounded-md bg-indigo-600 px-4 py-2 text-sm hover:bg-indigo-500">
            View incidents
          </Link>
        </div>
      </Panel>
      <Panel title="Live simulation events">
        <div className="space-y-1 font-mono text-xs text-slate-400">
          {events.map((e, i) => (
            <div key={i}>{e}</div>
          ))}
          {!events.length && <div>Waiting for simulation events…</div>}
        </div>
        {status?.running && (
          <div className="mt-3">
            <Badge tone="Investigating">Telemetry mutating in real time</Badge>
          </div>
        )}
      </Panel>
    </div>
  )
}
