export interface Conversation {
  id: string;
  title: string;
  message_count: number;
  created_at: string;
  updated_at: string;
  preview?: string;
}

export interface Message {
  id: string;
  user_message: string;
  ai_response: string;
  created_at: string;
}

export interface ConversationDetail extends Conversation {
  messages: Message[];
}

export interface CreateConversationRequest {
  title?: string;
  user_id?: string;
}

export interface CreateConversationResponse {
  id: string;
  title: string;
  message_count: number;
  created_at: string;
  updated_at: string;
}

export interface SaveMessageRequest {
  conversation_id: string;
  user_message: string;
  ai_response: string;
}

export interface SaveMessageResponse {
  id: string;
  conversation_id: string;
  user_message: string;
  ai_response: string;
  created_at: string;
}

export interface RenameConversationRequest {
  title: string;
}
