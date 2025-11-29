'use client';

import { useEffect, useRef, useCallback, useState } from 'react';
import { debug } from '@/lib/debug';

interface PriceUpdate {
  [symbol: string]: {
    price: number;
    timestamp: string;
    is_market_open: boolean;
  };
}

interface WebSocketMessage {
  type: string;
  data?: PriceUpdate;
  timestamp?: string;
  message?: string;
  symbols?: string[];
  client_id?: string;
}

interface UseWebSocketPricesOptions {
  symbols: string[];
  onPriceUpdate?: (prices: PriceUpdate) => void;
  enabled?: boolean;
}

export function useWebSocketPrices(options: UseWebSocketPricesOptions) {
  const { symbols, onPriceUpdate, enabled = true } = options;
  const [isConnected, setIsConnected] = useState(false);
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const symbolsRef = useRef<string[]>([]);
  const onPriceUpdateRef = useRef(onPriceUpdate);
  
  const MAX_RECONNECT_ATTEMPTS = 5;
  const RECONNECT_DELAY = 3000;

  // Update callback ref when it changes
  useEffect(() => {
    onPriceUpdateRef.current = onPriceUpdate;
  }, [onPriceUpdate]);

  const getWebSocketUrl = useCallback(() => {
    const getApiUrl = () => {
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
    };

    const apiUrl = getApiUrl();
    // Convert http/https to ws/wss
    // Handle both http:// and https:// properly
    if (apiUrl.startsWith('https://')) {
      return apiUrl.replace('https://', 'wss://') + '/api/ws/prices';
    } else if (apiUrl.startsWith('http://')) {
      return apiUrl.replace('http://', 'ws://') + '/api/ws/prices';
    } else {
      // Fallback: assume https if no protocol
      return `wss://${apiUrl}/api/ws/prices`;
    }
  }, []);

  const connect = useCallback(() => {
    if (!enabled) {
      debug.log('[WebSocket] Disabled, skipping connection');
      return;
    }

    if (wsRef.current?.readyState === WebSocket.OPEN) {
      debug.log('[WebSocket] Already connected, skipping reconnect');
      return;
    }

    const wsUrl = getWebSocketUrl();
    debug.log(`[WebSocket] Connecting to ${wsUrl}`);
    
    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        debug.log('[WebSocket] Connected');
        setIsConnected(true);
        setConnectionError(null);
        reconnectAttemptsRef.current = 0;
        
        // Subscribe to symbols
        if (symbolsRef.current.length > 0) {
          ws.send(JSON.stringify({
            type: 'subscribe',
            symbols: symbolsRef.current
          }));
          debug.log(`[WebSocket] Subscribed to ${symbolsRef.current.length} symbols`);
        }
      };

      ws.onmessage = (event) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data);
          
          switch (message.type) {
            case 'connected':
              debug.log(`[WebSocket] Connected: ${message.client_id}`);
              break;
            
            case 'price_update':
              if (message.data && onPriceUpdateRef.current) {
                // Reduced logging - only log summary, not every update
                onPriceUpdateRef.current(message.data);
              }
              break;
            
            case 'subscribed':
              debug.log(`[WebSocket] Subscribed to ${message.symbols?.length || 0} symbols`);
              break;
            
            case 'unsubscribed':
              debug.log(`[WebSocket] Unsubscribed from ${message.symbols?.length || 0} symbols`);
              break;
            
            case 'heartbeat':
              // Keep-alive, no action needed - removed logging
              break;
            
            case 'error':
              debug.error(`[WebSocket] Server error: ${message.message}`);
              setConnectionError(message.message || 'WebSocket error');
              break;
            
            default:
              debug.log(`[WebSocket] Unknown message type: ${message.type}`);
          }
        } catch (error) {
          debug.error('[WebSocket] Error parsing message:', error);
        }
      };

      ws.onerror = (error) => {
        debug.error('[WebSocket] Connection error:', error);
        setConnectionError('WebSocket connection error');
      };

      ws.onclose = (event) => {
        debug.log(`[WebSocket] Connection closed (code: ${event.code}, reason: ${event.reason || 'none'})`);
        setIsConnected(false);
        wsRef.current = null;

        // Attempt reconnect if not a normal closure
        if (event.code !== 1000 && reconnectAttemptsRef.current < MAX_RECONNECT_ATTEMPTS && enabled) {
          reconnectAttemptsRef.current++;
          const delay = RECONNECT_DELAY * reconnectAttemptsRef.current;
          debug.log(`[WebSocket] Reconnecting in ${delay}ms (attempt ${reconnectAttemptsRef.current}/${MAX_RECONNECT_ATTEMPTS})`);
          
          reconnectTimeoutRef.current = setTimeout(() => {
            connect();
          }, delay);
        } else if (reconnectAttemptsRef.current >= MAX_RECONNECT_ATTEMPTS) {
          debug.error('[WebSocket] Max reconnection attempts reached');
          setConnectionError('WebSocket connection lost. Falling back to HTTP polling.');
        }
      };
    } catch (error) {
      debug.error('[WebSocket] Error creating connection:', error);
      setConnectionError('Failed to create WebSocket connection');
    }
  }, [enabled, getWebSocketUrl]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    if (wsRef.current) {
      wsRef.current.close(1000, 'Client disconnecting');
      wsRef.current = null;
    }

    setIsConnected(false);
    reconnectAttemptsRef.current = 0;
    setConnectionError(null);
  }, []);

  // Update subscriptions when symbols change
  useEffect(() => {
    symbolsRef.current = symbols;
    
    if (wsRef.current?.readyState === WebSocket.OPEN && symbols.length > 0) {
      wsRef.current.send(JSON.stringify({
        type: 'subscribe',
        symbols: symbols
      }));
      debug.log(`[WebSocket] Updated subscription to: ${symbols.join(', ')}`);
    }
  }, [symbols]);

  // Connect/disconnect based on enabled state
  useEffect(() => {
    if (enabled) {
      connect();
    } else {
      disconnect();
    }

    return () => {
      disconnect();
    };
  }, [enabled, connect, disconnect]);

  return {
    isConnected,
    connectionError,
    reconnect: connect,
    disconnect,
  };
}

