import { useEffect, useRef, useState } from "react";

function wsUrl(channel: string) {
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${window.location.host}/ws/${channel}`;
}

/**
 * Subscribe to a server WebSocket channel with auto-reconnect.
 * Desktop WebViews often drop sockets; pair with HTTP polling for critical state.
 */
export function useChannel<T = unknown>(channel: string | null) {
  const [last, setLast] = useState<T | null>(null);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const attemptRef = useRef(0);

  useEffect(() => {
    if (!channel) return;

    let cancelled = false;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let pingTimer: ReturnType<typeof setInterval> | null = null;

    const clearTimers = () => {
      if (reconnectTimer) {
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
      }
      if (pingTimer) {
        clearInterval(pingTimer);
        pingTimer = null;
      }
    };

    const connect = () => {
      if (cancelled) return;
      clearTimers();
      const ws = new WebSocket(wsUrl(channel));
      wsRef.current = ws;

      ws.onopen = () => {
        if (cancelled) return;
        attemptRef.current = 0;
        setConnected(true);
        pingTimer = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            try {
              ws.send("ping");
            } catch {
              /* ignore */
            }
          }
        }, 25_000);
      };

      ws.onerror = () => {
        try {
          ws.close();
        } catch {
          /* ignore */
        }
      };

      ws.onclose = () => {
        if (cancelled) return;
        setConnected(false);
        wsRef.current = null;
        clearTimers();
        attemptRef.current += 1;
        const delay = Math.min(30_000, 400 * 2 ** Math.min(attemptRef.current, 7));
        reconnectTimer = setTimeout(connect, delay);
      };

      ws.onmessage = (ev) => {
        if (typeof ev.data !== "string" || ev.data === "ping") return;
        try {
          setLast(JSON.parse(ev.data) as T);
        } catch {
          // ignore non-JSON heartbeats
        }
      };
    };

    connect();
    return () => {
      cancelled = true;
      clearTimers();
      wsRef.current?.close();
      wsRef.current = null;
      setConnected(false);
    };
  }, [channel]);

  return { last, connected };
}
