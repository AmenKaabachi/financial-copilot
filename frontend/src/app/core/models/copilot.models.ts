export interface CopilotRequest {
  question: string;
  model?: string;
}

export interface CopilotResponse {
  question: string;
  answer: string;
  model: string;
  tier: number;
  fallback_used: boolean;
  response_time: number;
  provider?: string;
  time_to_first_token_ms?: number;
}

/**
 * Generic metadata structure for AI responses.
 * Designed for extensibility — new fields can be added without API changes.
 */
export interface ResponseMetadata {
  model: string;
  provider: string;
  time_to_first_token_ms: number;
  finish_reason?: string;
  total_generation_ms?: number;
  prompt_tokens?: number;
  completion_tokens?: number;
  total_tokens?: number;
  estimated_cost_usd?: number;
  cached?: boolean;
  /** Additional fields can be added as needed */
  [key: string]: unknown;
}
