'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { pricesApi, marketApi } from '@/services/api';
import { debug } from '@/lib/debug';
import { INTERVALS } from '@/lib/constants';
import { useWebSocketPrices } from './useWebSocketPrices';
import { useConnectivity } from '@/hooks/useConnectivity';

interface PriceData {
  price: number;
  timestamp: string;
  isMarketOpen: boolean;
}

interface MarketStatus {
  is_open: boolean;
  timestamp?: string;
  next_open?: string;
  next_close?: string;
}

export function useLivePrices() {
  const [prices, setPrices] = useState<Record<string, PriceData>>({});
  const [marketStatus, setMarketStatus] = useState<MarketStatus>({ is_open: false });
  const [isLoading, setIsLoading] = useState(false);
  const [useWebSocket, setUseWebSocket] = useState(true);
  const priceIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const marketStatusIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const symbolsRef = useRef<string[]>([]);
  const intervalMsRef = useRef<number>(INTERVALS.MARKET_OPEN_POLL);
  const marketStatusRef = useRef<MarketStatus>({ is_open: false });
  const { isBackendReachable } = useConnectivity();

  const fetchMarketStatus = useCallback(async (): Promise<MarketStatus> => {
    try {
      const response = await marketApi.getMarketClock();
      const status = response.data;
      setMarketStatus(status);
      marketStatusRef.current = status; // Update ref for use in callbacks
      return status;
    } catch (error) {
      debug.error('Error fetching market status:', error);
      const fallbackStatus = { is_open: false };
      marketStatusRef.current = fallbackStatus;
      return fallbackStatus;
    }
  }, []);

  const fetchPrices = useCallback(async (symbols: string[]) => {
    if (!symbols || symbols.length === 0) return;
    
    // Don't fetch if backend is unreachable (useConnectivity will handle recovery)
    if (!isBackendReachable) {
      debug.log('[useLivePrices] Backend unreachable, skipping price fetch');
      return;
    }
    
    setIsLoading(true);
    try {
      const symbolString = Array.isArray(symbols) ? symbols.join(',') : symbols;
      // Reduced logging - only log summary, not every symbol
      debug.log(`[useLivePrices] Fetching prices for ${symbols.length} symbols`);
      
      const response = await pricesApi.getPrices(symbolString);
      
      // Update prices map - API response should include is_market_open for each price
      const newPrices: Record<string, PriceData> = {};
      response.data.prices.forEach((priceData: any) => {
        // Use is_market_open from API response, fallback to ref (always fresh)
        const isMarketOpen = priceData.is_market_open ?? marketStatusRef.current.is_open;
        
        newPrices[priceData.symbol] = {
          price: priceData.price,
          timestamp: priceData.timestamp,
          isMarketOpen,
        };
      });
      
      setPrices((prev) => ({ ...prev, ...newPrices }));
      // Reduced logging - price updates happen frequently
    } catch (error) {
      debug.error('Error fetching prices:', error);
    } finally {
      setIsLoading(false);
    }
  }, []); // No dependencies - uses refs for market status

  const stopPriceUpdates = useCallback(() => {
    if (priceIntervalRef.current) {
      clearInterval(priceIntervalRef.current);
      priceIntervalRef.current = null;
    }
    if (marketStatusIntervalRef.current) {
      clearInterval(marketStatusIntervalRef.current);
      marketStatusIntervalRef.current = null;
    }
  }, []);

  const startPriceUpdates = useCallback(async (symbols: string[], intervalMs: number = INTERVALS.MARKET_OPEN_POLL) => {
    debug.log(`[useLivePrices] Starting price updates for ${symbols.length} symbols`);
    
    // Clear existing intervals
    stopPriceUpdates();
    
    // Store symbols and interval in refs for use in intervals
    symbolsRef.current = symbols;
    intervalMsRef.current = intervalMs;
    
    // Helper function to setup intervals based on market status
    const setupIntervals = (isMarketOpen: boolean) => {
      // Clear existing price interval
      if (priceIntervalRef.current) {
        clearInterval(priceIntervalRef.current);
        priceIntervalRef.current = null;
      }
      
      // Set up price updates based on market status
      const updatePrices = () => {
        // Use refs to get latest symbols - reduced logging
        fetchPrices(symbolsRef.current);
      };
      
      if (isMarketOpen) {
        // Market open: update every 10 seconds (or specified interval)
        priceIntervalRef.current = setInterval(updatePrices, intervalMs);
      } else {
        // Market closed: update every 5 minutes
        priceIntervalRef.current = setInterval(updatePrices, INTERVALS.MARKET_CLOSED_POLL);
      }
    };
    
    // Fetch market status first
    const status = await fetchMarketStatus();
    debug.log(`[useLivePrices] Market status: ${status.is_open ? 'OPEN' : 'CLOSED'}`);
    
    // Fetch prices immediately
    await fetchPrices(symbols);
    
    // Set up initial intervals based on market status
    setupIntervals(status.is_open);
    
    // Set up market status check
    marketStatusIntervalRef.current = setInterval(async () => {
      const newStatus = await fetchMarketStatus();
      // Restart price updates if market status changed
      if (newStatus.is_open !== status.is_open) {
        debug.log(`[useLivePrices] Market status changed: ${status.is_open ? 'OPEN' : 'CLOSED'} -> ${newStatus.is_open ? 'OPEN' : 'CLOSED'}`);
        setupIntervals(newStatus.is_open);
        // Fetch prices immediately when market status changes
        await fetchPrices(symbolsRef.current);
      }
    }, 60000);
  }, [fetchMarketStatus, fetchPrices, stopPriceUpdates]);

  const getPrice = useCallback((symbol: string): PriceData | null => {
    return prices[symbol] || null;
  }, [prices]);

  // WebSocket integration - try WebSocket first, fallback to HTTP polling
  const { isConnected: wsConnected, connectionError: wsError } = useWebSocketPrices({
    symbols: symbolsRef.current,
    enabled: useWebSocket && symbolsRef.current.length > 0,
    onPriceUpdate: (priceUpdates) => {
      // Update prices from WebSocket - reduced logging
      setPrices((prev) => {
        const updated = { ...prev };
        Object.entries(priceUpdates).forEach(([symbol, data]) => {
          updated[symbol] = {
            price: data.price,
            timestamp: data.timestamp,
            isMarketOpen: data.is_market_open,
          };
        });
        return updated;
      });
    },
  });

  // Stop HTTP polling when WebSocket is connected (WebSocket is primary)
  useEffect(() => {
    if (wsConnected && priceIntervalRef.current) {
      // WebSocket is connected - stop HTTP polling to avoid duplicate fetches
      debug.log('[useLivePrices] WebSocket connected - stopping HTTP polling');
      stopPriceUpdates();
    } else if (!wsConnected && !priceIntervalRef.current && symbolsRef.current.length > 0) {
      // WebSocket disconnected - restart HTTP polling
      debug.log('[useLivePrices] WebSocket disconnected - restarting HTTP polling');
      const status = marketStatusRef.current;
      const intervalMs = status.is_open ? intervalMsRef.current : INTERVALS.MARKET_CLOSED_POLL;
      priceIntervalRef.current = setInterval(() => {
        fetchPrices(symbolsRef.current);
      }, intervalMs);
    }
  }, [wsConnected, fetchPrices, stopPriceUpdates]);

  // Fallback to HTTP polling if WebSocket fails
  useEffect(() => {
    if (!wsConnected && wsError && useWebSocket && symbolsRef.current.length > 0) {
      // WebSocket failed, disable it and rely on HTTP polling
      debug.log('[useLivePrices] WebSocket unavailable, falling back to HTTP polling');
      setUseWebSocket(false);
    } else if (wsConnected && !useWebSocket && symbolsRef.current.length > 0) {
      // WebSocket reconnected, enable it again
      debug.log('[useLivePrices] WebSocket reconnected');
      setUseWebSocket(true);
    }
  }, [wsConnected, wsError, useWebSocket]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopPriceUpdates();
    };
  }, [stopPriceUpdates]);

  return {
    prices,
    marketStatus,
    isLoading,
    fetchPrices,
    fetchMarketStatus,
    startPriceUpdates,
    stopPriceUpdates,
    getPrice,
    wsConnected, // Expose WebSocket connection status
  };
}

