-- CloudDesk Support Platform — Row Level Security (RLS) Policies
-- PostgreSQL 15+ / Supabase RLS Policy Definitions
-- Implements RBAC: viewer (1) < agent (2) < admin (3) and service_role bypass

-- ============================================================================
-- 1. ENABLE ROW LEVEL SECURITY ON ALL TABLES
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
-- 2. SERVICE ROLE BYPASS POLICIES (Backend Administrative / Service Access)
-- ============================================================================
-- The backend uses the service-role key server-side only. Full access granted.
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
-- 3. PROFILES POLICIES
-- ============================================================================
-- Authenticated users can view profiles
CREATE POLICY authenticated_select_profiles ON profiles
    FOR SELECT TO authenticated
    USING (true);

-- Users can update their own profile
CREATE POLICY authenticated_update_own_profile ON profiles
    FOR UPDATE TO authenticated
    USING (auth.uid()::text = id)
    WITH CHECK (auth.uid()::text = id);

-- ============================================================================
-- 4. CUSTOMERS, SUBSCRIPTIONS, WORKSPACES, PRODUCTS
-- ============================================================================
-- All authenticated roles (viewer, agent, admin) can read customer metadata
CREATE POLICY authenticated_select_customers ON customers
    FOR SELECT TO authenticated
    USING (true);

CREATE POLICY authenticated_manage_customers ON customers
    FOR ALL TO authenticated
    USING (coalesce(auth.jwt() ->> 'role', '') IN ('agent', 'admin'))
    WITH CHECK (coalesce(auth.jwt() ->> 'role', '') IN ('agent', 'admin'));

CREATE POLICY authenticated_select_subscriptions ON subscriptions
    FOR SELECT TO authenticated
    USING (true);

CREATE POLICY authenticated_manage_subscriptions ON subscriptions
    FOR ALL TO authenticated
    USING (coalesce(auth.jwt() ->> 'role', '') IN ('agent', 'admin'))
    WITH CHECK (coalesce(auth.jwt() ->> 'role', '') IN ('agent', 'admin'));

CREATE POLICY authenticated_select_workspaces ON workspaces
    FOR SELECT TO authenticated
    USING (true);

CREATE POLICY authenticated_manage_workspaces ON workspaces
    FOR ALL TO authenticated
    USING (coalesce(auth.jwt() ->> 'role', '') IN ('agent', 'admin'))
    WITH CHECK (coalesce(auth.jwt() ->> 'role', '') IN ('agent', 'admin'));

CREATE POLICY authenticated_select_products ON products
    FOR SELECT TO authenticated
    USING (true);

CREATE POLICY admin_manage_products ON products
    FOR ALL TO authenticated
    USING (coalesce(auth.jwt() ->> 'role', '') = 'admin')
    WITH CHECK (coalesce(auth.jwt() ->> 'role', '') = 'admin');

-- ============================================================================
-- 5. TICKETS & TICKET MESSAGES POLICIES
-- ============================================================================
-- Viewers, agents, and admins can read tickets and messages
CREATE POLICY authenticated_select_tickets ON tickets
    FOR SELECT TO authenticated
    USING (true);

CREATE POLICY authenticated_mutate_tickets ON tickets
    FOR ALL TO authenticated
    USING (coalesce(auth.jwt() ->> 'role', '') IN ('agent', 'admin'))
    WITH CHECK (coalesce(auth.jwt() ->> 'role', '') IN ('agent', 'admin'));

CREATE POLICY authenticated_select_ticket_messages ON ticket_messages
    FOR SELECT TO authenticated
    USING (true);

CREATE POLICY authenticated_insert_ticket_messages ON ticket_messages
    FOR INSERT TO authenticated
    WITH CHECK (coalesce(auth.jwt() ->> 'role', '') IN ('agent', 'admin'));

-- ============================================================================
-- 6. SUPPORT ARTICLES & INCIDENTS
-- ============================================================================
-- Public and authenticated users can view published support articles
CREATE POLICY select_published_support_articles ON support_articles
    FOR SELECT
    USING (published = true);

-- Admins can manage knowledge articles (reindex / updates)
CREATE POLICY admin_manage_support_articles ON support_articles
    FOR ALL TO authenticated
    USING (coalesce(auth.jwt() ->> 'role', '') = 'admin')
    WITH CHECK (coalesce(auth.jwt() ->> 'role', '') = 'admin');

CREATE POLICY authenticated_select_incidents ON incidents
    FOR SELECT TO authenticated
    USING (true);

CREATE POLICY agent_admin_manage_incidents ON incidents
    FOR ALL TO authenticated
    USING (coalesce(auth.jwt() ->> 'role', '') IN ('agent', 'admin'))
    WITH CHECK (coalesce(auth.jwt() ->> 'role', '') IN ('agent', 'admin'));

-- ============================================================================
-- 7. WORKFLOW RUNS, EVENTS, ACTIONS & APPROVALS
-- ============================================================================
CREATE POLICY authenticated_select_workflow_runs ON workflow_runs
    FOR SELECT TO authenticated
    USING (true);

CREATE POLICY agent_admin_manage_workflow_runs ON workflow_runs
    FOR ALL TO authenticated
    USING (coalesce(auth.jwt() ->> 'role', '') IN ('agent', 'admin'))
    WITH CHECK (coalesce(auth.jwt() ->> 'role', '') IN ('agent', 'admin'));

CREATE POLICY authenticated_select_workflow_events ON workflow_events
    FOR SELECT TO authenticated
    USING (true);

CREATE POLICY authenticated_select_resolution_actions ON resolution_actions
    FOR SELECT TO authenticated
    USING (true);

CREATE POLICY authenticated_select_approval_requests ON approval_requests
    FOR SELECT TO authenticated
    USING (true);

-- Only agents and admins can decide on approval requests (viewers are restricted)
CREATE POLICY agent_admin_update_approval_requests ON approval_requests
    FOR UPDATE TO authenticated
    USING (coalesce(auth.jwt() ->> 'role', '') IN ('agent', 'admin'))
    WITH CHECK (coalesce(auth.jwt() ->> 'role', '') IN ('agent', 'admin'));

-- ============================================================================
-- 8. ESCALATIONS, CUSTOMER MEMORY & AUDIT LOGS
-- ============================================================================
CREATE POLICY authenticated_select_escalations ON escalations
    FOR SELECT TO authenticated
    USING (true);

CREATE POLICY agent_admin_manage_escalations ON escalations
    FOR ALL TO authenticated
    USING (coalesce(auth.jwt() ->> 'role', '') IN ('agent', 'admin'))
    WITH CHECK (coalesce(auth.jwt() ->> 'role', '') IN ('agent', 'admin'));

CREATE POLICY authenticated_select_customer_memory ON customer_memory
    FOR SELECT TO authenticated
    USING (true);

CREATE POLICY agent_admin_manage_customer_memory ON customer_memory
    FOR ALL TO authenticated
    USING (coalesce(auth.jwt() ->> 'role', '') IN ('agent', 'admin'))
    WITH CHECK (coalesce(auth.jwt() ->> 'role', '') IN ('agent', 'admin'));

-- All authenticated roles can view audit logs
CREATE POLICY authenticated_select_audit_logs ON audit_logs
    FOR SELECT TO authenticated
    USING (true);
-- Note: Audit logs can only be inserted by service_role via middleware; no updates or deletes permitted.
