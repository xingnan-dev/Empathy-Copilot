export type EvidenceType =
  | 'VERIFIED_BUSINESS_FACT'
  | 'CONSUMER_REPORTED'
  | 'AI_OBSERVATION'
  | 'AI_INFERENCE'
  | 'UNKNOWN'

export interface EvidenceRecord {
  id: string
  fact: string
  type: EvidenceType
  source: string
  timestamp?: string
  provenance: string
}

export const s00154 = {
  caseId: 'S00154',
  consumer: '蒋a**',
  scenario: 'Adverse reaction · Medical attention',
  orderId: '6920073444593979097',
  product: 'Firming Gift Set',
  paid: '¥1,398',
  ticketId: 'BLFY27898314',
  signals: [
    'Medical attention reported',
    'Consumer reports facial swelling',
    'Medical material uploaded',
    'Adverse-reaction service case exists',
  ],
  evidence: [
    {
      id: 'consumer-swelling',
      fact: 'Facial swelling after cream use',
      type: 'CONSUMER_REPORTED',
      source: 'Consumer message · S00154',
      timestamp: '11 May · 16:20',
      provenance: 'Message 94422222481506.PNM',
    },
    {
      id: 'order-purchase',
      fact: 'Firming Gift Set purchased · ¥1,398',
      type: 'VERIFIED_BUSINESS_FACT',
      source: 'Order system',
      timestamp: '27 Apr · 07:24',
      provenance: 'Order 6920073444593979097',
    },
    {
      id: 'service-ticket',
      fact: 'Adverse-reaction service case exists',
      type: 'VERIFIED_BUSINESS_FACT',
      source: 'Service record',
      timestamp: '11 May · 16:49',
      provenance: 'Ticket BLFY27898314',
    },
    {
      id: 'uploaded-material',
      fact: 'Medical document received',
      type: 'AI_OBSERVATION',
      source: 'Uploaded image',
      timestamp: '11 May · 16:21',
      provenance: 'Message 25581855302692.PNM',
    },
  ] satisfies EvidenceRecord[],
  unknowns: [
    'Exact product actually used',
    'Exact first-use time',
    'Other recent routine changes',
    'Current symptom progression',
  ],
} as const
