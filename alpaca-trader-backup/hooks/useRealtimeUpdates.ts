'use client';

import { useEffect, useRef, useCallback, useState } from 'react';
import { debug } from '@/lib/debug';

interface SSEEvent {
  type: string;
  data?: any;
  timestamp: string;
}

interface UseRealtimeUpdatesOptions {
  onOrderCreated?: () => void;
  onOrderUpdated?: () => void;
  onOrderDeleted?: () => void;
  onOrdersBulkCreated?: () => void;
}

/**
 * Hook for real-time updates via Server-Sent Events (SSE).
 * 
 * Connects to the backend SSE endpoint and listens for order change events.
 * Automatically reconnects on disconnect.
 * 
 * @param options - Callback functions for different event types
 */
export function useRealtimeUpdates(options: UseRealtimeUpdatesOptions) {
  const [isConnected, setIsConnected] = useState(false);
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const MAX_RECONNECT_ATTEMPTS = 5;
  const RECONNECT_DELAY = 3000; // 3 seconds

  // Store callbacks in ref to prevent them from triggering reconnections
  const callbacksRef = useRef(options);
  
  // Update callbacks ref whenever options change (without triggering reconnect)
  useEffect(() => {
    callbacksRef.current = options;
  }, [options]);

  const getApiUrl = useCallback(() => {
    // Same logic as api.ts
    if (typeof window !== 'undefined' && (window as any).__API_URL__) {
      return (window as any).__API_URL__;
    }
    if (typeof process !== 'undefined' && process.env) {
      const envUrl = process.env.NEXT_PUBLIC_API_URL || process.env.API_URL;
      if (envUrl) return envUrl;
    }
    if (typeof window !== 'undefined' && window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1') {
      return 'https://api-trading.parthchandak.info';
    }
    return 'http://localhost:8000';
  }, []);

  const connect = useCallback(() => {
    if (eventSourceRef.current) {
      debug.log('[SSE] Already connected, skipping reconnect');
      return;
    }

    const apiUrl = getApiUrl();
    const sseUrl = `${apiUrl}/api/events/stream`;
    
    debug.log(`[SSE] Connecting to ${sseUrl}`);
    setConnectionError(null);

    try {
      const eventSource = new EventSource(sseUrl);
      eventSourceRef.current = eventSource;

      eventSource.onopen = () => {
        debug.log('[SSE] Connection established');
        setIsConnected(true);
        setConnectionError(null);
        reconnectAttemptsRef.current = 0; // Reset reconnect attempts on successful connection
      };

      eventSource.onmessage = (event) => {
        try {
          const data: SSEEvent = JSON.parse(event.data);

          // Handle different event types using callbacksRef (always up-to-date, doesn't trigger reconnects)
          switch (data.type) {
            case 'connected':
              // Connection confirmed - reduced logging
              break;
            
            case 'heartbeat':
              // Heartbeat - no action needed, no logging
              break;
            
            case 'order_created':
              callbacksRef.current.onOrderCreated?.();
              break;
            
            case 'order_updated':
              callbacksRef.current.onOrderUpdated?.();
              break;
            
            case 'order_deleted':
              callbacksRef.current.onOrderDeleted?.();
              break;
            
            case 'orders_bulk_created':
              callbacksRef.current.onOrdersBulkCreated?.();
              break;
            
            default:
              debug.log(`[SSE] Unknown event type: ${data.type}`);
          }
        } catch (error) {
          debug.error('[SSE] Error parsing event data:', error);
        }
      };

      eventSource.onerror = (error) => {
        // Check if this is a QUIC protocol error (common with Cloudflare Tunnel)
        const isQuicError = eventSource.readyState === EventSource.CLOSED && 
                           (error.target as EventSource)?.readyState === EventSource.CLOSED;
        
        // QUIC protocol errors are transient and expected with Cloudflare Tunnel + SSE
        // They auto-reconnect, so we don't need to log them as errors
        if (isQuicError) {
          debug.log('[SSE] QUIC protocol error (transient) - will auto-reconnect');
        } else {
          debug.error('[SSE] Connection error:', error);
        }
        
        setIsConnected(false);
        
        // Close the connection
        eventSource.close();
        eventSourceRef.current = null;

        // Attempt to reconnect with exponential backoff
        if (reconnectAttemptsRef.current < MAX_RECONNECT_ATTEMPTS) {
          reconnectAttemptsRef.current++;
          const delay = RECONNECT_DELAY * reconnectAttemptsRef.current;
          
          // Only show error message for non-QUIC errors
          if (!isQuicError) {
            debug.log(`[SSE] Reconnecting in ${delay}ms (attempt ${reconnectAttemptsRef.current}/${MAX_RECONNECT_ATTEMPTS})`);
            setConnectionError(`Reconnecting... (attempt ${reconnectAttemptsRef.current}/${MAX_RECONNECT_ATTEMPTS})`);
          } else {
            // Silent reconnect for QUIC errors (they're expected)
            debug.log(`[SSE] Auto-reconnecting after QUIC error (attempt ${reconnectAttemptsRef.current}/${MAX_RECONNECT_ATTEMPTS})`);
          }
          
          reconnectTimeoutRef.current = setTimeout(() => {
            connect();
          }, delay);
        } else {
          debug.error('[SSE] Max reconnection attempts reached');
          setConnectionError('Connection lost. Please refresh the page.');
        }
      };
    } catch (error) {
      debug.error('[SSE] Error creating EventSource:', error);
      setConnectionError('Failed to establish connection');
    }
  }, [getApiUrl]); // ✅ ONLY getApiUrl as dependency - callbacks are in ref!

  const disconnect = useCallback(() => {
    debug.log('[SSE] Disconnecting...');
    
    // Clear reconnect timeout
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    // Close EventSource connection
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }

    setIsConnected(false);
    reconnectAttemptsRef.current = 0;
  }, []);

  useEffect(() => {
    // Connect ONCE on mount
    connect();

    // Disconnect on unmount
    return () => {
      disconnect();
    };
  }, [connect, disconnect]); // These are stable now because connect only depends on getApiUrl

  return {
    isConnected,
    connectionError,
    reconnect: connect,
  };
}

