import { Component, inject, EventEmitter, Output, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ConversationService } from '../../core/services/conversation.service';
import { Conversation } from '../../core/models/conversation.models';

@Component({
  selector: 'app-conversation-item',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="conversation-item" [class.active]="isActive" (click)="onSelect()">
      <div class="conversation-item-icon">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
        </svg>
      </div>
      <div class="conversation-item-content" *ngIf="conversation">
        <div class="conversation-item-title">{{ conversation.title }}</div>
      </div>
      <div class="conversation-item-actions">
        <button class="action-btn rename-btn" (click)="startRename($event)" title="Rename" aria-label="Rename conversation">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
            <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
          </svg>
        </button>
        <button class="action-btn delete-btn" (click)="confirmDelete($event)" title="Delete" aria-label="Delete conversation">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="3 6 5 6 21 6"/>
            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
          </svg>
        </button>
      </div>

      <div class="rename-overlay" *ngIf="isRenaming" (click)="$event.stopPropagation()">
        <input
          type="text"
          class="rename-input"
          [(ngModel)]="newTitle"
          (keyup.enter)="saveRename()"
          (keyup.escape)="cancelRename()"
          [autofocus]="true"
          maxlength="255"
        />
        <div class="rename-actions">
          <button class="rename-btn-save" (click)="saveRename()">Save</button>
          <button class="rename-btn-cancel" (click)="cancelRename()">Cancel</button>
        </div>
      </div>

      <div class="delete-modal-backdrop" *ngIf="showDeleteConfirm" (click)="cancelDelete()">
        <div class="delete-modal" (click)="$event.stopPropagation()">
          <div class="delete-modal-icon">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="3 6 5 6 21 6"/>
              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
            </svg>
          </div>
          <div class="delete-modal-title">Delete conversation?</div>
          <div class="delete-modal-message">This action cannot be undone.</div>
          <div class="delete-modal-actions">
            <button class="delete-modal-btn cancel" (click)="cancelDelete()">Cancel</button>
            <button class="delete-modal-btn danger" (click)="executeDelete()">Delete</button>
          </div>
        </div>
      </div>
    </div>
  `,
  styleUrl: './conversation-item.component.css'
})
export class ConversationItemComponent {
  private conversationService = inject(ConversationService);

  @Input() conversation: Conversation | null = null;
  @Input() isActive = false;
  @Output() select = new EventEmitter<Conversation>();
  @Output() deleted = new EventEmitter<string>();
  @Output() renamed = new EventEmitter<{ id: string; title: string }>();

  isRenaming = false;
  newTitle = '';
  showDeleteConfirm = false;

  onSelect(): void {
    if (this.isRenaming) return;
    if (this.conversation) {
      this.select.emit(this.conversation);
    }
  }

  startRename(event: Event): void {
    event.stopPropagation();
    if (!this.conversation) return;
    this.newTitle = this.conversation.title;
    this.isRenaming = true;
  }

  saveRename(): void {
    if (!this.conversation || !this.newTitle.trim()) {
      this.cancelRename();
      return;
    }
    const trimmed = this.newTitle.trim();
    this.conversationService.renameConversation(this.conversation.id, trimmed).subscribe({
      next: () => {
        this.renamed.emit({ id: this.conversation!.id, title: trimmed });
        this.isRenaming = false;
      },
      error: () => {
        this.isRenaming = false;
      }
    });
  }

  cancelRename(): void {
    this.isRenaming = false;
    this.newTitle = '';
  }

  confirmDelete(event: Event): void {
    event.stopPropagation();
    if (!this.conversation) return;
    this.showDeleteConfirm = true;
  }

  cancelDelete(): void {
    this.showDeleteConfirm = false;
  }

  executeDelete(): void {
    if (!this.conversation) return;
    this.conversationService.deleteConversation(this.conversation.id).subscribe({
      next: () => {
        this.deleted.emit(this.conversation!.id);
        this.showDeleteConfirm = false;
      },
      error: () => {
        this.showDeleteConfirm = false;
      }
    });
  }

}
