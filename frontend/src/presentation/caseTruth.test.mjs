import assert from 'node:assert/strict'
import test from 'node:test'

import {
  currentServiceRecordEvidence,
  decisionSupportLabels,
  restoredServiceHistory,
} from './caseTruth.ts'

const base = {
  evidence: [
    {
      id: 'severity',
      fact: 'SEVERE',
      type: 'CONSUMER_REPORTED',
      source: 'Official consumer message M1',
      provenance: 'Consumer Message · M1',
      timestamp: '2026-05-01T10:00:00',
    },
    {
      id: 'medical',
      fact: 'reported medical attention',
      type: 'CONSUMER_REPORTED',
      source: 'Official consumer message M1',
      provenance: 'Consumer Message · M1',
      timestamp: '2026-05-01T10:00:00',
    },
  ],
  restored_context: false,
  previous_service_history: [],
}

test('no restored history produces no returning-consumer support', () => {
  assert.deepEqual(restoredServiceHistory(base), [])
})

test('restored history can support returning-consumer wording', () => {
  const history = [{ historical_case_id: 'EARLIER-CASE' }]
  assert.deepEqual(
    restoredServiceHistory({ ...base, restored_context: true, previous_service_history: history }),
    history,
  )
})

test('no service-record evidence produces no service-record claim', () => {
  assert.deepEqual(currentServiceRecordEvidence(base), [])
  assert.equal(decisionSupportLabels(base).includes('Current service record available'), false)
})

test('consumer-reported text cannot become a verified service-record claim', () => {
  const consumerReport = {
    id: 'consumer-service-reference',
    fact: 'consumer says a service case exists',
    type: 'CONSUMER_REPORTED',
    source: 'Official service record SR-UNVERIFIED',
    provenance: 'Consumer Message · M1',
    timestamp: '2026-05-01T10:02:00',
  }
  const view = { ...base, evidence: [...base.evidence, consumerReport] }
  assert.deepEqual(currentServiceRecordEvidence(view), [])
  assert.equal(decisionSupportLabels(view).includes('Current service record available'), false)
})

test('authoritative service evidence enables supported service-record wording', () => {
  const serviceEvidence = {
    id: 'service',
    fact: 'IN_PROGRESS',
    type: 'VERIFIED_BUSINESS_FACT',
    source: 'Official service record SR-1',
    provenance: 'Service System · SR-1',
    timestamp: '2026-05-01T10:03:00',
  }
  const view = { ...base, evidence: [...base.evidence, serviceEvidence] }
  assert.deepEqual(currentServiceRecordEvidence(view), [serviceEvidence])
  assert.equal(decisionSupportLabels(view).includes('Current service record available'), true)
})
