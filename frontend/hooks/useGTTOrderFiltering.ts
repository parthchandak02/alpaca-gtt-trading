import { useState, useMemo, useCallback } from 'react';
import { isCryptoSymbol } from '@/lib/utils';
import type { GTTOrder } from '@/lib/types';

type SortField = 'name' | 'price' | 'dateCreated' | 'lastActivity';

interface GroupedOrder {
  symbol: string;
  orders: GTTOrder[];
  total_value: number;
  locked_buying_power: number;
  filled_count: number;
  total_count: number;
  all_order_details: GTTOrder['order_details'];
  earliest_created: string;
  latest_updated: string;
}

interface UseGTTOrderFilteringProps {
  groupedOrders: GroupedOrder[];
  searchQuery: string;
  filterType: 'all' | 'stocks' | 'crypto';
  sortField: SortField | null;
  sortDirection: 'asc' | 'desc';
  companyNames: Record<string, string>;
  getPrice: (symbol: string) => { price: number } | null;
}

/**
 * Hook to filter and sort grouped GTT orders
 * Handles search, type filtering, and sorting logic
 */
export function useGTTOrderFiltering({
  groupedOrders,
  searchQuery,
  filterType,
  sortField,
  sortDirection,
  companyNames,
  getPrice,
}: UseGTTOrderFilteringProps) {
  const filteredOrders = useMemo(() => {
    let groups = groupedOrders;
    
    // Filter out stocks with no orders (total_count === 0)
    groups = groups.filter(group => group.total_count > 0);
    
    // Apply type filter (all, stocks, crypto)
    if (filterType !== 'all') {
      groups = groups.filter(group => {
        const isCrypto = isCryptoSymbol(group.symbol);
        return filterType === 'crypto' ? isCrypto : !isCrypto;
      });
    }
    
    // Apply search filter if query exists
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      groups = groups.filter(group => {
        const symbol = group.symbol.toLowerCase();
        const companyName = (companyNames[group.symbol] || '').toLowerCase();
        return symbol.includes(query) || companyName.includes(query);
      });
    }
    
    // Apply sorting
    if (sortField) {
      groups = [...groups].sort((a, b) => {
        let comparison = 0;
        
        switch (sortField) {
          case 'name':
            // Sort by company name if available, otherwise by symbol
            const nameA = (companyNames[a.symbol] || a.symbol).toLowerCase();
            const nameB = (companyNames[b.symbol] || b.symbol).toLowerCase();
            comparison = nameA.localeCompare(nameB);
            break;
            
          case 'price':
            // Sort by current price
            const priceA = getPrice(a.symbol)?.price || 0;
            const priceB = getPrice(b.symbol)?.price || 0;
            comparison = priceA - priceB;
            break;
            
          case 'dateCreated':
            // Sort by earliest created_at
            comparison = new Date(a.earliest_created).getTime() - new Date(b.earliest_created).getTime();
            break;
            
          case 'lastActivity':
            // Sort by latest updated_at
            comparison = new Date(a.latest_updated).getTime() - new Date(b.latest_updated).getTime();
            break;
        }
        
        return sortDirection === 'asc' ? comparison : -comparison;
      });
    }
    
    return groups;
  }, [groupedOrders, searchQuery, companyNames, filterType, sortField, sortDirection, getPrice]);

  return filteredOrders;
}

/**
 * Hook to manage sort state and handle sort button clicks
 */
export function useGTTOrderSorting() {
  const [sortField, setSortField] = useState<SortField | null>(null);
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc');

  const handleSort = useCallback((field: SortField) => {
    if (sortField === field) {
      // Toggle direction if same field
      setSortDirection(prev => prev === 'asc' ? 'desc' : 'asc');
    } else {
      // Set new field with ascending direction
      setSortField(field);
      setSortDirection('asc');
    }
  }, [sortField]);

  return {
    sortField,
    sortDirection,
    handleSort,
  };
}

