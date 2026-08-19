import { Injectable } from '@angular/core';
import { environment } from '../../../../environments/environment';

/**
 * BankMatch Configuration Service
 *
 * Centralizes BankMatch API configuration, authentication token injection,
 * and mock mode toggling.
 */
@Injectable({
  providedIn: 'root',
})
export class BankMatchConfigService {
  private apiBaseUrl: string = environment.bankMatchApiBaseUrl || '';
  private mockMode: boolean = environment.bankMatchUseMockData ?? true;

  /**
   * Token Provider Hook:
   * Dhirar should replace this implementation to return the real Bearer token
   * from BankMatch authentication session/storage.
   */
  private tokenProvider: () => string | null = () => {
    // Integration Hook: Connect real token source here (e.g. localStorage or auth state)
    return null;
  };

  public get baseUrl(): string {
    return this.apiBaseUrl;
  }

  public setBaseUrl(url: string): void {
    this.apiBaseUrl = url;
  }

  public get isMockMode(): boolean {
    return this.mockMode;
  }

  public setMockMode(enabled: boolean): void {
    this.mockMode = enabled;
  }

  public getAuthToken(): string | null {
    return this.tokenProvider();
  }

  public setTokenProvider(provider: () => string | null): void {
    this.tokenProvider = provider;
  }
}
