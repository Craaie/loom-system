"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import type { SSEConnectionState } from "@/types/sse";

const MAX_RECONNECT_ATTEMPTS = 5;
const INITIAL_RECONNECT_DELAY = 1000;
const HEARTBEAT_TIMEOUT = 30_000;

interface UseSSEOptions {
  /** SSE 事件流 URL */
  url: string;
  /** 收到消息时的回调 */
  onMessage: (data: any) => void;
  /** 连接关闭时的回调 */
  onEnd?: () => void;
  /** 是否启用（默认 true） */
  enabled?: boolean;
}

/**
 * SSE 连接管理 Hook
 * 
 * 特性：
 * - 指数退避自动重连（最多 5 次）
 * - 30s 心跳超时检测
 * - 组件卸载自动断开
 * - 手动重连支持
 */
export function useSSE({ url, onMessage, onEnd, enabled = true }: UseSSEOptions): SSEConnectionState & { reconnect: () => void } {
  const [connectionState, setConnectionState] = useState<SSEConnectionState>({
    isConnected: false,
    lastEventTime: Date.now(),
    error: null,
    reconnectAttempts: 0,
  });

  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const heartbeatTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const attemptsRef = useRef(0);

  // 稳定引用回调，避免 useEffect 重跑
  const onMessageRef = useRef(onMessage);
  onMessageRef.current = onMessage;
  const onEndRef = useRef(onEnd);
  onEndRef.current = onEnd;

  const cleanup = useCallback(() => {
    eventSourceRef.current?.close();
    eventSourceRef.current = null;
    if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
    if (heartbeatTimeoutRef.current) clearTimeout(heartbeatTimeoutRef.current);
  }, []);

  const resetHeartbeat = useCallback(() => {
    if (heartbeatTimeoutRef.current) clearTimeout(heartbeatTimeoutRef.current);
    heartbeatTimeoutRef.current = setTimeout(() => {
      console.warn("[SSE] Heartbeat timeout, reconnecting...");
      cleanup();
      scheduleReconnect();
    }, HEARTBEAT_TIMEOUT);
  }, [cleanup]);

  const scheduleReconnect = useCallback(() => {
    if (attemptsRef.current >= MAX_RECONNECT_ATTEMPTS) {
      setConnectionState(prev => ({
        ...prev,
        isConnected: false,
        error: `重连失败（已尝试 ${MAX_RECONNECT_ATTEMPTS} 次）`,
      }));
      return;
    }

    const delay = INITIAL_RECONNECT_DELAY * Math.pow(2, attemptsRef.current);
    attemptsRef.current += 1;

    setConnectionState(prev => ({
      ...prev,
      isConnected: false,
      reconnectAttempts: attemptsRef.current,
      error: `正在重连... (${attemptsRef.current}/${MAX_RECONNECT_ATTEMPTS})`,
    }));

    reconnectTimeoutRef.current = setTimeout(() => {
      connect();
    }, delay);
  }, []);

  const connect = useCallback(() => {
    cleanup();

    const es = new EventSource(url);
    eventSourceRef.current = es;

    es.onopen = () => {
      attemptsRef.current = 0;
      setConnectionState({
        isConnected: true,
        lastEventTime: Date.now(),
        error: null,
        reconnectAttempts: 0,
      });
      resetHeartbeat();
    };

    es.onmessage = (event) => {
      const now = Date.now();
      setConnectionState(prev => ({ ...prev, lastEventTime: now }));
      resetHeartbeat();

      try {
        const data = JSON.parse(event.data);
        if (data.event === "end" || data.event === "error") {
          setConnectionState(prev => ({ ...prev, isConnected: false }));
          es.close();
          if (data.event === "end") onEndRef.current?.();
          // Let onMessage handle the error display
          onMessageRef.current(data);
          return;
        }
        onMessageRef.current(data);
      } catch (e) {
        console.error("[SSE] Parse error:", e);
      }
    };

    es.onerror = () => {
      console.error("[SSE] Connection error");
      es.close();
      scheduleReconnect();
    };
  }, [url, cleanup, resetHeartbeat, scheduleReconnect]);

  useEffect(() => {
    if (!enabled) return;
    connect();
    return cleanup;
  }, [url, enabled]);

  const reconnect = useCallback(() => {
    attemptsRef.current = 0;
    connect();
  }, [connect]);

  return { ...connectionState, reconnect };
}
