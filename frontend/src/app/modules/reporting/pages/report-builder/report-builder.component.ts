import { Component, OnInit } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterModule } from '@angular/router';
import { ReportDefinition } from '../../models/reporting.models';

interface SectionNode {
  id: string;
  type: 'kpi' | 'chart' | 'table' | 'text';
  label: string;
  config: Record<string, any>;
}

interface AvailableElement {
  type: 'kpi' | 'chart' | 'table' | 'text';
  label: string;
  description: string;
  icon: string;
  defaultConfig: Record<string, any>;
}

@Component({
  selector: 'app-report-builder',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterModule],
  templateUrl: './report-builder.component.html',
  styleUrl: './report-builder.component.css',
})
export class ReportBuilderComponent implements OnInit {
  reports: ReportDefinition[] = [];
  selectedReport: ReportDefinition | null = null;
  sections: SectionNode[] = [];
  loading = true;
  error = false;
  saving = false;

  activeTab: 'sections' | 'elements' | 'export' | 'versions' = 'sections';
  showNewReport = false;
  newReportName = '';
  newReportDescription = '';
  newReportSource: string = 'manual';
  changeNote = '';

  // Export
  exportFormat: string = 'pdf';
  exportStatus: string = '';

  // Versions
  versions: any[] = [];

  // Available elements for the palette
  availableElements: AvailableElement[] = [
    {
      type: 'kpi',
      label: 'Revenue KPI',
      description: 'Total revenue with paid invoice count',
      icon: '💰',
      defaultConfig: { kpis: ['revenue'] },
    },
    {
      type: 'kpi',
      label: 'Expenses KPI',
      description: 'Total expenses with count',
      icon: '💸',
      defaultConfig: { kpis: ['expenses'] },
    },
    {
      type: 'kpi',
      label: 'Profit KPI',
      description: 'Net profit with margin percentage',
      icon: '📈',
      defaultConfig: { kpis: ['profit'] },
    },
    {
      type: 'kpi',
      label: 'Reconciliation Rate',
      description: 'Reconciliation success rate',
      icon: '✅',
      defaultConfig: { kpis: ['reconciliation_rate'] },
    },
    {
      type: 'kpi',
      label: 'Matching Accuracy',
      description: 'Detailed matching accuracy stats',
      icon: '🎯',
      defaultConfig: { kpis: ['matching_accuracy'] },
    },
    {
      type: 'kpi',
      label: 'Anomaly Stats',
      description: 'Total anomalies and severity breakdown',
      icon: '⚠️',
      defaultConfig: { kpis: ['anomaly_stats'] },
    },
    {
      type: 'kpi',
      label: 'Transaction Summary',
      description: 'ERP and bank transaction counts',
      icon: '🔄',
      defaultConfig: { kpis: ['total_transactions'] },
    },
    {
      type: 'chart',
      label: 'Reconciliation Trend',
      description: 'Success/failure over time (line chart)',
      icon: '📊',
      defaultConfig: { chart_type: 'line', data_source: 'reconciliation_trend' },
    },
    {
      type: 'chart',
      label: 'Transaction Volume',
      description: 'Monthly transaction amounts (bar chart)',
      icon: '📊',
      defaultConfig: { chart_type: 'bar', data_source: 'transaction_volume' },
    },
    {
      type: 'chart',
      label: 'Anomaly Distribution',
      description: 'Anomalies by severity (donut chart)',
      icon: '🍩',
      defaultConfig: { chart_type: 'donut', data_source: 'anomaly_distribution' },
    },
    {
      type: 'chart',
      label: 'Bank vs ERP',
      description: 'Side-by-side volume comparison',
      icon: '📊',
      defaultConfig: { chart_type: 'grouped_bar', data_source: 'bank_vs_erp' },
    },
    {
      type: 'chart',
      label: 'Payment Status',
      description: 'Paid vs outstanding distribution',
      icon: '🥧',
      defaultConfig: { chart_type: 'pie', data_source: 'payment_status' },
    },
    {
      type: 'table',
      label: 'Reconciliation Data',
      description: 'Detailed reconciliation records table',
      icon: '📋',
      defaultConfig: { data_source: 'reconciliations', columns: ['id', 'status', 'amount'] },
    },
    {
      type: 'table',
      label: 'Anomaly Data',
      description: 'Anomaly records with severity and type',
      icon: '📋',
      defaultConfig: { data_source: 'anomalies', columns: ['id', 'severity', 'type', 'amount'] },
    },
    {
      type: 'table',
      label: 'Transaction Data',
      description: 'ERP transaction records',
      icon: '📋',
      defaultConfig: { data_source: 'erp_transactions', columns: ['id', 'supplier', 'amount', 'status'] },
    },
    {
      type: 'text',
      label: 'Summary Section',
      description: 'Add a text summary or description',
      icon: '📝',
      defaultConfig: { content: 'Enter your summary text here...' },
    },
  ];

  constructor(
    private http: HttpClient,
    private route: ActivatedRoute
  ) {}

  ngOnInit(): void {
    console.log('[ReportBuilder] ngOnInit triggered');
    // Check if we have a report ID from the route
    this.route.params.subscribe(params => {
      const reportId = params['id'];
      console.log(`[ReportBuilder] Route parameter 'id':`, reportId);
      if (reportId) {
        console.log(`[ReportBuilder] Calling loadReport(${reportId})`);
        this.loadReport(reportId);
      } else {
        console.log(`[ReportBuilder] No report ID found, loading all reports`);
        this.loadReports();
      }
    });
  }

  loadReports(): void {
    this.http.get<{ status: string; data: ReportDefinition[] }>('/api/reporting/builder/reports').subscribe({
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

  loadReport(reportId: string): void {
    console.log(`[ReportBuilder] Executing HTTP GET to /api/reporting/builder/reports/${reportId}`);
    this.http.get<{ status: string; data: ReportDefinition }>(`/api/reporting/builder/reports/${reportId}`).subscribe({
      next: (res) => {
        console.log(`[ReportBuilder] Received HTTP Response:`, res);
        if (res.status === 'ok') {
          console.log(`[ReportBuilder] Mapping to selectedReport model.`);
          this.selectedReport = res.data;
          this.parseDefinition(res.data.definition);
          this.loadVersions();
        } else {
          console.log(`[ReportBuilder] HTTP Response status was not ok`);
        }
        this.loading = false;
      },
      error: (err) => {
        console.error(`[ReportBuilder] HTTP request failed:`, err);
        this.error = true;
        this.loading = false;
      },
    });
  }

  selectReport(report: ReportDefinition): void {
    this.selectedReport = report;
    this.parseDefinition(report.definition);
    this.loadVersions();
    this.activeTab = 'sections';
  }

  parseDefinition(definition: Record<string, unknown>): void {
    const def = definition as Record<string, any>;
    this.sections = (def['sections'] || []) as SectionNode[];
  }

  createReport(): void {
    if (!this.newReportName.trim()) return;
    this.http.post<{ status: string; data: ReportDefinition }>('/api/reporting/builder/reports', {
      name: this.newReportName,
      description: this.newReportDescription,
      source: this.newReportSource,
      status: 'draft',
      definition: { sections: [] },
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
    if (!confirm('Delete this report?')) return;
    this.http.delete<{ status: string }>(`/api/reporting/builder/reports/${reportId}`).subscribe({
      next: (res) => {
        if (res.status === 'ok') {
          this.reports = this.reports.filter(r => r.id !== reportId);
          if (this.selectedReport?.id === reportId) {
            this.selectedReport = null;
            this.sections = [];
          }
        }
      },
      error: () => {},
    });
  }

  toggleFavorite(reportId: string): void {
    this.http.post<{ status: string; data: ReportDefinition }>(`/api/reporting/builder/reports/${reportId}/favorite`, {}).subscribe({
      next: (res) => {
        if (res.status === 'ok' && res.data) {
          const idx = this.reports.findIndex(r => r.id === reportId);
          if (idx !== -1) this.reports[idx] = res.data;
          if (this.selectedReport?.id === reportId) this.selectedReport = res.data;
        }
      },
      error: () => {},
    });
  }

  // Element palette actions
  addElement(element: AvailableElement): void {
    if (!this.selectedReport) return;
    const section: SectionNode = {
      id: `section_${Date.now()}`,
      type: element.type,
      label: element.label,
      config: { ...element.defaultConfig },
    };
    this.sections.push(section);
    this.saveDefinition();
  }

  removeSection(sectionId: string): void {
    this.sections = this.sections.filter(s => s.id !== sectionId);
    this.saveDefinition();
  }

  moveSection(index: number, direction: -1 | 1): void {
    const newIndex = index + direction;
    if (newIndex < 0 || newIndex >= this.sections.length) return;
    [this.sections[index], this.sections[newIndex]] = [this.sections[newIndex], this.sections[index]];
    this.saveDefinition();
  }

  updateSectionLabel(sectionId: string, label: string): void {
    const section = this.sections.find(s => s.id === sectionId);
    if (section) {
      section.label = label;
      this.saveDefinition();
    }
  }

  updateSectionConfig(sectionId: string, key: string, value: any): void {
    const section = this.sections.find(s => s.id === sectionId);
    if (section) {
      section.config[key] = value;
      this.saveDefinition();
    }
  }

  saveDefinition(): void {
    if (!this.selectedReport) return;
    this.saving = true;
    const definition = { sections: this.sections };
    this.http.put<{ status: string; data: ReportDefinition }>(`/api/reporting/builder/reports/${this.selectedReport.id}`, {
      definition,
    }).subscribe({
      next: (res) => {
        if (res.status === 'ok' && res.data) {
          const idx = this.reports.findIndex(r => r.id === this.selectedReport!.id);
          if (idx !== -1) this.reports[idx] = res.data;
          this.selectedReport = res.data;
        }
        this.saving = false;
      },
      error: () => { this.saving = false; },
    });
  }

  // Version management
  loadVersions(): void {
    if (!this.selectedReport) return;
    this.http.get<{ status: string; data: any[] }>(`/api/reporting/builder/reports/${this.selectedReport.id}/versions`).subscribe({
      next: (res) => {
        if (res.status === 'ok') this.versions = res.data;
      },
      error: () => {},
    });
  }

  createVersion(): void {
    if (!this.selectedReport) return;
    this.http.post<{ status: string; data: any }>(`/api/reporting/builder/reports/${this.selectedReport.id}/versions`, {
      definition: { sections: this.sections },
      change_note: this.changeNote || 'Manual save',
    }).subscribe({
      next: (res) => {
        if (res.status === 'ok') {
          this.versions.unshift(res.data);
          this.changeNote = '';
        }
      },
      error: () => {},
    });
  }

  // Export
  exportReport(): void {
    if (!this.selectedReport) return;
    this.exportStatus = 'processing';
    this.http.post(`/api/reporting/builder/reports/${this.selectedReport.id}/export`, 
      { format: this.exportFormat },
      { responseType: 'blob' }
    ).subscribe({
      next: (blob) => {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        const filename = this.selectedReport ? this.selectedReport.name.replace(/[^a-z0-9]/gi, '_').toLowerCase() : 'report';
        a.download = `${filename}_export.${this.exportFormat}`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
        
        this.exportStatus = 'done';
        setTimeout(() => { this.exportStatus = ''; }, 3000);
      },
      error: () => { this.exportStatus = 'failed'; },
    });
  }

  getFilteredElements(type: string): AvailableElement[] {
    return this.availableElements.filter(el => el.type === type);
  }

  // Helpers
  getSectionIcon(type: string): string {
    const icons: Record<string, string> = {
      kpi: '📊',
      chart: '📈',
      table: '📋',
      text: '📝',
    };
    return icons[type] || '📄';
  }

  getStatusClass(status: string): string {
    const map: Record<string, string> = {
      draft: 'status-draft',
      published: 'status-published',
      archived: 'status-archived',
    };
    return map[status] || 'status-draft';
  }

  formatDate(dateStr: string): string {
    if (!dateStr) return '';
    return new Date(dateStr).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
  }
}
