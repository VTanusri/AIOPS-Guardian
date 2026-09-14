# High API Latency

## Symptoms
- p95/p99 latency breaches SLO
- Slow traces across gateway and service spans
- Downstream dependency delays
- User-facing timeouts

## Common Causes
- Slow database queries
- Downstream service degradation
- Inefficient code paths / N+1 queries
- Resource contention (CPU, memory)

## Investigation Steps
1. Open recent high-latency traces and find the slowest span
2. Check DB latency and connection metrics
3. Compare latency before/after latest deployment
4. Inspect GC pauses and CPU saturation

## Recommended Actions
- Optimize slow queries or add indexes
- Enable caching for hot paths
- Scale horizontally if CPU-bound
- Roll back recent problematic release if needed

## Risks
- Aggressive retries can amplify latency (retry storms)

## Rollback
- Revert deploy
- Disable experimental feature flags contributing to load
