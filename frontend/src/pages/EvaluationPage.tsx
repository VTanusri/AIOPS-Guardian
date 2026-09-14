import { useQuery } from '@tanstack/react-query'
import { api } from '../services/api'
import { Loading, Panel, StatCard } from '../components/ui'

export default function EvaluationPage() {
  const { data, isLoading, refetch, isFetching } = useQuery({
    queryKey: ['evaluation'],
    queryFn: api.evaluation,
  })

  if (isLoading || !data) return <Loading />

  return (
    <div className="space-y-4">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-xl font-semibold">Evaluation</h1>
          <p className="text-sm text-slate-400">
            Measured offline scenario metrics — not fabricated dashboard numbers.
          </p>
        </div>
        <button
          onClick={() => refetch()}
          className="rounded-md border border-[#1f2a3d] px-3 py-2 text-sm hover:bg-slate-800"
        >
          {isFetching ? 'Running…' : 'Re-run evaluation'}
        </button>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        <StatCard label="RCA Accuracy" value={`${data.rca_accuracy}%`} tone="ai" />
        <StatCard label="Incident Detection" value={`${data.incident_detection}%`} />
        <StatCard label="RAG Top-1 Accuracy" value={`${data.rag_top1_accuracy}%`} />
        <StatCard label="False Positive Rate" value={`${data.false_positive_rate}%`} tone="warn" />
        <StatCard label="Average RCA Time" value={`${data.average_rca_time_s}s`} />
        <StatCard label="Correlation Accuracy" value={`${data.correlation_accuracy}%`} />
      </div>
      <Panel title="Run details">
        <div className="grid gap-2 text-sm text-slate-300 sm:grid-cols-2">
          <div>Sample size: {data.sample_size}</div>
          <div>False negatives (count): {data.false_negatives}</div>
          <div>Measured at: {new Date(data.measured_at).toLocaleString()}</div>
        </div>
      </Panel>
    </div>
  )
}
