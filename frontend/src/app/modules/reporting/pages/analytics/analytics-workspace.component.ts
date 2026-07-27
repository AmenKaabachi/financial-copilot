import { Component, OnInit } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';

interface KpiData {
  revenue: { total_revenue: number; outstanding_revenue: number; invoice_count: number; paid_invoice_count: number };
  expenses: { total_expenses: number; expense_count: number };
  profit: { net_profit: number; profit_margin: number; total_revenue: number; total_expenses: number };
  cash_flow: { total_inflows: number; total_outflows: number; net_cash_flow: number };
  outstanding_invoices: { outstanding_count: number; total_outstanding: number; average_outstanding: number };
  payment_delays: { delayed_count: number; total_delayed_amount: number };
  reconciliation_rate: { reconciliation_rate: number; total_invoices: number; reconciled_count: number; unreconciled_count: number };
}

interface TrendPoint {
  period: string;
  value: number;
}

interface HeatmapCell {
  date: string;
  severity: string;
  count: number;
}

interface PivotRow {
  group: string;
  total: number;
  count: number;
  average?: number;
}

@Component({
  selector: 'app-analytics-workspace',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './analytics-workspace.component.html',
  styleUrl: './analytics-workspace.component.css',
})
export class AnalyticsWorkspaceComponent implements OnInit {
  kpis: KpiData | null = null;
  trends: TrendPoint[] = [];
  heatmapData: any = null;
  pivotData: PivotRow[] = [];
  loading = true;
  error = false;

  activeTab = 'kpis';
  trendMetric = 'amount';
  trendBucket = 'month';
  pivotRowField = 'category';
  pivotColumnField = 'month';
  pivotValueField = 'amount';
  pivotAggFunc = 'sum';

  dateFrom: string = '';
  dateTo: string = '';

  constructor(private http: HttpClient) {}

  ngOnInit(): void {
    this.loadKpis();
    this.loadTrends();
    this.loadHeatmap();
    this.loadPivot();
  }

  loadKpis(): void {
    this.http.get<{ status: string; data: KpiData }>('/reporting/analytics/kpis').subscribe({
      next: (res) => {
        if (res.status === 'ok') {
          this.kpis = res.data;
        }
        this.loading = false;
      },
      error: () => {
        this.error = true;
        this.loading = false;
      },
    });
  }

  loadTrends(): void {
    this.http.get<{ status: string; data: { series: TrendPoint[] } }>(
      `/reporting/analytics/trends?metric=${this.trendMetric}&bucket=${this.trendBucket}`
    ).subscribe({
      next: (res) => {
        if (res.status === 'ok') {
          this.trends = res.data.series;
        }
      },
      error: () => {},
    });
  }

  loadHeatmap(): void {
    this.http.get<{ status: string; data: any }>('/reporting/analytics/heatmap').subscribe({
      next: (res) => {
        if (res.status === 'ok') {
          this.heatmapData = res.data;
        }
      },
      error: () => {},
    });
  }

  loadPivot(): void {
    this.http.get<{ status: string; data: { rows: PivotRow[] } }>(
      `/reporting/analytics/pivot?row_field=${this.pivotRowField}&column_field=${this.pivotColumnField}&value_field=${this.pivotValueField}&agg_func=${this.pivotAggFunc}`
    ).subscribe({
      next: (res) => {
        if (res.status === 'ok') {
          this.pivotData = res.data.rows || [];
        }
      },
      error: () => {},
    });
  }

  refreshAll(): void {
    this.loadKpis();
    this.loadTrends();
    this.loadHeatmap();
    this.loadPivot();
  }

  getKpiValue(key: keyof KpiData): number {
    if (!this.kpis) return 0;
    const kpi = this.kpis[key];
    if (!kpi) return 0;
    if (key === 'profit') return (kpi as any).net_profit || 0;
    if (key === 'cash_flow') return (kpi as any).net_cash_flow || 0;
    if (key === 'reconciliation_rate') return (kpi as any).reconciliation_rate || 0;
    return 0;
  }

  getKpiLabel(key: keyof KpiData): string {
    const labels: Record<string, string> = {
      revenue: 'Revenue',
      expenses: 'Expenses',
      profit: 'Net Profit',
      cash_flow: 'Cash Flow',
      outstanding_invoices: 'Outstanding Invoices',
      payment_delays: 'Payment Delays',
      reconciliation_rate: 'Reconciliation Rate',
    };
    return labels[key] || key;
  }

  getMaxTrendValue(): number {
    if (this.trends.length === 0) return 0;
    return Math.max(...this.trends.map((t) => Math.abs(t.value)));
  }
}
