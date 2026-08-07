-- Migration: Export jobs with progress tracking
-- Run in Supabase SQL editor or via migration tool

-- report_export_jobs: tracks asynchronous export jobs with progress updates
CREATE TABLE IF NOT EXISTS report_export_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    report_id UUID REFERENCES report_definitions(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'processing', 'completed', 'failed')),
    progress INTEGER NOT NULL DEFAULT 0 CHECK (progress >= 0 AND progress <= 100),
    current_step TEXT DEFAULT '',
    file_path TEXT,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_export_jobs_report ON report_export_jobs(report_id);
CREATE INDEX IF NOT EXISTS idx_export_jobs_status ON report_export_jobs(status);
CREATE INDEX IF NOT EXISTS idx_export_jobs_created ON report_export_jobs(created_at DESC);