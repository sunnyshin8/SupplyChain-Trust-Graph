'use client'

import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  Boxes,
  Building2,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  CircleDollarSign,
  Clock3,
  Database,
  Factory,
  FileCheck2,
  FileText,
  Fingerprint,
  GitBranch,
  Info,
  LayoutDashboard,
  Link2,
  LockKeyhole,
  Menu,
  PackageCheck,
  RefreshCw,
  Route,
  Search,
  Send,
  ShieldCheck,
  Sparkles,
  Truck,
  UserCheck,
  Users,
  X,
  XCircle,
} from 'lucide-react'
import { demoBundle } from './demoData'
import type {
  ActorId,
  Alternative,
  ConversationAnswer,
  DemoBundle,
  Evidence,
  Identity,
  Mitigation,
  ScenarioComparison,
  ToastState,
} from './types'

const money = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
  maximumFractionDigits: 0,
})

const shortMoney = (value: number) => `$${Math.round(value / 1000)}K`
const previewScenarios: ScenarioComparison = {
  supplier_id: 'SUP-042',
  scenarios: [
    { delay_days: 3, severity: 'MONITORED', revenue_at_risk: 0, orders_at_risk: 0, plants_at_risk: 0, strategic_customers_at_risk: 0, source_references: ['DOC-042-09'] },
    { delay_days: 7, severity: 'HIGH', revenue_at_risk: 436000, orders_at_risk: 2, plants_at_risk: 2, strategic_customers_at_risk: 2, source_references: ['DOC-042-09', 'SHP-8801', 'SHP-8802'] },
    { delay_days: 14, severity: 'CRITICAL', revenue_at_risk: 586000, orders_at_risk: 3, plants_at_risk: 2, strategic_customers_at_risk: 2, source_references: ['DOC-042-09', 'SHP-8801', 'SHP-8802'] },
    { delay_days: 21, severity: 'CRITICAL', revenue_at_risk: 754000, orders_at_risk: 4, plants_at_risk: 2, strategic_customers_at_risk: 2, source_references: ['DOC-042-09', 'SHP-8801', 'SHP-8802'] },
  ],
  first_exposure_delay_days: 7,
  metric_definition: 'Protected stock plus on-time inbound supply must satisfy cumulative demand.',
  source_system: 'UNVERIFIED_PREVIEW',
  generated_at: '2026-09-29T10:30:00+05:30',
}
const prettyDate = (value: string) =>
  new Intl.DateTimeFormat('en-US', { day: '2-digit', month: 'short' }).format(new Date(value))
const prettyTime = (value: string) =>
  new Intl.DateTimeFormat('en-US', {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value))

const actorProfiles: Record<ActorId, { name: string; title: string; initials: string }> = {
  'maya.iyer': { name: 'Maya Iyer', title: 'Supply Planning', initials: 'MI' },
  'aisha.rao': { name: 'Aisha Rao', title: 'VP Operations', initials: 'AR' },
}

async function apiError(response: Response, fallback: string) {
  try {
    const payload = await response.json() as { detail?: string; error?: string }
    return payload.detail || payload.error || fallback
  } catch {
    return fallback
  }
}

function BrandMark({ small = false }: { small?: boolean }) {
  return (
    <div className={`brand-mark ${small ? 'brand-mark--small' : ''}`} aria-hidden="true">
      <span className="brand-node node-a" />
      <span className="brand-node node-b" />
      <span className="brand-node node-c" />
      <span className="brand-link link-a" />
      <span className="brand-link link-b" />
    </div>
  )
}

function NavItem({
  icon: Icon,
  label,
  target,
  active,
  onClick,
}: {
  icon: typeof LayoutDashboard
  label: string
  target: string
  active: boolean
  onClick: (target: string) => void
}) {
  return (
    <button className={`nav-item ${active ? 'active' : ''}`} onClick={() => onClick(target)}>
      <Icon size={18} strokeWidth={1.8} />
      <span>{label}</span>
      {active && <span className="nav-indicator" />}
    </button>
  )
}

function StatCard({
  label,
  value,
  detail,
  icon: Icon,
  tone,
  delay,
}: {
  label: string
  value: string | number
  detail: string
  icon: typeof Activity
  tone: string
  delay: number
}) {
  return (
    <article className={`stat-card tone-${tone} reveal`} style={{ animationDelay: `${delay}ms` }}>
      <div className="stat-top">
        <span className="stat-label">{label}</span>
        <span className="stat-icon"><Icon size={18} /></span>
      </div>
      <strong>{value}</strong>
      <span className="stat-detail">{detail}</span>
      <span className="stat-accent" />
    </article>
  )
}

function SectionHeading({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow: string
  title: string
  description: string
  action?: ReactNode
}) {
  return (
    <div className="section-heading">
      <div>
        <span className="eyebrow">{eyebrow}</span>
        <h2>{title}</h2>
        <p>{description}</p>
      </div>
      {action}
    </div>
  )
}

function RiskBadge({ level }: { level: string }) {
  const normalized = level.toLowerCase()
  return <span className={`risk-badge risk-${normalized}`}><span />{level}</span>
}

function ImpactGraph({ analysis }: { analysis: DemoBundle['analysis'] }) {
  const [selected, setSelected] = useState('order')
  const graphNodes = [
    { key: 'supplier', icon: Building2, label: 'Supplier', value: analysis.supplier.supplier_id, meta: analysis.supplier.supplier_name.split(' ')[0] },
    { key: 'part', icon: Boxes, label: 'Parts', value: `${analysis.affected_parts.length} affected`, meta: analysis.affected_parts.map((part) => part.part_id.replace('PRT-', '')).join(' · ') },
    { key: 'plant', icon: Factory, label: 'Plants', value: `${analysis.affected_plants.length} at risk`, meta: analysis.affected_plants.map((plant) => plant.city).join(' · ') },
    { key: 'shipment', icon: Truck, label: 'Shipments', value: `${analysis.affected_shipments.length} delayed`, meta: `+${analysis.delay_days} days` },
    { key: 'order', icon: PackageCheck, label: 'Orders', value: `${analysis.open_orders.length} at risk`, meta: `${shortMoney(analysis.risk_summary.revenue_at_risk)} value` },
    { key: 'customer', icon: Users, label: 'Customers', value: `${analysis.affected_customers.length} exposed`, meta: `${analysis.affected_customers.filter((customer) => customer.tier === 'Strategic').length} strategic` },
  ]
  return (
    <div className="impact-graph" aria-label="Supply-chain impact path">
      {graphNodes.map((node, index) => {
        const Icon = node.icon
        return (
          <div className="graph-step" key={node.key}>
            <button
              className={`graph-node ${selected === node.key ? 'selected' : ''}`}
              onClick={() => setSelected(node.key)}
              style={{ animationDelay: `${160 + index * 90}ms` }}
            >
              <span className="graph-icon"><Icon size={20} /></span>
              <span className="graph-copy">
                <small>{node.label}</small>
                <strong>{node.value}</strong>
                <em>{node.meta}</em>
              </span>
              {selected === node.key && <Check size={15} className="graph-check" />}
            </button>
            {index < graphNodes.length - 1 && (
              <span className="graph-connector">
                <span className="connector-flow" />
                <ChevronRight size={15} />
              </span>
            )}
          </div>
        )
      })}
    </div>
  )
}

function App() {
  const [bundle, setBundle] = useState<DemoBundle>(demoBundle)
  const [mode, setMode] = useState<'loading' | 'api' | 'preview'>('loading')
  const [activeSection, setActiveSection] = useState('overview')
  const [menuOpen, setMenuOpen] = useState(false)
  const [delayDays, setDelayDays] = useState(14)
  const [investigating, setInvestigating] = useState(false)
  const [selectedAlternative, setSelectedAlternative] = useState<Alternative>(demoBundle.alternatives[0])
  const [evidenceFilter, setEvidenceFilter] = useState('All evidence')
  const [selectedEvidence, setSelectedEvidence] = useState<Evidence | null>(null)
  const [mitigation, setMitigation] = useState<Mitigation | null>(null)
  const [pendingMitigations, setPendingMitigations] = useState<Mitigation[]>([])
  const [drafting, setDrafting] = useState(false)
  const [approving, setApproving] = useState(false)
  const [returning, setReturning] = useState(false)
  const [actorId, setActorId] = useState<ActorId>('maya.iyer')
  const [identity, setIdentity] = useState<Identity | null>(null)
  const [question, setQuestion] = useState('What revenue is at risk if SUP-042 is delayed by 14 days?')
  const [asking, setAsking] = useState(false)
  const [conversation, setConversation] = useState<ConversationAnswer | null>(null)
  const [scenarioComparison, setScenarioComparison] = useState<ScenarioComparison>(previewScenarios)
  const [toast, setToast] = useState<ToastState | null>(null)
  const isDemoIdentity = !identity || identity.identity_source === 'ALLOWLISTED_DEMO_PRINCIPAL'
  const canDraft = identity?.roles.includes('SUPPLY_PLANNER') ?? false
  const canApprove = identity?.roles.includes('MITIGATION_APPROVER') ?? false
  const activeName = identity?.display_name ?? actorProfiles[actorId].name
  const activeTitle = identity?.title ?? actorProfiles[actorId].title
  const activeInitials = activeName.split(/\s+/).map((part) => part[0]).join('').slice(0, 2).toUpperCase()

  const refreshApprovalInbox = useCallback(async () => {
    const response = await fetch('/api/mitigations?status=PENDING_APPROVAL', { headers: { 'X-Demo-Actor': actorId } })
    if (!response.ok) throw new Error(await apiError(response, 'Approval inbox unavailable'))
    const payload = await response.json() as { mitigations: Mitigation[] }
    setPendingMitigations(payload.mitigations)
    setMitigation((current) => {
      const refreshedCurrent = payload.mitigations.find((item) => item.action_id === current?.action_id)
      if (refreshedCurrent) return refreshedCurrent
      if (current && current.status !== 'PENDING_APPROVAL') return current
      return payload.mitigations[0] ?? null
    })
  }, [actorId])

  useEffect(() => {
    fetch('/api/demo?supplier_id=SUP-042&delay_days=14')
      .then((response) => {
        if (!response.ok) throw new Error('API unavailable')
        return response.json() as Promise<DemoBundle>
      })
      .then((payload) => {
        setBundle(payload)
        setSelectedAlternative(payload.alternatives[0])
        setMode('api')
      })
      .catch(() => {
        setMode('preview')
        setToast({ message: 'Governed API unavailable — showing unverified preview data only', tone: 'error' })
      })
  }, [])

  useEffect(() => {
    fetch('/api/session', { headers: { 'X-Demo-Actor': actorId } })
      .then(async (response) => {
        if (!response.ok) throw new Error(await apiError(response, 'Identity verification failed'))
        return response.json() as Promise<Identity>
      })
      .then(setIdentity)
      .catch(() => setIdentity(null))
  }, [actorId])

  useEffect(() => {
    fetch('/api/mitigations?status=PENDING_APPROVAL', { headers: { 'X-Demo-Actor': actorId } })
      .then(async (response) => {
        if (!response.ok) throw new Error(await apiError(response, 'Approval inbox unavailable'))
        return response.json() as Promise<{ mitigations: Mitigation[] }>
      })
      .then((payload) => {
        setPendingMitigations(payload.mitigations)
        setMitigation((current) => {
          const refreshedCurrent = payload.mitigations.find((item) => item.action_id === current?.action_id)
          if (refreshedCurrent) return refreshedCurrent
          if (current && current.status !== 'PENDING_APPROVAL') return current
          return payload.mitigations[0] ?? null
        })
      })
      .catch(() => undefined)
  }, [actorId])

  useEffect(() => {
    fetch('/api/scenarios/compare?supplier_id=SUP-042&delay_days=3&delay_days=7&delay_days=14&delay_days=21')
      .then((response) => {
        if (!response.ok) throw new Error('Scenario comparison unavailable')
        return response.json() as Promise<ScenarioComparison>
      })
      .then(setScenarioComparison)
      .catch(() => undefined)
  }, [])

  useEffect(() => {
    if (!toast) return
    const timer = window.setTimeout(() => setToast(null), 3500)
    return () => window.clearTimeout(timer)
  }, [toast])

  const evidence = useMemo(() => {
    if (evidenceFilter === 'All evidence') return bundle.analysis.evidence
    return bundle.analysis.evidence.filter((item) => item.source_type === evidenceFilter)
  }, [bundle.analysis.evidence, evidenceFilter])
  const provenance = bundle.provenance ?? {
    ...demoBundle.provenance,
    repository_mode: bundle.analysis.source_system.startsWith('SNOWFLAKE_') ? 'snowflake' as const : 'fixture' as const,
    source_system: bundle.analysis.source_system,
    snapshot_loaded_at: bundle.analysis.generated_at,
    metric_lineage: 'Deterministic metric v1.0 · legacy runtime response',
  }
  const cocoEvaluation = bundle.audit_events.find(
    (event) => event.event_type === 'CORTEX_ANALYST_EVAL',
  )

  const scrollTo = (target: string) => {
    setActiveSection(target)
    setMenuOpen(false)
    document.getElementById(target)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  const switchActor = (nextActor: ActorId) => {
    setActorId(nextActor)
    const profile = actorProfiles[nextActor]
    setToast({ message: `Demo identity switched to ${profile.name} · ${profile.title}`, tone: 'info' })
  }

  const askQuestion = async (nextQuestion = question) => {
    const governedQuestion = nextQuestion.trim()
    if (governedQuestion.length < 3) {
      setToast({ message: 'Enter a supply-chain question first', tone: 'error' })
      return
    }
    setQuestion(governedQuestion)
    setAsking(true)
    try {
      const response = await fetch('/api/conversation', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Demo-Actor': actorId },
        body: JSON.stringify({ question: governedQuestion }),
      })
      if (!response.ok) throw new Error(await apiError(response, 'Governed answer failed'))
      const answer = await response.json() as ConversationAnswer
      setConversation(answer)
      setToast({
        message: answer.status === 'ANSWERED' ? `Grounded answer ${answer.correlation_id} generated` : answer.answer,
        tone: answer.status === 'ANSWERED' ? 'success' : 'info',
      })
    } catch (error) {
      setToast({ message: `${error instanceof Error ? error.message : 'Governed answer failed'} — no answer was fabricated`, tone: 'error' })
    } finally {
      setAsking(false)
    }
  }

  const runInvestigation = async () => {
    setInvestigating(true)
    const started = Date.now()
    try {
      const supplierId = bundle.analysis.supplier.supplier_id
      const response = await fetch(`/api/demo?supplier_id=${encodeURIComponent(supplierId)}&delay_days=${delayDays}`)
      if (!response.ok) throw new Error('Could not run workflow')
      const payload = await response.json() as DemoBundle
      const remaining = Math.max(0, 700 - (Date.now() - started))
      await new Promise((resolve) => window.setTimeout(resolve, remaining))
      setBundle(payload)
      if (payload.alternatives.length > 0) setSelectedAlternative(payload.alternatives[0])
      setMode('api')
      setToast({ message: `Investigation ${payload.analysis.correlation_id} completed`, tone: 'success' })
    } catch (error) {
      await new Promise((resolve) => window.setTimeout(resolve, 700))
      setMode('preview')
      setToast({ message: `${error instanceof Error ? error.message : 'Investigation failed'} — last verified result preserved`, tone: 'error' })
    } finally {
      setInvestigating(false)
    }
  }

  const createDraft = async () => {
    setDrafting(true)
    const body = {
      disruption_context: {
        supplier_id: bundle.analysis.supplier.supplier_id,
        delay_days: delayDays,
        correlation_id: bundle.analysis.correlation_id,
      },
      selected_mitigation_option: selectedAlternative,
    }
    try {
      const response = await fetch('/api/mitigations/draft', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Demo-Actor': actorId },
        body: JSON.stringify(body),
      })
      if (!response.ok) throw new Error(await apiError(response, 'Draft rejected'))
      const created = await response.json() as Mitigation
      setMitigation(created)
      setPendingMitigations((current) => [
        created,
        ...current.filter((item) => item.action_id !== created.action_id),
      ])
      setMode('api')
      setToast({ message: 'Governed draft created — switch to Aisha for an independent decision', tone: 'success' })
    } catch (error) {
      setToast({ message: `${error instanceof Error ? error.message : 'Draft rejected'} — no draft was created`, tone: 'error' })
    } finally {
      setDrafting(false)
    }
  }

  const approveDraft = async () => {
    if (!mitigation) return
    setApproving(true)
    try {
      const response = await fetch(`/api/mitigations/${mitigation.action_id}/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Demo-Actor': actorId },
        body: JSON.stringify({
          reason: 'Approved after reviewing governed impact, evidence, and supplier qualification.',
          expected_version: mitigation.version,
          idempotency_key: `approve-${mitigation.action_id}-v${mitigation.version}`,
        }),
      })
      if (!response.ok) {
        if (response.status === 409) await refreshApprovalInbox()
        throw new Error(await apiError(response, 'Approval failed'))
      }
      const approved = await response.json() as Mitigation
      setMitigation(approved)
      setPendingMitigations((current) => current.filter((item) => item.action_id !== approved.action_id))
      setToast({ message: 'Human approval recorded after all policy checks passed', tone: 'success' })
    } catch (error) {
      setToast({ message: `${error instanceof Error ? error.message : 'Approval failed'} — pending state preserved`, tone: 'error' })
    } finally {
      setApproving(false)
    }
  }

  const returnDraft = async () => {
    if (!mitigation) return
    setReturning(true)
    const reason = 'Recheck premium freight assumptions before approval.'
    try {
      const response = await fetch(`/api/mitigations/${mitigation.action_id}/return-for-revision`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Demo-Actor': actorId },
        body: JSON.stringify({
          reason,
          expected_version: mitigation.version,
          idempotency_key: `revise-${mitigation.action_id}-v${mitigation.version}`,
        }),
      })
      if (!response.ok) {
        if (response.status === 409) await refreshApprovalInbox()
        throw new Error(await apiError(response, 'Return for revision failed'))
      }
      const returned = await response.json() as Mitigation
      setMitigation(returned)
      setPendingMitigations((current) => current.filter((item) => item.action_id !== returned.action_id))
      setMode('api')
      setToast({ message: 'Draft returned for revision — no external action executed', tone: 'success' })
    } catch (error) {
      setToast({ message: `${error instanceof Error ? error.message : 'Revision decision failed'} — pending state preserved`, tone: 'error' })
    } finally {
      setReturning(false)
    }
  }

  return (
    <div className="app-shell">
      <aside className={`sidebar ${menuOpen ? 'open' : ''}`}>
        <button className="mobile-close" onClick={() => setMenuOpen(false)} aria-label="Close navigation"><X size={20} /></button>
        <div className="brand">
          <BrandMark />
          <div><strong>SupplyChain</strong><span>Trust Graph</span></div>
        </div>

        <div className="sidebar-context">
          <span className="context-dot" />
          <div><small>Workspace</small><strong>Global operations</strong></div>
          <ChevronDown size={15} />
        </div>

        <nav>
          <span className="nav-label">Command center</span>
          <NavItem icon={LayoutDashboard} label="Overview" target="overview" active={activeSection === 'overview'} onClick={scrollTo} />
          <NavItem icon={Activity} label="Scenario planner" target="scenarios" active={activeSection === 'scenarios'} onClick={scrollTo} />
          <NavItem icon={Sparkles} label="Ask the graph" target="conversation" active={activeSection === 'conversation'} onClick={scrollTo} />
          <NavItem icon={Search} label="Investigation" target="investigation" active={activeSection === 'investigation'} onClick={scrollTo} />
          <NavItem icon={FileCheck2} label="Evidence" target="evidence" active={activeSection === 'evidence'} onClick={scrollTo} />
          <NavItem icon={Route} label="Mitigation" target="mitigation" active={activeSection === 'mitigation'} onClick={scrollTo} />
          <NavItem icon={Fingerprint} label="Approval & audit" target="approval" active={activeSection === 'approval'} onClick={scrollTo} />
        </nav>

        <div className="governance-card">
          <span className="shield-wrap"><ShieldCheck size={20} /></span>
          <div>
            <strong>Governance active</strong>
            <p>Deterministic answers. Segregated human approval.</p>
          </div>
          <span className="governance-state">7 POLICY GATES ON</span>
        </div>

        <div className="sidebar-footer">
          <div className="avatar">{activeInitials}</div>
          <div><strong>{activeName}</strong><span>{activeTitle}</span></div>
          <span className={`identity-status ${identity ? 'verified' : ''}`} title={identity?.identity_source}>{identity ? 'Verified' : 'Offline'}</span>
        </div>
        {isDemoIdentity && <div className="identity-switcher" aria-label="Demo identity">
          <button className={actorId === 'maya.iyer' ? 'active' : ''} onClick={() => switchActor('maya.iyer')}>Planner</button>
          <button className={actorId === 'aisha.rao' ? 'active' : ''} onClick={() => switchActor('aisha.rao')}>Approver</button>
        </div>}
      </aside>

      {menuOpen && <button className="sidebar-scrim" onClick={() => setMenuOpen(false)} aria-label="Close menu" />}

      <main>
        <header className="topbar">
          <button className="menu-button" onClick={() => setMenuOpen(true)} aria-label="Open navigation"><Menu size={20} /></button>
          <div className="breadcrumbs"><span>Supply chain</span><ChevronRight size={14} /><strong>Control tower</strong></div>
          <div className="topbar-actions">
            {mode === 'api' && cocoEvaluation && (
              <span
                className="coco-credit-pill"
                title={`${cocoEvaluation.summary} · ${cocoEvaluation.audit_id}`}
              >
                <Sparkles size={13} />CoCo credits · 3/3 verified
              </span>
            )}
            <span className={`source-pill ${mode}`}><Database size={14} />{mode === 'api' ? (provenance.repository_mode === 'snowflake' ? 'Snowflake governed' : 'Governed fixture') : mode === 'loading' ? 'Connecting' : 'Unverified preview'}</span>
            <span className="updated">Loaded {prettyTime(provenance.snapshot_loaded_at)}</span>
            <button className="icon-button" onClick={runInvestigation} aria-label="Refresh"><RefreshCw size={17} /></button>
          </div>
        </header>

        <div className="page">
          {mode === 'preview' && (
            <div className="fail-closed-banner" role="alert"><AlertTriangle size={17} /><span><strong>Fail-closed mode:</strong> preview data is visible, but investigations and state-changing actions require the governed API.</span></div>
          )}
          <section id="overview" className="hero page-section">
            <div className="hero-copy reveal">
              <div className="eyebrow-row"><span className="eyebrow">OPERATIONS CONTROL TOWER</span><span className="live-pill"><i />1 active disruption</span></div>
              <h1>Know what’s at risk.<br /><span>Prove every decision.</span></h1>
              <p>Trace disruption impact across your supply network using governed definitions, connected evidence, and approval-safe actions.</p>
            </div>
            <div className="hero-trust reveal" style={{ animationDelay: '100ms' }}>
              <div className="trust-ring"><ShieldCheck size={25} /></div>
              <div><small>Trust posture</small><strong>All controls active</strong><span>{provenance.policy_checks.length}/{provenance.policy_checks.length} policy checks passed</span></div>
              <ChevronRight size={18} />
            </div>
          </section>

          <section className="stats-grid" aria-label="Executive summary">
            <StatCard label="Revenue at risk" value={shortMoney(bundle.summary.revenue_at_risk)} detail={`Across ${bundle.analysis.open_orders.length} open orders`} icon={CircleDollarSign} tone="red" delay={100} />
            <StatCard label="Plants at stockout risk" value={bundle.summary.plants_at_risk} detail={bundle.analysis.affected_plants.map((plant) => plant.city).join(' · ') || 'No plant exposed'} icon={Factory} tone="amber" delay={160} />
            <StatCard label="Orders at risk" value={bundle.summary.orders_at_risk} detail={`${bundle.analysis.affected_customers.filter((customer) => customer.tier === 'Strategic').length} strategic customers`} icon={PackageCheck} tone="indigo" delay={220} />
            <StatCard label="Pending approvals" value={mode === 'api' ? pendingMitigations.length : bundle.summary.pending_approvals} detail={pendingMitigations.length > 0 ? `${pendingMitigations.length} governed action${pendingMitigations.length === 1 ? '' : 's'} waiting` : 'No action waiting'} icon={UserCheck} tone="blue" delay={280} />
          </section>

          <section id="scenarios" className="page-section scenario-section">
            <SectionHeading
              eyebrow="Decision threshold explorer"
              title="See when disruption becomes material"
              description="Compare the same governed supply and demand records across multiple delay assumptions before choosing a response."
              action={<span className="policy-chip"><ShieldCheck size={14} />Quantity-aware metric</span>}
            />
            <div className="scenario-panel panel">
              <div className="scenario-list">
                {scenarioComparison.scenarios.map((scenario) => {
                  const maxRisk = Math.max(...scenarioComparison.scenarios.map((item) => item.revenue_at_risk), 1)
                  return (
                    <button key={scenario.delay_days} className={`scenario-row ${delayDays === scenario.delay_days ? 'selected' : ''}`} onClick={() => setDelayDays(scenario.delay_days)}>
                      <span className="scenario-delay"><Clock3 size={15} /><strong>{scenario.delay_days} days</strong></span>
                      <span className="scenario-bar"><i style={{ width: `${Math.max(2, scenario.revenue_at_risk / maxRisk * 100)}%` }} /></span>
                      <span className="scenario-value"><strong>{shortMoney(scenario.revenue_at_risk)}</strong><small>{scenario.orders_at_risk} orders · {scenario.plants_at_risk} plants</small></span>
                      <RiskBadge level={scenario.severity} />
                    </button>
                  )
                })}
              </div>
              <aside className="scenario-threshold">
                <span><Activity size={18} />First material exposure</span>
                <strong>{scenarioComparison.first_exposure_delay_days ? `${scenarioComparison.first_exposure_delay_days} days` : 'No exposure'}</strong>
                <p>The threshold is derived from protected inventory, on-time inbound quantities, and cumulative customer demand.</p>
                <button className="secondary-button" onClick={() => { scrollTo('investigation'); void runInvestigation() }}>Run selected scenario<ArrowRight size={15} /></button>
              </aside>
            </div>
          </section>

          <section id="conversation" className="page-section conversation-section">
            <SectionHeading
              eyebrow="Governed conversational analytics"
              title="Ask the trust graph"
              description="Natural language chooses an allowlisted tool path; metrics and facts still come only from governed code and source records."
              action={<span className="policy-chip"><ShieldCheck size={14} />Deterministic tools only</span>}
            />
            <div className="conversation-panel panel">
              <div className="conversation-intro">
                <span className="conversation-mark"><Sparkles size={22} /></span>
                <div><strong>Supply-chain analyst</strong><p>I will ask for missing identifiers and reject requests that bypass approval or invent data.</p></div>
                <span className="answer-policy">NO FREE-FORM METRICS</span>
              </div>
              <div className="prompt-suggestions" aria-label="Suggested questions">
                {[
                  'What revenue is at risk if SUP-042 is delayed by 14 days?',
                  'What is the inventory risk for PRT-AX14 at PLT-PUN?',
                  'Which approved alternatives exist for PRT-AX14 at PLT-PUN?',
                ].map((suggestion) => (
                  <button key={suggestion} onClick={() => askQuestion(suggestion)}>{suggestion}</button>
                ))}
              </div>
              <form className="conversation-form" onSubmit={(event) => { event.preventDefault(); askQuestion() }}>
                <Search size={18} />
                <input value={question} onChange={(event) => setQuestion(event.target.value)} aria-label="Ask a governed supply-chain question" />
                <button className="primary-button" type="submit" disabled={asking || mode !== 'api'}>
                  {asking ? <><RefreshCw size={16} className="spin" />Grounding…</> : <><Send size={16} />Ask graph</>}
                </button>
              </form>
              {conversation ? (
                <div className={`conversation-answer answer-${conversation.status.toLowerCase().replaceAll('_', '-')}`}>
                  <div className="answer-head">
                    <span>{conversation.status === 'ANSWERED' ? <ShieldCheck size={18} /> : <Info size={18} />}</span>
                    <div><small>{conversation.intent.replaceAll('_', ' ')}</small><strong>{conversation.status.replaceAll('_', ' ')}</strong></div>
                    <code>{conversation.correlation_id}</code>
                  </div>
                  <p>{conversation.answer}</p>
                  {conversation.facts && conversation.facts.length > 0 && (
                    <div className="answer-facts">
                      {conversation.facts.map((fact) => <div key={fact.label}><span>{fact.label}</span><strong>{fact.value}</strong></div>)}
                    </div>
                  )}
                  <div className="answer-lineage">
                    <span><GitBranch size={14} />Tools: {conversation.tool_calls.length ? conversation.tool_calls.join(' → ') : 'none'}</span>
                    <span><Fingerprint size={14} />Audit: {conversation.audit_id}</span>
                  </div>
                  {conversation.source_references.length > 0 && (
                    <div className="answer-sources">
                      <small>Source references</small>
                      <div>{conversation.source_references.map((reference) => {
                        const source = conversation.evidence?.find((item) => item.reference_id === reference)
                        return source ? <button key={reference} onClick={() => setSelectedEvidence(source)}>{reference}</button> : <code key={reference}>{reference}</code>
                      })}</div>
                    </div>
                  )}
                </div>
              ) : (
                <div className="conversation-empty"><Database size={18} /><span>No generated answer yet. Try the revenue-at-risk question for the judging flow.</span></div>
              )}
            </div>
          </section>

          <section id="investigation" className="page-section investigation-section">
            <SectionHeading
              eyebrow="Disruption investigation"
              title="Trace the blast radius"
              description="Follow the governed relationships from supplier delay to customer impact."
              action={<span className="correlation"><Link2 size={14} />{bundle.analysis.correlation_id}</span>}
            />

            <div className="investigation-layout">
              <div className="investigation-main panel">
                <div className="disruption-toolbar">
                  <div className="supplier-select">
                    <span className="supplier-logo">NW</span>
                    <div><small>Active supplier</small><strong>{bundle.analysis.supplier.supplier_id} · {bundle.analysis.supplier.supplier_name}</strong></div>
                  </div>
                  <div className="delay-input">
                    <label htmlFor="delay-days">Reported delay</label>
                    <div><input id="delay-days" type="number" min="1" max="90" value={delayDays} onChange={(event) => setDelayDays(Number(event.target.value))} /><span>days</span></div>
                  </div>
                  <button className="primary-button" onClick={runInvestigation} disabled={investigating}>
                    {investigating ? <><RefreshCw size={17} className="spin" />Tracing impact…</> : <><Sparkles size={17} />Run investigation</>}
                  </button>
                </div>

                <div className="impact-summary">
                  <div className="severity-marker"><AlertTriangle size={21} /></div>
                  <div><RiskBadge level={bundle.analysis.risk_summary.severity} /><h3>{bundle.analysis.risk_summary.headline}</h3><p>{bundle.analysis.risk_summary.narrative}</p></div>
                  <div className="confidence"><span>Evidence coverage</span><strong>{provenance.evidence_coverage_percent}%</strong><div><i style={{ width: `${provenance.evidence_coverage_percent}%` }} /></div></div>
                </div>

                <div className="graph-heading"><div><GitBranch size={17} /><strong>Connected impact path</strong></div><span>Click a node to inspect</span></div>
                <ImpactGraph analysis={bundle.analysis} />
              </div>

              <aside className="explanation-card panel">
                <div className="explanation-head"><span><Sparkles size={16} />Governed explanation</span><span className="grounded">GROUNDED</span></div>
                <h3>Why is revenue at risk?</h3>
                <p>{bundle.analysis.risk_summary.narrative}</p>
                <div className="formula-card">
                  <small>REVENUE AT RISK · V1.0</small>
                  <div><span>Affected open orders</span><strong>{money.format(bundle.analysis.risk_summary.revenue_at_risk)}</strong></div>
                  <div><span>Protected / excluded orders</span><strong>{money.format(bundle.analysis.risk_summary.protected_order_value ?? 0)}</strong></div>
                  <div className="formula-total"><span>Governed result</span><strong>{money.format(bundle.analysis.risk_summary.revenue_at_risk)}</strong></div>
                </div>
                <button className="text-button" onClick={() => scrollTo('evidence')}>View calculation evidence<ArrowRight size={15} /></button>
              </aside>
            </div>

            <div className="orders-card panel">
              <div className="card-title-row">
                <div><h3>Customer orders at risk</h3><p>Only orders failing the governed availability test are shown.</p></div>
                <span className="count-pill">{bundle.analysis.open_orders.length} orders</span>
              </div>
              <div className="table-scroll">
                <table>
                  <thead><tr><th>Order</th><th>Customer</th><th>Required</th><th>Part / plant</th><th>Order value</th><th>Impact</th></tr></thead>
                  <tbody>
                    {bundle.analysis.open_orders.map((order) => (
                      <tr key={order.order_id}>
                        <td><strong>{order.order_id}</strong><span>{order.quantity} units</span></td>
                        <td><strong>{order.customer_name}</strong><span className={`tier tier-${order.customer_tier.toLowerCase()}`}>{order.customer_tier}</span></td>
                        <td><strong>{prettyDate(order.required_date)}</strong><span>{order.reason.split(' ').slice(0, 5).join(' ')}</span></td>
                        <td><strong>{order.part_id}</strong><span>{order.plant_id}</span></td>
                        <td><strong>{money.format(order.order_value)}</strong></td>
                        <td><RiskBadge level={order.impact_severity} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </section>

          <section id="evidence" className="page-section evidence-section">
            <SectionHeading eyebrow="Evidence ledger" title="Every answer has a source" description="Inspect source records, timestamps, and the assumptions behind this investigation." />
            <div className="evidence-layout">
              <div className="evidence-list panel">
                <div className="filter-row">
                  {['All evidence', 'Supplier notice', 'Shipment scenario', 'Governed metric'].map((filter) => (
                    <button key={filter} className={filter === evidenceFilter ? 'active' : ''} onClick={() => setEvidenceFilter(filter)}>{filter}</button>
                  ))}
                </div>
                <div className="evidence-items">
                  {evidence.map((item, index) => (
                    <article className="evidence-item" key={item.reference_id} style={{ animationDelay: `${index * 70}ms` }}>
                      <span className={`evidence-type type-${item.source_type.toLowerCase().replace(' ', '-')}`}>
                        {item.source_type === 'Supplier notice' ? <FileText size={18} /> : item.source_type === 'Governed metric' ? <ShieldCheck size={18} /> : <Truck size={18} />}
                      </span>
                      <div className="evidence-body">
                        <div><span>{item.source_type}</span><code>{item.reference_id}</code></div>
                        <h3>{item.title}</h3><p>{item.detail}</p>
                        <small><Database size={12} />{item.source_system}<i />{item.evidence_status === 'SCENARIO_PROJECTION' ? 'Source updated' : 'Observed'} {prettyTime(item.observed_at)}</small>
                      </div>
                      <button aria-label={`Open ${item.reference_id}`} onClick={() => setSelectedEvidence(item)}><ArrowRight size={17} /></button>
                    </article>
                  ))}
                </div>
              </div>
              <aside className="assumptions panel">
                <div className="assumption-icon"><Info size={20} /></div>
                <h3>Calculation assumptions</h3>
                <p>Explicit inputs applied by the governed workflow. The model is never allowed to silently fill a gap.</p>
                <ul>{bundle.analysis.assumptions.map((item) => <li key={item}><CheckCircle2 size={16} /><span>{item}</span></li>)}</ul>
                <div className="freshness"><span><Clock3 size={15} />Snapshot loaded</span><strong>{prettyTime(provenance.snapshot_loaded_at)}</strong></div>
                <div className="lineage"><span><GitBranch size={15} />Metric lineage</span><strong>{provenance.metric_lineage}</strong></div>
                <div className="lineage"><span><ShieldCheck size={15} />Semantic cross-check</span><strong>{provenance.semantic_validation.status}</strong></div>
                {provenance.query_ids.length > 0 && <div className="lineage"><span><Fingerprint size={15} />Snowflake query</span><strong>{provenance.query_ids.at(-1)}</strong></div>}
              </aside>
            </div>
          </section>

          <section id="mitigation" className="page-section mitigation-section">
            <SectionHeading eyebrow="Mitigation planner" title="Choose a safe recovery path" description="Only qualified, approved supplier-part-plant combinations are eligible." action={<span className="policy-chip"><LockKeyhole size={14} />Approved sources only</span>} />
            <div className="mitigation-layout">
              <div className="alternatives panel">
                <div className="card-title-row"><div><h3>Ranked alternatives</h3><p>Scored by arrival, coverage, cost, and customer priority.</p></div><span className="count-pill">{bundle.alternatives.length} eligible</span></div>
                <div className="alternative-list">
                  {bundle.alternatives.map((alternative) => (
                    <button key={`${alternative.supplier_id}-${alternative.part_id}`} className={`alternative ${selectedAlternative.supplier_id === alternative.supplier_id && selectedAlternative.part_id === alternative.part_id ? 'selected' : ''}`} onClick={() => setSelectedAlternative(alternative)}>
                      <span className="rank">#{alternative.recommendation_rank}</span>
                      <span className="alternative-main"><span><strong>{alternative.supplier_name}</strong><em><ShieldCheck size={13} />Approved</em></span><small>{alternative.supplier_id} · {alternative.part_id} → {alternative.plant_id}</small><p>{alternative.tradeoff}</p></span>
                      <span className="alternative-metrics"><span><small>Lead time</small><strong>{alternative.lead_time_days} days</strong></span><span><small>Capacity</small><strong>{alternative.available_capacity} units</strong></span><span><small>Cost</small><strong>{alternative.cost_band}</strong></span><span><small>Coverage</small><strong>{alternative.coverage_percent}%</strong></span></span>
                      <span className="radio"><i /></span>
                    </button>
                  ))}
                </div>
              </div>

              <aside className="recommendation panel">
                <div className="recommendation-label"><Sparkles size={16} />Recommended action</div>
                <h3>Source {selectedAlternative.part_id} from {selectedAlternative.supplier_name}</h3>
                <p>{selectedAlternative.tradeoff}</p>
                <div className="recommendation-flow">
                  <span><strong>{selectedAlternative.supplier_id}</strong><small>Alternative</small></span><ArrowRight size={16} /><span><strong>{selectedAlternative.available_capacity}</strong><small>Units</small></span><ArrowRight size={16} /><span><strong>{selectedAlternative.plant_id.replace('PLT-', '')}</strong><small>Plant</small></span>
                </div>
                <div className="impact-benefit"><span><CircleDollarSign size={18} /></span><div><small>Capacity-weighted protected revenue</small><strong>{shortMoney(selectedAlternative.estimated_protected_revenue ?? Math.round(bundle.analysis.risk_summary.revenue_at_risk * selectedAlternative.coverage_percent / 100))}</strong></div></div>
                <div className="safety-note"><LockKeyhole size={15} /><span>Creates a draft only. No supplier or purchase order will be changed.</span></div>
                <button className="primary-button full" onClick={createDraft} disabled={drafting || !canDraft || mode !== 'api'}>{drafting ? <><RefreshCw size={17} className="spin" />Creating governed draft…</> : <><FileCheck2 size={17} />Create mitigation draft</>}</button>
                <div className="role-requirement"><UserCheck size={14} /><span>{canDraft ? 'Planner role verified for drafting' : isDemoIdentity ? 'Switch to Maya · Planner to create a draft' : 'Your Snowflake identity has read-only access'}</span></div>
              </aside>
            </div>
          </section>

          <section id="approval" className="page-section approval-section">
            <SectionHeading eyebrow="Approval & audit" title="Control stays with people" description="Recommendations remain inert until an authorized, independent human records a decision." action={<span className="policy-chip"><UserCheck size={14} />Acting as {activeName}</span>} />
            <div className="approval-layout">
              <div className={`approval-gate panel ${mitigation ? 'has-draft' : ''} ${mitigation?.status === 'APPROVED' ? 'approved' : ''} ${mitigation?.status === 'RETURNED_FOR_REVISION' ? 'returned' : ''}`}>
                {pendingMitigations.length > 0 && (
                  <div className="approval-inbox" aria-label="Pending approval inbox">
                    <span><UserCheck size={14} /><strong>Approval inbox</strong><em>{pendingMitigations.length}</em></span>
                    <div>{pendingMitigations.map((item) => <button key={item.action_id} className={mitigation?.action_id === item.action_id ? 'active' : ''} onClick={() => setMitigation(item)}><strong>{item.action_id}</strong><small>{item.proposed_supplier_id} · {item.part_id} → {item.plant_id}</small></button>)}</div>
                  </div>
                )}
                {!mitigation ? (
                  <div className="empty-approval"><span><UserCheck size={26} /></span><h3>No actions awaiting approval</h3><p>Select an approved alternative and create a mitigation draft to begin the controlled approval flow.</p><button className="secondary-button" onClick={() => scrollTo('mitigation')}>Open mitigation planner<ArrowRight size={15} /></button></div>
                ) : (
                  <>
                    <div className="approval-head">
                      <span className="approval-icon">{mitigation.status === 'APPROVED' ? <CheckCircle2 size={23} /> : mitigation.status === 'RETURNED_FOR_REVISION' ? <XCircle size={23} /> : <Clock3 size={23} />}</span>
                      <div><span>{mitigation.status === 'APPROVED' ? 'Decision recorded' : mitigation.status === 'RETURNED_FOR_REVISION' ? 'Planner update required' : 'Human decision required'}</span><h3>{mitigation.status.replaceAll('_', ' ')}</h3></div>
                      <code>{mitigation.action_id}</code>
                    </div>
                    <div className="approval-detail-grid">
                      <div><span>Action</span><strong>Source from approved alternative</strong></div><div><span>Supplier</span><strong>{mitigation.proposed_supplier_id}</strong></div><div><span>Part / plant</span><strong>{mitigation.part_id} · {mitigation.plant_id}</strong></div><div><span>Owner</span><strong>{mitigation.owner}</strong></div><div><span>Action version</span><strong>v{mitigation.version}</strong></div><div><span>Policy decision</span><strong>{mitigation.policy_decision_id}</strong></div>
                    </div>
                    {mitigation.status === 'PENDING_APPROVAL' ? (
                      <><div className="approval-role-gate"><LockKeyhole size={15} /><span>{canApprove ? 'Approver role verified · owner separation enforced server-side' : isDemoIdentity ? 'Switch to Aisha · Approver to record an independent decision' : 'Your Snowflake identity is not an approver'}</span></div><div className="approval-actions"><button className="reject-button" onClick={returnDraft} disabled={returning || !canApprove}>{returning ? <><RefreshCw size={17} className="spin" />Returning…</> : <><XCircle size={17} />Return for revision</>}</button><button className="approve-button" onClick={approveDraft} disabled={approving || !canApprove}>{approving ? <><RefreshCw size={17} className="spin" />Recording…</> : <><CheckCircle2 size={17} />Approve action</>}</button></div></>
                    ) : mitigation.status === 'APPROVED' ? (
                      <div className="approved-banner"><CheckCircle2 size={18} /><div><strong>Approved by {mitigation.approved_by}</strong><span>Approval is recorded; execution remains a separate downstream step.</span></div></div>
                    ) : (
                      <div className="returned-banner"><XCircle size={18} /><div><strong>Returned by {mitigation.returned_by}</strong><span>{mitigation.revision_reason} No external action was executed.</span></div></div>
                    )}
                  </>
                )}
              </div>
              <div className="audit-timeline panel">
                <div className="card-title-row"><div><h3>Attributable audit trail</h3><p>Append-only event contract with correlation IDs</p></div><Fingerprint size={20} /></div>
                <div className="timeline">
                  {mitigation && <div className="timeline-item new"><span><FileCheck2 size={14} /></span><div><strong>{mitigation.status === 'APPROVED' ? 'Human approval recorded' : mitigation.status === 'RETURNED_FOR_REVISION' ? 'Returned for revision' : 'Mitigation draft created'}</strong><p>{mitigation.status === 'APPROVED' ? mitigation.approved_by : mitigation.status === 'RETURNED_FOR_REVISION' ? mitigation.returned_by : mitigation.owner}</p><small>Just now · {mitigation.audit_id}</small></div></div>}
                  {bundle.audit_events.map((event) => <div className="timeline-item" key={event.audit_id}><span><Activity size={14} /></span><div><strong>{event.event_type.replaceAll('_', ' ').toLowerCase()}</strong><p>{event.summary}</p><small>{prettyTime(event.created_at)} · {event.audit_id}</small></div></div>)}
                </div>
              </div>
            </div>
          </section>

          <footer>
            <div><BrandMark small /><span>SupplyChain Trust Graph</span></div>
            <p>Governed by Snowflake · Orchestrated through the Supply Chain Management MCP Server</p>
            <span>Demo environment · Synthetic data</span>
          </footer>
        </div>
      </main>

      {selectedEvidence && (
        <div className="evidence-modal-backdrop" onMouseDown={() => setSelectedEvidence(null)}>
          <section className="evidence-modal" role="dialog" aria-modal="true" aria-labelledby="evidence-detail-title" onMouseDown={(event) => event.stopPropagation()}>
            <div className="evidence-modal-head">
              <span className={`evidence-type type-${selectedEvidence.source_type.toLowerCase().replace(' ', '-')}`}><FileCheck2 size={19} /></span>
              <div><span>{selectedEvidence.source_type}</span><code>{selectedEvidence.reference_id}</code></div>
              <button onClick={() => setSelectedEvidence(null)} aria-label="Close evidence detail"><X size={18} /></button>
            </div>
            <h2 id="evidence-detail-title">{selectedEvidence.title}</h2>
            <p>{selectedEvidence.detail}</p>
            <dl><div><dt>Source system</dt><dd>{selectedEvidence.source_system}</dd></div><div><dt>{selectedEvidence.evidence_status === 'SCENARIO_PROJECTION' ? 'Source updated' : 'Observed'}</dt><dd>{prettyTime(selectedEvidence.observed_at)}</dd></div><div><dt>Status</dt><dd>{selectedEvidence.evidence_status?.replaceAll('_', ' ') ?? 'RECORDED'}</dd></div></dl>
            <div className="evidence-verified"><ShieldCheck size={17} /><span>{selectedEvidence.evidence_status === 'SCENARIO_PROJECTION' ? 'Projection derived from a recorded shipment and the selected delay assumption.' : 'Verified source record linked to this governed investigation.'}</span></div>
          </section>
        </div>
      )}
      {toast && <div className={`toast toast-${toast.tone}`}>{toast.tone === 'error' ? <XCircle size={18} /> : toast.tone === 'info' ? <Info size={18} /> : <CheckCircle2 size={18} />}<span>{toast.message}</span></div>}
    </div>
  )
}

export default App
