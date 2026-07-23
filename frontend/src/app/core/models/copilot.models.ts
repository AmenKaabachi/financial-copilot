export interface CopilotRequest {
  question: string;
}

export interface CopilotResponse {
  question: string;
  answer: string;
  model: string;
  tier: number;
  fallback_used: boolean;
  response_time: number;
}
