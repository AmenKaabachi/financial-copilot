export interface BenchmarkRequest {
  question: string;
  models: string[];
  max_tokens?: number;
  temperature?: number;
  intent?: string;
}

export interface BenchmarkResult {
  model: string;
  provider: string;
  answer: string;
  status: 'SUCCESS' | 'FAILED' | 'TIMEOUT' | 'RATE_LIMIT';
  response_time_ms: number;
  ttft_ms: number;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  tokens_per_second: number;
  quality_score?: number;
  error?: string;
}

export interface BenchmarkRanking {
  fastest_model?: string;
  best_latency_model?: string;
  best_quality_model?: string;
  most_efficient_model?: string;
  most_reliable_model?: string;
  recommended_production_model?: string;
}

export interface BenchmarkResponse {
  question: string;
  intent: string;
  results: BenchmarkResult[];
  rankings?: BenchmarkRanking;
}

export const AVAILABLE_BENCHMARK_MODELS = [
  { id: 'openai/gpt-oss-20b:free', name: 'GPT OSS 20B', tag: 'Fast' },
  { id: 'google/gemma-4-26b-a4b-it:free', name: 'Gemma 4 26B A4B', tag: 'Balanced' },
  { id: 'poolside/laguna-xs-2.1:free', name: 'Poolside Laguna XS 2.1', tag: 'Fast' },
  { id: 'nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free', name: 'Nemotron 3 Nano Omni 30B Reasoning', tag: 'Reasoning' },
  { id: 'nvidia/nemotron-3-nano-30b-a3b:free', name: 'Nemotron 3 Nano 30B', tag: 'Medium' },
  { id: 'nvidia/nemotron-nano-9b-v2:free', name: 'Nemotron Nano 9B v2', tag: 'Compact' },
  { id: 'google/gemma-4-31b-it:free', name: 'Gemma 4 31B IT', tag: 'High Quality' },
  { id: 'nvidia/nemotron-3-ultra-550b-a55b:free', name: 'Nemotron 3 Ultra 550B', tag: 'Ultra' },
  { id: 'nvidia/nemotron-3-super-120b-a12b:free', name: 'Nemotron 3 Super 120B', tag: 'Super' },
];

export const INTENT_OPTIONS = [
  { id: 'AUTO', name: 'Auto detection' },
  { id: 'INVOICE_LOOKUP', name: 'Invoice lookup' },
  { id: 'ANOMALY_LOOKUP', name: 'Anomaly lookup' },
  { id: 'RECONCILIATION_ANALYSIS', name: 'Reconciliation analysis' },
  { id: 'DATASET_REVIEW', name: 'Dataset review' },
  { id: 'RECOMMENDATIONS', name: 'Recommendations' },
  { id: 'FINANCIAL_ANALYSIS', name: 'Financial analysis' },
];
