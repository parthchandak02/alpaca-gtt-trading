'use client';

import { useState, useCallback } from 'react';
import { assetApi } from '@/services/api';
import { debug } from '@/lib/debug';

const companyNamesCache: Record<string, string> = {};

export function useCompanyNames() {
  const [cache, setCache] = useState<Record<string, string>>(companyNamesCache);

  const getCompanyName = useCallback(async (symbol: string): Promise<string | null> => {
    if (!symbol) return null;
    
    // Check cache first
    if (cache[symbol]) {
      return cache[symbol];
    }
    
    try {
      const response = await assetApi.getInfo(symbol);
      const name = response.data?.name || symbol;
      // Update cache
      setCache((prev) => ({ ...prev, [symbol]: name }));
      companyNamesCache[symbol] = name;
      return name;
    } catch (error) {
      debug.error(`Error fetching company name for ${symbol}:`, error);
      // Cache the symbol itself as fallback
      setCache((prev) => ({ ...prev, [symbol]: symbol }));
      companyNamesCache[symbol] = symbol;
      return symbol;
    }
  }, [cache]);
  
  const getCompanyNames = useCallback(async (symbols: string[]): Promise<Record<string, string>> => {
    const names: Record<string, string> = {};
    const uncachedSymbols = symbols.filter(s => !cache[s]);
    
    // Batch requests to avoid overwhelming backend (max 5 concurrent)
    const BATCH_SIZE = 5;
    for (let i = 0; i < uncachedSymbols.length; i += BATCH_SIZE) {
      const batch = uncachedSymbols.slice(i, i + BATCH_SIZE);
      const promises = batch.map(async (symbol) => {
        try {
          const response = await assetApi.getInfo(symbol);
          const name = response.data?.name || symbol;
          names[symbol] = name;
          companyNamesCache[symbol] = name;
        } catch (error) {
          debug.error(`Error fetching company name for ${symbol}:`, error);
          names[symbol] = symbol;
          companyNamesCache[symbol] = symbol;
        }
      });
      
      await Promise.all(promises);
      
      // Small delay between batches to prevent overwhelming backend
      if (i + BATCH_SIZE < uncachedSymbols.length) {
        await new Promise(resolve => setTimeout(resolve, 100));
      }
    }
    
    // Update cache state
    setCache((prev) => ({ ...prev, ...names }));
    
    // Add cached names
    symbols.forEach(symbol => {
      if (cache[symbol]) {
        names[symbol] = cache[symbol];
      }
    });
    
    return names;
  }, [cache]);
  
  return {
    getCompanyName,
    getCompanyNames,
    companyNamesCache: cache,
  };
}

