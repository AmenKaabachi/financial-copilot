import { Component, OnInit, AfterViewInit, OnDestroy, ViewChild, ElementRef, PLATFORM_ID, Inject, QueryList, ViewChildren } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { CommonModule, isPlatformBrowser } from '@angular/common';
import { FormsModule } from '@angular/forms';
import * as echarts from 'echarts';

interface KpiData {
  revenue: { total_revenue: number; outstanding_revenue: number; invoice_count: number; paid_invoice_count: number };
  expenses: { total_expenses: number; expense_count: number };
  profit: { net_profit: number; profit_margin: number; total_revenue: number; total_expenses: number };
  cash_flow: { total_inflows: number; total_outflows: number; net_cash_flow: number };
  outstanding_invoices: { outstanding_count: number; total_outstanding: number; average_outstanding: number };
  payment_delays: { delayed_count: number; total_delayed_amount: number };
  reconciliation_rate: { reconciliation_rate: number; total_invoices: number; reconciled_count: number; unreconciled_count: number };
  total_transactions: { erp_count: number; bank_count: number; total_count: number; erp_volume: number; bank_volume: number; total_volume: number };
  anomaly_stats: { total_anomalies: number; high_severity_count: number; medium_severity_count: number; low_severity_count: number; severity_distribution: Record<string, number>; type_distribution: Record<string, number> };
  matching_accuracy: { matching_accuracy: number; total_reconciliations: number; matched_count: number; unmatched_count: number; pending_count: number; partial_count: number };
}

interface ChartDataset {
  label: string;
  data: number[];
}

interface ChartDataResponse {
  chart_type: string;
  labels: string[];
  datasets: ChartDataset[];
  severity?: { labels: string[]; data: number[] };
  type?: { labels: string[]; data: number[] };
}

// Custom type to store resize handler with chart
interface ChartWithResize extends echarts.ECharts {
  _resizeHandler?: () => void;
}

@Component({
  selector: 'app-analytics-workspace',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './analytics-workspace.component.html',
  styleUrl: './analytics-workspace.component.css',
})
export class AnalyticsWorkspaceComponent implements OnInit, AfterViewInit, OnDestroy {
  // Use ViewChildren with a single template reference
  @ViewChildren('chartContainer')
  chartContainers!: QueryList<ElementRef>;

  kpis: KpiData | null = null;
  loading = true;
  error = false;
  isBrowser: boolean;

  // Filters
  dateFrom: string = '';
  dateTo: string = '';
  statusFilter: string = 'all';
  severityFilter: string = 'all';

  // Chart instances
  private charts: ChartWithResize[] = [];
  private chartDataCache: Record<string, ChartDataResponse> = {};
  private loadedCharts = new Set<string>();
  private viewReady = false;
  private chartDataLoaded = false;
  private isRendering = false;
  private initAttempts = 0;
  private readonly MAX_INIT_ATTEMPTS = 10;
  private readonly CHART_TYPES = ['reconciliation_trend', 'transaction_volume', 'anomaly_distribution', 'anomaly_type', 'bank_vs_erp', 'payment_status'];

  constructor(
    private http: HttpClient,
    @Inject(PLATFORM_ID) platformId: Object
  ) {
    this.isBrowser = isPlatformBrowser(platformId);
  }

  ngOnInit(): void {
    this.loadAllData();
  }

  ngAfterViewInit(): void {
    if (!this.isBrowser) return;

    this.viewReady = true;

    // Log initial view children
    console.log('[Analytics] Initial view children:', this.chartContainers.length);

    // Subscribe to changes in chart containers
    this.chartContainers.changes.subscribe(() => {
      console.log('[Analytics] View children changed - containers:', this.chartContainers.length);
      if (this.chartDataLoaded && this.chartContainers.length > 0) {
        this.tryInitCharts();
      }
    });

    // Initial attempt after a delay
    setTimeout(() => {
      if (this.chartDataLoaded) {
        this.tryInitCharts();
      }
    }, 300);
  }

  ngOnDestroy(): void {
    this.disposeCharts();
  }

  loadAllData(): void {
    // Dispose existing charts before loading new data
    this.disposeCharts();

    this.loading = true;
    this.error = false;
    this.chartDataLoaded = false;
    this.chartDataCache = {};
    this.loadedCharts.clear();
    this.initAttempts = 0;

    this.loadKpis();
    this.CHART_TYPES.forEach(type => this.loadChartData(type));
  }

  applyFilters(): void {
    this.loadAllData();
  }

  resetFilters(): void {
    this.dateFrom = '';
    this.dateTo = '';
    this.statusFilter = 'all';
    this.severityFilter = 'all';
    this.loadAllData();
  }

  private loadKpis(): void {
    let url = '/api/reporting/analytics/kpis';
    const params = new URLSearchParams();
    if (this.dateFrom) params.set('date_from', this.dateFrom);
    if (this.dateTo) params.set('date_to', this.dateTo);
    if (params.toString()) url += '?' + params.toString();

    console.log('[Analytics] Fetching KPIs from:', url);

    this.http.get<{ status: string; data: KpiData }>(url).subscribe({
      next: (res) => {
        console.log('[Analytics] KPI response:', res);
        if (res.status === 'ok') {
          this.kpis = res.data;

          // ✅ Trigger chart initialization after KPI loads
          setTimeout(() => {
            if (this.chartDataLoaded) {
              console.log('[Analytics] KPI loaded, retry chart initialization');
              this.tryInitCharts();
            }
          }, 300);
        } else {
          console.error('[Analytics] KPI response status not ok:', res);
          this.error = true;
        }
        this.loading = false;
      },
      error: (err) => {
        console.error('[Analytics] KPI error:', err);
        this.error = true;
        this.loading = false;
      },
    });
  }

  private loadChartData(chartType: string): void {
    let url = `/api/reporting/analytics/chart-data?chart_type=${chartType}`;
    if (this.dateFrom) url += `&date_from=${this.dateFrom}`;
    if (this.dateTo) url += `&date_to=${this.dateTo}`;
    if (this.statusFilter !== 'all') url += `&status=${this.statusFilter}`;
    if (this.severityFilter !== 'all') url += `&severity=${this.severityFilter}`;

    console.log('[Analytics] Fetching chart data from:', url);

    this.http.get<{ status: string; data: ChartDataResponse }>(url).subscribe({
      next: (res) => {
        console.log('[Analytics] Chart data for', chartType, ':', res);
        if (res.status === 'ok' && res.data) {
          const chartData = res.data;

          // Store data
          this.chartDataCache[chartType] = chartData;
          this.loadedCharts.add(chartType);

          // Check if ALL charts are loaded
          const allLoaded = this.loadedCharts.size === this.CHART_TYPES.length;

          if (allLoaded) {
            console.log('[Analytics] All charts data loaded!');
            this.chartDataLoaded = true;

            // Give Angular time to create DOM elements
            setTimeout(() => {
              this.tryInitCharts();
            }, 200);
          }
        }
      },
      error: (err) => {
        console.error('[Analytics] Chart data error:', chartType, err);
        // Mark as loaded even on error to prevent infinite waiting
        this.loadedCharts.add(chartType);

        const allLoaded = this.loadedCharts.size === this.CHART_TYPES.length;
        if (allLoaded) {
          console.log('[Analytics] All charts loaded (with errors)');
          this.chartDataLoaded = true;
          setTimeout(() => {
            this.tryInitCharts();
          }, 200);
        }
      },
    });
  }

  private tryInitCharts(): void {
    this.initAttempts++;

    // Log current state
    console.log(`[Analytics] Try #${this.initAttempts} - viewReady:`, this.viewReady,
                'dataLoaded:', this.chartDataLoaded,
                'loaded:', this.loadedCharts.size,
                'expected:', this.CHART_TYPES.length,
                'containers:', this.chartContainers.length);

    // Only initialize if ALL conditions are met
    if (
      !this.isBrowser ||
      !this.viewReady ||
      !this.chartDataLoaded ||
      this.loadedCharts.size < this.CHART_TYPES.length ||
      this.isRendering
    ) {
      console.log('[Analytics] Waiting for conditions...');

      // If we have data but no containers yet, wait for containers
      if (this.chartDataLoaded && this.chartContainers.length === 0 && this.initAttempts < this.MAX_INIT_ATTEMPTS) {
        console.log('[Analytics] Waiting for containers to appear...');
        setTimeout(() => {
          this.tryInitCharts();
        }, 300);
      }
      return;
    }

    // Check if containers exist
    if (this.chartContainers.length === 0) {
      console.warn('[Analytics] No containers found, retrying...');
      if (this.initAttempts < this.MAX_INIT_ATTEMPTS) {
        setTimeout(() => {
          this.tryInitCharts();
        }, 300);
      }
      return;
    }

    console.log('[Analytics] All conditions met, initializing charts...');
    this.initCharts();
  }

  private initCharts(): void {
    if (!this.isBrowser || this.isRendering || this.chartContainers.length === 0) return;
    this.isRendering = true;

    console.log('[Analytics] Initializing charts with', this.chartContainers.length, 'containers');

    // Get containers as array
    const containers = this.chartContainers.toArray();
    console.log('[Analytics] Containers:', containers.length);

    // Map chart types to container indices (matches HTML order)
    const chartDomMap: Record<string, HTMLElement | undefined> = {
      reconciliation_trend: containers[0]?.nativeElement,
      transaction_volume: containers[1]?.nativeElement,
      anomaly_distribution: containers[2]?.nativeElement,
      anomaly_type: containers[3]?.nativeElement,
      bank_vs_erp: containers[4]?.nativeElement,
      payment_status: containers[5]?.nativeElement,
    };

    let renderedCount = 0;

    // Render each chart
    this.CHART_TYPES.forEach(type => {
      if (this.chartDataCache[type]) {
        const dom = chartDomMap[type];
        if (dom) {
          const success = this.renderChart(type, dom);
          if (success) renderedCount++;
        } else {
          console.warn('[Analytics] DOM not ready for chart:', type);
        }
      }
    });

    console.log(`[Analytics] Rendered ${renderedCount} charts`);
    this.isRendering = false;

    // Force resize after all charts are rendered
    setTimeout(() => {
      this.charts.forEach(chart => {
        try { chart.resize(); } catch (e) {}
      });
    }, 200);
  }

  private renderChart(chartType: string, dom: HTMLElement): boolean {
    if (!this.isBrowser || !dom) return false;

    const data = this.chartDataCache[chartType];
    if (!data) return false;

    // Skip if no data for specific chart types
    if (chartType === 'bank_vs_erp' && (!data.labels || data.labels.length === 0)) {
      console.warn('[Analytics] Skipping bank_vs_erp chart - no labels data');
      return false;
    }

    let option: echarts.EChartsOption = {};

    switch (chartType) {
      case 'reconciliation_trend':
        option = this.buildLineChart(data);
        break;
      case 'transaction_volume':
        option = this.buildBarChart(data);
        break;
      case 'anomaly_distribution':
        if (data.severity?.labels && data.severity?.data) {
          option = this.buildDonutChart(data.severity.labels, data.severity.data);
        }
        break;
      case 'anomaly_type':
        if (data.labels && data.datasets && data.datasets.length > 0) {
          option = this.buildHorizontalBarChart(data.labels, data.datasets[0].data);
        }
        break;
      case 'bank_vs_erp':
        if (data.labels && data.labels.length > 0) {
          option = this.buildGroupedBarChart(data);
        }
        break;
      case 'payment_status':
        option = this.buildPieChart(data);
        break;
    }

    if (Object.keys(option).length > 0) {
      try {
        // Dispose existing chart
        const existing = echarts.getInstanceByDom(dom);
        if (existing) {
          existing.dispose();
        }

        const chart = echarts.init(dom) as ChartWithResize;
        chart.setOption(option);

        // Store resize handler
        const resizeHandler = () => {
          try { chart.resize(); } catch (e) {}
        };
        chart._resizeHandler = resizeHandler;

        this.charts.push(chart);
        window.addEventListener('resize', resizeHandler);

        // Force initial resize
        setTimeout(() => {
          try { chart.resize(); } catch (e) {}
        }, 100);

        console.log(`[Analytics] Successfully rendered chart: ${chartType}`);
        return true;
      } catch (error) {
        console.warn('[Analytics] Failed to render chart:', chartType, error);
        return false;
      }
    }

    return false;
  }

  private buildLineChart(data: ChartDataResponse): echarts.EChartsOption {
    return {
      tooltip: { trigger: 'axis' },
      legend: { bottom: 0, data: data.datasets.map(d => d.label) },
      grid: { left: '3%', right: '4%', bottom: '15%', top: '10%', containLabel: true },
      xAxis: { type: 'category', data: data.labels, axisLabel: { rotate: 45, fontSize: 10 } },
      yAxis: { type: 'value' },
      series: data.datasets.map(d => ({
        name: d.label,
        type: 'line' as const,
        smooth: true,
        areaStyle: { opacity: 0.15 },
        data: d.data,
        itemStyle: { color: d.label === 'Successful' ? '#10b981' : '#ef4444' },
      })),
    };
  }

  private buildBarChart(data: ChartDataResponse): echarts.EChartsOption {
    return {
      tooltip: { trigger: 'axis' },
      grid: { left: '3%', right: '4%', bottom: '15%', top: '10%', containLabel: true },
      xAxis: { type: 'category', data: data.labels, axisLabel: { rotate: 45, fontSize: 10 } },
      yAxis: { type: 'value' },
      series: data.datasets.map(d => ({
        name: d.label,
        type: 'bar' as const,
        data: d.data,
        itemStyle: { color: '#2F5FE0', borderRadius: [4, 4, 0, 0] },
      })),
    };
  }

  private buildDonutChart(labels: string[], data: number[]): echarts.EChartsOption {
    const colors = ['#ef4444', '#f59e0b', '#10b981', '#6b7280'];
    return {
      tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
      series: [{
        type: 'pie' as const,
        radius: ['40%', '70%'],
        center: ['50%', '55%'],
        avoidLabelOverlap: false,
        label: { show: true, formatter: '{b}\n{d}%', fontSize: 10 },
        emphasis: { label: { show: true, fontSize: 14, fontWeight: 'bold' } },
        data: labels.map((l, i) => ({
          value: data[i] || 0,
          name: l,
          itemStyle: { color: colors[i % colors.length] }
        })),
      }],
    };
  }

  private buildHorizontalBarChart(labels: string[], data: number[]): echarts.EChartsOption {
    return {
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      grid: { left: '3%', right: '4%', bottom: '10%', top: '10%', containLabel: true },
      xAxis: { type: 'value' },
      yAxis: { type: 'category', data: labels, axisLabel: { fontSize: 10 } },
      series: [{
        type: 'bar' as const,
        data: data.map((v, i) => ({
          value: v,
          itemStyle: { color: ['#6366f1', '#8b5cf6', '#a78bfa', '#c4b5fd'][i % 4] }
        })),
      }],
    };
  }

  private buildGroupedBarChart(data: ChartDataResponse): echarts.EChartsOption {
    return {
      tooltip: { trigger: 'axis' },
      legend: { bottom: 0, data: data.datasets.map(d => d.label) },
      grid: { left: '3%', right: '4%', bottom: '15%', top: '10%', containLabel: true },
      xAxis: { type: 'category', data: data.labels, axisLabel: { rotate: 45, fontSize: 10 } },
      yAxis: { type: 'value' },
      series: data.datasets.map(d => ({
        name: d.label,
        type: 'bar' as const,
        data: d.data,
        itemStyle: { color: d.label === 'ERP Volume' ? '#2F5FE0' : '#10b981' },
        barGap: '20%',
      })),
    };
  }

  private buildPieChart(data: ChartDataResponse): echarts.EChartsOption {
    const colors = ['#10b981', '#f59e0b'];
    return {
      tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
      series: [{
        type: 'pie' as const,
        radius: ['0%', '70%'],
        center: ['50%', '55%'],
        label: { show: true, formatter: '{b}\n{d}%', fontSize: 12 },
        data: data.labels.map((l, i) => ({
          value: data.datasets[0]?.data[i] || 0,
          name: l,
          itemStyle: { color: colors[i % colors.length] }
        })),
      }],
    };
  }

  private disposeCharts(): void {
    this.charts.forEach((chart) => {
      if (chart._resizeHandler) {
        window.removeEventListener('resize', chart._resizeHandler);
      }
      try { chart.dispose(); } catch (e) {}
    });
    this.charts = [];
    this.isRendering = false;
  }

  // Helper methods for template
  getKpiValue(key: string): number {
    if (!this.kpis) return 0;
    const kpi = (this.kpis as any)[key];
    if (!kpi) return 0;

    switch (key) {
      case 'revenue': return kpi.total_revenue || 0;
      case 'expenses': return kpi.total_expenses || 0;
      case 'profit': return kpi.net_profit || 0;
      case 'cash_flow': return kpi.net_cash_flow || 0;
      case 'reconciliation_rate': return kpi.reconciliation_rate || 0;
      case 'matching_accuracy': return kpi.matching_accuracy || 0;
      case 'total_transactions': return kpi.total_count || 0;
      case 'anomaly_stats': return kpi.total_anomalies || 0;
      default: return 0;
    }
  }

  getKpiLabel(key: string): string {
    const labels: Record<string, string> = {
      revenue: 'Revenue',
      expenses: 'Expenses',
      profit: 'Net Profit',
      cash_flow: 'Cash Flow',
      outstanding_invoices: 'Outstanding',
      payment_delays: 'Delays',
      reconciliation_rate: 'Recon. Rate',
      total_transactions: 'Transactions',
      anomaly_stats: 'Anomalies',
      matching_accuracy: 'Match Accuracy',
    };
    return labels[key] || key;
  }

  getKpiSubtext(key: string): string {
    if (!this.kpis) return '';
    const kpi = (this.kpis as any)[key];
    if (!kpi) return '';
    switch (key) {
      case 'revenue': return `${kpi.paid_invoice_count || 0} paid invoices`;
      case 'expenses': return `${kpi.expense_count || 0} expense entries`;
      case 'profit': return `${kpi.profit_margin || 0}% margin`;
      case 'cash_flow': return `${kpi.total_inflows || 0} inflows`;
      case 'outstanding_invoices': return `${kpi.outstanding_count || 0} invoices`;
      case 'payment_delays': return `${kpi.total_delayed_amount || 0} delayed`;
      case 'reconciliation_rate': return `${kpi.reconciled_count || 0}/${kpi.total_invoices || 0}`;
      case 'total_transactions': return `${kpi.erp_count || 0} ERP / ${kpi.bank_count || 0} Bank`;
      case 'anomaly_stats': return `${kpi.high_severity_count || 0} high severity`;
      case 'matching_accuracy': return `${kpi.matched_count || 0}/${kpi.total_reconciliations || 0}`;
      default: return '';
    }
  }

}
