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
  id: string;
  type: 'kpi' | 'chart' | 'table' | 'text';
  label: string;
  config: Record<string, any>;
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

export interface AnalyticsKpis {
  revenue: { total_revenue: number; outstanding_revenue: number; invoice_count: number; paid_invoice_count: number };
  expenses: { total_expenses: number; expense_count: number };
  profit: { net_profit: number; profit_margin: number; total_revenue: number; total_expenses: number };
  cash_flow: { total_inflows: number; total_outflows: number; net_cash_flow: number };
  outstanding_invoices: { outstanding_count: number; total_outstanding: number; average_outstanding: number };
  payment_delays: { delayed_count: number; total_delayed_amount: number };
  reconciliation_rate: { reconciliation_rate: number; total_invoices: number; reconciled_count: number; unreconciled_count: number };
  total_transactions: { erp_count: number; bank_count: number; total_volume: number };
  anomaly_stats: { total_anomalies: number; high_severity_count: number; severity_distribution: Record<string, number>; type_distribution: Record<string, number> };
  matching_accuracy: { total_reconciliations: number; matched_count: number; unmatched_count: number; pending_count: number; accuracy_rate: number };
}

export interface ChartDataResponse {
  chart_type: string;
  data_source: string;
  labels: string[];
  datasets: ChartDataset[];
}

export interface ChartDataset {
  label: string;
  data: number[];
  backgroundColor?: string[];
  borderColor?: string;
  fill?: boolean;
}

export interface AvailableElement {
  type: 'kpi' | 'chart' | 'table' | 'text';
  label: string;
  description: string;
  icon: string;
  defaultConfig: Record<string, any>;
}
