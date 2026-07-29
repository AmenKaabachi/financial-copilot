import { Component, OnInit } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterModule } from '@angular/router';

interface ReportSummary {
  id: string;
  name: string;
  description: string;
  status: string;
  report_type: string;
  created_at: string;
  updated_at: string;
  is_favorite: boolean;
}

interface DashboardSummary {
  total_reports: number;
  draft_reports: number;
  published_reports: number;
  total_templates: number;
  total_exports: number;
  recent_reports: ReportSummary[];
  favorite_reports: ReportSummary[];
}

interface TemplateSummary {
  id: string;
  name: string;
  category: string;
  scope: string;
  thumbnail_url: string;
  is_favorite: boolean;
}

interface ExportJob {
  id: string;
  report_id: string;
  format: string;
  status: string;
  file_url: string;
  requested_at: string;
}

@Component({
  selector: 'app-reporting-dashboard',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterModule],
  templateUrl: './reporting-dashboard.component.html',
  styleUrl: './reporting-dashboard.component.css',
})
export class ReportingDashboardComponent implements OnInit {
  summary: DashboardSummary | null = null;
  reports: ReportSummary[] = [];
  templates: TemplateSummary[] = [];
  exports: Record<string, ExportJob[]> = {};
  loading = true;
  error = false;
  showCreateModal = false;
  newReportName = '';
  newReportDescription = '';
  newReportSource: string = 'manual';

  constructor(private http: HttpClient) {}

  ngOnInit(): void {
    this.loadDashboard();
    this.loadReports();
    this.loadTemplates();
  }

loadDashboard(): void {
  this.http.get<{ status: string; data: DashboardSummary }>('/reporting/dashboard')
    .subscribe({
      next: (res) => {
        console.log('[Dashboard Response]', res);

        if (res.status === 'ok') {
          this.summary = res.data;
        }

        this.loading = false;
      },
      error: (err) => {
        console.error('[Dashboard Error]', err);
        this.error = true;
        this.loading = false;
      },
    });
}

  loadReports(): void {
    this.http.get<{ status: string; data: ReportSummary[] }>('/reporting/builder/reports?limit=50').subscribe({
      next: (res) => {
        if (res.status === 'ok') {
          this.reports = res.data;
          this.reports.forEach(r => this.loadExports(r.id));
        }
      },
      error: () => {},
    });
  }

  loadTemplates(): void {
    this.http.get<{ status: string; data: TemplateSummary[] }>('/reporting/builder/templates').subscribe({
      next: (res) => {
        if (res.status === 'ok') {
          this.templates = res.data;
        }
      },
      error: () => {},
    });
  }

  loadExports(reportId: string): void {
    this.http.get<{ status: string; data: ExportJob[] }>(`/reporting/builder/reports/${reportId}/exports`).subscribe({
      next: (res) => {
        if (res.status === 'ok') {
          this.exports[reportId] = res.data;
        }
      },
      error: () => {},
    });
  }

  createReport(): void {
    if (!this.newReportName.trim()) return;
    this.http.post<{ status: string; data: ReportSummary }>('/reporting/builder/reports', {
      name: this.newReportName,
      description: this.newReportDescription,
      source: this.newReportSource,
      status: 'draft',
      definition: { sections: [], filters: [], charts: [] },
    }).subscribe({
      next: (res) => {
        if (res.status === 'ok') {
          this.reports.unshift(res.data);
          this.showCreateModal = false;
          this.newReportName = '';
          this.newReportDescription = '';
        }
      },
      error: () => {},
    });
  }

  deleteReport(reportId: string): void {
    if (!confirm('Are you sure you want to delete this report?')) return;
    this.http.delete<{ status: string }>(`/reporting/builder/reports/${reportId}`).subscribe({
      next: (res) => {
        if (res.status === 'ok') {
          this.reports = this.reports.filter(r => r.id !== reportId);
        }
      },
      error: () => {},
    });
  }

  toggleFavorite(reportId: string): void {
    this.http.post<{ status: string; data: ReportSummary }>(`/reporting/builder/reports/${reportId}/favorite`, {}).subscribe({
      next: (res) => {
        if (res.status === 'ok' && res.data) {
          const idx = this.reports.findIndex(r => r.id === reportId);
          if (idx !== -1) this.reports[idx] = res.data;
        }
      },
      error: () => {},
    });
  }

  exportReport(reportId: string, format: string): void {
    this.http.post<{ status: string; data: ExportJob }>(`/reporting/builder/reports/${reportId}/export`, { format }).subscribe({
      next: (res) => {
        if (res.status === 'ok') {
          if (!this.exports[reportId]) this.exports[reportId] = [];
          this.exports[reportId].unshift(res.data);
        }
      },
      error: () => {},
    });
  }

  getStatusClass(status: string): string {
    const map: Record<string, string> = {
      draft: 'status-draft',
      published: 'status-published',
      archived: 'status-archived',
    };
    return map[status] || 'status-draft';
  }

  getExportStatusClass(status: string): string {
    const map: Record<string, string> = {
      queued: 'export-queued',
      processing: 'export-processing',
      done: 'export-done',
      failed: 'export-failed',
    };
    return map[status] || 'export-queued';
  }

  formatDate(dateStr: string): string {
    if (!dateStr) return '';
    const d = new Date(dateStr);
    return d.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
  }
}
