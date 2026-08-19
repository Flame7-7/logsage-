// LogSage AI — WebSocket Hook

import { useCallback, useEffect, useRef, useState } from "react";
import { createLiveSocket } from "@/lib/api";
import type { LiveLogEntry, WSMessage } from "@/types";

const MAX_LIVE_ENTRIES = 200;

export function useLiveFeed() {
  const [entries, setEntries] = useState<LiveLogEntry[]>([]);
  const [connected, setConnected] = useState(false);
  const [lastAlert, setLastAlert] = useState<WSMessage | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    try {
      const ws = createLiveSocket();
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
      };

      ws.onmessage = (event) => {
        try {
          const msg: WSMessage = JSON.parse(event.data);

          if (msg.type === "log_entry") {
            const entry = msg.payload as LiveLogEntry;
            setEntries((prev) => [entry, ...prev].slice(0, MAX_LIVE_ENTRIES));
          } else if (msg.type === "alert") {
            setLastAlert(msg);
          }
        } catch {
          // Ignore parse errors
        }
      };

      ws.onclose = () => {
        setConnected(false);
        // Reconnect after 3s
        reconnectTimer.current = setTimeout(connect, 3000);
      };

      ws.onerror = () => {
        ws.close();
      };
    } catch {
      reconnectTimer.current = setTimeout(connect, 5000);
    }
  }, []);

  useEffect(() => {
    connect();
    return () => {
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, [connect]);

  const clearEntries = useCallback(() => setEntries([]), []);

  return { entries, connected, lastAlert, clearEntries };
}
