/**
 * Standard BankMatch API response envelope.
 * Unconfirmed payloads use 'unknown' type safety.
 */
export interface BankMatchResponse<T = unknown> {
  success: boolean;
  data: T;
  message?: string;
  error?: string;
}

/**
 * BankMatch API Endpoint paths.
 */
export const BANKMATCH_ENDPOINTS = {
  KPIS: '/api/enterprise-reporting/kpis',
  TRENDS: '/api/enterprise-reporting/trends',
  MATCH_RATE_DISTRIBUTION: '/api/enterprise-reporting/match-rate-distribution',
  TOP_ANOMALIES: '/api/enterprise-reporting/top-anomalies',
  EXCEPTIONS: '/api/enterprise-reporting/exceptions',
  EXCEPTION_AGING: '/api/enterprise-reporting/exception-aging',
  ROOT_CAUSES: '/api/enterprise-reporting/root-causes',
  EXECUTIVE_OVERVIEW: '/api/enterprise-reporting/executive-overview',
  DASHBOARD_COMPTABLE: '/api/dashboard/comptable',
  DASHBOARD_ADMIN: '/api/dashboard/admin',
} as const;

export type BankMatchEndpointKey = keyof typeof BANKMATCH_ENDPOINTS;
