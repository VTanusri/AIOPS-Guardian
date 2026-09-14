import { Panel } from '../components/ui'

export default function AboutPage() {
  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">About AIOps Guardian</h1>
      <Panel>
        <p className="text-sm leading-relaxed text-slate-300">
          AIOps Guardian is an academic AIOps platform that monitors telemetry, detects anomalies with
          explainable ML/statistics, correlates incidents, retrieves operational knowledge with RAG, and
          produces structured root-cause analysis. The LLM reasons over evidence — it is not the sole source
          of truth.
        </p>
      </Panel>
    </div>
  )
}
