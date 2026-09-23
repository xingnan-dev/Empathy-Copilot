import { apiRequest } from './client'
import type { CaseView } from './types'

export const getCase = (caseId: string) => apiRequest<CaseView>(`/api/cases/${caseId}`)
export const approveCase = (caseId: string, expectedRevision: number) => apiRequest<CaseView>(`/api/cases/${caseId}/human-approval`, { method: 'POST', body: JSON.stringify({ expected_revision: expectedRevision }) })
