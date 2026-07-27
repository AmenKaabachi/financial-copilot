import { Component, inject, EventEmitter, Output, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ConversationService } from '../../core/services/conversation.service';
import { Conversation } from '../../core/models/conversation.models';

@Component({
  selector: 'app-new-conversation-button',
  standalone: true,
  imports: [CommonModule],
  template: `
    <button class="new-conversation-btn" (click)="createNewConversation()" [disabled]="isLoading" title="New Conversation">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <line x1="12" y1="5" x2="12" y2="19"/>
        <line x1="5" y1="12" x2="19" y2="12"/>
      </svg>
      <span *ngIf="showLabel">New Conversation</span>
    </button>
  `,
  styleUrl: './new-conversation-button.component.css'
})
export class NewConversationButtonComponent {
  private conversationService = inject(ConversationService);

  @Output() conversationCreated = new EventEmitter<Conversation>();
  @Input() showLabel = true;
  isLoading = false;

  createNewConversation(): void {
    this.isLoading = true;
    this.conversationService.createConversation().subscribe({
      next: (conversation) => {
        this.conversationService.addConversation(conversation);
        this.conversationCreated.emit(conversation);
        this.isLoading = false;
      },
      error: (err) => {
        console.error('Failed to create conversation:', err);
        this.isLoading = false;
      }
    });
  }
}
