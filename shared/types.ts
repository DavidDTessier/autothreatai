export interface ProviderInterface {
  getModels(): Promise<ProviderModel[]>;
  generate(messages: ChatMessage[], options?: GenerateOptions): Promise<GenerateResponse>;
}

export interface ProviderModel {
  id: string;
  label: string;
  provider: string;
}

export interface ChatMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
}

export interface GenerateOptions {
  temperature?: number;
  maxTokens?: number;
  topP?: number;
}

export interface GenerateResponse {
  content: string;
  usage?: {
    promptTokens?: number;
    completionTokens?: number;
    totalTokens?: number;
  };
}

export interface ProviderConfig {
  id: string;
  name: string;
  baseUrl?: string;
  apiKey?: string;
  defaultModel?: string;
  enabled: boolean;
}