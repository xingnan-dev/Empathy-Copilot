import { apiRequest } from './client'
import type { CaseView, ResponseDraft } from './types'

export const getCase = (caseId: string) => apiRequest<CaseView>(`/api/cases/${caseId}`)
export const approveCase = (caseId: string, expectedRevision: number) => apiRequest<CaseView>(`/api/cases/${caseId}/human-approval`, { method: 'POST', body: JSON.stringify({ expected_revision: expectedRevision }) })
export const generateResponseDraft = (caseId: string, expectedRevision: number) => apiRequest<ResponseDraft>(`/api/cases/${caseId}/response-draft`, { method: 'POST', body: JSON.stringify({ expected_revision: expectedRevision }) })
export const ingestConsumerMessage = (caseId: string, message: string, messageId: string, expectedRevision: number) => apiRequest<CaseView>(`/api/cases/${caseId}/messages`, { method: 'POST', body: JSON.stringify({ message, message_id: messageId, expected_revision: expectedRevision }) })
