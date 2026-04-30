/**
 * SSE (Server-Sent Events) 类型定义
 */

export interface SSEUpdateEvent {
  event: "update";
  data: {
    next: string[];
    cost: number;
    error?: string;
    logs?: Array<{
      source: string;
      level: string;
      message: string;
      ts: number;
    }>;
  };
}

export interface SSEEndEvent {
  event: "end";
  data: Record<string, never>;
}

export interface SSEPingEvent {
  event: "ping";
  data: Record<string, never>;
}

export type SSEEvent = SSEUpdateEvent | SSEEndEvent | SSEPingEvent;

export interface SSEConnectionState {
  isConnected: boolean;
  lastEventTime: number;
  error: string | null;
  reconnectAttempts: number;
}
