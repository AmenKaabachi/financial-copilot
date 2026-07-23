import { Component, inject, EventEmitter, Output, Input, OnChanges, SimpleChanges } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ConversationService } from '../../core/services/conversation.service';
import { Conversation, Message } from '../../core/models/conversation.models';
import { ConversationItemComponent } from './conversation-item.component';

@Component({
  selector: 'app-conversation-history',
  standalone: true,
  imports: [CommonModule, FormsModule, ConversationItemComponent],
  templateUrl: './conversation-history.component.html',
  styleUrl: './conversation-history.component.css'
})
export class ConversationHistoryComponent implements OnChanges {
  private conversationService = inject(ConversationService);

  @Output() conversationSelected = new EventEmitter<{ conversationId: string; messages: Message[] }>();
  @Output() closePanel = new EventEmitter<void>();
  @Output() conversationDeleted = new EventEmitter<string>();
  @Output() conversationRenamed = new EventEmitter<{ id: string; title: string }>();
  @Input() isPanelOpen = false;
  @Input() activeConversationId: string | null = null;

  conversations: Conversation[] = [];
  isLoadingConversations = false;
  errorMessage = '';
  searchQuery = '';

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['isPanelOpen'] && this.isPanelOpen) {
      this.loadConversations();
    }
  }

  closePanelDirect(): void {
    this.isPanelOpen = false;
    this.closePanel.emit();
  }

  loadConversations(): void {
    console.log('[History] Loading conversations');
    this.isLoadingConversations = true;
    this.errorMessage = '';
    this.searchQuery = '';

    this.conversationService.getConversations().subscribe({
      next: (conversations) => {
        this.conversations = conversations;
        this.conversationService.setConversations(conversations);
        this.isLoadingConversations = false;
        console.log(`[History] Loaded ${conversations.length} conversations`);
      },
      error: (err) => {
        this.errorMessage = err.message || 'Failed to load conversations';
        this.isLoadingConversations = false;
      }
    });
  }

  get filteredConversations(): Conversation[] {
    if (!this.searchQuery.trim()) {
      return this.conversations;
    }
    const query = this.searchQuery.toLowerCase().trim();
    return this.conversations.filter(c => c.title.toLowerCase().includes(query));
  }

  selectConversation(conversation: Conversation): void {
    this.conversationService.getConversation(conversation.id).subscribe({
      next: (detail) => {
        this.conversationSelected.emit({ conversationId: conversation.id, messages: detail.messages });
        this.closePanelDirect();
      },
      error: (err) => {
        this.errorMessage = err.message || 'Failed to load messages';
      }
    });
  }

  onConversationDeleted(conversationId: string): void {
    this.conversations = this.conversations.filter(c => c.id !== conversationId);
    this.conversationService.removeConversation(conversationId);
    this.conversationDeleted.emit(conversationId);
  }

  onConversationRenamed(update: { id: string; title: string }): void {
    const conv = this.conversations.find(c => c.id === update.id);
    if (conv) {
      conv.title = update.title;
    }
    this.conversationRenamed.emit(update);
  }

  formatDate(dateString: string): string {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: date.getFullYear() !== now.getFullYear() ? 'numeric' : undefined });
  }
}
