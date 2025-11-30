import { useState, useCallback, useMemo } from 'react';
import { gttOrdersApi } from '@/services/api';
import { useLivePrices } from '@/hooks/useLivePrices';
import { useCompanyNames } from '@/hooks/useCompanyNames';
import { debug } from '@/lib/debug';
import { toast } from 'sonner';
import type { GTTOrder } from '@/lib/types';

/**
 * Hook to manage GTT order data fetching, updating, and refreshing
 * Handles orders state, company names, and price updates
 */
export function useGTTOrderData() {
  const { startPriceUpdates, stopPriceUpdates, getPrice, marketStatus } = useLivePrices();
  const { getCompanyNames } = useCompanyNames();
  
  const [orders, setOrders] = useState<GTTOrder[]>([]);
  const [companyNames, setCompanyNames] = useState<Record<string, string>>({});
  const [isLoading, setIsLoading] = useState(true);

  // Extract unique symbols from orders array
  const extractSymbols = useCallback((ordersData: GTTOrder[]): string[] => {
    return Array.from(new Set(ordersData.map((o: GTTOrder) => o.symbol))) as string[];
  }, []);

  // Shared logic to update orders, company names, and price updates
  const updateOrdersData = useCallback(async (ordersData: GTTOrder[]) => {
    setOrders(ordersData);
    
    // Update company names and price updates for all symbols
    const symbols = extractSymbols(ordersData);
    if (symbols.length > 0) {
      const names = await getCompanyNames(symbols);
      setCompanyNames(names);
      startPriceUpdates(symbols);
    }
  }, [extractSymbols, getCompanyNames, startPriceUpdates]);

  // Silent refresh that updates data without showing loading state
  // This preserves UI state like expanded cards and scroll position
  const silentRefreshOrders = useCallback(async () => {
    try {
      const response = await gttOrdersApi.getAll();
      const ordersData = response.data || [];
      await updateOrdersData(ordersData);
    } catch (error: any) {
      debug.error('Error silently refreshing orders:', error);
      // Don't show toast for silent refresh failures - user can manually refresh if needed
    }
  }, [updateOrdersData]);

  // Fetch orders with loading state and error handling
  const fetchOrders = useCallback(async () => {
    try {
      setIsLoading(true);
      const response = await gttOrdersApi.getAll();
      const ordersData = response.data || [];
      await updateOrdersData(ordersData);
    } catch (error: any) {
      debug.error('Error fetching orders:', error);
      
      // Extract detailed error information
      let errorMessage = 'Failed to load GTT orders';
      let errorDetails = '';
      
      if (error.response) {
        // API responded with error status
        const status = error.response.status;
        const statusText = error.response.statusText;
        const detail = error.response.data?.detail || error.response.data?.message || '';
        
        errorDetails = `Status: ${status} ${statusText}`;
        if (detail) {
          errorDetails += ` - ${typeof detail === 'string' ? detail : JSON.stringify(detail)}`;
        }
      } else if (error.request) {
        // Request was made but no response received
        errorDetails = 'No response from server. Check if backend is running.';
      } else {
        // Error setting up the request
        errorDetails = error.message || 'Unknown error occurred';
      }
      
      // Handle circuit breaker errors
      if ((error as any).isCircuitBreakerOpen) {
        errorDetails = 'Backend is temporarily unavailable. Retrying automatically...';
      }
      
      toast.error(`${errorMessage}. ${errorDetails}`, { duration: 8000 });
    } finally {
      setIsLoading(false);
    }
  }, [updateOrdersData]);

  // Extract symbols for use in other hooks
  const orderSymbols = useMemo(() => extractSymbols(orders), [orders, extractSymbols]);

  return {
    orders,
    companyNames,
    isLoading,
    orderSymbols,
    fetchOrders,
    silentRefreshOrders,
    updateOrdersData,
    stopPriceUpdates,
    setOrders,
    getPrice,
    marketStatus,
  };
}

