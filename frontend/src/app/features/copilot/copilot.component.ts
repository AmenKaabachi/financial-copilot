import { Component, ElementRef, inject, viewChild, afterNextRender, HostListener, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MarkdownModule } from 'ngx-markdown';
import { Subscription } from 'rxjs';
import { CopilotService } from '../../core/services/copilot.service';
import { CopilotResponse, ResponseMetadata } from '../../core/models/copilot.models';
import { ConversationService } from '../../core/services/conversation.service';
import { Conversation, Message } from '../../core/models/conversation.models';
import { NewConversationButtonComponent } from './new-conversation-button.component';
import { ConversationHistoryComponent } from './conversation-history.component';
import { BenchmarkComponent } from '../benchmark/benchmark.component';

interface ChatMessage {
  role: 'user' | 'ai';
  content: string;
  model?: string;
  tier?: number;
  fallbackUsed?: boolean;
  responseTime?: number;
  timeToFirstTokenMs?: number;
  provider?: string;
  streaming?: boolean;
  timestamp?: Date;
  warningMessage?: string;
  cancelled?: boolean;
  responseMetadata?: ResponseMetadata;
}

@Component({
  selector: 'app-copilot',
  standalone: true,
  imports: [CommonModule, FormsModule, MarkdownModule, NewConversationButtonComponent, ConversationHistoryComponent, BenchmarkComponent],
  templateUrl: './copilot.component.html',
  styleUrl: './copilot.component.css'
})
export class CopilotComponent implements OnInit, OnDestroy {
  private copilotService = inject(CopilotService);
  private conversationService = inject(ConversationService);
  private scrollAnchor = viewChild<ElementRef<HTMLDivElement>>('scrollAnchor');
  private chatScroll = viewChild<ElementRef<HTMLDivElement>>('chatScroll');

  activeTab: 'chat' | 'benchmark' = 'chat';
  question: string = '';
  messages: ChatMessage[] = [];

  isLoading: boolean = false;
  errorMessage: string = '';
  showScrollButton: boolean = false;

  // Response cancellation
  currentStreamSubscription: Subscription | null = null;
  currentGenerationId: string = '';
  generationTimeout: any = null;
  private readonly GENERATION_TIMEOUT_MS = 120000; // 2 minutes max

  // Model selector
  selectedModel: string = 'auto';
  modelOptions = [
    { id: 'auto', name: 'Auto (Smart Routing)', tag: 'Recommended' },
    { id: 'openai/gpt-oss-20b:free', name: 'GPT OSS 20B', tag: 'Fast' },
    { id: 'google/gemma-4-26b-a4b-it:free', name: 'Gemma 4 26B A4B', tag: 'Balanced' },
    { id: 'poolside/laguna-xs-2.1:free', name: 'Laguna XS 2.1', tag: 'Fast' },
    { id: 'nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free', name: 'Nemotron Omni 30B', tag: 'Reasoning' },
    { id: 'nvidia/nemotron-3-nano-30b-a3b:free', name: 'Nemotron Nano 30B', tag: 'Medium' },
    { id: 'nvidia/nemotron-nano-9b-v2:free', name: 'Nemotron Nano 9B', tag: 'Compact' },
    { id: 'google/gemma-4-31b-it:free', name: 'Gemma 4 31B IT', tag: 'High Quality' },
    { id: 'nvidia/nemotron-3-ultra-550b-a55b:free', name: 'Nemotron Ultra 550B', tag: 'Ultra' },
    { id: 'nvidia/nemotron-3-super-120b-a12b:free', name: 'Nemotron Super 120B', tag: 'Super' },
  ];
  modelDropdownOpen = false;

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

  /** Get short display name for a model ID */
  getModelShortName(modelId: string): string {
    const found = this.modelOptions.find(m => m.id === modelId);
    return found ? found.name.split('(')[0].trim() : modelId;
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

  /** Cancel the currently ongoing generation (if any) */
  cancelGeneration(): void {
    // Unsubscribe to abort the HTTP stream
    if (this.currentStreamSubscription) {
      this.currentStreamSubscription.unsubscribe();
      this.currentStreamSubscription = null;
    }

    // Clear generation timeout
    if (this.generationTimeout) {
      clearTimeout(this.generationTimeout);
      this.generationTimeout = null;
    }

    // Mark the last AI message as cancelled (if still streaming)
    for (let i = this.messages.length - 1; i >= 0; i--) {
      const msg = this.messages[i];
      if (msg.role === 'ai' && msg.streaming) {
        msg.streaming = false;
        msg.cancelled = true;
        break;
      }
    }

    this.isLoading = false;
  }

  /** Cleanup on destroy */
  ngOnDestroy(): void {
    this.cancelGeneration();
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

  /** Generate a unique generation ID */
  private generateId(): string {
    return `${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
  }

  /** Send a question to the AI service and handle streaming response */
  private sendToAI(question: string): void {
    // Cancel any previous ongoing generation before starting a new one
    this.cancelGeneration();

    this.isLoading = true;
    this.errorMessage = '';

    // Generate a unique ID for this generation to prevent stale responses
    const generationId = this.generateId();
    this.currentGenerationId = generationId;

    const aiMessage: ChatMessage = {
      role: 'ai',
      content: '',
      streaming: true,
      timestamp: new Date()
    };
    this.messages.push(aiMessage);
    this.scrollToBottom(true);

    // Safety timeout: auto-cancel after 2 minutes
    this.generationTimeout = setTimeout(() => {
      if (this.currentGenerationId === generationId) {
        this.cancelGeneration();
      }
    }, this.GENERATION_TIMEOUT_MS);

    const ensureConversation = () => {
      if (this.conversationId) {
        this.startStream(question, aiMessage, this.conversationId, generationId);
      } else {
        console.log('[Copilot] No active conversation, creating one...');
        this.conversationService.createConversation().subscribe({
          next: (conversation) => {
            console.log('[Copilot] Conversation created:', conversation.id);
            this.conversationService.addConversation(conversation);
            this.conversationId = conversation.id;
            this.startStream(question, aiMessage, conversation.id, generationId);
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

  private startStream(question: string, aiMessage: ChatMessage, conversationId: string, generationId: string): void {
    const requestPayload: any = { question, conversation_id: conversationId };
    // Pass model override if user selected a specific model (not "auto")
    if (this.selectedModel && this.selectedModel !== 'auto') {
      requestPayload.model = this.selectedModel;
    }
    console.log('[Copilot] Sending stream request:', { question: question.slice(0, 50), conversation_id: conversationId, model: requestPayload.model || 'auto', generationId });

    const sub = this.copilotService.askQuestionStream(requestPayload).subscribe({
      next: (event) => {
        // Ignore stale events from old generations (race condition protection)
        if (this.currentGenerationId !== generationId) {
          return;
        }

        if (event.type === 'token' && event.content) {
          aiMessage.content += event.content;
          if (this.isNearBottom()) {
            this.scrollToBottom(true);
          }
        } else if (event.type === 'metadata') {
          // Store metadata on the current AI message for display
          aiMessage.provider = event.provider || 'OpenRouter';
          aiMessage.timeToFirstTokenMs = event.time_to_first_token_ms ?? undefined;
          aiMessage.model = event.model || aiMessage.model;
          aiMessage.responseMetadata = {
            model: event.model || 'unknown',
            provider: event.provider || 'OpenRouter',
            time_to_first_token_ms: event.time_to_first_token_ms ?? 0,
            finish_reason: event['finish_reason'] as string | undefined,
          };
        } else if (event.type === 'warning') {
          aiMessage.warningMessage = event.message || 'Response shortened. Ask "continue" to complete the analysis.';
          if (this.isNearBottom()) {
            this.scrollToBottom(true);
          }
        } else if (event.type === 'done') {
          // Use fallback defaults if metadata fields are missing
          aiMessage.model = event.model || aiMessage.model || 'unknown';
          aiMessage.tier = event.tier;
          aiMessage.fallbackUsed = event.fallback_used ?? false;
          aiMessage.responseTime = event.response_time ?? 0;
          aiMessage.provider = event.provider || aiMessage.provider || 'OpenRouter';
          aiMessage.timeToFirstTokenMs = event.time_to_first_token_ms ?? aiMessage.timeToFirstTokenMs ?? undefined;
          aiMessage.streaming = false;
          aiMessage.timestamp = new Date();
          // Ensure responseMetadata is populated
          if (!aiMessage.responseMetadata) {
            aiMessage.responseMetadata = {
              model: aiMessage.model || 'unknown',
              provider: aiMessage.provider || 'OpenRouter',
              time_to_first_token_ms: aiMessage.timeToFirstTokenMs ?? 0,
              finish_reason: event['finish_reason'] as string | undefined,
            };
          }
          this.scrollToBottom(true);
          this.loadConversations();
          console.log('[Copilot] Stream complete:', {
            model: aiMessage.model,
            provider: aiMessage.provider,
            fallback: aiMessage.fallbackUsed,
            response_time: aiMessage.responseTime,
            ttft_ms: aiMessage.timeToFirstTokenMs,
            response_length: aiMessage.content.length,
          });
        } else if (event.type === 'cancelled') {
          // Backend acknowledged cancellation
          aiMessage.streaming = false;
          aiMessage.cancelled = true;
          this.isLoading = false;
        }
      },
      error: (err) => {
        // Only handle error if this is still the current generation
        if (this.currentGenerationId !== generationId) {
          return;
        }
        aiMessage.streaming = false;
        aiMessage.content = aiMessage.content || 'Sorry, something went wrong while generating the response.';
        this.errorMessage = err.message;
        this.isLoading = false;
        this.scrollToBottom(true);
        console.error('[Copilot] Stream error:', err);
      },
      complete: () => {
        // Only handle completion if this is still the current generation
        if (this.currentGenerationId !== generationId) {
          return;
        }
        aiMessage.streaming = false;
        this.isLoading = false;
        this.currentStreamSubscription = null;

        // Clear timeout
        if (this.generationTimeout) {
          clearTimeout(this.generationTimeout);
          this.generationTimeout = null;
        }
      }
    });

    this.currentStreamSubscription = sub;
  }

}
