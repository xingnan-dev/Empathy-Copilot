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

export interface EvidenceGapRecord {
  id: string
  label: string
  why: string
  resolve: string
}

export interface TimelineRecord {
  id: string
  date: string
  time?: string
  type: 'ORDER' | 'CONSUMER_MESSAGE' | 'MATERIAL_UPLOAD' | 'SERVICE_RECORD' | 'AGENT_ACTION'
  title: string
  detail: string
  source: string
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
      fact: 'Consumer reports facial swelling after cream use',
      type: 'CONSUMER_REPORTED',
      source: 'Consumer message · S00154',
      timestamp: '11 May · 16:20',
      provenance: 'Message 94422222481506.PNM',
    },
    {
      id: 'consumer-medical-attention',
      fact: 'Consumer reports medical attention',
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
      fact: 'Medical material uploaded',
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
  gaps: [
    {
      id: 'EXACT_PRODUCT_USED',
      label: 'Exact product used',
      why: 'The order contains a gift set; purchase does not identify which item was actually used.',
      resolve: 'Ask consumer',
    },
    {
      id: 'ACTUAL_FIRST_USE_TIME',
      label: 'Actual first-use time',
      why: 'Purchase date does not prove actual usage date.',
      resolve: 'Ask consumer',
    },
    {
      id: 'RECENT_REGIMEN_CHANGES',
      label: 'Recent routine changes',
      why: 'Other recent product changes may affect attribution.',
      resolve: 'Ask consumer',
    },
    {
      id: 'CURRENT_SYMPTOM_PROGRESSION',
      label: 'Current symptom progression',
      why: 'The current direction of symptoms is not established in the available records.',
      resolve: 'Human follow-up',
    },
  ] satisfies EvidenceGapRecord[],
  timeline: [
    {
      id: 'order-created',
      date: '27 Apr 2026',
      time: '07:24',
      type: 'ORDER',
      title: 'Firming Gift Set purchased',
      detail: 'Order value ¥1,398. Purchase is verified; usage is not.',
      source: 'Order 6920073444593979097',
    },
    {
      id: 'consumer-report',
      date: '11 May 2026',
      time: '16:20',
      type: 'CONSUMER_MESSAGE',
      title: 'Facial swelling and medical attention reported',
      detail: 'Consumer-reported information; not a medical diagnosis.',
      source: 'Conversation S00154',
    },
    {
      id: 'material-upload',
      date: '11 May 2026',
      time: '16:21',
      type: 'MATERIAL_UPLOAD',
      title: 'Medical material uploaded',
      detail: 'The upload is observed. Its medical contents are not verified by the system.',
      source: 'Message 25581855302692.PNM',
    },
    {
      id: 'service-record',
      date: '11 May 2026',
      time: '16:49',
      type: 'SERVICE_RECORD',
      title: 'Adverse-reaction service case recorded',
      detail: 'Relevant service handling record exists.',
      source: 'Ticket BLFY27898314',
    },
  ] satisfies TimelineRecord[],
  activity: [
    { id: 'restore', label: 'Restored current case context', status: 'COMPLETED', technical: 'CHECKPOINT' },
    { id: 'order', label: 'Retrieved order history', status: 'COMPLETED', technical: 'CALL_TOOL' },
    { id: 'service', label: 'Retrieved service history', status: 'COMPLETED', technical: 'CALL_TOOL' },
    { id: 'ground', label: 'Grounded evidence with provenance', status: 'COMPLETED', technical: 'EVIDENCE' },
    { id: 'gaps', label: 'Detected four open evidence gaps', status: 'COMPLETED', technical: 'GAP_CHECK' },
    { id: 'safety', label: 'Evaluated escalation safety path', status: 'COMPLETED', technical: 'POLICY' },
    { id: 'approval', label: 'Waiting for human approval', status: 'CURRENT', technical: 'WAIT_FOR_HUMAN' },
  ],
} as const
