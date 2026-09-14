import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '../services/api'
import { Badge, Loading, Panel } from '../components/ui'

export default function LogsPage() {
  const [service, setService] = useState('')
  const [severity, setSeverity] = useState('')
  const [q, setQ] = useState('')
  const [expanded, setExpanded] = useState<number | null>(null)

  const { data: services } = useQuery({ queryKey: ['services'], queryFn: api.services })
  const { data, isLoading } = useQuery({
    queryKey: ['logs', service, severity, q],
    queryFn: () => {
      const p = new URLSearchParams({ limit: '150' })
      if (service) p.set('service', service)
      if (severity) p.set('severity', severity)
      if (q) p.set('q', q)
      return api.logs(`?${p}`)
    },
    refetchInterval: 2500,
  })

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold">Logs</h1>
        <p className="text-sm text-slate-400">Live log explorer with filters and trace navigation.</p>
      </div>
      <div className="flex flex-wrap gap-2">
        <input
          className="rounded-md border border-[#1f2a3d] bg-[#111827] px-3 py-2 text-sm"
          placeholder="Search message…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <select
          className="rounded-md border border-[#1f2a3d] bg-[#111827] px-3 py-2 text-sm"
          value={service}
          onChange={(e) => setService(e.target.value)}
        >
          <option value="">All services</option>
          {(services || []).map((s) => (
            <option key={s.name} value={s.name}>
              {s.display_name}
            </option>
          ))}
        </select>
        <select
          className="rounded-md border border-[#1f2a3d] bg-[#111827] px-3 py-2 text-sm"
          value={severity}
          onChange={(e) => setSeverity(e.target.value)}
        >
          <option value="">All severities</option>
          {['DEBUG', 'INFO', 'WARN', 'ERROR'].map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </div>
      <Panel>
        {isLoading ? (
          <Loading />
        ) : (
          <div className="max-h-[70vh] overflow-auto font-mono text-xs">
            {(data || []).map((row) => (
              <div
                key={row.id}
                className="cursor-pointer border-b border-[#1f2a3d]/70 px-1 py-2 hover:bg-slate-800/40"
                onClick={() => setExpanded(expanded === row.id ? null : row.id)}
              >
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-slate-500">{new Date(row.timestamp).toLocaleTimeString()}</span>
                  <Badge tone={row.severity === 'ERROR' ? 'CRITICAL' : row.severity === 'WARN' ? 'MEDIUM' : 'INFO'}>
                    {row.severity}
                  </Badge>
                  <span className="text-sky-300">{row.service}</span>
                  <span className="text-slate-200">{row.message}</span>
                </div>
                {expanded === row.id && (
                  <div className="mt-2 space-y-1 text-slate-400">
                    <div>host: {row.host}</div>
                    <div>
                      trace:{' '}
                      {row.trace_id ? (
                        <Link className="text-indigo-300 hover:underline" to={`/traces?trace=${row.trace_id}`}>
                          {row.trace_id}
                        </Link>
                      ) : (
                        '—'
                      )}
                    </div>
                    <div>span: {row.span_id || '—'}</div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </Panel>
    </div>
  )
}
