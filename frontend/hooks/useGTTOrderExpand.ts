import { useState, useEffect, useRef, useCallback } from 'react';
import type { GTTOrder } from '@/lib/types';

/**
 * Hook to manage expand/collapse state for GTT orders
 * Handles individual order expansion and expand-all functionality
 */
export function useGTTOrderExpand(orders: GTTOrder[]) {
  const [expandedOrders, setExpandedOrders] = useState<Set<string>>(new Set());
  const [expandAll, setExpandAll] = useState(false);
  const prevExpandAllRef = useRef(expandAll);

  // Extract unique symbols from orders
  const extractSymbols = (ordersData: GTTOrder[]): string[] => {
    return Array.from(new Set(ordersData.map((o: GTTOrder) => o.symbol)));
  };

  // Handle expand all toggle - use symbol instead of order id
  // Preserve expanded state when orders update (don't collapse accordions)
  useEffect(() => {
    const prevExpandAll = prevExpandAllRef.current;
    prevExpandAllRef.current = expandAll;
    
    if (expandAll) {
      // When expandAll is true, expand all symbols (including new ones)
      const symbols = extractSymbols(orders);
      setExpandedOrders(new Set(symbols));
    } else if (prevExpandAll && !expandAll) {
      // Only collapse all if expandAll changed from true to false (user clicked collapse)
      // Don't reset when orders change - preserve user's manual expand/collapse state
      setExpandedOrders(new Set());
    }
    // When expandAll is false and stays false, don't modify expandedOrders
    // This prevents accordions from collapsing when orders are updated after delete/link
  }, [expandAll, orders]);

  const toggleExpand = useCallback((symbol: string) => {
    setExpandedOrders(prev => {
      const newExpanded = new Set(prev);
      if (newExpanded.has(symbol)) {
        newExpanded.delete(symbol);
      } else {
        newExpanded.add(symbol);
      }
      return newExpanded;
    });
  }, []);

  const toggleExpandAll = useCallback(() => {
    setExpandAll(prev => !prev);
  }, []);

  return {
    expandedOrders,
    expandAll,
    toggleExpand,
    toggleExpandAll,
  };
}

