import type { DemoBundle } from './types'

export const demoBundle: DemoBundle = {
  summary: {
    active_disruptions: 1,
    revenue_at_risk: 586000,
    plants_at_risk: 2,
    orders_at_risk: 3,
    pending_approvals: 0,
  },
  analysis: {
    correlation_id: 'WF-7A41C2',
    generated_at: '2026-09-29T10:30:00+05:30',
    source_system: 'GOVERNED_FIXTURE_LAYER',
    supplier: { supplier_id: 'SUP-042', supplier_name: 'NordWerk Components', risk_tier: 'Critical' },
    delay_days: 14,
    risk_summary: {
      severity: 'CRITICAL',
      headline: '3 orders worth $586K require intervention',
      narrative: 'Two inbound shipments now land after customer-required dates. Strategic accounts are exposed at both Pune and Bengaluru plants.',
      revenue_at_risk: 586000,
      impacted_orders: 3,
      protected_order_value: 168000,
    },
    affected_parts: [
      { part_id: 'PRT-AX14', part_name: 'Precision bearing assembly', category: 'Drive systems' },
      { part_id: 'PRT-CTRL9', part_name: 'Motor control unit', category: 'Electronics' },
    ],
    affected_plants: [
      { plant_id: 'PLT-PUN', plant_name: 'Pune Assembly', city: 'Pune' },
      { plant_id: 'PLT-BLR', plant_name: 'Bengaluru Systems', city: 'Bengaluru' },
    ],
    affected_shipments: [
      { shipment_id: 'SHP-8801', part_id: 'PRT-AX14', plant_id: 'PLT-PUN', original_eta: '2026-10-03', delayed_eta: '2026-10-17', status: 'DELAYED' },
      { shipment_id: 'SHP-8802', part_id: 'PRT-CTRL9', plant_id: 'PLT-BLR', original_eta: '2026-10-05', delayed_eta: '2026-10-19', status: 'DELAYED' },
    ],
    open_orders: [
      { order_id: 'SO-7101', customer_id: 'CUS-101', customer_name: 'Apex Mobility', customer_tier: 'Strategic', part_id: 'PRT-AX14', part_name: 'Precision bearing assembly', plant_id: 'PLT-PUN', required_date: '2026-10-08', order_value: 240000, quantity: 400, impact_severity: 'CRITICAL', reason: 'Delayed inbound lands 9 days after required date' },
      { order_id: 'SO-7102', customer_id: 'CUS-204', customer_name: 'Meridian Robotics', customer_tier: 'Priority', part_id: 'PRT-AX14', part_name: 'Precision bearing assembly', plant_id: 'PLT-PUN', required_date: '2026-10-12', order_value: 150000, quantity: 250, impact_severity: 'HIGH', reason: 'Available-to-promise is below order demand' },
      { order_id: 'SO-7103', customer_id: 'CUS-117', customer_name: 'Helios Industrial', customer_tier: 'Strategic', part_id: 'PRT-CTRL9', part_name: 'Motor control unit', plant_id: 'PLT-BLR', required_date: '2026-10-10', order_value: 196000, quantity: 140, impact_severity: 'CRITICAL', reason: 'Delayed inbound lands 9 days after required date' },
    ],
    affected_customers: [
      { customer_id: 'CUS-101', customer_name: 'Apex Mobility', tier: 'Strategic', orders_at_risk: 1 },
      { customer_id: 'CUS-117', customer_name: 'Helios Industrial', tier: 'Strategic', orders_at_risk: 1 },
      { customer_id: 'CUS-204', customer_name: 'Meridian Robotics', tier: 'Priority', orders_at_risk: 1 },
    ],
    evidence: [
      { reference_id: 'DOC-042-09', source_type: 'Supplier notice', title: 'Capacity incident notice', detail: 'Supplier confirmed a 14-day slip caused by heat-treatment line maintenance.', source_system: 'Supplier Portal', observed_at: '2026-09-29T08:15:00+05:30', evidence_status: 'RECORDED' },
      { reference_id: 'SHP-8801', source_type: 'Shipment scenario', title: 'Pune projected inbound ETA', detail: 'Scenario projects 470 units of PRT-AX14 from 03 Oct to 17 Oct.', source_system: 'TMS', observed_at: '2026-09-29T08:24:00+05:30', evidence_status: 'SCENARIO_PROJECTION' },
      { reference_id: 'SHP-8802', source_type: 'Shipment scenario', title: 'Bengaluru projected inbound ETA', detail: 'Scenario projects 225 units of PRT-CTRL9 from 05 Oct to 19 Oct.', source_system: 'TMS', observed_at: '2026-09-29T08:27:00+05:30', evidence_status: 'SCENARIO_PROJECTION' },
      { reference_id: 'METRIC-RAR-V1', source_type: 'Governed metric', title: 'Revenue at risk · v1.0', detail: 'Sum of open-order value where protected stock plus inbound supply arriving by the required date cannot satisfy cumulative demand.', source_system: 'Governed fixture + deterministic metric v1.0', observed_at: '2026-09-29T10:30:00+05:30', evidence_status: 'DERIVED' },
    ],
    assumptions: [
      'Confirmed inbound dates include the reported 14-day delay.',
      'Safety stock is protected before customer-order allocation.',
      'No unapproved suppliers are included in mitigation ranking.',
    ],
    metric_definition: 'SUM(open_order_value) when protected stock plus inbound supply arriving by the required date is below cumulative order demand',
  },
  alternatives: [
    { supplier_id: 'SUP-017', supplier_name: 'Axis Precision Works', part_id: 'PRT-AX14', plant_id: 'PLT-PUN', lead_time_days: 5, available_capacity: 500, cost_band: '+8–11%', approved: true, recommendation_rank: 1, coverage_percent: 100, estimated_protected_revenue: 390000, projected_arrival_date: '2026-10-04', shortage_quantity: 470, protected_quantity: 470, tradeoff: 'Fastest qualified response with the strongest available coverage.' },
    { supplier_id: 'SUP-018', supplier_name: 'VoltEdge Systems', part_id: 'PRT-CTRL9', plant_id: 'PLT-BLR', lead_time_days: 7, available_capacity: 200, cost_band: '+12–15%', approved: true, recommendation_rank: 2, coverage_percent: 100, estimated_protected_revenue: 196000, projected_arrival_date: '2026-10-06', shortage_quantity: 105, protected_quantity: 105, tradeoff: 'Fastest qualified response with the strongest available coverage.' },
    { supplier_id: 'SUP-063', supplier_name: 'Kaveri Industrial Co.', part_id: 'PRT-AX14', plant_id: 'PLT-PUN', lead_time_days: 8, available_capacity: 300, cost_band: '+3–5%', approved: true, recommendation_rank: 3, coverage_percent: 64, estimated_protected_revenue: 288000, projected_arrival_date: '2026-10-07', shortage_quantity: 470, protected_quantity: 300, tradeoff: 'Lower-cost partial coverage; combine with allocation prioritization.' },
  ],
  audit_events: [
    { audit_id: 'AUD-9F2A10', event_type: 'INVESTIGATION_COMPLETED', actor: 'Supply Chain MCP', created_at: '2026-09-29T10:30:00+05:30', summary: 'Governed impact analysis completed for SUP-042 / 14 days.', correlation_id: 'WF-7A41C2' },
    { audit_id: 'AUD-4BC812', event_type: 'DISRUPTION_RECEIVED', actor: 'Supplier Portal', created_at: '2026-09-29T08:15:00+05:30', summary: 'Supplier delay notice registered and linked to two inbound shipments.', correlation_id: 'WF-7A41C2' },
  ],
  provenance: {
    repository_mode: 'fixture',
    source_system: 'GOVERNED_FIXTURE_LAYER',
    snapshot_loaded_at: '2026-09-29T10:30:00+05:30',
    metric_lineage: 'Governed fixture → deterministic metric v1.0',
    metric_engine: 'DETERMINISTIC_PYTHON_V1',
    query_ids: [],
    semantic_validation: {
      status: 'NOT_APPLICABLE',
      reason: 'Fixture mode has no live Snowflake semantic view.',
    },
    database_zones: {
      source: 'GOVERNED_FIXTURE_LAYER',
      analytics: 'DETERMINISTIC_METRICS',
      workflow: 'IN_MEMORY_WORKFLOW',
      audit: 'IN_MEMORY_APPEND_ONLY_AUDIT',
    },
    evidence_coverage_percent: 100,
    policy_checks: [
      'governed-identifiers',
      'protected-safety-stock',
      'approved-alternatives-only',
      'draft-only-action',
      'role-authorization',
      'separation-of-duties',
      'versioned-idempotent-decision',
    ],
  },
}
