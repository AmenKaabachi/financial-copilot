-- Migration: Remove templates feature
-- Run in Supabase SQL editor or via migration tool

-- Drop report_templates table and all its data
DROP TABLE IF EXISTS report_templates CASCADE;

-- Update report_definitions source constraint to remove 'template' option
ALTER TABLE report_definitions DROP CONSTRAINT IF EXISTS report_definitions_source_check;
ALTER TABLE report_definitions ADD CONSTRAINT report_definitions_source_check CHECK (source IN ('manual', 'ai'));
