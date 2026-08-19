import { Component, OnInit, AfterViewInit, OnDestroy, ElementRef, PLATFORM_ID, Inject, QueryList, ViewChildren } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { CommonModule, isPlatformBrowser } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Observable, Subject, forkJoin, of } from 'rxjs';
import { catchError, takeUntil, finalize } from 'rxjs/operators';
import * as echarts from 'echarts';
import { environment } from '../../../../../environments/environment';

interface ApiResponse<T> {
  status: string;
  data: T;
}

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

interface StoredChart {
  instance: echarts.ECharts;
  resizeHandler: () => void;
}

@Component({
  selector: 'app-analytics-workspace',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './analytics-workspace.component.html',
  styleUrl: './analytics-workspace.component.css',
})
export class AnalyticsWorkspaceComponent implements OnInit, AfterViewInit, OnDestroy {
  @ViewChildren('chartContainer') chartContainers!: QueryList<ElementRef>;

  kpis: KpiData | null = null;
  loading = true;
  error = false;
  isBrowser: boolean;

  // Filters
  dateFrom: string = '';
  dateTo: string = '';
  statusFilter: string = 'all';
  severityFilter: string = 'all';

  // Chart instances & lifecycle management
  private destroy$ = new Subject<void>();
  private chartInstances = new Map<string, StoredChart>();
  private chartDataCache: Record<string, ChartDataResponse> = {};
  private chartDataLoaded = false;
  private chartsRendered = false;
  private viewReady = false;

  private readonly CHART_TYPES = [
    'reconciliation_trend',
    'transaction_volume',
    'anomaly_distribution',
    'anomaly_type',
    'bank_vs_erp',
    'payment_status'
  ];

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

    // Reactively trigger chart initialization when DOM containers are created/updated
    this.chartContainers.changes
      .pipe(takeUntil(this.destroy$))
      .subscribe(() => {
        this.tryInitCharts();
      });

    // Attempt chart initialization if data is already available
    this.tryInitCharts();
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
    this.disposeCharts();
  }

  loadAllData(): void {
    this.disposeCharts();

    this.loading = true;
    this.error = false;
    this.chartDataLoaded = false;
    this.chartsRendered = false;
    this.chartDataCache = {};

    this.log('Loading data...');

    // Build observables for KPIs and individual chart datasets
    const kpiObs = this.fetchKpis().pipe(
      catchError(err => {
        this.logError('Failed to load KPIs:', err);
        return of(null);
      })
    );

    const chartDataObsMap: Record<string, Observable<ApiResponse<ChartDataResponse> | null>> = {};
    this.CHART_TYPES.forEach(type => {
      chartDataObsMap[type] = this.fetchChartData(type).pipe(
        catchError(err => {
          this.logError(`Failed to load chart data for ${type}:`, err);
          return of(null);
        })
      );
    });

    forkJoin({
      kpis: kpiObs,
      charts: forkJoin(chartDataObsMap)
    })
    .pipe(
      takeUntil(this.destroy$),
      finalize(() => {
        this.loading = false;
      })
    )
    .subscribe({
      next: (results) => {
        if (results.kpis && results.kpis.status === 'ok') {
          this.kpis = results.kpis.data;
        } else {
          this.error = true;
          this.logError('KPI payload invalid or error returned');
        }

        let loadedCount = 0;
        const chartsMap = results.charts as Record<string, ApiResponse<ChartDataResponse> | null>;
        if (chartsMap) {
          Object.keys(chartsMap).forEach(chartType => {
            const res = chartsMap[chartType];
            if (res && res.status === 'ok' && res.data) {
              this.chartDataCache[chartType] = res.data;
              loadedCount++;
            }
          });
        }

        this.chartDataLoaded = true;
        this.log(`Data loaded: ${loadedCount}/${this.CHART_TYPES.length} charts`);

        // Check if containers are ready to render charts
        this.tryInitCharts();
      },
      error: (err) => {
        this.logError('Failed to execute analytics data requests:', err);
        this.error = true;
      }
    });
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

  private fetchKpis() {
    let url = '/api/reporting/analytics/kpis';
    const params = new URLSearchParams();
    if (this.dateFrom) params.set('date_from', this.dateFrom);
    if (this.dateTo) params.set('date_to', this.dateTo);
    if (params.toString()) url += '?' + params.toString();

    return this.http.get<{ status: string; data: KpiData }>(url);
  }

  private fetchChartData(chartType: string) {
    let url = `/api/reporting/analytics/chart-data?chart_type=${chartType}`;
    if (this.dateFrom) url += `&date_from=${this.dateFrom}`;
    if (this.dateTo) url += `&date_to=${this.dateTo}`;
    if (this.statusFilter !== 'all') url += `&status=${this.statusFilter}`;
    if (this.severityFilter !== 'all') url += `&severity=${this.severityFilter}`;

    return this.http.get<{ status: string; data: ChartDataResponse }>(url);
  }

  private tryInitCharts(): void {
    if (
      !this.isBrowser ||
      !this.viewReady ||
      !this.chartDataLoaded ||
      this.chartsRendered ||
      !this.chartContainers ||
      this.chartContainers.length === 0
    ) {
      return;
    }

    this.chartsRendered = true;
    this.initCharts();
  }

  private initCharts(): void {
    const containers = this.chartContainers.toArray();
    this.log(`Rendering ${this.CHART_TYPES.length} charts`);

    let renderedCount = 0;

    this.CHART_TYPES.forEach(type => {
      const container = containers.find(
        c => c.nativeElement.dataset['chart'] === type
      );
      const dom = container?.nativeElement;

      if (dom) {
        const success = this.renderChart(type, dom);
        if (success) renderedCount++;
      } else {
        this.logError(`Container DOM not found for chart type: ${type}`);
      }
    });

    this.log(`Charts ready (${renderedCount}/${this.CHART_TYPES.length} rendered)`);

    if (typeof window !== 'undefined' && window.requestAnimationFrame) {
      window.requestAnimationFrame(() => {
        this.chartInstances.forEach(({ instance }) => {
          try { instance.resize(); } catch (e) {}
        });
      });
    }
  }

  private renderChart(chartType: string, dom: HTMLElement): boolean {
    if (!this.isBrowser || !dom) return false;

    const data = this.chartDataCache[chartType];
    if (!data) return false;

    if (chartType === 'bank_vs_erp' && (!data.labels || data.labels.length === 0)) {
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
        let item = this.chartInstances.get(chartType);
        let chartInstance = item?.instance || echarts.getInstanceByDom(dom);

        if (!chartInstance) {
          chartInstance = echarts.init(dom);
          const resizeHandler = () => {
            try { chartInstance?.resize(); } catch (e) {}
          };
          window.addEventListener('resize', resizeHandler);
          this.chartInstances.set(chartType, { instance: chartInstance, resizeHandler });
        }

        chartInstance.setOption(option, true);
        return true;
      } catch (error) {
        this.logError(`Failed to render chart: ${chartType}`, error);
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
    this.chartInstances.forEach(({ instance, resizeHandler }) => {
      if (this.isBrowser && resizeHandler) {
        window.removeEventListener('resize', resizeHandler);
      }
      try {
        instance.dispose();
      } catch (e) {}
    });
    this.chartInstances.clear();
    this.chartsRendered = false;
  }

  private log(message: string, ...args: any[]): void {
    if (!environment.production) {
      console.log(`[Analytics] ${message}`, ...args);
    }
  }

  private logError(message: string, ...args: any[]): void {
    console.error(`[Analytics] ${message}`, ...args);
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

