export type Basis = 'found' | 'inferred' | 'unresolved'
export type Confidence = 'high' | 'medium' | 'low'
export type Evidence = { document_id: string; page: number; clause: string; quote: string }
export type Field = { value: string | null; basis: Basis; confidence: Confidence; reason: string; evidence: Evidence[] }
export type OcrDocument = {
  id: string
  filename: string
  status: 'queued' | 'processing' | 'ready' | 'failed'
  pages: { number: number; text: string; method: 'native' | 'ocr'; quality: 'good' | 'poor' | 'unknown' }[]
  error: string | null
}
export const fieldNames = ['parties', 'term', 'renewal', 'termination', 'payment', 'liability', 'restrictions'] as const
export type FieldName = typeof fieldNames[number]
export type Contract = { id: string; document_id: string; name: string; category: string; fields: Record<FieldName, Field> }
export type Action = { id: string; contract_id: string; title: string; due_date: string; event_date: string | null; basis: Basis; confidence: Confidence; reason: string; evidence: Evidence[] }
export type Conflict = { id: string; title: string; contract_ids: string[]; summary: string; question: string; confidence: Confidence; evidence: Evidence[] }
export type Portfolio = { schema_version: '1.0'; as_of: string; documents: OcrDocument[]; contracts: Contract[]; actions: Action[]; conflicts: Conflict[] }
