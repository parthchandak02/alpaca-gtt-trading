import { useEffect, useRef } from 'react';
import { usePositions } from '@/hooks/usePositions';
import { useLivePrices } from '@/hooks/useLivePrices';

interface UseGTTOrderPositionsProps {
  symbols: string[];
}

/**
 * Hook to manage position updates for GTT order symbols
 * Handles throttled position updates when prices change
 */
export function useGTTOrderPositions({ symbols }: UseGTTOrderPositionsProps) {
  const { getPrice } = useLivePrices();
  const { getPosition, updatePositionWithPrice } = usePositions({
    symbols,
    enabled: symbols.length > 0,
  });

  // Use a ref to track last update time to avoid excessive updates
  const lastPriceUpdateRef = useRef<Record<string, number>>({});
  
  useEffect(() => {
    if (symbols.length === 0) return;
    
    const updatePositions = () => {
      symbols.forEach((symbol) => {
        const price = getPrice(symbol);
        if (price) {
          const lastUpdate = lastPriceUpdateRef.current[symbol];
          const now = Date.now();
          // Only update if price changed or it's been more than 1 second since last update
          if (!lastUpdate || now - lastUpdate > 1000) {
            updatePositionWithPrice(symbol, price);
            lastPriceUpdateRef.current[symbol] = now;
          }
        }
      });
    };

    // Update immediately
    updatePositions();
    
    // Set up interval to update positions periodically (every 2 seconds)
    const interval = setInterval(updatePositions, 2000);
    
    return () => clearInterval(interval);
  }, [symbols, getPrice, updatePositionWithPrice]);

  return {
    getPosition,
  };
}

