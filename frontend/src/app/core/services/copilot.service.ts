import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Observable, throwError } from 'rxjs';
import { catchError } from 'rxjs/operators';
import { environment } from '../../../environments/environment';
import { CopilotRequest, CopilotResponse } from '../models/copilot.models';

export interface CopilotStreamEvent {
  type: 'token' | 'done' | 'error' | 'warning';
  content?: string;
  model?: string;
  tier?: number;
  fallback_used?: boolean;
  response_time?: number;
  message?: string;
}

@Injectable({
  providedIn: 'root'
})
export class CopilotService {
  private http = inject(HttpClient);
  private apiUrl = `${environment.apiUrl}/copilot/chat`;

  askQuestion(request: CopilotRequest & { conversation_id?: string }): Observable<CopilotResponse> {
    return this.http.post<CopilotResponse>(this.apiUrl, request).pipe(
      catchError(this.handleError)
    );
  }

  /**
   * Stream a chat response using Server-Sent Events.
   * Emits one CopilotStreamEvent per chunk, ending with a `done` event
   * carrying the response metadata.
   */
  askQuestionStream(request: CopilotRequest & { conversation_id?: string }): Observable<CopilotStreamEvent> {
    console.log('[CopilotService] askQuestionStream:', request);
    return new Observable<CopilotStreamEvent>((subscriber) => {
      const url = `${this.apiUrl}/stream`;
      const body = JSON.stringify(request);
      const controller = new AbortController();

      fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body,
        signal: controller.signal
      })
        .then((res) => {
          if (!res.ok || !res.body) {
            subscriber.error(new Error('AI service unavailable. Please try again later.'));
            return;
          }
          const reader = res.body.getReader();
          const decoder = new TextDecoder();
          let buffer = '';

          const read = (): Promise<void> =>
            reader.read().then(({ done, value }) => {
              if (done) {
                subscriber.complete();
                return;
              }
              buffer += decoder.decode(value, { stream: true });
              const events = buffer.split('\n\n');
              buffer = events.pop() ?? '';
              for (const raw of events) {
                const line = raw.trim();
                if (!line.startsWith('data:')) {
                  continue;
                }
                const payload = line.slice('data:'.length).trim();
                if (!payload) {
                  continue;
                }
                try {
                  const event = JSON.parse(payload) as CopilotStreamEvent;
                  subscriber.next(event);
                  if (event.type === 'error') {
                    subscriber.error(new Error(event.message ?? 'AI service unavailable.'));
                    return;
                  }
                } catch {
                  // Ignore malformed event lines.
                }
              }
              return read();
            });

          return read();
        })
        .catch((err) => {
          if (err?.name === 'AbortError') {
            subscriber.complete();
          } else {
            subscriber.error(new Error('AI service unavailable. Please try again later.'));
          }
        });

      return () => controller.abort();
    });
  }

  private handleError(error: HttpErrorResponse) {
    // Return an observable with a user-facing error message.
    return throwError(() => new Error('AI service unavailable. Please try again later.'));
  }
}
