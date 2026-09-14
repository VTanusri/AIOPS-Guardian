# Disk Full

## Symptoms
- Disk utilization near 100%
- Write failures, database errors
- Log shipping or backup failures

## Common Causes
- Unrotated logs
- Large temp files
- Database growth / bloat
- Misconfigured retention

## Investigation Steps
1. Identify fullest mount points
2. Find largest directories safely
3. Check DB tablespace growth
4. Verify log rotation configuration

## Recommended Actions
- Clear safe temporary artifacts after verification
- Expand volume if capacity planning requires
- Fix retention/rotation policies

## Risks
- Deleting files blindly can destroy needed data

## Rollback
- Restore from backup if accidental deletion occurs
