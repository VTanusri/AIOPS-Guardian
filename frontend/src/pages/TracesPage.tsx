import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import { api } from '../services/api'
import { Badge, Loading, Panel } from '../components/ui'

export default function TracesPage() {
  const [params] = useSearchParams()
  const highlight = params.get('trace') || ''
  const { data, isLoading } = useQuery({
    queryKey: ['traces'],
    queryFn: api.traces,
    refetchInterval: 4000,
  })
  const [selected, setSelected] = useState<string>(highlight)

  const trace = useMemo(() => {
    if (!data?.length) return null
    const id = selected || highlight || data[0].trace_id
    return data.find((t) => t.trace_id === id) || data[0]
  }, [data, selected, highlight])

  const maxDur = Math.max(...(trace?.spans.map((s) => s.start_offset_ms + s.duration_ms) || [1]))

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold">Traces</h1>
        <p className="text-sm text-slate-400">Distributed trace explorer with waterfall visualization.</p>
      </div>
      <div className="grid gap-4 xl:grid-cols-3">
        <Panel title="Recent traces" className="xl:col-span-1">
          {isLoading ? (
            <Loading />
          ) : (
            <div className="max-h-[70vh] space-y-1 overflow-auto">
              {(data || []).map((t) => (
                <button
                  key={t.trace_id}
                  onClick={() => setSelected(t.trace_id)}
                  className={`w-full rounded-md border px-3 py-2 text-left text-sm ${
                    trace?.trace_id === t.trace_id ? 'border-indigo-500 bg-slate-800' : 'border-[#1f2a3d]'
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate font-mono text-xs">{t.trace_id.slice(0, 12)}…</span>
                    <Badge tone={t.status === 'error' ? 'CRITICAL' : 'ok'}>{t.status}</Badge>
                  </div>
                  <div className="mt-1 text-xs text-slate-500">
                    {t.root_service} · {t.total_duration_ms.toFixed(0)}ms
                  </div>
                </button>
              ))}
            </div>
          )}
        </Panel>
        <Panel title="Waterfall" className="xl:col-span-2">
          {!trace ? (
            <Loading />
          ) : (
            <div className="space-y-3">
              <div className="text-xs text-slate-500">
                {trace.trace_id} · {trace.total_duration_ms.toFixed(0)}ms · {trace.spans.length} spans
              </div>
              {trace.spans.map((span) => {
                const left = (span.start_offset_ms / maxDur) * 100
                const width = Math.max(2, (span.duration_ms / maxDur) * 100)
                const failed = span.status === 'error'
                return (
                  <div key={span.span_id} className="text-sm">
                    <div className="mb-1 flex justify-between text-xs text-slate-400">
                      <span>
                        {span.service} · {span.operation}
                      </span>
                      <span>
                        {span.duration_ms.toFixed(0)}ms {failed ? 'ERROR' : ''}
                      </span>
                    </div>
                    <div className="relative h-4 rounded bg-slate-900">
                      <div
                        className={`absolute top-0 h-4 rounded ${failed ? 'bg-rose-500' : 'bg-sky-500'}`}
                        style={{ left: `${left}%`, width: `${width}%` }}
                      />
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </Panel>
      </div>
    </div>
  )
}
