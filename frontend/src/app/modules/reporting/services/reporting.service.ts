import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import {
  ReportDefinition, ReportVersion, ExportJob,
  AnalyticsKpis, ChartDataResponse, AiReportRequest, AiReportPreview,
  ReportSection, AnalyticsComponent, ComponentPreview
} from '../models/reporting.models';

export interface DashboardSummary {
  total_reports: number;
  draft_reports: number;
  published_reports: number;
  total_exports: number;
  recent_reports: ReportSummary[];
  favorite_reports: ReportSummary[];
}

export interface ReportSummary {
  id: string;
  name: string;
  description: string;
  status: string;
  report_type: string;
  created_at: string;
  updated_at: string;
  is_favorite: boolean;
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

import { BankMatchIntegrationService } from '../../../integrations/bankmatch';

@Injectable({
  providedIn: 'root',
})
export class ReportingService {
  private apiUrl = '/api/reporting';

  constructor(
    private http: HttpClient,
    private bankMatchService: BankMatchIntegrationService
  ) {}


  // Dashboard
  getDashboard(): Observable<{ status: string; data: DashboardSummary }> {
    return this.http.get<{ status: string; data: DashboardSummary }>(`${this.apiUrl}/dashboard`);
  }

  // Analytics KPIs with optional date filtering
  getKpis(dateFrom?: string, dateTo?: string): Observable<{ status: string; data: AnalyticsKpis }> {
    let params = new HttpParams();
    if (dateFrom) params = params.set('date_from', dateFrom);
    if (dateTo) params = params.set('date_to', dateTo);
    return this.http.get<{ status: string; data: AnalyticsKpis }>(`${this.apiUrl}/analytics/kpis`, { params });
  }

  // Chart data endpoint
  getChartData(
    chartType: string,
    dateFrom?: string,
    dateTo?: string
  ): Observable<{ status: string; data: ChartDataResponse }> {
    let params = new HttpParams().set('chart_type', chartType);
    if (dateFrom) params = params.set('date_from', dateFrom);
    if (dateTo) params = params.set('date_to', dateTo);
    return this.http.get<{ status: string; data: ChartDataResponse }>(`${this.apiUrl}/analytics/chart-data`, { params });
  }

  // Trends
  getTrends(metric: string = 'amount', bucket: string = 'month'): Observable<{ status: string; data: { series: TrendPoint[] } }> {
    return this.http.get<{ status: string; data: { series: TrendPoint[] } }>(`${this.apiUrl}/analytics/trends?metric=${metric}&bucket=${bucket}`);
  }

  // Heatmap
  getHeatmap(): Observable<{ status: string; data: any }> {
    return this.http.get<{ status: string; data: any }>(`${this.apiUrl}/analytics/heatmap`);
  }

  // Pivot
  getPivot(rowField: string, columnField: string, valueField: string, aggFunc: string = 'sum'): Observable<{ status: string; data: any }> {
    return this.http.get<{ status: string; data: any }>(`${this.apiUrl}/analytics/pivot?row_field=${rowField}&column_field=${columnField}&value_field=${valueField}&agg_func=${aggFunc}`);
  }

  // Report Builder CRUD
  getBuilderReports(limit: number = 20, offset: number = 0): Observable<{ status: string; data: ReportDefinition[] }> {
    return this.http.get<{ status: string; data: ReportDefinition[] }>(`${this.apiUrl}/builder/reports?limit=${limit}&offset=${offset}`);
  }

  getBuilderReport(reportId: string): Observable<{ status: string; data: ReportDefinition }> {
    return this.http.get<{ status: string; data: ReportDefinition }>(`${this.apiUrl}/builder/reports/${reportId}`);
  }

  createBuilderReport(name: string, description: string, source: string): Observable<{ status: string; data: ReportDefinition }> {
    return this.http.post<{ status: string; data: ReportDefinition }>(`${this.apiUrl}/builder/reports`, {
      name, description, source, status: 'draft',
      definition: { sections: [] },
    });
  }

  updateBuilderReport(reportId: string, definition: any): Observable<{ status: string; data: ReportDefinition }> {
    return this.http.put<{ status: string; data: ReportDefinition }>(`${this.apiUrl}/builder/reports/${reportId}`, { definition });
  }

  deleteBuilderReport(reportId: string): Observable<{ status: string }> {
    return this.http.delete<{ status: string }>(`${this.apiUrl}/builder/reports/${reportId}`);
  }

  toggleBuilderFavorite(reportId: string): Observable<{ status: string; data: ReportDefinition }> {
    return this.http.post<{ status: string; data: ReportDefinition }>(`${this.apiUrl}/builder/reports/${reportId}/favorite`, {});
  }

  // AI Report Generation
  generateAiStructure(request: AiReportRequest): Observable<{ status: string; data: AiReportPreview }> {
    return this.http.post<{ status: string; data: AiReportPreview }>(`${this.apiUrl}/builder/ai/generate-structure`, request);
  }

  createAiReport(data: any): Observable<{ status: string; data: ReportDefinition }> {
    return this.http.post<{ status: string; data: ReportDefinition }>(`${this.apiUrl}/builder/ai/create-report`, data);
  }

  // Manual Builder
  createManualReport(data: any): Observable<{ status: string; data: ReportDefinition }> {
    return this.http.post<{ status: string; data: ReportDefinition }>(`${this.apiUrl}/builder/manual/create-report`, data);
  }

  updateReportSections(reportId: string, sections: ReportSection[]): Observable<{ status: string; data: ReportDefinition }> {
    return this.http.put<{ status: string; data: ReportDefinition }>(`${this.apiUrl}/builder/reports/${reportId}/sections`, { sections });
  }

  publishReport(reportId: string): Observable<{ status: string; data: ReportDefinition }> {
    return this.http.post<{ status: string; data: ReportDefinition }>(`${this.apiUrl}/builder/reports/${reportId}/publish`, {});
  }

  // Versions
  createVersion(reportId: string, definition: any, changeNote: string): Observable<{ status: string; data: any }> {
    return this.http.post<{ status: string; data: any }>(`${this.apiUrl}/builder/reports/${reportId}/versions`, {
      definition, change_note: changeNote,
    });
  }

  listVersions(reportId: string): Observable<{ status: string; data: any[] }> {
    return this.http.get<{ status: string; data: any[] }>(`${this.apiUrl}/builder/reports/${reportId}/versions`);
  }

  // Exports
  createExport(reportId: string, format: string): Observable<{ status: string; data: ExportJob }> {
    return this.http.post<{ status: string; data: ExportJob }>(`${this.apiUrl}/builder/reports/${reportId}/export`, { format });
  }

  listExports(reportId: string): Observable<{ status: string; data: ExportJob[] }> {
    return this.http.get<{ status: string; data: ExportJob[] }>(`${this.apiUrl}/builder/reports/${reportId}/exports`);
  }

  // Analytics Component Registry
  getAnalyticsComponents(group?: string, componentType?: string): Observable<{ status: string; data: AnalyticsComponent[]; total: number }> {
    let params = new HttpParams();
    if (group) params = params.set('group', group);
    if (componentType) params = params.set('component_type', componentType);
    return this.http.get<{ status: string; data: AnalyticsComponent[]; total: number }>(`${this.apiUrl}/builder/analytics-components`, { params });
  }

  getAnalyticsComponent(componentId: string): Observable<{ status: string; data: AnalyticsComponent }> {
    return this.http.get<{ status: string; data: AnalyticsComponent }>(`${this.apiUrl}/builder/analytics-components/${componentId}`);
  }

  getComponentPreview(componentId: string, params?: { date_from?: string; date_to?: string; bucket?: string; limit?: number }): Observable<{ status: string; data: ComponentPreview }> {
    let httpParams = new HttpParams();
    if (params?.date_from) httpParams = httpParams.set('date_from', params.date_from);
    if (params?.date_to) httpParams = httpParams.set('date_to', params.date_to);
    if (params?.bucket) httpParams = httpParams.set('bucket', params.bucket);
    if (params?.limit) httpParams = httpParams.set('limit', params.limit.toString());
    return this.http.get<{ status: string; data: ComponentPreview }>(`${this.apiUrl}/builder/analytics-components/${componentId}/preview`, { params: httpParams });
  }

  // BankMatch Integration Data Delegation
  getBankMatchEndpointData<T = unknown>(endpointPath: string): Observable<T> {
    return this.bankMatchService.getEndpointData<T>(endpointPath);
  }
}

