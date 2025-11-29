'use client';

import { useEffect, useState } from 'react';
import { useLivePrices } from '@/hooks/useLivePrices';
import { useAuth } from '@/hooks/useAuth';
import { useRealtimeUpdates } from '@/hooks/useRealtimeUpdates';
import { useGTTOrderGrouping } from '@/hooks/useGTTOrderGrouping';
import { useGTTOrderFiltering, useGTTOrderSorting } from '@/hooks/useGTTOrderFiltering';
import { useTemplateDownloads } from '@/hooks/useTemplateDownloads';
import { useGTTOrderData } from '@/hooks/useGTTOrderData';
import { useGTTOrderExpand } from '@/hooks/useGTTOrderExpand';
import { useGTTOrderActions } from '@/hooks/useGTTOrderActions';
import { useGTTOrderPositions } from '@/hooks/useGTTOrderPositions';
import { GTTOrderCard } from './GTTOrderCard';
import { AddGTTOrderModal } from './AddGTTOrderModal';
import { CSVUploadModal } from './CSVUploadModal';
import { AccountSummary } from './AccountSummary';
import { GTTOrdersActions } from './GTTOrdersActions';
import { GTTOrdersSearchBar } from './GTTOrdersSearchBar';
import { GlassCard } from '@/components/glass';
import { RefreshCw } from 'lucide-react';
import { debug } from '@/lib/debug';
import { isCryptoSymbol } from '@/lib/utils';

export function GTTOrdersPage() {
  const { logout } = useAuth();
  const { marketStatus, getPrice } = useLivePrices();
  
  // Order data management
  const {
    orders,
    companyNames,
    isLoading,
    orderSymbols,
    fetchOrders,
    silentRefreshOrders,
    setOrders,
    stopPriceUpdates,
  } = useGTTOrderData();

  // Expand/collapse state
  const { expandedOrders, expandAll, toggleExpand, toggleExpandAll } = useGTTOrderExpand(orders);

  // Sort state
  const { sortField, sortDirection, handleSort } = useGTTOrderSorting();
  
  // Template downloads
  const { handleDownloadStocksTemplate, handleDownloadCryptoTemplate } = useTemplateDownloads();

  // Order actions
  const {
    showAddModal,
    showCSVModal,
    setShowAddModal,
    setShowCSVModal,
    handleDeleteOrder,
    handleOrderCreated,
    handleCSVUploaded,
  } = useGTTOrderActions({
    orders,
    setOrders,
    silentRefreshOrders,
  });

  // Position updates
  const { getPosition } = useGTTOrderPositions({ symbols: orderSymbols });

  // Search and filter state
  const [searchQuery, setSearchQuery] = useState('');
  const [filterType, setFilterType] = useState<'all' | 'stocks' | 'crypto'>('all');

  // Real-time updates via SSE
  const { isConnected: isRealtimeConnected } = useRealtimeUpdates({
    onOrderCreated: () => {
      silentRefreshOrders();
    },
    onOrderUpdated: () => {
      silentRefreshOrders();
    },
    onOrderDeleted: () => {
      silentRefreshOrders();
    },
    onOrdersBulkCreated: () => {
      silentRefreshOrders();
    },
  });



  // Fetch initial data on mount
  useEffect(() => {
    fetchOrders();
    
    return () => {
      stopPriceUpdates();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // Only run on mount

  // Group orders by symbol and aggregate data
  const groupedOrders = useGTTOrderGrouping(orders);

  // Filter and sort orders
  const filteredOrders = useGTTOrderFiltering({
    groupedOrders,
    searchQuery,
    filterType,
    sortField,
    sortDirection,
    companyNames,
    getPrice,
  });

  const marketIsOpen = marketStatus.is_open;

  return (
    <div className="space-y-1.5 sm:space-y-2">
      {/* Account Summary Component */}
      <AccountSummary marketIsOpen={marketIsOpen} onLogout={logout} />

      {/* Action Buttons */}
      <GTTOrdersActions
        onAddOrder={() => setShowAddModal(true)}
        onUploadCSV={() => setShowCSVModal(true)}
        onDownloadStocksTemplate={handleDownloadStocksTemplate}
        onDownloadCryptoTemplate={handleDownloadCryptoTemplate}
      />

      {/* Search and Filter */}
      <GTTOrdersSearchBar
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        sortField={sortField}
        sortDirection={sortDirection}
        onSort={handleSort}
        filterType={filterType}
        onFilterChange={setFilterType}
        onRefresh={fetchOrders}
        expandAll={expandAll}
        onToggleExpandAll={toggleExpandAll}
      />

      {/* Orders List */}
      {isLoading ? (
        <GlassCard className="p-6">
          <div className="flex items-center justify-center">
            <RefreshCw className="h-6 w-6 animate-spin text-text-secondary" />
          </div>
        </GlassCard>
      ) : filteredOrders.length === 0 ? (
        <GlassCard className="p-6 text-center">
          <p className="text-sm text-text-secondary">
            {searchQuery ? 'No orders found matching your search.' : 'No GTT orders yet. Create your first order!'}
          </p>
        </GlassCard>
      ) : (
        <div className="space-y-1.5">
          {filteredOrders.map((group) => {
            const isCrypto = isCryptoSymbol(group.symbol);
            return (
              <GTTOrderCard
                key={group.symbol}
                symbol={group.symbol}
                orders={group.orders}
                aggregatedData={{
                  total_value: group.total_value,
                  locked_buying_power: group.locked_buying_power,
                  filled_count: group.filled_count,
                  total_count: group.total_count,
                  all_order_details: group.all_order_details,
                }}
                companyName={companyNames[group.symbol] || group.symbol}
                currentPrice={getPrice(group.symbol)}
                position={getPosition(group.symbol)}
                isExpanded={expandedOrders.has(group.symbol)}
                isCrypto={isCrypto}
                onToggleExpand={() => toggleExpand(group.symbol)}
                onDelete={(orderId: number) => handleDeleteOrder(orderId)}
                onOrderUpdated={silentRefreshOrders}
              />
            );
          })}
        </div>
      )}

      {/* Modals */}
      {showAddModal && (
        <AddGTTOrderModal
          open={showAddModal}
          onClose={() => setShowAddModal(false)}
          onSuccess={handleOrderCreated}
        />
      )}

      {showCSVModal && (
        <CSVUploadModal
          open={showCSVModal}
          onClose={() => setShowCSVModal(false)}
          onSuccess={handleCSVUploaded}
        />
      )}
    </div>
  );
}

