import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MarkdownModule } from 'ngx-markdown';
import { BenchmarkService } from './benchmark.service';
import { BenchmarkChartsComponent } from './benchmark-charts/benchmark-charts.component';
import {
  BenchmarkRequest,
  BenchmarkResponse,
  BenchmarkResult,
  AVAILABLE_BENCHMARK_MODELS,
  INTENT_OPTIONS,
} from './benchmark.models';

@Component({
  selector: 'app-benchmark',
  standalone: true,
  imports: [CommonModule, FormsModule, MarkdownModule, BenchmarkChartsComponent],
  templateUrl: './benchmark.component.html',
  styleUrl: './benchmark.component.css'
})
export class BenchmarkComponent {
  private benchmarkService = inject(BenchmarkService);

  // Configuration Inputs
  question: string = 'Explain why invoice INV00020 failed reconciliation';
  selectedModels: string[] = [
    'openai/gpt-oss-20b:free',
    'google/gemma-4-26b-a4b-it:free',
    'google/gemma-4-31b-it:free'
  ];
  maxTokens: number = 800;
  temperature: number = 0.2;
  selectedIntent: string = 'AUTO';

  // Constants
  availableModels = AVAILABLE_BENCHMARK_MODELS;
  intentOptions = INTENT_OPTIONS;

  // Execution State
  isLoading: boolean = false;
  errorMessage: string = '';
  benchmarkData: BenchmarkResponse | null = null;
  sortColumn: keyof BenchmarkResult = 'response_time_ms';
  sortAscending: boolean = true;

  // Preset example prompts
  presets = [
    "Summarize these invoices",
    "Why did invoice INV00020 fail reconciliation?",
    "Explain missing payment anomaly INV00020"
  ];

  setPreset(presetText: string): void {
    this.question = presetText;
  }

  isModelSelected(modelId: string): boolean {
    return this.selectedModels.includes(modelId);
  }

  toggleModel(modelId: string): void {
    if (this.isModelSelected(modelId)) {
      this.selectedModels = this.selectedModels.filter(m => m !== modelId);
    } else {
      this.selectedModels.push(modelId);
    }
  }

  selectAllModels(): void {
    this.selectedModels = this.availableModels.map(m => m.id);
  }

  deselectAllModels(): void {
    this.selectedModels = [];
  }

  runBenchmark(): void {
    if (!this.question.trim()) {
      this.errorMessage = 'Please enter a benchmark question.';
      return;
    }
    if (this.selectedModels.length === 0) {
      this.errorMessage = 'Please select at least one model to test.';
      return;
    }

    this.isLoading = true;
    this.errorMessage = '';

    const payload: BenchmarkRequest = {
      question: this.question.trim(),
      models: this.selectedModels,
      max_tokens: this.maxTokens,
      temperature: this.temperature,
      intent: this.selectedIntent === 'AUTO' ? undefined : this.selectedIntent,
    };

    this.benchmarkService.runBenchmark(payload).subscribe({
      next: (response) => {
        this.benchmarkData = response;
        this.isLoading = false;
      },
      error: (err) => {
        this.errorMessage = err.message || 'Error executing benchmark.';
        this.isLoading = false;
      }
    });
  }

  rateModel(result: BenchmarkResult, score: number): void {
    result.quality_score = score;
  }

  getModelLabel(modelId: string): string {
    const found = this.availableModels.find(m => m.id === modelId);
    return found ? found.name : modelId;
  }

  // Table Sorting
  sortResults(column: keyof BenchmarkResult): void {
    if (this.sortColumn === column) {
      this.sortAscending = !this.sortAscending;
    } else {
      this.sortColumn = column;
      this.sortAscending = true;
    }
  }

  get sortedResults(): BenchmarkResult[] {
    if (!this.benchmarkData?.results) return [];
    return [...this.benchmarkData.results].sort((a, b) => {
      let valA: any = a[this.sortColumn] ?? 0;
      let valB: any = b[this.sortColumn] ?? 0;

      if (typeof valA === 'string') {
        return this.sortAscending ? valA.localeCompare(valB) : valB.localeCompare(valA);
      }
      return this.sortAscending ? valA - valB : valB - valA;
    });
  }

  // Export functions
  exportCSV(): void {
    if (!this.benchmarkData) return;
    const headers = ['Model', 'Status', 'Response Time (ms)', 'TTFT (ms)', 'Prompt Tokens', 'Completion Tokens', 'Total Tokens', 'Tokens/Sec', 'Quality Score'];
    const rows = this.benchmarkData.results.map(r => [
      `"${r.model}"`,
      r.status,
      r.response_time_ms,
      r.ttft_ms,
      r.prompt_tokens,
      r.completion_tokens,
      r.total_tokens,
      r.tokens_per_second,
      r.quality_score || 'N/A'
    ]);

    const csvContent = 'data:text/csv;charset=utf-8,' + [headers.join(','), ...rows.map(e => e.join(','))].join('\n');
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement('a');
    link.setAttribute('href', encodedUri);
    link.setAttribute('download', `benchmark_results_${Date.now()}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }

  exportJSON(): void {
    if (!this.benchmarkData) return;
    const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(this.benchmarkData, null, 2));
    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute('href', dataStr);
    downloadAnchor.setAttribute('download', `benchmark_results_${Date.now()}.json`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  }

  generateReport(): void {
    if (!this.benchmarkData) return;
    const rankings = this.benchmarkData.rankings;
    const reportText = `================================================
LLM BENCHMARK REPORT
AI Financial Copilot — Experimental Evaluation
Date: ${new Date().toLocaleString()}
================================================

QUESTION TESTED:
"${this.benchmarkData.question}"

INTENT DETECTED / SPECIFIED:
${this.benchmarkData.intent}

MODELS TESTED:
${this.benchmarkData.results.map(r => `- ${r.model} (${r.status})`).join('\n')}

AUTOMATED RANKINGS & HIGHLIGHTS:
- Recommended Production Model: ${rankings?.recommended_production_model || 'N/A'}
- Fastest Response Time: ${rankings?.fastest_model || 'N/A'}
- Lowest TTFT (Latency): ${rankings?.best_latency_model || 'N/A'}
- Most Token Efficient: ${rankings?.most_efficient_model || 'N/A'}

DETAILED METRICS:
${this.benchmarkData.results.map(r => `
------------------------------------------------
Model: ${r.model}
Status: ${r.status}
Response Time: ${r.response_time_ms} ms
Time To First Token: ${r.ttft_ms} ms
Total Tokens: ${r.total_tokens} (Prompt: ${r.prompt_tokens}, Completion: ${r.completion_tokens})
Tokens/Sec: ${r.tokens_per_second}
Quality Score: ${r.quality_score ? r.quality_score + '/5' : 'Unrated'}
${r.error ? 'Error: ' + r.error : ''}
`).join('\n')}
================================================`;

    const blob = new Blob([reportText], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `benchmark_report_${Date.now()}.txt`;
    link.click();
    URL.revokeObjectURL(url);
  }
}
