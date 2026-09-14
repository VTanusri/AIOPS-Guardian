import assert from 'node:assert/strict'
import { formatConfidence, isKnownSeverity } from './format.ts'

assert.equal(isKnownSeverity('CRITICAL'), true)
assert.equal(isKnownSeverity('nope'), false)
assert.equal(formatConfidence(82.4), '82%')
assert.equal(formatConfidence(null), '—')
console.log('frontend format utils ok')
