# High Error Rate

## Symptoms
- Spike in HTTP 5xx or application exceptions
- Alerting on error budget burn
- Correlated user reports

## Common Causes
- Bad deploy / configuration
- Dependency failures
- Unhandled exceptions
- Resource exhaustion cascading into errors

## Investigation Steps
1. Group errors by endpoint, status code, and exception type
2. Attach failing requests to traces
3. Check dependency health and recent changes
4. Validate canary or feature flag state

## Recommended Actions
- Roll back or forward-fix the failing change
- Enable graceful degradation
- Increase logging sampling carefully for failing paths

## Risks
- Auto-remediation restarts may hide root cause

## Rollback
- Revert release
- Disable faulty flag
