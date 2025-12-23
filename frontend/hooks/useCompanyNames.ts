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
    
    // Add cached names immediately
    symbols.forEach(symbol => {
      if (cache[symbol]) {
        names[symbol] = cache[symbol];
      }
    });
    
    // If all symbols are cached, return immediately
    if (uncachedSymbols.length === 0) {
      return names;
    }
    
    // Batch requests to avoid overwhelming backend (max 10 concurrent, no delays)
    const BATCH_SIZE = 10;
    const promises: Promise<void>[] = [];
    
    for (let i = 0; i < uncachedSymbols.length; i += BATCH_SIZE) {
      const batch = uncachedSymbols.slice(i, i + BATCH_SIZE);
      const batchPromises = batch.map(async (symbol) => {
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
      
      promises.push(...batchPromises);
    }
    
    // Execute all batches concurrently (no delays)
    await Promise.all(promises);
    
    // Update cache state once
    setCache((prev) => ({ ...prev, ...names }));
    
    return names;
  }, [cache]);
  
  return {
    getCompanyName,
    getCompanyNames,
    companyNamesCache: cache,
  };
}

