export function isKnownSeverity(sev: string): boolean {
  return ['INFO', 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'].includes(sev)
}

export function formatConfidence(value?: number | null): string {
  if (value == null) return '—'
  return `${value.toFixed(0)}%`
}
