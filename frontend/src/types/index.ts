export type Incident = {
  id: number
  incident_id: string
  title: string
  severity: string
  status: string
  started_at: string
  ended_at?: string | null
  affected_services: string[]
  current_root_cause?: string | null
  confidence?: number | null
  summary?: string | null
  correlated_signals: string[]
  anomaly_count: number
  evidence_count: number
}

export type Evidence = {
  id: number
  metric: string
  value: number
  expected_value?: string | null
  anomaly_status: boolean
  timestamp: string
  source: string
  service: string
}

export type Rca = {
  id: number
  root_cause: string
  confidence: number
  confidence_label: string
  severity: string
  supporting_evidence: string[]
  contradicting_evidence: string[]
  recommendations: string[]
  retrieved_knowledge: string[]
  score_breakdown: Record<string, number>
  reasoning_summary?: string | null
  created_at: string
}

export type IncidentDetail = Incident & {
  events: { id: number; event_type: string; message: string; timestamp: string }[]
  evidence: Evidence[]
  rca?: Rca | null
  recommendations: string[]
}

export type DashboardSummary = {
  system_status: string
  service_count: number
  active_incidents: number
  active_anomalies: number
  overall_risk_score: number
  metrics: Record<string, number>
  active_incident_list: Incident[]
  recent_alerts: { id: number; message: string; severity: string; timestamp: string }[]
  ai_summary: string
  health_timeline: { t: string; status: string; risk: number }[]
  anomaly_timeline: { t: string; metric: string; severity: string; service: string }[]
  service_health: { name: string; display_name: string; status: string }[]
}

export type Metric = {
  id: number
  service: string
  metric: string
  value: number
  unit: string
  timestamp: string
}

export type LogRow = {
  id: number
  timestamp: string
  severity: string
  service: string
  message: string
  trace_id?: string | null
  span_id?: string | null
  host: string
}

export type TraceRow = {
  id: number
  trace_id: string
  root_service: string
  total_duration_ms: number
  status: string
  started_at: string
  spans: {
    span_id: string
    parent_span_id?: string | null
    service: string
    operation: string
    duration_ms: number
    status: string
    start_offset_ms: number
  }[]
}

export type ServiceRow = {
  id: number
  name: string
  display_name: string
  tier: string
  status: string
  dependencies: string[]
}

export type EvaluationMetrics = {
  rca_accuracy: number
  incident_detection: number
  rag_top1_accuracy: number
  false_positive_rate: number
  average_rca_time_s: number
  false_negatives: number
  correlation_accuracy: number
  sample_size: number
  measured_at: string
}
