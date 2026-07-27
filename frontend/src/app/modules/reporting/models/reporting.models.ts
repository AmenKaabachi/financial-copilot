export interface ReportDefinition {
  id: string;
  name: string;
  description: string;
  version: number;
  tags: string[];
  owner_id: string;
  source: 'manual' | 'ai' | 'template';
  status: 'draft' | 'published' | 'archived';
  definition: Record<string, unknown>;
  is_favorite: boolean;
  created_at: string;
  updated_at: string;
}

export interface ReportSection {
  type: string;
  kpis?: string[];
  chart_type?: string;
  data_source?: string;
  filters?: Record<string, unknown>;
  columns?: unknown[];
  grouping?: unknown[];
  sorting?: unknown[];
  text?: string;
  content?: string;
}

export interface ReportVersion {
  id: string;
  report_id: string;
  version_number: number;
  definition: Record<string, unknown>;
  change_note: string;
  created_at: string;
  created_by: string;
}

export interface ReportTemplate {
  id: string;
  name: string;
  category: string;
  scope: 'builtin' | 'company' | 'user';
  definition: Record<string, unknown>;
  thumbnail_url: string;
  created_by: string;
  is_favorite: boolean;
  created_at: string;
  updated_at: string;
}

export interface ExportJob {
  id: string;
  report_id: string;
  version_id: string;
  format: 'pdf' | 'excel' | 'csv';
  status: 'queued' | 'processing' | 'done' | 'failed';
  file_url: string;
  requested_at: string;
  completed_at: string;
}