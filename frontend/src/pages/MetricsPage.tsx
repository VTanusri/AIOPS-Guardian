import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { api } from '../services/api'
import { Loading, Panel } from '../components/ui'

const METRIC_OPTIONS = [
  'cpu_utilization',
  'memory_utilization',
  'disk_utilization',
  'network_utilization',
  'request_rate',
  'api_latency',
  'error_rate',
  'db_connection_usage',
  'db_latency',
]

export default function MetricsPage() {
  const [service, setService] = useState('')
  const [metric, setMetric] = useState('cpu_utilization')
  const [minutes, setMinutes] = useState(30)

  const { data, isLoading } = useQuery({
    queryKey: ['metrics', service, metric, minutes],
    queryFn: () => {
      const p = new URLSearchParams({ minutes: String(minutes), limit: '800' })
      if (service) p.set('service', service)
      if (metric) p.set('metric', metric)
      return api.metrics(`?${p}`)
    },
    refetchInterval: 3000,
  })

  const { data: services } = useQuery({ queryKey: ['services'], queryFn: api.services })

  const chartData = useMemo(() => {
    if (!data) return []
    return [...data]
      .reverse()
      .map((d) => ({
        t: new Date(d.timestamp).toLocaleTimeString(),
        value: d.value,
        service: d.service,
      }))
  }, [data])

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold">Live Metrics</h1>
        <p className="text-sm text-slate-400">Real-time telemetry with service and metric filters.</p>
      </div>
      <div className="flex flex-wrap gap-3">
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
          value={metric}
          onChange={(e) => setMetric(e.target.value)}
        >
          {METRIC_OPTIONS.map((m) => (
            <option key={m} value={m}>
              {m}
            </option>
          ))}
        </select>
        <select
          className="rounded-md border border-[#1f2a3d] bg-[#111827] px-3 py-2 text-sm"
          value={minutes}
          onChange={(e) => setMinutes(Number(e.target.value))}
        >
          <option value={15}>Last 15m</option>
          <option value={30}>Last 30m</option>
          <option value={60}>Last 1h</option>
        </select>
      </div>
      <Panel title={`${metric}${service ? ` · ${service}` : ''}`}>
        {isLoading ? (
          <Loading />
        ) : (
          <div className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData}>
                <CartesianGrid stroke="#1f2a3d" strokeDasharray="3 3" />
                <XAxis dataKey="t" stroke="#64748b" fontSize={11} minTickGap={40} />
                <YAxis stroke="#64748b" fontSize={11} />
                <Tooltip contentStyle={{ background: '#111827', border: '1px solid #1f2a3d' }} />
                <Legend />
                <Line type="monotone" dataKey="value" stroke="#38bdf8" dot={false} strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </Panel>
    </div>
  )
}
