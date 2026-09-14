# Database Connection Pool Exhaustion

## Symptoms
- Database connection utilization approaches or exceeds 80–100%
- Application threads block waiting for connections
- Increased database timeout errors
- API latency and HTTP 5xx rates rise together

## Common Causes
- Connection leaks (connections not returned to the pool)
- Long-running transactions holding connections
- Pool max size too low for concurrency
- Sudden traffic spike without autoscaling

## Investigation Steps
1. Check current pool usage vs max pool size
2. Identify sessions with long `active` or `idle in transaction` state
3. Correlate API latency and error spikes with DB saturation timing
4. Review recent deploys for ORM session mismanagement

## Recommended Actions
- Fix connection leak in application code
- Kill runaway transactions only after identifying ownership
- Temporarily raise pool size only with capacity validation
- Add connection acquisition timeouts and metrics

## Risks
- Restarting the database drops in-flight work
- Blindly increasing pool size can overload the DB CPU/memory

## Rollback
- Revert pool configuration changes
- Redeploy previous application version if a leak was introduced
