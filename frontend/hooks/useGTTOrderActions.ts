import { useState, useCallback } from 'react';
import { gttOrdersApi } from '@/services/api';
import { toast } from 'sonner';
import type { GTTOrder } from '@/lib/types';

interface UseGTTOrderActionsProps {
  orders: GTTOrder[];
  setOrders: React.Dispatch<React.SetStateAction<GTTOrder[]>>;
  silentRefreshOrders: () => Promise<void>;
}

/**
 * Hook to handle GTT order actions (delete, create, CSV upload)
 * Manages modal state and order operations
 */
export function useGTTOrderActions({
  orders,
  setOrders,
  silentRefreshOrders,
}: UseGTTOrderActionsProps) {
  const [showAddModal, setShowAddModal] = useState(false);
  const [showCSVModal, setShowCSVModal] = useState(false);

  const handleDeleteOrder = useCallback(async (id: number) => {
    try {
      // Optimistically remove the order from state
      setOrders(prevOrders => prevOrders.filter(order => order.id !== id));
      
      await gttOrdersApi.delete(id);
      toast.success('Order deleted successfully');
      
      // Silently refresh to ensure data consistency without resetting UI
      silentRefreshOrders();
    } catch (error: any) {
      // On error, restore the order by refetching
      toast.error(error.response?.data?.detail || 'Failed to delete order');
      silentRefreshOrders(); // Restore correct state
      throw error; // Re-throw so ConfirmDeleteButton can handle loading state
    }
  }, [setOrders, silentRefreshOrders]);

  const handleOrderCreated = useCallback(() => {
    setShowAddModal(false);
    silentRefreshOrders();
  }, [silentRefreshOrders]);

  const handleCSVUploaded = useCallback(async () => {
    // Don't close modal yet - wait for orders to load
    // Fetch orders and wait for them to complete
    await silentRefreshOrders();
    // Modal will close after this promise resolves
    setShowCSVModal(false);
  }, [silentRefreshOrders]);

  return {
    showAddModal,
    showCSVModal,
    setShowAddModal,
    setShowCSVModal,
    handleDeleteOrder,
    handleOrderCreated,
    handleCSVUploaded,
  };
}

