import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

export interface DashboardSummary {
  total_reports: number;
  draft_reports: number;
  published_reports: number;
  total_templates: number;
  total_exports: number;
  recent_reports: ReportSummary[];
  favorite_reports: ReportSummary[];
}

export interface ReportSummary {
  id: string;
  name: string;
  description: string;
  status: string;
  source: string;
  created_at: string;
  updated_at: string;
}

export interface KpiData {
  revenue: { total_revenue: number; outstanding_revenue: number; invoice_count: number; paid_invoice_count: number };
  expenses: { total_expenses: number; expense_count: number };
  profit: { net_profit: number; profit_margin: number; total_revenue: number; total_expenses: number };
  cash_flow: { total_inflows: number; total_outflows: number; net_cash_flow: number };
  outstanding_invoices: { outstanding_count: number; total_outstanding: number; average_outstanding: number };
  payment_delays: { delayed_count: number; total_delayed_amount: number };
  reconciliation_rate: { reconciliation_rate: number; total_invoices: number; reconciled_count: number; unreconciled_count: number };
}

export interface TrendPoint {
  period: string;
  value: number;
}

export interface PivotRow {
  group: string;
  total: number;
  count: number;
  average?: number;
}

@Injectable({
  providedIn: 'root',
})
export class ReportingService {
  constructor(private http: HttpClient) {}

  getDashboard(): Observable<{ status: string; data: DashboardSummary }> {
    return this.http.get<{ status: string; data: DashboardSummary }>('/reporting/dashboard');
  }

  getKpis(): Observable<{ status: string; data: KpiData }> {
    return this.http.get<{ status: string; data: KpiData }>('/reporting/analytics/kpis');
  }

  getTrends(metric: string = 'amount', bucket: string = 'month'): Observable<{ status: string; data: { series: TrendPoint[] } }> {
    return this.http.get<{ status: string; data: { series: TrendPoint[] } }>(`/reporting/analytics/trends?metric=${metric}&bucket=${bucket}`);
  }

  getHeatmap(): Observable<{ status: string; data: any }> {
    return this.http.get<{ status: string; data: any }>('/reporting/analytics/heatmap');
  }

  getPivot(rowField: string, columnField: string, valueField: string, aggFunc: string = 'sum'): Observable<{ status: string; data: { rows: PivotRow[] } }> {
    return this.http.get<{ status: string; data: { rows: PivotRow[] } }>(`/reporting/analytics/pivot?row_field=${rowField}&column_field=${columnField}&value_field=${valueField}&agg_func=${aggFunc}`);
  }

  getBuilderReports(limit: number = 20, offset: number = 0): Observable<{ status: string; data: ReportDefinition[] }> {
    return this.http.get<{ status: string; data: ReportDefinition[] }>(`/reporting/builder/reports?limit=${limit}&offset=${offset}`);
  }

  getBuilderReport(reportId: string): Observable<{ status: string; data: ReportDefinition }> {
    return this.http.get<{ status: string; data: ReportDefinition }>(`/reporting/builder/reports/${reportId}`);
  }

  createBuilderReport(name: string, description: string, source: string): Observable<{ status: string; data: ReportDefinition }> {
    return this.http.post<{ status: string; data: ReportDefinition }>('/reporting/builder/reports', {
      name, description, source, status: 'draft',
      definition: { sections: [], filters: [], charts: [] },
    });
  }

  updateBuilderReport(reportId: string, definition: any): Observable<{ status: string; data: ReportDefinition }> {
    return this.http.put<{ status: string; data: ReportDefinition }>(`/reporting/builder/reports/${reportId}`, { definition });
  }

  deleteBuilderReport(reportId: string): Observable<{ status: string }> {
    return this.http.delete<{ status: string }>(`/reporting/builder/reports/${reportId}`);
  }

  toggleBuilderFavorite(reportId: string): Observable<{ status: string; data: ReportDefinition }> {
    return this.http.post<{ status: string; data: ReportDefinition }>(`/reporting/builder/reports/${reportId}/favorite`, {});
  }

  createVersion(reportId: string, definition: any, changeNote: string): Observable<{ status: string; data: any }> {
    return this.http.post<{ status: string; data: any }>(`/reporting/builder/reports/${reportId}/versions`, {
      definition, change_note: changeNote,
    });
  }

  listVersions(reportId: string): Observable<{ status: string; data: any[] }> {
    return this.http.get<{ status: string; data: any[] }>(`/reporting/builder/reports/${reportId}/versions`);
  }

  // TODO: Add templates, preview, history, scheduled endpoints
}