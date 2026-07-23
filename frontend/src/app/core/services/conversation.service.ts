import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Observable, throwError, BehaviorSubject } from 'rxjs';
import { catchError } from 'rxjs/operators';
import { environment } from '../../../environments/environment';
import {
  Conversation,
  ConversationDetail,
  CreateConversationRequest,
  CreateConversationResponse,
  Message,
  SaveMessageRequest,
  SaveMessageResponse,
} from '../models/conversation.models';

@Injectable({
  providedIn: 'root'
})
export class ConversationService {
  private http = inject(HttpClient);
  private apiUrl = `${environment.apiUrl}/copilot`;

  private conversationsSubject = new BehaviorSubject<Conversation[]>([]);
  conversations$ = this.conversationsSubject.asObservable();

  /** Fetch all conversations for the current user */
  getConversations(limit: number = 50): Observable<Conversation[]> {
    return this.http.get<Conversation[]>(`${this.apiUrl}/conversations`, {
      params: { limit: limit.toString() }
    }).pipe(
      catchError(this.handleError),
      // Update the behavior subject
      // Note: we do this via tap in the component or here
    );
  }

  /** Fetch a specific conversation with all messages */
  getConversationMessages(conversationId: string, limit: number = 100): Observable<ConversationDetail> {
    return this.http.get<ConversationDetail>(`${this.apiUrl}/conversations/${conversationId}/messages`, {
      params: { limit: limit.toString() }
    }).pipe(catchError(this.handleError));
  }

  /** Alias for backwards compatibility */
  getConversation(conversationId: string, limit: number = 100): Observable<ConversationDetail> {
    return this.getConversationMessages(conversationId, limit);
  }

  /** Create a new conversation */
  createConversation(title?: string): Observable<CreateConversationResponse> {
    const body: CreateConversationRequest = { title: title || 'New Conversation' };
    return this.http.post<CreateConversationResponse>(`${this.apiUrl}/conversations`, body).pipe(
      catchError(this.handleError)
    );
  }

  /** Delete a conversation and all its messages */
  deleteConversation(conversationId: string): Observable<any> {
    return this.http.delete(`${this.apiUrl}/conversations/${conversationId}`).pipe(
      catchError(this.handleError)
    );
  }

  /** Save a new message pair to a conversation */
  saveMessage(request: SaveMessageRequest): Observable<SaveMessageResponse> {
    return this.http.post<SaveMessageResponse>(`${this.apiUrl}/chat/history`, request).pipe(
      catchError(this.handleError)
    );
  }

  /** Rename a conversation */
  renameConversation(conversationId: string, title: string): Observable<any> {
    return this.http.put(`${this.apiUrl}/conversations/${conversationId}`, { title }).pipe(
      catchError(this.handleError)
    );
  }

  /** Search conversations by title (client-side filter helper) */
  searchConversations(query: string): Observable<Conversation[]> {
    return this.http.get<Conversation[]>(`${this.apiUrl}/conversations`, {
      params: { q: query, limit: '50' }
    }).pipe(
      catchError(this.handleError)
    );
  }

  /** Update the local conversations cache */
  setConversations(conversations: Conversation[]): void {
    this.conversationsSubject.next(conversations);
  }

  /** Add a new conversation to the local cache */
  addConversation(conversation: Conversation): void {
    const current = this.conversationsSubject.value;
    this.conversationsSubject.next([conversation, ...current]);
  }

  /** Remove a conversation from the local cache */
  removeConversation(conversationId: string): void {
    const current = this.conversationsSubject.value;
    this.conversationsSubject.next(current.filter(c => c.id !== conversationId));
  }

  private handleError(error: HttpErrorResponse) {
    let errorMessage = 'An unknown error occurred';
    if (error.error instanceof ErrorEvent) {
      errorMessage = error.error.message;
    } else {
      errorMessage = error.error?.detail || error.message || `Error Code: ${error.status}`;
    }
    return throwError(() => new Error(errorMessage));
  }
}
