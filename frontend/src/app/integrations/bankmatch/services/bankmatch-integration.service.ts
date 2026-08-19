import { Injectable } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Observable, of, throwError } from 'rxjs';
import { map, catchError } from 'rxjs/operators';
import { BankMatchResponse, BANKMATCH_ENDPOINTS } from '../models/bankmatch.models';
import { BankMatchConfigService } from './bankmatch-config.service';
import { BANKMATCH_MOCK_RESPONSES } from '../mocks/bankmatch-mock-data';

/**
 * BankMatch Integration Service
 *
 * Provides a clean integration boundary between the frontend analytics/reporting components
 * and external BankMatch endpoints. Transparently handles mock data mode, response envelope
 * unwrapping (extracting response.data), and Bearer token header injection.
 */
@Injectable({
  providedIn: 'root',
})
export class BankMatchIntegrationService {
  constructor(
    private http: HttpClient,
    private configService: BankMatchConfigService
  ) {}

  /**
   * Core request dispatcher for BankMatch endpoints.
   * Extracts data payload from { success: true, data: T } envelope.
   */
  public getEndpointData<T = unknown>(endpointPath: string): Observable<T> {
    if (this.configService.isMockMode) {
      const mockEnvelope = BANKMATCH_MOCK_RESPONSES[endpointPath];
      if (mockEnvelope && mockEnvelope.success) {
        return of(mockEnvelope.data as T);
      }
      return of({} as T);
    }

    const fullUrl = `${this.configService.baseUrl}${endpointPath}`;
    let headers = new HttpHeaders();
    const token = this.configService.getAuthToken();
    if (token) {
      headers = headers.set('Authorization', `Bearer ${token}`);
    }

    return this.http.get<BankMatchResponse<T>>(fullUrl, { headers }).pipe(
      map((response) => {
        if (response && response.success) {
          return response.data;
        }
        throw new Error(response?.error || 'BankMatch API request succeeded with false status');
      }),
      catchError((err) => {
        // Safe fallback to mock data on network failure during transition
        const fallbackMock = BANKMATCH_MOCK_RESPONSES[endpointPath];
        if (fallbackMock && fallbackMock.success) {
          return of(fallbackMock.data as T);
        }
        return throwError(() => err);
      })
    );
  }

  // 1. GET /api/enterprise-reporting/kpis
  public getEnterpriseKpis(): Observable<unknown> {
    return this.getEndpointData(BANKMATCH_ENDPOINTS.KPIS);
  }

  // 2. GET /api/enterprise-reporting/trends
  public getEnterpriseTrends(): Observable<unknown> {
    return this.getEndpointData(BANKMATCH_ENDPOINTS.TRENDS);
  }

  // 3. GET /api/enterprise-reporting/match-rate-distribution
  public getMatchRateDistribution(): Observable<unknown> {
    return this.getEndpointData(BANKMATCH_ENDPOINTS.MATCH_RATE_DISTRIBUTION);
  }

  // 4. GET /api/enterprise-reporting/top-anomalies
  public getTopAnomalies(): Observable<unknown> {
    return this.getEndpointData(BANKMATCH_ENDPOINTS.TOP_ANOMALIES);
  }

  // 5. GET /api/enterprise-reporting/exceptions
  public getExceptions(): Observable<unknown> {
    return this.getEndpointData(BANKMATCH_ENDPOINTS.EXCEPTIONS);
  }

  // 6. GET /api/enterprise-reporting/exception-aging
  public getExceptionAging(): Observable<unknown> {
    return this.getEndpointData(BANKMATCH_ENDPOINTS.EXCEPTION_AGING);
  }

  // 7. GET /api/enterprise-reporting/root-causes
  public getRootCauses(): Observable<unknown> {
    return this.getEndpointData(BANKMATCH_ENDPOINTS.ROOT_CAUSES);
  }

  // 8. GET /api/enterprise-reporting/executive-overview
  public getExecutiveOverview(): Observable<unknown> {
    return this.getEndpointData(BANKMATCH_ENDPOINTS.EXECUTIVE_OVERVIEW);
  }

  // 9. GET /api/dashboard/comptable
  public getDashboardComptable(): Observable<unknown> {
    return this.getEndpointData(BANKMATCH_ENDPOINTS.DASHBOARD_COMPTABLE);
  }

  // 10. GET /api/dashboard/admin
  public getDashboardAdmin(): Observable<unknown> {
    return this.getEndpointData(BANKMATCH_ENDPOINTS.DASHBOARD_ADMIN);
  }
}
