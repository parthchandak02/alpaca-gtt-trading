import { useMemo } from 'react';
import type { GTTOrder } from '@/lib/types';

/**
 * Hook to group GTT orders by symbol and aggregate data
 * Returns grouped orders with aggregated totals and metadata
 */
export function useGTTOrderGrouping(orders: GTTOrder[]) {
  const groupedOrders = useMemo(() => {
    const groups: Record<string, {
      symbol: string;
      orders: GTTOrder[];
      total_value: number;
      locked_buying_power: number;
      filled_count: number;
      total_count: number;
      all_order_details: GTTOrder['order_details'];
      earliest_created: string;
      latest_updated: string;
    }> = {};

    orders.forEach(order => {
      const symbol = order.symbol;
      if (!groups[symbol]) {
        groups[symbol] = {
          symbol,
          orders: [],
          total_value: 0,
          locked_buying_power: 0,
          filled_count: 0,
          total_count: 0,
          all_order_details: [],
          earliest_created: order.created_at,
          latest_updated: order.updated_at,
        };
      }

      groups[symbol].orders.push(order);
      groups[symbol].total_value += order.total_value;
      groups[symbol].locked_buying_power += order.locked_buying_power;
      groups[symbol].filled_count += order.filled_count;
      groups[symbol].total_count += order.total_count;
      
      // Combine all order details with order reference
      if (order.order_details) {
        order.order_details.forEach((detail) => {
          groups[symbol].all_order_details.push({
            ...detail,
            gtt_order_id: order.id, // Keep reference to parent order
          });
        });
      }

      // Track earliest created and latest updated
      if (new Date(order.created_at) < new Date(groups[symbol].earliest_created)) {
        groups[symbol].earliest_created = order.created_at;
      }
      if (new Date(order.updated_at) > new Date(groups[symbol].latest_updated)) {
        groups[symbol].latest_updated = order.updated_at;
      }
    });

    return Object.values(groups);
  }, [orders]);

  return groupedOrders;
}

