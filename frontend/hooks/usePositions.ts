'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { accountApi } from '@/services/api';
import { debug } from '@/lib/debug';
import { useConnectivity } from '@/hooks/useConnectivity';
import type { Position, PriceData } from '@/lib/types';

interface UsePositionsOptions {
  symbols?: string[]; // Optional: filter positions by symbols
  onPositionUpdate?: (positions: Record<string, Position>) => void;
  enabled?: boolean;
}

/**
 * Normalize crypto symbol to trading format (BTC/USD).
 * Matches backend normalization logic.
 */
function normalizeCryptoSymbol(symbol: string): string {
  const upper = symbol.toUpperCase().trim();
  
  // Already in trading format
  if (upper.includes('/')) {
    return upper;
  }
  
  // Try to convert position format to trading format (BTCUSD -> BTC/USD)
  const cryptoQuotes = ['USD', 'USDT', 'USDC'];
  for (const quote of cryptoQuotes) {
    if (upper.endsWith(quote) && upper.length > quote.length) {
      const base = upper.slice(0, -quote.length);
      // Return in trading format
      return `${base}/${quote}`;
    }
  }
  
  // Return unchanged if not crypto or can't normalize
  return upper;
}

/**
 * Normalize a symbol for comparison (handles both formats).
 */
function normalizeSymbolForComparison(symbol: string): string {
  return normalizeCryptoSymbol(symbol);
}

/**
 * Hook to fetch and manage position data.
 * Updates positions when prices change (recalculates market_value and P/L).
 */
export function usePositions(options: UsePositionsOptions = {}) {
  const { symbols, onPositionUpdate, enabled = true } = options;
  const { isBackendReachable } = useConnectivity();
  const [positions, setPositions] = useState<Record<string, Position>>({});
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const onPositionUpdateRef = useRef(onPositionUpdate);
  const positionsRef = useRef<Record<string, Position>>({});

  // Update callback ref when it changes
  useEffect(() => {
    onPositionUpdateRef.current = onPositionUpdate;
  }, [onPositionUpdate]);

  // Update positions ref when positions change
  useEffect(() => {
    positionsRef.current = positions;
  }, [positions]);

  const fetchPositions = useCallback(async () => {
    if (!enabled) return;
    
    // Skip if backend is unreachable
    if (!isBackendReachable) {
      debug.log('[usePositions] Backend unreachable, skipping fetch');
      return;
    }

    try {
      setIsLoading(true);
      setError(null);
      const response = await accountApi.getPositions();
      const allPositions = response.data || [];

      // Normalize symbols for comparison (backend normalizes crypto symbols)
      const normalizedSymbols = symbols
        ? symbols.map(s => normalizeSymbolForComparison(s))
        : null;

      // Filter by symbols if provided (compare normalized versions)
      const filteredPositions = normalizedSymbols
        ? allPositions.filter((p: Position) => {
            const normalizedPositionSymbol = normalizeSymbolForComparison(p.symbol);
            return normalizedSymbols.includes(normalizedPositionSymbol);
          })
        : allPositions;

      // Only log summary, not individual matches (reduces console noise)
      if (symbols && symbols.length > 0) {
        debug.log('[usePositions] Fetched positions:', {
          requested: symbols.length,
          matched: filteredPositions.length,
          totalAvailable: allPositions.length,
        });
      }

      // Convert to record keyed by normalized symbol
      // Use original order symbols as keys so we can look them up correctly
      const positionsMap: Record<string, Position> = {};
      
      filteredPositions.forEach((pos: Position) => {
        const normalizedPositionSymbol = normalizeSymbolForComparison(pos.symbol);
        
        // Find matching symbol from original symbols array (could be in different format)
        if (normalizedSymbols) {
          const matchingSymbol = symbols!.find(s => 
            normalizeSymbolForComparison(s) === normalizedPositionSymbol
          );
          if (matchingSymbol) {
            positionsMap[matchingSymbol] = pos;
          } else {
            // Fallback: use normalized symbol as key
            positionsMap[normalizedPositionSymbol] = pos;
          }
        } else {
          // No filtering: use position symbol as-is
          positionsMap[pos.symbol] = pos;
        }
      });

      setPositions(positionsMap);
      positionsRef.current = positionsMap;
      onPositionUpdateRef.current?.(positionsMap);
    } catch (err: any) {
      debug.error('[usePositions] Error fetching positions:', err);
      setError(err.message || 'Failed to fetch positions');
    } finally {
      setIsLoading(false);
    }
  }, [symbols, enabled, isBackendReachable]);

  // Update position when price changes (recalculate market_value and P/L)
  const updatePositionWithPrice = useCallback((symbol: string, priceData: PriceData) => {
    setPositions((prev) => {
      const position = prev[symbol];
      if (!position) return prev;

      const currentPrice = priceData.price;
      const quantity = position.quantity;
      const avgEntryPrice = position.avg_entry_price;
      const costBasis = position.cost_basis;

      // Recalculate market value and P/L
      const marketValue = quantity * currentPrice;
      const unrealizedPl = marketValue - costBasis;
      const unrealizedPlpc = costBasis !== 0 ? (unrealizedPl / costBasis) * 100 : 0;

      const updatedPosition: Position = {
        ...position,
        current_price: currentPrice,
        market_value: marketValue,
        unrealized_pl: unrealizedPl,
        unrealized_plpc: unrealizedPlpc,
      };

      const updated = {
        ...prev,
        [symbol]: updatedPosition,
      };

      positionsRef.current = updated;
      onPositionUpdateRef.current?.(updated);
      return updated;
    });
  }, []);

  // Initial fetch and re-fetch when backend becomes reachable
  useEffect(() => {
    if (isBackendReachable) {
      fetchPositions();
    }
  }, [fetchPositions, isBackendReachable]);

  // Get position for a specific symbol (normalizes symbol for lookup)
  const getPosition = useCallback((symbol: string): Position | null => {
    // Try direct lookup first
    if (positions[symbol]) {
      return positions[symbol];
    }
    
    // Try normalized lookup (handles BTCUSD vs BTC/USD)
    const normalized = normalizeSymbolForComparison(symbol);
    for (const [key, pos] of Object.entries(positions)) {
      if (normalizeSymbolForComparison(key) === normalized) {
        return pos;
      }
    }
    
    return null;
  }, [positions]);

  return {
    positions,
    isLoading,
    error,
    getPosition,
    refetch: fetchPositions,
    updatePositionWithPrice,
  };
}

