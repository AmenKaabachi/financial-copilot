import { Component, OnInit } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ReportDefinition } from '../../models/reporting.models';

interface SectionNode {
  id: string;
  type: string;
  label: string;
  children?: SectionNode[];
}

interface FilterOption {
  field: string;
  operator: string;
  value: string;
}

interface ChartConfig {
  type: string;
  data_source: string;
  x_axis: string;
  y_axis: string;
  group_by?: string;
}

@Component({
  selector: 'app-report-builder',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './report-builder.component.html',
  styleUrl: './report-builder.component.css',
})
export class ReportBuilderComponent implements OnInit {
  reports: ReportDefinition[] = [];
  selectedReport: ReportDefinition | null = null;
  sections: SectionNode[] = [];
  filters: FilterOption[] = [];
  charts: ChartConfig[] = [];
  loading = true;
  error = false;

  activeTab = 'sections';
  showNewReport = false;
  newReportName = '';
  newReportDescription = '';
  newReportSource: 'manual' | 'ai' | 'template' = 'manual';

  constructor(private http: HttpClient) {}

  ngOnInit(): void {
    this.loadReports();
  }

  loadReports(): void {
    this.http.get<{ status: string; data: ReportDefinition[] }>('/reporting/builder/reports').subscribe({
      next: (res) => {
        if (res.status === 'ok') {
          this.reports = res.data;
        }
        this.loading = false;
      },
      error: () => {
        this.error = true;
        this.loading = false;
      },
    });
  }

  selectReport(report: ReportDefinition): void {
    this.selectedReport = report;
    this.sections = this._parseSections(report.definition);
    this.filters = this._parseFilters(report.definition);
    this.charts = this._parseCharts(report.definition);
    this.activeTab = 'sections';
  }

  createReport(): void {
    if (!this.newReportName.trim()) return;
    this.http.post<{ status: string; data: ReportDefinition }>('/reporting/builder/reports', {
      name: this.newReportName,
      description: this.newReportDescription,
      source: this.newReportSource,
      status: 'draft',
      definition: { sections: [], filters: [], charts: [] },
    }).subscribe({
      next: (res) => {
        if (res.status === 'ok') {
          this.reports.unshift(res.data);
          this.showNewReport = false;
          this.newReportName = '';
          this.newReportDescription = '';
          this.selectReport(res.data);
        }
      },
      error: () => {},
    });
  }

  deleteReport(reportId: string): void {
    this.http.delete<{ status: string }>(`/reporting/builder/reports/${reportId}`).subscribe({
      next: (res) => {
        if (res.status === 'ok') {
          this.reports = this.reports.filter((r) => r.id !== reportId);
          if (this.selectedReport?.id === reportId) {
            this.selectedReport = null;
            this.sections = [];
            this.filters = [];
            this.charts = [];
          }
        }
      },
      error: () => {},
    });
  }

  toggleFavorite(reportId: string): void {
    this.http.post<{ status: string; data: ReportDefinition }>(`/reporting/builder/reports/${reportId}/favorite`, {}).subscribe({
      next: (res) => {
        if (res.status === 'ok' && res.data) {
          const idx = this.reports.findIndex((r) => r.id === reportId);
          if (idx !== -1) {
            this.reports[idx] = res.data;
          }
          if (this.selectedReport?.id === reportId) {
            this.selectedReport = res.data;
          }
        }
      },
      error: () => {},
    });
  }

  addSection(type: string): void {
    if (!this.selectedReport) return;
    const section = {
      id: `section_${Date.now()}`,
      type,
      label: `New ${type} section`,
    };
    this.sections.push(section);
    this._saveDefinition();
  }

  removeSection(sectionId: string): void {
    this.sections = this.sections.filter((s) => s.id !== sectionId);
    this._saveDefinition();
  }

  updateSectionLabel(sectionId: string, label: string): void {
    const section = this.sections.find((s) => s.id === sectionId);
    if (section) {
      section.label = label;
      this._saveDefinition();
    }
  }

  addFilter(): void {
    this.filters.push({ field: '', operator: 'equals', value: '' });
    this._saveDefinition();
  }

  removeFilter(index: number): void {
    this.filters.splice(index, 1);
    this._saveDefinition();
  }

  updateFilter(index: number, field: string, operator: string, value: string): void {
    this.filters[index] = { field, operator, value };
    this._saveDefinition();
  }

  addChart(): void {
    this.charts.push({ type: 'bar', data_source: '', x_axis: '', y_axis: '' });
    this._saveDefinition();
  }

  removeChart(index: number): void {
    this.charts.splice(index, 1);
    this._saveDefinition();
  }

  updateChart(index: number, key: string, value: string): void {
    this.charts[index][key as keyof ChartConfig] = value as any;
    this._saveDefinition();
  }

  saveReport(): void {
    if (!this.selectedReport) return;
    const definition = {
      sections: this.sections,
      filters: this.filters,
      charts: this.charts,
    };
    this.http.put<{ status: string; data: ReportDefinition }>(`/reporting/builder/reports/${this.selectedReport.id}`, {
      definition,
    }).subscribe({
      next: (res) => {
        if (res.status === 'ok' && res.data) {
          const idx = this.reports.findIndex((r) => r.id === this.selectedReport!.id);
          if (idx !== -1) {
            this.reports[idx] = res.data;
          }
          this.selectedReport = res.data;
        }
      },
      error: () => {},
    });
  }

  createVersion(): void {
    if (!this.selectedReport) return;
    this.http.post<{ status: string; data: any }>(`/reporting/builder/reports/${this.selectedReport.id}/versions`, {
      definition: { sections: this.sections, filters: this.filters, charts: this.charts },
      change_note: 'Manual save',
    }).subscribe({
      next: (res) => {
        if (res.status === 'ok') {
          if (this.selectedReport) {
            this.selectedReport = { ...this.selectedReport, version: (this.selectedReport.version || 0) + 1 };
          }
        }
      },
      error: () => {},
    });
  }

  private _parseSections(definition: Record<string, unknown>): SectionNode[] {
    const def = definition as Record<string, any>;
    return (def['sections'] || []) as SectionNode[];
  }

  private _parseFilters(definition: Record<string, unknown>): FilterOption[] {
    const def = definition as Record<string, any>;
    return (def['filters'] || []) as FilterOption[];
  }

  private _parseCharts(definition: Record<string, unknown>): ChartConfig[] {
    const def = definition as Record<string, any>;
    return (def['charts'] || []) as ChartConfig[];
  }

  private _saveDefinition(): void {
    if (!this.selectedReport) return;
    const definition = {
      sections: this.sections,
      filters: this.filters,
      charts: this.charts,
    };
    this.http.put<{ status: string; data: ReportDefinition }>(`/reporting/builder/reports/${this.selectedReport.id}`, {
      definition,
    }).subscribe({
      next: (res) => {
        if (res.status === 'ok' && res.data) {
          const idx = this.reports.findIndex((r) => r.id === this.selectedReport!.id);
          if (idx !== -1) {
            this.reports[idx] = res.data;
          }
          this.selectedReport = res.data;
        }
      },
      error: () => {},
    });
  }
}
