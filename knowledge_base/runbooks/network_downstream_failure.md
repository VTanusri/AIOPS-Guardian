# Network / Downstream Failure

## Symptoms
- Elevated latency/errors to external or peer services
- Connection resets, DNS failures, timeouts
- Partial outage isolated to dependency path

## Common Causes
- Provider outage
- Firewall / security group changes
- DNS misconfiguration
- Network congestion or packet loss

## Investigation Steps
1. Test connectivity and DNS resolution to dependency
2. Compare error rates for external vs internal paths
3. Review recent network policy changes
4. Check circuit breaker and retry configuration

## Recommended Actions
- Fail open/closed appropriately with feature flags
- Engage dependency owner / provider status page
- Tune retries to avoid storms

## Risks
- Aggressive failover can overload secondary regions

## Rollback
- Revert network ACL/security group changes
- Restore prior routing configuration
