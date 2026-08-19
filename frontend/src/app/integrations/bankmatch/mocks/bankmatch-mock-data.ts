import { BankMatchResponse, BANKMATCH_ENDPOINTS } from '../models/bankmatch.models';

/**
 * Contract-compatible mock data for all 10 BankMatch endpoints.
 * Response envelope strictly follows { success: true, data: { ... } }.
 */
export const BANKMATCH_MOCK_RESPONSES: Record<string, BankMatchResponse<unknown>> = {
  [BANKMATCH_ENDPOINTS.KPIS]: {
    success: true,
    data: {
      total_transactions: 142850,
      reconciled_rate: 98.42,
      pending_exceptions: 142,
      total_unmatched_amount: 34250.75,
      auto_match_efficiency: 94.1,
      avg_resolution_time_hours: 4.2,
      risk_score_index: 'Low'
    }
  },

  [BANKMATCH_ENDPOINTS.TRENDS]: {
    success: true,
    data: {
      metric: 'reconciliation_volume',
      period: 'monthly',
      series: [
        { label: 'Jan', value: 12400, matched: 12200, exception_count: 200 },
        { label: 'Feb', value: 13100, matched: 12900, exception_count: 200 },
        { label: 'Mar', value: 14500, matched: 14300, exception_count: 200 },
        { label: 'Apr', value: 13900, matched: 13700, exception_count: 200 },
        { label: 'May', value: 15200, matched: 15000, exception_count: 200 },
        { label: 'Jun', value: 16800, matched: 16550, exception_count: 250 },
        { label: 'Jul', value: 17400, matched: 17150, exception_count: 250 },
        { label: 'Aug', value: 18100, matched: 17900, exception_count: 200 }
      ]
    }
  },

  [BANKMATCH_ENDPOINTS.MATCH_RATE_DISTRIBUTION]: {
    success: true,
    data: {
      exact_matches: 82.5,
      fuzzy_matches: 11.9,
      rule_based_matches: 4.0,
      manual_matches: 1.6
    }
  },

  [BANKMATCH_ENDPOINTS.TOP_ANOMALIES]: {
    success: true,
    data: {
      total: 3,
      anomalies: [
        { id: 'ANO-101', type: 'Amount Mismatch', severity: 'High', description: 'Transaction #9401 difference > $5,000', detected_at: '2026-08-18' },
        { id: 'ANO-102', type: 'Duplicate Reference', severity: 'Medium', description: 'Reference #REF-8842 reused across 2 statements', detected_at: '2026-08-17' },
        { id: 'ANO-103', type: 'Unrecognized Counterparty', severity: 'Low', description: 'New vendor counterparty detected without master mapping', detected_at: '2026-08-16' }
      ]
    }
  },

  [BANKMATCH_ENDPOINTS.EXCEPTIONS]: {
    success: true,
    data: {
      total_count: 142,
      categories: [
        { name: 'Timing Difference', count: 64, value: 15200.00 },
        { name: 'Fee Deductions', count: 42, value: 4850.50 },
        { name: 'Missing Reference', count: 24, value: 8900.25 },
        { name: 'Currency Variance', count: 12, value: 5300.00 }
      ]
    }
  },

  [BANKMATCH_ENDPOINTS.EXCEPTION_AGING]: {
    success: true,
    data: {
      brackets: [
        { range: '0-7 days', count: 98, percentage: 69.0 },
        { range: '8-15 days', count: 28, percentage: 19.7 },
        { range: '16-30 days', count: 12, percentage: 8.5 },
        { range: '30+ days', count: 4, percentage: 2.8 }
      ]
    }
  },

  [BANKMATCH_ENDPOINTS.ROOT_CAUSES]: {
    success: true,
    data: {
      causes: [
        { cause: 'Bank Wire Delay', percentage: 42.0 },
        { cause: 'ERP Posting Lag', percentage: 31.5 },
        { cause: 'Manual Data Entry Error', percentage: 18.0 },
        { cause: 'Unallocated Bank Charge', percentage: 8.5 }
      ]
    }
  },

  [BANKMATCH_ENDPOINTS.EXECUTIVE_OVERVIEW]: {
    success: true,
    data: {
      organization: 'Central BankMatch System',
      reporting_period: 'Q3 2026',
      health_score: 96.5,
      summary_text: 'Reconciliation pipelines are operating cleanly with 98.42% overall match rate and minimal 30+ day aging exceptions.'
    }
  },

  [BANKMATCH_ENDPOINTS.DASHBOARD_COMPTABLE]: {
    success: true,
    data: {
      assigned_tasks: 18,
      pending_review: 7,
      completed_today: 34,
      daily_accuracy: 99.1
    }
  },

  [BANKMATCH_ENDPOINTS.DASHBOARD_ADMIN]: {
    success: true,
    data: {
      active_connectors: 12,
      healthy_services: 12,
      last_sync_timestamp: '2026-08-19T14:00:00Z',
      system_status: 'OPERATIONAL'
    }
  }
};
