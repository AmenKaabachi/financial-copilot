import { Injectable, signal, computed, NgZone } from '@angular/core';
import { BenchmarkResponse, BenchmarkResult } from '../../features/benchmark/benchmark.models';

const STORAGE_KEY = 'benchmark_session';
const SESSION_TTL_MS = 2 * 60 * 60 * 1000;

export interface BenchmarkSession {
  sessionId: string;
  createdAt: number;
  lastUpdated: number;
  benchmarkRuns: BenchmarkResponse[];
}

@Injectable({
  providedIn: 'root'
})
export class BenchmarkStateService {
  private session = signal<BenchmarkSession | null>(null);
  sessionExists = computed(() => this.session() !== null);
  sessionRunCount = computed(() => this.session()?.benchmarkRuns.length ?? 0);

  constructor(private ngZone: NgZone) {
    this.restoreSession();
  }

  restoreSession(): void {
    if (typeof window === 'undefined' || !window.sessionStorage) {
      return;
    }
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return;
    }
    try {
      const data = JSON.parse(raw) as BenchmarkSession;
      if (Date.now() - data.lastUpdated > SESSION_TTL_MS) {
        this.clearSession();
        return;
      }
      this.ngZone.run(() => {
        this.session.set(data);
      });
    } catch {
      this.clearSession();
    }
  }

  loadFromApi(response: BenchmarkResponse): void {
    const current = this.session();
    const runs = current ? [...current.benchmarkRuns, response] : [response];
    const updated: BenchmarkSession = {
      sessionId: current?.sessionId ?? this.generateSessionId(),
      createdAt: current?.createdAt ?? Date.now(),
      lastUpdated: Date.now(),
      benchmarkRuns: runs,
    };
    this.persist(updated);
  }

  getLatestRun(): BenchmarkResponse | undefined {
    return this.session()?.benchmarkRuns.slice(-1)[0];
  }

  getAllRuns(): BenchmarkResponse[] {
    return this.session()?.benchmarkRuns ?? [];
  }

  clearSession(): void {
    if (typeof window !== 'undefined' && window.sessionStorage) {
      sessionStorage.removeItem(STORAGE_KEY);
    }
    this.ngZone.run(() => {
      this.session.set(null);
    });
  }

  private persist(data: BenchmarkSession): void {
    if (typeof window !== 'undefined' && window.sessionStorage) {
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(data));
    }
    this.ngZone.run(() => {
      this.session.set(data);
    });
  }

  private generateSessionId(): string {
    return `benchmark-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
  }
}
