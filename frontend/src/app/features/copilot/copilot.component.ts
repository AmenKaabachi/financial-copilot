import { Component, ElementRef, inject, viewChild, afterNextRender, HostListener, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MarkdownModule } from 'ngx-markdown';
import { CopilotService } from '../../core/services/copilot.service';
import { CopilotResponse } from '../../core/models/copilot.models';
import { ConversationService } from '../../core/services/conversation.service';
import { Conversation, Message } from '../../core/models/conversation.models';
import { NewConversationButtonComponent } from './new-conversation-button.component';
import { ConversationHistoryComponent } from './conversation-history.component';

interface ChatMessage {
  role: 'user' | 'ai';
  content: string;
  model?: string;
  tier?: number;
  fallbackUsed?: boolean;
  responseTime?: number;
  streaming?: boolean;
  timestamp?: Date;
  warningMessage?: string;
}

@Component({
  selector: 'app-copilot',
  standalone: true,
  imports: [CommonModule, FormsModule, MarkdownModule, NewConversationButtonComponent, ConversationHistoryComponent],
  templateUrl: './copilot.component.html',
  styleUrl: './copilot.component.css'
})
export class CopilotComponent implements OnInit {
  private copilotService = inject(CopilotService);
  private conversationService = inject(ConversationService);
  private scrollAnchor = viewChild<ElementRef<HTMLDivElement>>('scrollAnchor');
  private chatScroll = viewChild<ElementRef<HTMLDivElement>>('chatScroll');

  question: string = '';
  messages: ChatMessage[] = [];
  isLoading: boolean = false;
  errorMessage: string = '';
  showScrollButton: boolean = false;

  // Conversation history
  conversationId: string | null = null;
  historyPanelOpen = false;

  // Hover toolbar state
  editingIndex: number | null = null;
  editedContent: string = '';
  copiedIndex: number | null = null;

  constructor() {
    afterNextRender(() => this.scrollToBottom(false));
  }

  ngOnInit(): void {
    this.loadConversations();
  }

  @HostListener('window:resize')
  onResize(): void {
    if (this.showScrollButton && this.isNearBottom()) {
      this.scrollToBottom(false);
    }
  }

  toggleHistoryPanel(): void {
    this.historyPanelOpen = !this.historyPanelOpen;
    if (this.historyPanelOpen) {
      this.loadConversations();
    }
  }

  closeHistoryPanel(): void {
    this.historyPanelOpen = false;
  }

  loadConversations(): void {
    console.log('[History] Loading conversations');
    this.conversationService.getConversations().subscribe({
      next: (conversations) => {
        console.log(`[History] Loaded ${conversations.length} conversations`);
        this.conversationService.setConversations(conversations);
      },
      error: (err) => {
        console.error('[History] Failed to load conversations:', err);
      }
    });
  }

  /** Create a new conversation and reset the chat */
  onConversationCreated(conversation: Conversation): void {
    this.conversationId = conversation.id;
    this.messages = [];
    this.errorMessage = '';
    this.question = '';
    this.scrollToBottom(false);
  }

  /** Load messages from a previous conversation */
  loadConversationMessages(conversationId: string, messages: Message[]): void {
    console.log('[History] Opening conversation ID:', conversationId);
    const fullMessages: ChatMessage[] = [];
    messages.forEach(msg => {
      fullMessages.push({
        role: 'user' as const,
        content: msg.user_message,
        timestamp: new Date(msg.created_at),
      });
      fullMessages.push({
        role: 'ai' as const,
        content: msg.ai_response,
        timestamp: new Date(msg.created_at),
      });
    });

    this.conversationId = conversationId;
    this.messages = fullMessages;
    this.historyPanelOpen = false;
    this.scrollToBottom(false);
  }

  /** Handle conversation deleted from history */
  onConversationDeleted(conversationId: string): void {
    if (this.conversationId === conversationId) {
      this.conversationId = null;
      this.messages = [];
    }
  }

  /** Handle conversation renamed from history */
  onConversationRenamed(update: { id: string; title: string }): void {
    // Title update is handled locally in the history component
    // No additional action needed here unless we show the title somewhere
  }

  /** Format timestamp for display */
  formatTime(date: Date): string {
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }

  /** Check if there's a currently streaming message */
  hasStreamingMessage(): boolean {
    return this.messages.some(m => m.streaming);
  }

  /** Whether the user is close enough to the bottom that we can auto-scroll */
  isNearBottom(threshold: number = 80): boolean {
    const el = this.chatScroll()?.nativeElement;
    if (!el) return true;
    const distance = el.scrollHeight - el.scrollTop - el.clientHeight;
    return distance <= threshold;
  }

  /** Scroll the chat view to the latest content */
  scrollToBottom(smooth: boolean = true): void {
    const anchor = this.scrollAnchor()?.nativeElement;
    if (anchor) {
      setTimeout(() => {
        anchor.scrollIntoView({ behavior: smooth ? 'smooth' : 'auto', block: 'end' });
      }, 50);
    }
  }

  /** Handle scroll events to toggle the "scroll to bottom" button */
  onChatScroll(): void {
    this.showScrollButton = !this.isNearBottom();
  }

  /** Jump to the bottom immediately when the user taps the button */
  scrollToBottomInstant(): void {
    this.showScrollButton = false;
    this.scrollToBottom(false);
  }

  /** Copy message content to clipboard */
  copyMessage(content: string, index: number): void {
    navigator.clipboard.writeText(content).then(() => {
      this.copiedIndex = index;
      setTimeout(() => {
        this.copiedIndex = null;
      }, 2000);
    });
  }

  /** Start inline editing a user message */
  startEdit(index: number, content: string): void {
    this.editingIndex = index;
    this.editedContent = content;
  }

  /** Cancel inline editing */
  cancelEdit(): void {
    this.editingIndex = null;
    this.editedContent = '';
  }

  /** Save edited message and resend */
  saveEdit(index: number): void {
    if (!this.editedContent.trim() || this.isLoading) {
      return;
    }

    const newContent = this.editedContent.trim();
    this.editingIndex = null;
    this.editedContent = '';

    // Update the user message
    this.messages[index].content = newContent;
    this.messages[index].timestamp = new Date();

    // Remove all messages after this one (the old AI response and any subsequent messages)
    this.messages = this.messages.slice(0, index + 1);

    // Send the edited message
    this.sendToAI(newContent);
  }

  /** Regenerate an AI response */
  regenerateResponse(aiIndex: number): void {
    if (this.isLoading) {
      return;
    }

    // Find the user message that preceded this AI response
    const userMessage = this.messages[aiIndex - 1];
    if (!userMessage || userMessage.role !== 'user') {
      return;
    }

    // Remove the AI response
    this.messages.splice(aiIndex, 1);

    // Resend the user message
    this.sendToAI(userMessage.content);
  }

  /** Send a new question */
  askQuestion(): void {
    if (!this.question.trim() || this.isLoading) {
      return;
    }

    const userQuestion = this.question.trim();
    this.messages.push({
      role: 'user',
      content: userQuestion,
      timestamp: new Date()
    });
    this.question = '';
    this.errorMessage = '';
    this.scrollToBottom(true);

    this.sendToAI(userQuestion);
  }

  /** Send a question to the AI service and handle streaming response */
  private sendToAI(question: string): void {
    this.isLoading = true;
    this.errorMessage = '';

    const aiMessage: ChatMessage = {
      role: 'ai',
      content: '',
      streaming: true,
      timestamp: new Date()
    };
    this.messages.push(aiMessage);
    this.scrollToBottom(true);

    const ensureConversation = () => {
      if (this.conversationId) {
        this.startStream(question, aiMessage, this.conversationId);
      } else {
        console.log('[Copilot] No active conversation, creating one...');
        this.conversationService.createConversation().subscribe({
          next: (conversation) => {
            console.log('[Copilot] Conversation created:', conversation.id);
            this.conversationService.addConversation(conversation);
            this.conversationId = conversation.id;
            this.startStream(question, aiMessage, conversation.id);
          },
          error: (err) => {
            console.error('[Copilot] Failed to create conversation:', err);
            this.isLoading = false;
            aiMessage.streaming = false;
            aiMessage.content = 'Failed to create conversation. Please try again.';
          }
        });
      }
    };

    ensureConversation();
  }

  private startStream(question: string, aiMessage: ChatMessage, conversationId: string): void {
    const requestPayload: any = { question, conversation_id: conversationId };
    console.log('[Copilot] Sending stream request:', { question: question.slice(0, 50), conversation_id: conversationId });

    this.copilotService.askQuestionStream(requestPayload).subscribe({
      next: (event) => {
        if (event.type === 'token' && event.content) {
          aiMessage.content += event.content;
          if (this.isNearBottom()) {
            this.scrollToBottom(true);
          }
        } else if (event.type === 'warning') {
          aiMessage.warningMessage = event.message || 'Response shortened. Ask "continue" to complete the analysis.';
          if (this.isNearBottom()) {
            this.scrollToBottom(true);
          }
        } else if (event.type === 'done') {
          // Use fallback defaults if metadata fields are missing
          aiMessage.model = event.model || 'unknown';
          aiMessage.tier = event.tier;
          aiMessage.fallbackUsed = event.fallback_used ?? false;
          aiMessage.responseTime = event.response_time ?? 0;
          aiMessage.streaming = false;
          aiMessage.timestamp = new Date();
          this.scrollToBottom(true);
          this.loadConversations();
          console.log('[Copilot] Stream complete:', {
            model: aiMessage.model,
            fallback: aiMessage.fallbackUsed,
            response_time: aiMessage.responseTime,
            response_length: aiMessage.content.length,
            metadata_emitted: event.model !== undefined || event.response_time !== undefined
          });
        }
      },
      error: (err) => {
        aiMessage.streaming = false;
        aiMessage.content = aiMessage.content || 'Sorry, something went wrong while generating the response.';
        this.errorMessage = err.message;
        this.isLoading = false;
        this.scrollToBottom(true);
        console.error('[Copilot] Stream error:', err);
      },
      complete: () => {
        aiMessage.streaming = false;
        this.isLoading = false;
      }
    });
  }

}
