import { useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { api } from '../services/api'
import { Badge, Loading, Panel } from '../components/ui'

const PROMPTS = [
  'What is the root cause?',
  'Why did this incident happen?',
  'What evidence supports the diagnosis?',
  'What should I investigate next?',
  'Are there similar historical incidents?',
  'Which runbook applies?',
]

export default function AIInvestigationPage() {
  const { data: incidents } = useQuery({ queryKey: ['incidents'], queryFn: api.incidents, refetchInterval: 4000 })
  const [incidentId, setIncidentId] = useState('')
  const [question, setQuestion] = useState(PROMPTS[0])
  const [result, setResult] = useState<any>(null)

  const ask = useMutation({
    mutationFn: () => api.ask(incidentId, question),
    onSuccess: (data) => setResult(data),
  })

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold">AI Investigation</h1>
        <p className="text-sm text-slate-400">
          Evidence-grounded Q&A. Knowledge is retrieved before answering — no unsupported operational claims.
        </p>
      </div>
      <Panel title="Console">
        <div className="grid gap-3 md:grid-cols-2">
          <select
            className="rounded-md border border-[#1f2a3d] bg-[#0f172a] px-3 py-2 text-sm"
            value={incidentId}
            onChange={(e) => setIncidentId(e.target.value)}
          >
            <option value="">Select incident…</option>
            {(incidents || []).map((i) => (
              <option key={i.incident_id} value={i.incident_id}>
                {i.incident_id} — {i.title}
              </option>
            ))}
          </select>
          <select
            className="rounded-md border border-[#1f2a3d] bg-[#0f172a] px-3 py-2 text-sm"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
          >
            {PROMPTS.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
        </div>
        <textarea
          className="mt-3 w-full rounded-md border border-[#1f2a3d] bg-[#0f172a] px-3 py-2 text-sm"
          rows={3}
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
        />
        <button
          disabled={!incidentId || ask.isPending}
          onClick={() => ask.mutate()}
          className="mt-3 rounded-md bg-indigo-600 px-4 py-2 text-sm hover:bg-indigo-500 disabled:opacity-50"
        >
          {ask.isPending ? 'Retrieving knowledge & reasoning…' : 'Ask Guardian'}
        </button>
      </Panel>

      {ask.isPending && <Loading />}

      {result && (
        <div className="grid gap-4 xl:grid-cols-2">
          <Panel title="Answer">
            <p className="whitespace-pre-wrap text-sm text-slate-300">{result.answer}</p>
            <div className="mt-3 flex flex-wrap gap-2 text-sm">
              <Badge tone="Investigating">Confidence {result.confidence?.toFixed?.(0)}%</Badge>
              <Badge tone="INFO">LLM: {result.llm_provider}</Badge>
            </div>
            <div className="mt-2 text-xs text-slate-500">
              Affected: {(result.affected_services || []).join(', ')}
            </div>
          </Panel>
          <Panel title="Evidence used">
            <ul className="space-y-2 text-sm">
              {(result.evidence_used || []).map((e: any) => (
                <li key={e.id} className="rounded border border-[#1f2a3d] px-3 py-2">
                  {e.metric} = {e.value} (expected {e.expected_value || 'n/a'}) · {e.service}
                </li>
              ))}
            </ul>
          </Panel>
          <Panel title="Retrieved knowledge" className="xl:col-span-2">
            <div className="space-y-3">
              {(result.retrieved_knowledge || []).map((h: any, i: number) => (
                <div key={i} className="rounded border border-[#1f2a3d] p-3 text-sm">
                  <div className="font-medium text-indigo-200">
                    {h.title} <span className="text-xs text-slate-500">score {h.score}</span>
                  </div>
                  <p className="mt-1 text-slate-400">{h.content?.slice(0, 280)}…</p>
                </div>
              ))}
              {!result.retrieved_knowledge?.length && (
                <div className="text-slate-500">No knowledge hits (index may still be building).</div>
              )}
            </div>
          </Panel>
        </div>
      )}
    </div>
  )
}
