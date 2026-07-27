-- Migration: Reporting module tables
-- Run in Supabase SQL editor or via migration tool

-- report_definitions: core report configuration entity
CREATE TABLE IF NOT EXISTS report_definitions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    version INTEGER NOT NULL DEFAULT 1,
    tags TEXT[] DEFAULT '{}',
    owner_id TEXT,
    source TEXT NOT NULL DEFAULT 'manual' CHECK (source IN ('manual', 'ai', 'template')),
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'published', 'archived')),
    definition JSONB NOT NULL DEFAULT '{}',
    is_favorite BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_report_definitions_owner ON report_definitions(owner_id);
CREATE INDEX IF NOT EXISTS idx_report_definitions_status ON report_definitions(status);
CREATE INDEX IF NOT EXISTS idx_report_definitions_source ON report_definitions(source);
CREATE INDEX IF NOT EXISTS idx_report_definitions_tags ON report_definitions USING GIN(tags);
CREATE INDEX IF NOT EXISTS idx_report_definitions_created_at ON report_definitions(created_at DESC);

-- report_versions: version history for report definitions
CREATE TABLE IF NOT EXISTS report_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    report_id UUID NOT NULL REFERENCES report_definitions(id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL,
    definition JSONB NOT NULL DEFAULT '{}',
    change_note TEXT DEFAULT '',
    created_by TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_report_versions_report ON report_versions(report_id);
CREATE INDEX IF NOT EXISTS idx_report_versions_version ON report_versions(report_id, version_number);

-- report_templates: reusable report templates
CREATE TABLE IF NOT EXISTS report_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    category TEXT DEFAULT 'custom',
    scope TEXT NOT NULL DEFAULT 'builtin' CHECK (scope IN ('builtin', 'company', 'user')),
    definition JSONB NOT NULL DEFAULT '{}',
    thumbnail_url TEXT,
    created_by TEXT,
    is_favorite BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_report_templates_scope ON report_templates(scope);
CREATE INDEX IF NOT EXISTS idx_report_templates_category ON report_templates(category);

-- report_exports: export job tracking (Phase 7 foundation)
CREATE TABLE IF NOT EXISTS report_exports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    report_id UUID REFERENCES report_definitions(id) ON DELETE SET NULL,
    version_id UUID REFERENCES report_versions(id) ON DELETE SET NULL,
    format TEXT NOT NULL CHECK (format IN ('pdf', 'excel', 'csv')),
    status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'processing', 'done', 'failed')),
    file_url TEXT,
    requested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_report_exports_report ON report_exports(report_id);
CREATE INDEX IF NOT EXISTS idx_report_exports_status ON report_exports(status);

-- ai_report_sessions: audit trail for AI-generated reports
CREATE TABLE IF NOT EXISTS ai_report_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT,
    prompt_text TEXT NOT NULL,
    resolved_intent TEXT,
    resolved_filters JSONB DEFAULT '{}',
    generated_definition JSONB DEFAULT '{}',
    model TEXT,
    request_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ai_report_sessions_user ON ai_report_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_ai_report_sessions_created ON ai_report_sessions(created_at DESC);

-- scheduled_reports: foundation for scheduled report delivery (Phase 9)
CREATE TABLE IF NOT EXISTS scheduled_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    report_id UUID REFERENCES report_definitions(id) ON DELETE CASCADE,
    frequency TEXT NOT NULL CHECK (frequency IN ('daily', 'weekly', 'monthly', 'quarterly', 'yearly')),
    delivery_method TEXT NOT NULL DEFAULT 'export_only' CHECK (delivery_method IN ('email', 'export_only')),
    recipients TEXT[] DEFAULT '{}',
    is_active BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_scheduled_reports_report ON scheduled_reports(report_id);
CREATE INDEX IF NOT EXISTS idx_scheduled_reports_active ON scheduled_reports(is_active);