-- Migration: 0001_initial_schema.sql
-- Description: Initial schema, updated_at triggers, and RLS policies for CloudDesk Support Platform
-- Date: 2026-10-28

BEGIN;

-- ============================================================================
-- 1. FUNCTIONS & TRIGGERS
-- ============================================================================
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 2. CORE TABLES DDL
-- ============================================================================
CREATE TABLE IF NOT EXISTS profiles (
    id VARCHAR(36) PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    full_name VARCHAR(255),
    role VARCHAR(50) NOT NULL DEFAULT 'agent',
    avatar_url VARCHAR(512),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TRIGGER trg_profiles_updated_at
    BEFORE UPDATE ON profiles
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE IF NOT EXISTS customers (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    plan VARCHAR(50) NOT NULL DEFAULT 'free',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TRIGGER trg_customers_updated_at
    BEFORE UPDATE ON customers
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE IF NOT EXISTS subscriptions (
    id VARCHAR(36) PRIMARY KEY,
    customer_id VARCHAR(36) NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    plan VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    seats INTEGER NOT NULL DEFAULT 1,
    current_period_end TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TRIGGER trg_subscriptions_updated_at
    BEFORE UPDATE ON subscriptions
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE INDEX IF NOT EXISTS idx_subscriptions_customer ON subscriptions(customer_id);

CREATE TABLE IF NOT EXISTS workspaces (
    id VARCHAR(36) PRIMARY KEY,
    customer_id VARCHAR(36) NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(255) NOT NULL,
    storage_used_bytes BIGINT NOT NULL DEFAULT 0,
    storage_limit_bytes BIGINT NOT NULL DEFAULT 10737418240,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TRIGGER trg_workspaces_updated_at
    BEFORE UPDATE ON workspaces
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE INDEX IF NOT EXISTS idx_workspaces_customer ON workspaces(customer_id);
CREATE INDEX IF NOT EXISTS idx_workspaces_slug ON workspaces(slug);

CREATE TABLE IF NOT EXISTS products (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(255) UNIQUE NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TRIGGER trg_products_updated_at
    BEFORE UPDATE ON products
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE IF NOT EXISTS tickets (
    id VARCHAR(36) PRIMARY KEY,
    customer_id VARCHAR(36) NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    assigned_to VARCHAR(36) REFERENCES profiles(id) ON DELETE SET NULL,
    subject VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'new',
    severity VARCHAR(50) NOT NULL DEFAULT 'medium',
    category VARCHAR(50) NOT NULL DEFAULT 'other',
    channel VARCHAR(50) NOT NULL DEFAULT 'email',
    resolution_summary TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TRIGGER trg_tickets_updated_at
    BEFORE UPDATE ON tickets
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE INDEX IF NOT EXISTS idx_tickets_customer ON tickets(customer_id);
CREATE INDEX IF NOT EXISTS idx_tickets_assigned ON tickets(assigned_to);
CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status);
CREATE INDEX IF NOT EXISTS idx_tickets_severity ON tickets(severity);
CREATE INDEX IF NOT EXISTS idx_tickets_category ON tickets(category);

CREATE TABLE IF NOT EXISTS ticket_messages (
    id VARCHAR(36) PRIMARY KEY,
    ticket_id VARCHAR(36) NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    author_role VARCHAR(50) NOT NULL,
    author_id VARCHAR(255),
    body TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TRIGGER trg_ticket_messages_updated_at
    BEFORE UPDATE ON ticket_messages
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE INDEX IF NOT EXISTS idx_ticket_messages_ticket ON ticket_messages(ticket_id, created_at);

CREATE TABLE IF NOT EXISTS support_articles (
    id VARCHAR(36) PRIMARY KEY,
    slug VARCHAR(255) UNIQUE NOT NULL,
    title VARCHAR(255) NOT NULL,
    category VARCHAR(50) NOT NULL,
    tags JSONB NOT NULL DEFAULT '[]'::jsonb,
    summary TEXT NOT NULL,
    content TEXT NOT NULL,
    published BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TRIGGER trg_support_articles_updated_at
    BEFORE UPDATE ON support_articles
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE INDEX IF NOT EXISTS idx_support_articles_category ON support_articles(category);

CREATE TABLE IF NOT EXISTS incidents (
    id VARCHAR(36) PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    service VARCHAR(100) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'investigating',
    severity VARCHAR(50) NOT NULL DEFAULT 'medium',
    impact_summary TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TRIGGER trg_incidents_updated_at
    BEFORE UPDATE ON incidents
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE INDEX IF NOT EXISTS idx_incidents_service ON incidents(service);
CREATE INDEX IF NOT EXISTS idx_incidents_status ON incidents(status);

CREATE TABLE IF NOT EXISTS workflow_runs (
    id VARCHAR(36) PRIMARY KEY,
    ticket_id VARCHAR(36) NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    status VARCHAR(50) NOT NULL DEFAULT 'queued',
    current_node VARCHAR(100),
    completed_nodes JSONB NOT NULL DEFAULT '[]'::jsonb,
    state JSONB NOT NULL DEFAULT '{}'::jsonb,
    error TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TRIGGER trg_workflow_runs_updated_at
    BEFORE UPDATE ON workflow_runs
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE INDEX IF NOT EXISTS idx_workflow_runs_ticket ON workflow_runs(ticket_id);
CREATE INDEX IF NOT EXISTS idx_workflow_runs_status ON workflow_runs(status);

CREATE TABLE IF NOT EXISTS workflow_events (
    id VARCHAR(36) PRIMARY KEY,
    workflow_id VARCHAR(36) NOT NULL REFERENCES workflow_runs(id) ON DELETE CASCADE,
    ticket_id VARCHAR(36) NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    node_name VARCHAR(100) NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    duration_ms INTEGER NOT NULL DEFAULT 0,
    tokens_used INTEGER NOT NULL DEFAULT 0,
    cost_estimate DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TRIGGER trg_workflow_events_updated_at
    BEFORE UPDATE ON workflow_events
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE INDEX IF NOT EXISTS idx_workflow_events_workflow ON workflow_events(workflow_id);
CREATE INDEX IF NOT EXISTS idx_workflow_events_ticket ON workflow_events(ticket_id);

CREATE TABLE IF NOT EXISTS resolution_actions (
    id VARCHAR(36) PRIMARY KEY,
    workflow_id VARCHAR(36) NOT NULL REFERENCES workflow_runs(id) ON DELETE CASCADE,
    ticket_id VARCHAR(36) NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    action_name VARCHAR(100) NOT NULL,
    action_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    status VARCHAR(50) NOT NULL DEFAULT 'planned',
    result JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TRIGGER trg_resolution_actions_updated_at
    BEFORE UPDATE ON resolution_actions
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE INDEX IF NOT EXISTS idx_resolution_actions_workflow ON resolution_actions(workflow_id);
CREATE INDEX IF NOT EXISTS idx_resolution_actions_ticket ON resolution_actions(ticket_id);

CREATE TABLE IF NOT EXISTS approval_requests (
    id VARCHAR(36) PRIMARY KEY,
    ticket_id VARCHAR(36) NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    workflow_id VARCHAR(36) NOT NULL REFERENCES workflow_runs(id) ON DELETE CASCADE,
    action_name VARCHAR(100) NOT NULL,
    action_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    decided_by VARCHAR(36) REFERENCES profiles(id) ON DELETE SET NULL,
    rejection_reason TEXT,
    decided_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TRIGGER trg_approval_requests_updated_at
    BEFORE UPDATE ON approval_requests
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE INDEX IF NOT EXISTS idx_approval_requests_ticket ON approval_requests(ticket_id);
CREATE INDEX IF NOT EXISTS idx_approval_requests_status ON approval_requests(status);

CREATE TABLE IF NOT EXISTS escalations (
    id VARCHAR(36) PRIMARY KEY,
    ticket_id VARCHAR(36) NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    workflow_id VARCHAR(36) REFERENCES workflow_runs(id) ON DELETE CASCADE,
    target_team VARCHAR(100) NOT NULL,
    policy_reason TEXT NOT NULL,
    severity VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'open',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TRIGGER trg_escalations_updated_at
    BEFORE UPDATE ON escalations
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE INDEX IF NOT EXISTS idx_escalations_ticket ON escalations(ticket_id);
CREATE INDEX IF NOT EXISTS idx_escalations_status ON escalations(status);

CREATE TABLE IF NOT EXISTS customer_memory (
    id VARCHAR(36) PRIMARY KEY,
    customer_id VARCHAR(36) NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    memory_type VARCHAR(50) NOT NULL DEFAULT 'note',
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TRIGGER trg_customer_memory_updated_at
    BEFORE UPDATE ON customer_memory
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE INDEX IF NOT EXISTS idx_customer_memory_customer ON customer_memory(customer_id, created_at);

CREATE TABLE IF NOT EXISTS audit_logs (
    id VARCHAR(36) PRIMARY KEY,
    actor_id VARCHAR(255) NOT NULL,
    client_ip VARCHAR(45) NOT NULL,
    http_method VARCHAR(10) NOT NULL,
    route VARCHAR(255) NOT NULL,
    request_id VARCHAR(36) NOT NULL,
    status_code INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_audit_logs_actor ON audit_logs(actor_id, created_at);
CREATE INDEX IF NOT EXISTS idx_audit_logs_request ON audit_logs(request_id);

-- ============================================================================
-- 3. ROW LEVEL SECURITY (RLS) ACTIVATION
-- ============================================================================
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE customers ENABLE ROW LEVEL SECURITY;
ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE workspaces ENABLE ROW LEVEL SECURITY;
ALTER TABLE products ENABLE ROW LEVEL SECURITY;
ALTER TABLE tickets ENABLE ROW LEVEL SECURITY;
ALTER TABLE ticket_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE support_articles ENABLE ROW LEVEL SECURITY;
ALTER TABLE incidents ENABLE ROW LEVEL SECURITY;
ALTER TABLE workflow_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE workflow_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE resolution_actions ENABLE ROW LEVEL SECURITY;
ALTER TABLE approval_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE escalations ENABLE ROW LEVEL SECURITY;
ALTER TABLE customer_memory ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;

-- ============================================================================
-- 4. SERVICE ROLE POLICIES
-- ============================================================================
CREATE POLICY service_role_profiles ON profiles FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY service_role_customers ON customers FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY service_role_subscriptions ON subscriptions FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY service_role_workspaces ON workspaces FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY service_role_products ON products FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY service_role_tickets ON tickets FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY service_role_ticket_messages ON ticket_messages FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY service_role_support_articles ON support_articles FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY service_role_incidents ON incidents FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY service_role_workflow_runs ON workflow_runs FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY service_role_workflow_events ON workflow_events FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY service_role_resolution_actions ON resolution_actions FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY service_role_approval_requests ON approval_requests FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY service_role_escalations ON escalations FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY service_role_customer_memory ON customer_memory FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY service_role_audit_logs ON audit_logs FOR ALL TO service_role USING (true) WITH CHECK (true);

-- ============================================================================
-- 5. AUTHENTICATED USER POLICIES
-- ============================================================================
CREATE POLICY authenticated_select_profiles ON profiles FOR SELECT TO authenticated USING (true);
CREATE POLICY authenticated_update_own_profile ON profiles FOR UPDATE TO authenticated USING (auth.uid()::text = id) WITH CHECK (auth.uid()::text = id);

CREATE POLICY authenticated_select_customers ON customers FOR SELECT TO authenticated USING (true);
CREATE POLICY authenticated_manage_customers ON customers FOR ALL TO authenticated USING (coalesce(auth.jwt() ->> 'role', '') IN ('agent', 'admin')) WITH CHECK (coalesce(auth.jwt() ->> 'role', '') IN ('agent', 'admin'));

CREATE POLICY authenticated_select_subscriptions ON subscriptions FOR SELECT TO authenticated USING (true);
CREATE POLICY authenticated_manage_subscriptions ON subscriptions FOR ALL TO authenticated USING (coalesce(auth.jwt() ->> 'role', '') IN ('agent', 'admin')) WITH CHECK (coalesce(auth.jwt() ->> 'role', '') IN ('agent', 'admin'));

CREATE POLICY authenticated_select_workspaces ON workspaces FOR SELECT TO authenticated USING (true);
CREATE POLICY authenticated_manage_workspaces ON workspaces FOR ALL TO authenticated USING (coalesce(auth.jwt() ->> 'role', '') IN ('agent', 'admin')) WITH CHECK (coalesce(auth.jwt() ->> 'role', '') IN ('agent', 'admin'));

CREATE POLICY authenticated_select_products ON products FOR SELECT TO authenticated USING (true);
CREATE POLICY admin_manage_products ON products FOR ALL TO authenticated USING (coalesce(auth.jwt() ->> 'role', '') = 'admin') WITH CHECK (coalesce(auth.jwt() ->> 'role', '') = 'admin');

CREATE POLICY authenticated_select_tickets ON tickets FOR SELECT TO authenticated USING (true);
CREATE POLICY authenticated_mutate_tickets ON tickets FOR ALL TO authenticated USING (coalesce(auth.jwt() ->> 'role', '') IN ('agent', 'admin')) WITH CHECK (coalesce(auth.jwt() ->> 'role', '') IN ('agent', 'admin'));

CREATE POLICY authenticated_select_ticket_messages ON ticket_messages FOR SELECT TO authenticated USING (true);
CREATE POLICY authenticated_insert_ticket_messages ON ticket_messages FOR INSERT TO authenticated WITH CHECK (coalesce(auth.jwt() ->> 'role', '') IN ('agent', 'admin'));

CREATE POLICY select_published_support_articles ON support_articles FOR SELECT USING (published = true);
CREATE POLICY admin_manage_support_articles ON support_articles FOR ALL TO authenticated USING (coalesce(auth.jwt() ->> 'role', '') = 'admin') WITH CHECK (coalesce(auth.jwt() ->> 'role', '') = 'admin');

CREATE POLICY authenticated_select_incidents ON incidents FOR SELECT TO authenticated USING (true);
CREATE POLICY agent_admin_manage_incidents ON incidents FOR ALL TO authenticated USING (coalesce(auth.jwt() ->> 'role', '') IN ('agent', 'admin')) WITH CHECK (coalesce(auth.jwt() ->> 'role', '') IN ('agent', 'admin'));

CREATE POLICY authenticated_select_workflow_runs ON workflow_runs FOR SELECT TO authenticated USING (true);
CREATE POLICY agent_admin_manage_workflow_runs ON workflow_runs FOR ALL TO authenticated USING (coalesce(auth.jwt() ->> 'role', '') IN ('agent', 'admin')) WITH CHECK (coalesce(auth.jwt() ->> 'role', '') IN ('agent', 'admin'));

CREATE POLICY authenticated_select_workflow_events ON workflow_events FOR SELECT TO authenticated USING (true);
CREATE POLICY authenticated_select_resolution_actions ON resolution_actions FOR SELECT TO authenticated USING (true);

CREATE POLICY authenticated_select_approval_requests ON approval_requests FOR SELECT TO authenticated USING (true);
CREATE POLICY agent_admin_update_approval_requests ON approval_requests FOR UPDATE TO authenticated USING (coalesce(auth.jwt() ->> 'role', '') IN ('agent', 'admin')) WITH CHECK (coalesce(auth.jwt() ->> 'role', '') IN ('agent', 'admin'));

CREATE POLICY authenticated_select_escalations ON escalations FOR SELECT TO authenticated USING (true);
CREATE POLICY agent_admin_manage_escalations ON escalations FOR ALL TO authenticated USING (coalesce(auth.jwt() ->> 'role', '') IN ('agent', 'admin')) WITH CHECK (coalesce(auth.jwt() ->> 'role', '') IN ('agent', 'admin'));

CREATE POLICY authenticated_select_customer_memory ON customer_memory FOR SELECT TO authenticated USING (true);
CREATE POLICY agent_admin_manage_customer_memory ON customer_memory FOR ALL TO authenticated USING (coalesce(auth.jwt() ->> 'role', '') IN ('agent', 'admin')) WITH CHECK (coalesce(auth.jwt() ->> 'role', '') IN ('agent', 'admin'));

CREATE POLICY authenticated_select_audit_logs ON audit_logs FOR SELECT TO authenticated USING (true);

COMMIT;
