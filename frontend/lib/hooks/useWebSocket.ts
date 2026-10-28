"use client";

import { useEffect, useRef, useCallback, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useNotificationStore } from "@/stores/notifications";
import { useTransferStore } from "@/stores/transfers";
import { queryKeys } from "@/lib/query/keys";
import { API_BASE_URL } from "@/lib/config";

interface WsMessage {
  event: string;
  data: Record<string, unknown>;
  timestamp: string;
}

const RECONNECT_DELAYS = [1000, 2000, 4000, 8000, 16000];
const MAX_RECONNECT = 5;

function getWsUrl(): string {
  const base = API_BASE_URL.replace(/^http/, "ws");
  return `${base}/api/v1/ws/connect`;
}

function getToken(): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(/(?:^|;\s*)access_token=([^;]*)/);
  return match ? match[1] : null;
}

export function useWebSocket() {
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectRef = useRef(0);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const queryClient = useQueryClient();
  const addNotification = useNotificationStore((s) => s.addNotification);

  const handleMessage = useCallback(
    (msg: WsMessage) => {
      addNotification(msg.event, msg.data, msg.timestamp);

      switch (msg.event) {
        case "upload:complete":
          queryClient.invalidateQueries({ queryKey: queryKeys.files.all });
          break;
        case "share:created":
          queryClient.invalidateQueries({ queryKey: queryKeys.shares.all });
          break;
        case "storage:changed":
          queryClient.invalidateQueries({ queryKey: queryKeys.auth.me() });
          break;
      }
    },
    [addNotification, queryClient]
  );

  const connect = useCallback(() => {
    const token = getToken();
    if (!token) return;

    const url = `${getWsUrl()}?token=${encodeURIComponent(token)}`;
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
      reconnectRef.current = 0;
    };

    ws.onmessage = (e) => {
      try {
        const msg: WsMessage = JSON.parse(e.data);
        handleMessage(msg);
      } catch {}
    };

    ws.onclose = (e) => {
      setConnected(false);
      wsRef.current = null;
      if (e.code !== 4001 && reconnectRef.current < MAX_RECONNECT) {
        const delay = RECONNECT_DELAYS[reconnectRef.current] ?? 16000;
        timerRef.current = setTimeout(() => {
          reconnectRef.current += 1;
          connect();
        }, delay);
      }
    };

    ws.onerror = () => {
      ws.close();
    };
  }, [handleMessage]);

  const disconnect = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    reconnectRef.current = MAX_RECONNECT;
    if (wsRef.current) {
      wsRef.current.close(1000, "manual disconnect");
      wsRef.current = null;
    }
    setConnected(false);
  }, []);

  useEffect(() => {
    connect();
    return () => disconnect();
  }, [connect, disconnect]);

  return { connected, reconnect: connect, disconnect };
}