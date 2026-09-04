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
  // Fast / Lightweight / Financial
  { id: 'inclusionai/ling-3.0-flash-fin:free', name: 'Ling 3.0 Flash Fin', tag: 'Finance' },
  { id: 'nvidia/nemotron-3.5-lightning:free', name: 'Nemotron 3.5 Lightning', tag: 'Fast' },
  { id: 'cohere/north-mini-code:free', name: 'Cohere North Mini Code', tag: 'JSON/Code' },
  { id: 'google/gemma-4-26b-a4b-it:free', name: 'Gemma 4 26B A4B', tag: 'Balanced' },
  { id: 'poolside/laguna-xs-2.1:free', name: 'Poolside Laguna XS 2.1', tag: 'Fast' },
  { id: 'liquid/lfm-2.5-2.6b:free', name: 'Liquid LFM 2.5 2.6B', tag: 'Ultra Fast' },
  { id: 'thinkingmachines/inkling-small:free', name: 'Inkling Small', tag: 'Compact' },
  // Medium / Reasoning / Multilingual
  { id: 'nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free', name: 'Nemotron 3 Nano Omni 30B Reasoning', tag: 'Reasoning' },
  { id: 'poolside/laguna-s-2.1:free', name: 'Poolside Laguna S 2.1', tag: 'Medium' },
  { id: 'z-ai/glm-5.2:free', name: 'GLM 5.2', tag: 'Multilingual' },
  { id: 'minimax/minimax-m2.7:free', name: 'MiniMax M2.7', tag: 'Analysis' },
  // Full / High Capacity / Executive
  { id: 'nvidia/nemotron-3-ultra-550b-a55b:free', name: 'Nemotron 3 Ultra 550B', tag: 'Ultra' },
  { id: 'nvidia/nemotron-3-super-120b-a12b:free', name: 'Nemotron 3 Super 120B', tag: 'Super' },
  { id: 'minimax/minimax-m3:free', name: 'MiniMax M3', tag: 'Executive' },
  { id: 'google/gemma-4-31b-it:free', name: 'Gemma 4 31B IT', tag: 'High Quality' },
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
