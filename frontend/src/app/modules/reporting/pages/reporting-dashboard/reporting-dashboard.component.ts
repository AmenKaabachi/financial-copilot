import { Component, OnInit, HostListener } from '@angular/core';
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
  total_exports: number;
  recent_reports: ReportSummary[];
  favorite_reports: ReportSummary[];
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
  exports: Record<string, ExportJob[]> = {};
  loading = true;
  error = false;
  showCreateModal = false;
  newReportName = '';
  newReportDescription = '';
  newReportSource: string = 'manual';
  showCreateDropdown = false;

  // Selection state
  selectedIds: Set<string> = new Set();
  bulkDeleting = false;
  notification: { type: 'success' | 'error'; message: string } | null = null;

  // Export dropdown state (per report)
  openExportMenuId: string | null = null;

  constructor(private http: HttpClient) {}

  // Close export dropdown when clicking outside
  @HostListener('document:click', ['$event'])
  onDocumentClick(event: MouseEvent): void {
    const target = event.target as HTMLElement;
    if (!target.closest('.export-dropdown')) {
      this.openExportMenuId = null;
    }
  }

  // ------------------------------------------------------------------
  // Selection helpers
  // ------------------------------------------------------------------

  get allSelected(): boolean {
    return this.reports.length > 0 && this.reports.every(r => this.selectedIds.has(r.id));
  }

  get someSelected(): boolean {
    return this.selectedIds.size > 0 && !this.allSelected;
  }

  get selectedCount(): number {
    return this.selectedIds.size;
  }

  toggleSelectAll(): void {
    if (this.allSelected) {
      this.selectedIds.clear();
    } else {
      this.reports.forEach(r => this.selectedIds.add(r.id));
    }
  }

  toggleSelect(reportId: string): void {
    if (this.selectedIds.has(reportId)) {
      this.selectedIds.delete(reportId);
    } else {
      this.selectedIds.add(reportId);
    }
  }

  deselectAll(): void {
    this.selectedIds.clear();
  }

  isSelected(reportId: string): boolean {
    return this.selectedIds.has(reportId);
  }

  ngOnInit(): void {
    this.loadDashboard();
    this.loadReports();
  }

  loadDashboard(): void {
    // ✅ Added /api prefix
    this.http.get<{ status: string; data: DashboardSummary }>('/api/reporting/dashboard')
      .subscribe({
        next: (res) => {
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
    // ✅ Added /api prefix
    this.http.get<{ status: string; data: ReportSummary[] }>('/api/reporting/builder/reports?limit=50').subscribe({
      next: (res) => {
        if (res.status === 'ok') {
          this.reports = res.data;
          this.reports.forEach(r => this.loadExports(r.id));
        }
      },
      error: () => {},
    });
  }

  loadExports(reportId: string): void {
    // ✅ Added /api prefix
    this.http.get<{ status: string; data: ExportJob[] }>(`/api/reporting/builder/reports/${reportId}/exports`).subscribe({
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
    // ✅ Added /api prefix
    this.http.post<{ status: string; data: ReportSummary }>('/api/reporting/builder/reports', {
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
    // ✅ Added /api prefix
    this.http.delete<{ status: string }>(`/api/reporting/builder/reports/${reportId}`).subscribe({
      next: (res) => {
        if (res.status === 'ok') {
          this.reports = this.reports.filter(r => r.id !== reportId);
          this.selectedIds.delete(reportId);
          this.showNotification('success', 'Report deleted successfully.');
        } else {
          this.showNotification('error', 'Failed to delete report.');
        }
      },
      error: () => {
        this.showNotification('error', 'Failed to delete report.');
      },
    });
  }

  // ------------------------------------------------------------------
  // Bulk delete
  // ------------------------------------------------------------------

  bulkDelete(): void {
    const ids = Array.from(this.selectedIds);
    if (ids.length === 0) return;

    const count = ids.length;
    const confirmed = confirm(
      `Are you sure you want to delete ${count} selected report${count > 1 ? 's' : ''}? This action cannot be undone.`
    );
    if (!confirmed) return;

    this.bulkDeleting = true;
    this.http.post<{ status: string; data: { deleted: number; failed: string[]; total: number } }>(
      '/api/reporting/builder/reports/bulk-delete',
      { report_ids: ids }
    ).subscribe({
      next: (res) => {
        this.bulkDeleting = false;
        if (res.status === 'ok') {
          const deleted = res.data.deleted;
          const failed = res.data.failed.length;
          // Remove deleted reports from the list
          this.reports = this.reports.filter(r => !this.selectedIds.has(r.id));
          this.selectedIds.clear();

          if (failed > 0) {
            this.showNotification('error', `${deleted} deleted, ${failed} failed.`);
          } else {
            this.showNotification('success', `${deleted} report${deleted > 1 ? 's' : ''} deleted successfully.`);
          }
        } else {
          this.showNotification('error', 'Failed to delete reports.');
        }
      },
      error: () => {
        this.bulkDeleting = false;
        this.showNotification('error', 'Failed to delete reports.');
      },
    });
  }

  toggleExportMenu(reportId: string): void {
    this.openExportMenuId = this.openExportMenuId === reportId ? null : reportId;
  }

  isExportMenuOpen(reportId: string): boolean {
    return this.openExportMenuId === reportId;
  }

  showNotification(type: 'success' | 'error', message: string): void {
    this.notification = { type, message };
    setTimeout(() => { this.notification = null; }, 4000);
  }

  dismissNotification(): void {
    this.notification = null;
  }

  toggleFavorite(reportId: string): void {
    // ✅ Added /api prefix
    this.http.post<{ status: string; data: ReportSummary }>(`/api/reporting/builder/reports/${reportId}/favorite`, {}).subscribe({
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
    this.openExportMenuId = null;
    // ✅ Added /api prefix
    this.http.post<{ status: string; data: ExportJob }>(`/api/reporting/builder/reports/${reportId}/export`, { format }).subscribe({
      next: (res) => {
        if (res.status === 'ok') {
          if (!this.exports[reportId]) this.exports[reportId] = [];
          this.exports[reportId].unshift(res.data);
          this.showNotification('success', `Export (${format.toUpperCase()}) started.`);
        } else {
          this.showNotification('error', 'Failed to start export.');
        }
      },
      error: () => {
        this.showNotification('error', 'Failed to start export.');
      },
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
