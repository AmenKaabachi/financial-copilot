import { Component, OnInit } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';

interface DashboardSummary {
  total_reports: number;
  draft_reports: number;
  published_reports: number;
  total_templates: number;
  total_exports: number;
  recent_reports: ReportSummary[];
  favorite_reports: ReportSummary[];
}

interface ReportSummary {
  id: string;
  name: string;
  description: string;
  status: string;
  source: string;
  created_at: string;
  updated_at: string;
}

interface WidgetState {
  title: string;
  icon: string;
  value: string;
  subtitle: string;
  emptyMessage: string;
  items: ReportSummary[];
  loading: boolean;
}

@Component({
  selector: 'app-reporting-dashboard',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './reporting-dashboard.component.html',
  styleUrl: './reporting-dashboard.component.css',
})
export class ReportingDashboardComponent implements OnInit {
  summary: DashboardSummary | null = null;
  loading = true;
  error = false;

  widgets: WidgetState[] = [
    {
      title: 'Recent Reports',
      icon: 'document-text',
      value: '',
      subtitle: 'Most recently created reports',
      emptyMessage: 'No reports yet. Create your first report in the Report Builder.',
      items: [],
      loading: true,
    },
    {
      title: 'Favorites',
      icon: 'star',
      value: '',
      subtitle: 'Your starred reports',
      emptyMessage: 'No favorite reports yet. Star a report to keep it here.',
      items: [],
      loading: true,
    },
    {
      title: 'Scheduled',
      icon: 'calendar',
      value: '',
      subtitle: 'Reports scheduled for delivery',
      emptyMessage: 'No scheduled reports yet. Set up a schedule in the Builder.',
      items: [],
      loading: true,
    },
    {
      title: 'AI-Generated',
      icon: 'sparkles',
      value: '',
      subtitle: 'Reports created by the AI Generator',
      emptyMessage: 'No AI-generated reports yet. Use the AI Generator to create one.',
      items: [],
      loading: true,
    },
  ];

  constructor(private http: HttpClient) {}

  ngOnInit(): void {
    this.loadDashboard();
  }

  loadDashboard(): void {
    this.loading = true;
    this.error = false;

    this.http.get<{ status: string; data: DashboardSummary }>('/reporting/dashboard').subscribe({
      next: (response) => {
        if (response.status === 'ok' && response.data) {
          this.summary = response.data;
          this.populateWidgets();
        }
        this.loading = false;
      },
      error: () => {
        this.error = true;
        this.loading = false;
      },
    });
  }

  private populateWidgets(): void {
    if (!this.summary) return;

    this.widgets[0].value = String(this.summary.total_reports);
    this.widgets[0].items = this.summary.recent_reports;
    this.widgets[0].loading = false;

    this.widgets[1].value = String(this.summary.favorite_reports.length);
    this.widgets[1].items = this.summary.favorite_reports;
    this.widgets[1].loading = false;

    this.widgets[2].value = '0';
    this.widgets[2].loading = false;

    this.widgets[3].value = String(
      this.summary.recent_reports.filter((r) => r.source === 'ai').length
    );
    this.widgets[3].loading = false;
  }

  getWidgetEmptyMessage(widget: WidgetState): string {
    return widget.emptyMessage;
  }

  isWidgetEmpty(widget: WidgetState): boolean {
    return widget.items.length === 0 && !widget.loading;
  }
}
