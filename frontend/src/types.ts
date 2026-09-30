export type Evidence = {
  reference_id: string
  source_type: string
  title: string
  detail: string
  source_system: string
  observed_at: string
}

export type Order = {
  order_id: string
  customer_id: string
  customer_name: string
  customer_tier: 'Strategic' | 'Priority' | 'Standard'
  part_id: string
  part_name: string
  plant_id: string
  required_date: string
  order_value: number
  quantity: number
  impact_severity: string
  reason: string
}

export type Alternative = {
  supplier_id: string
  supplier_name: string
  part_id: string
  plant_id: string
  lead_time_days: number
  available_capacity: number
  cost_band: string
  approved: boolean
  recommendation_rank: number
  coverage_percent: number
  estimated_protected_revenue: number
  tradeoff: string
}

export type AuditEvent = {
  audit_id: string
  event_type: string
  actor: string
  created_at: string
  summary: string
  correlation_id: string
}

export type DemoBundle = {
  summary: {
    active_disruptions: number
    revenue_at_risk: number
    plants_at_risk: number
    orders_at_risk: number
    pending_approvals: number
  }
  analysis: {
    correlation_id: string
    generated_at: string
    source_system: string
    supplier: { supplier_id: string; supplier_name: string; risk_tier: string }
    delay_days: number
    risk_summary: {
      severity: string
      headline: string
      narrative: string
      revenue_at_risk: number
      impacted_orders: number
      protected_order_value: number
    }
    affected_parts: Array<{ part_id: string; part_name: string; category: string }>
    affected_plants: Array<{ plant_id: string; plant_name: string; city: string }>
    affected_shipments: Array<{ shipment_id: string; part_id: string; plant_id: string; original_eta: string; delayed_eta: string; status: string }>
    open_orders: Order[]
    affected_customers: Array<{ customer_id: string; customer_name: string; tier: string; orders_at_risk: number }>
    evidence: Evidence[]
    assumptions: string[]
    metric_definition: string
  }
  alternatives: Alternative[]
  audit_events: AuditEvent[]
  provenance: {
    repository_mode: 'fixture' | 'snowflake'
    source_system: string
    snapshot_loaded_at: string
    metric_lineage: string
    metric_engine: string
    query_ids: string[]
    semantic_validation: {
      status: string
      query_id?: string
      rows?: Array<Record<string, unknown>>
      reason?: string
    }
    database_zones: Record<string, string>
    evidence_coverage_percent: number
    policy_checks: string[]
  }
}

export type Mitigation = {
  audit_id: string
  action_id: string
  correlation_id: string
  status: 'PENDING_APPROVAL' | 'APPROVED' | 'RETURNED_FOR_REVISION'
  action_type: string
  part_id: string
  plant_id: string
  proposed_supplier_id: string
  owner: string
  owner_id: string
  rationale: string
  created_at: string
  version: number
  policy_decision_id: string
  qualification_checked_at: string
  approved_by?: string
  approved_by_id?: string
  approved_at?: string
  approval_reason?: string
  returned_by?: string
  returned_by_id?: string
  returned_at?: string
  revision_reason?: string
}

export type ActorId = 'maya.iyer' | 'aisha.rao'

export type Identity = {
  actor_id: string
  display_name: string
  title: string
  roles: string[]
  identity_source: string
}

export type ConversationAnswer = {
  status: 'ANSWERED' | 'NEEDS_CLARIFICATION' | 'REJECTED_BY_POLICY'
  intent: string
  answer: string
  facts?: Array<{ label: string; value: string }>
  evidence?: Evidence[]
  missing_fields?: string[]
  tool_calls: string[]
  source_references: string[]
  correlation_id: string
  audit_id: string
  generated_at: string
  answer_policy?: string
  metric_definition?: string
}

export type ToastState = {
  message: string
  tone: 'success' | 'error' | 'info'
}
