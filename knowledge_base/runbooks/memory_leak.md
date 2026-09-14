# Memory Leak

## Symptoms
- Memory utilization trends upward without returning to baseline
- Increasing GC frequency/latency
- Eventual OOM kills or severe latency

## Common Causes
- Unbounded caches
- Listener/subscription leaks
- Large object retention in heaps
- Native memory growth

## Investigation Steps
1. Chart memory over hours/days for monotonic growth
2. Capture heap dump if safe in non-prod first
3. Review recent code allocating caches/collections
4. Check for goroutine/thread leaks

## Recommended Actions
- Bound cache sizes and TTLs
- Fix leak and redeploy
- Restart only as temporary mitigation with stakeholder approval

## Risks
- Restarts without fix cause recurring incidents

## Rollback
- Deploy previous version known to be stable
