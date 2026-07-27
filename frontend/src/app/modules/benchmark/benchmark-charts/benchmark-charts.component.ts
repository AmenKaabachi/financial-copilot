import { Component, Input, AfterViewInit, OnChanges, SimpleChanges, ElementRef, ViewChild, PLATFORM_ID, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { isPlatformBrowser } from '@angular/common';
import * as echarts from 'echarts';
import { BenchmarkResult } from '../benchmark.models';

@Component({
  selector: 'app-benchmark-charts',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './benchmark-charts.component.html',
  styleUrl: './benchmark-charts.component.css'
})
export class BenchmarkChartsComponent implements AfterViewInit, OnChanges {
  @Input() results: BenchmarkResult[] = [];
  @Input() visible: boolean = false;

  @ViewChild('responseTimeChart') responseTimeChartRef!: ElementRef;
  @ViewChild('tokenEfficiencyChart') tokenEfficiencyChartRef!: ElementRef;
  @ViewChild('qualitySpeedChart') qualitySpeedChartRef!: ElementRef;
  @ViewChild('rankingChart') rankingChartRef!: ElementRef;

  private platformId = inject(PLATFORM_ID);
  private responseTimeChart: echarts.ECharts | null = null;
  private tokenEfficiencyChart: echarts.ECharts | null = null;
  private qualitySpeedChart: echarts.ECharts | null = null;
  private rankingChart: echarts.ECharts | null = null;

  successfulResults: BenchmarkResult[] = [];

  ngAfterViewInit(): void {
    if (isPlatformBrowser(this.platformId) && this.visible && this.results.length > 0) {
      this.successfulResults = this.results.filter(r => r.status === 'SUCCESS');
      this.initCharts();
    }
  }

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['results'] && this.results.length > 0) {
      this.successfulResults = this.results.filter(r => r.status === 'SUCCESS');
    }
    if (changes['visible'] && this.visible && isPlatformBrowser(this.platformId) && this.results.length > 0) {
      // Delay to ensure DOM is rendered
      setTimeout(() => this.initCharts(), 100);
    }
  }

  private initCharts(): void {
    this.disposeCharts();
    if (this.successfulResults.length === 0) return;

    this.renderResponseTimeChart();
    this.renderTokenEfficiencyChart();
    this.renderQualitySpeedChart();
    this.renderRankingChart();
  }

  private getModelShortName(modelId: string): string {
    const map: Record<string, string> = {
      'openai/gpt-oss-20b:free': 'GPT OSS 20B',
      'google/gemma-4-26b-a4b-it:free': 'Gemma 26B A4B',
      'poolside/laguna-xs-2.1:free': 'Laguna XS 2.1',
      'nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free': 'Nemotron Omni 30B',
      'nvidia/nemotron-3-nano-30b-a3b:free': 'Nemotron Nano 30B',
      'nvidia/nemotron-nano-9b-v2:free': 'Nemotron Nano 9B',
      'google/gemma-4-31b-it:free': 'Gemma 31B IT',
      'nvidia/nemotron-3-ultra-550b-a55b:free': 'Nemotron Ultra 550B',
      'nvidia/nemotron-3-super-120b-a12b:free': 'Nemotron Super 120B',
    };
    return map[modelId] || modelId.split('/').pop() || modelId;
  }

  private renderResponseTimeChart(): void {
    if (!this.responseTimeChartRef) return;
    const dom = this.responseTimeChartRef.nativeElement;
    this.responseTimeChart = echarts.init(dom);

    const models = this.successfulResults.map(r => this.getModelShortName(r.model));
    const responseTimes = this.successfulResults.map(r => +(r.response_time_ms / 1000).toFixed(2));
    const ttftTimes = this.successfulResults.map(r => +(r.ttft_ms / 1000).toFixed(2));

    this.responseTimeChart.setOption({
      title: {
        text: 'Model Response Time',
        left: 'center',
        textStyle: { fontSize: 14, fontWeight: 600 }
      },
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' }
      },
      legend: {
        data: ['Total Response Time', 'Time to First Token'],
        top: 30
      },
      grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
      xAxis: {
        type: 'category',
        data: models,
        axisLabel: { rotate: 30, fontSize: 10 }
      },
      yAxis: {
        type: 'value',
        name: 'Seconds'
      },
      series: [
        {
          name: 'Total Response Time',
          type: 'bar',
          data: responseTimes,
          itemStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: '#6366f1' },
              { offset: 1, color: '#818cf8' }
            ]),
            borderRadius: [4, 4, 0, 0]
          },
          label: {
            show: true,
            position: 'top',
            formatter: (params: any) => params.value + 's',
            fontSize: 10
          }
        },
        {
          name: 'Time to First Token',
          type: 'bar',
          data: ttftTimes,
          itemStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: '#f59e0b' },
              { offset: 1, color: '#fbbf24' }
            ]),
            borderRadius: [4, 4, 0, 0]
          },
          label: {
            show: true,
            position: 'top',
            formatter: (params: any) => params.value + 's',
            fontSize: 10
          }
        }
      ]
    });

    this.responseTimeChart.resize();
  }

  private renderTokenEfficiencyChart(): void {
    if (!this.tokenEfficiencyChartRef) return;
    const dom = this.tokenEfficiencyChartRef.nativeElement;
    this.tokenEfficiencyChart = echarts.init(dom);

    const models = this.successfulResults.map(r => this.getModelShortName(r.model));
    const tokensPerSec = this.successfulResults.map(r => r.tokens_per_second);
    const totalTokens = this.successfulResults.map(r => r.total_tokens);

    this.tokenEfficiencyChart.setOption({
      title: {
        text: 'Token Efficiency',
        left: 'center',
        textStyle: { fontSize: 14, fontWeight: 600 }
      },
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' }
      },
      legend: {
        data: ['Tokens/Sec', 'Total Tokens'],
        top: 30
      },
      grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
      xAxis: {
        type: 'category',
        data: models,
        axisLabel: { rotate: 30, fontSize: 10 }
      },
      yAxis: [
        {
          type: 'value',
          name: 'Tokens/Sec',
          position: 'left'
        },
        {
          type: 'value',
          name: 'Total Tokens',
          position: 'right'
        }
      ],
      series: [
        {
          name: 'Tokens/Sec',
          type: 'bar',
          data: tokensPerSec,
          itemStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: '#10b981' },
              { offset: 1, color: '#34d399' }
            ]),
            borderRadius: [4, 4, 0, 0]
          },
          label: {
            show: true,
            position: 'top',
            formatter: (params: any) => params.value,
            fontSize: 10
          }
        },
        {
          name: 'Total Tokens',
          type: 'line',
          yAxisIndex: 1,
          data: totalTokens,
          lineStyle: { color: '#8b5cf6', width: 2 },
          itemStyle: { color: '#8b5cf6' },
          symbol: 'circle',
          symbolSize: 8,
          label: {
            show: true,
            position: 'top',
            formatter: (params: any) => params.value,
            fontSize: 10
          }
        }
      ]
    });

    this.tokenEfficiencyChart.resize();
  }

  private renderQualitySpeedChart(): void {
    if (!this.qualitySpeedChartRef) return;
    const dom = this.qualitySpeedChartRef.nativeElement;
    this.qualitySpeedChart = echarts.init(dom);

    const data = this.successfulResults.map(r => ({
      name: this.getModelShortName(r.model),
      value: [
        +(r.response_time_ms / 1000).toFixed(2),
        r.tokens_per_second,
        r.quality_score || 3
      ]
    }));

    this.qualitySpeedChart.setOption({
      title: {
        text: 'Quality vs Speed',
        left: 'center',
        textStyle: { fontSize: 14, fontWeight: 600 }
      },
      tooltip: {
        formatter: (params: any) => {
          const d = params.data;
          return `<strong>${d.name}</strong><br/>
                  Response Time: ${d.value[0]}s<br/>
                  Tokens/Sec: ${d.value[1]}<br/>
                  Quality Score: ${'★'.repeat(d.value[2])}${'☆'.repeat(5 - d.value[2])}`;
        }
      },
      grid: { left: '3%', right: '8%', bottom: '3%', containLabel: true },
      xAxis: {
        type: 'value',
        name: 'Response Time (s)',
        nameLocation: 'middle',
        nameGap: 25
      },
      yAxis: {
        type: 'value',
        name: 'Tokens/Sec'
      },
      series: [
        {
          type: 'scatter',
          data: data,
          symbolSize: (val: number[]) => Math.max(12, val[2] * 6),
          itemStyle: {
            color: (params: any) => {
              const score = params.data.value[2];
              if (score >= 4) return '#10b981';
              if (score >= 3) return '#6366f1';
              if (score >= 2) return '#f59e0b';
              return '#ef4444';
            }
          },
          label: {
            show: true,
            formatter: (params: any) => params.data.name,
            position: 'right',
            fontSize: 10
          },
          emphasis: {
            itemStyle: {
              shadowBlur: 10,
              shadowOffsetX: 0,
              shadowColor: 'rgba(0, 0, 0, 0.3)'
            }
          }
        }
      ]
    });

    this.qualitySpeedChart.resize();
  }

  private renderRankingChart(): void {
    if (!this.rankingChartRef) return;
    const dom = this.rankingChartRef.nativeElement;
    this.rankingChart = echarts.init(dom);

    const models = this.successfulResults.map(r => this.getModelShortName(r.model));

    // Normalize metrics for radar chart (0-100 scale)
    const maxResponseTime = Math.max(...this.successfulResults.map(r => r.response_time_ms));
    const maxTTFT = Math.max(...this.successfulResults.map(r => r.ttft_ms));
    const maxTokens = Math.max(...this.successfulResults.map(r => r.total_tokens));
    const maxTPS = Math.max(...this.successfulResults.map(r => r.tokens_per_second));

    const radarData = this.successfulResults.map(r => ({
      name: this.getModelShortName(r.model),
      value: [
        // Speed score (inverse of response time, higher is better)
        maxResponseTime > 0 ? +((1 - r.response_time_ms / maxResponseTime) * 100).toFixed(0) : 0,
        // Latency score (inverse of TTFT)
        maxTTFT > 0 ? +((1 - r.ttft_ms / maxTTFT) * 100).toFixed(0) : 0,
        // Token efficiency (inverse of total tokens)
        maxTokens > 0 ? +((1 - r.total_tokens / maxTokens) * 100).toFixed(0) : 0,
        // Throughput (tokens/sec normalized)
        maxTPS > 0 ? +((r.tokens_per_second / maxTPS) * 100).toFixed(0) : 0,
        // Quality score
        +((r.quality_score || 3) / 5 * 100).toFixed(0)
      ]
    }));

    this.rankingChart.setOption({
      title: {
        text: 'Overall Model Ranking',
        left: 'center',
        textStyle: { fontSize: 14, fontWeight: 600 }
      },
      tooltip: {
        trigger: 'item'
      },
      legend: {
        data: models,
        top: 30,
        textStyle: { fontSize: 10 }
      },
      radar: {
        indicator: [
          { name: 'Speed', max: 100 },
          { name: 'Latency', max: 100 },
          { name: 'Token Efficiency', max: 100 },
          { name: 'Throughput', max: 100 },
          { name: 'Quality', max: 100 }
        ],
        center: ['50%', '60%'],
        radius: '60%',
        shape: 'circle',
        axisName: {
          color: '#64748b',
          fontSize: 10
        },
        splitArea: {
          areaStyle: {
            color: ['rgba(99, 102, 241, 0.02)', 'rgba(99, 102, 241, 0.05)']
          }
        }
      },
      series: [
        {
          type: 'radar',
          data: radarData,
          symbol: 'circle',
          symbolSize: 6,
          lineStyle: { width: 2 },
          areaStyle: { opacity: 0.1 }
        }
      ]
    });

    this.rankingChart.resize();
  }

  private disposeCharts(): void {
    if (this.responseTimeChart) { this.responseTimeChart.dispose(); this.responseTimeChart = null; }
    if (this.tokenEfficiencyChart) { this.tokenEfficiencyChart.dispose(); this.tokenEfficiencyChart = null; }
    if (this.qualitySpeedChart) { this.qualitySpeedChart.dispose(); this.qualitySpeedChart = null; }
    if (this.rankingChart) { this.rankingChart.dispose(); this.rankingChart = null; }
  }

  onResize(): void {
    if (this.responseTimeChart) this.responseTimeChart.resize();
    if (this.tokenEfficiencyChart) this.tokenEfficiencyChart.resize();
    if (this.qualitySpeedChart) this.qualitySpeedChart.resize();
    if (this.rankingChart) this.rankingChart.resize();
  }
}
