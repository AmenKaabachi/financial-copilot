import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Observable, throwError } from 'rxjs';
import { catchError } from 'rxjs/operators';
import { environment } from '../../../environments/environment';
import { BenchmarkRequest, BenchmarkResponse } from './benchmark.models';

@Injectable({
  providedIn: 'root'
})
export class BenchmarkService {
  private http = inject(HttpClient);
  private apiUrl = `${environment.apiUrl}/copilot/benchmark`;

  runBenchmark(request: BenchmarkRequest): Observable<BenchmarkResponse> {
    return this.http.post<BenchmarkResponse>(this.apiUrl, request).pipe(
      catchError(this.handleError)
    );
  }

  private handleError(error: HttpErrorResponse) {
    let msg = 'Failed to execute benchmark test. Please check backend connection.';
    if (error.error && error.error.detail) {
      msg = error.error.detail;
    }
    return throwError(() => new Error(msg));
  }
}
