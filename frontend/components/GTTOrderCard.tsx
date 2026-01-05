'use client';

// React
import { useState, useEffect } from 'react';

// Components
import { GlassCard } from '@/components/glass';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Tooltip } from '@/components/ui/tooltip';
import { AnimatedPrice } from './AnimatedPrice';
import { PriceChart } from './PriceChart';

// Icons
import { ChevronDown, ChevronUp, Trash2, Check, Pencil, Link2, Link2Off, ExternalLink, Circle, Clock, Activity } from 'lucide-react';

// Services
import { gttOrdersApi, ordersApi } from '@/services/api';

// Utilities
import { formatCurrency, formatDate, formatTimeAgo, formatPositionQuantity, formatQuantity } from '@/lib/formatters';
import { getStatusBadgeVariant, formatStatusText } from '@/lib/orderStatus';
import { cn } from '@/lib/utils';
import { debug } from '@/lib/debug';
import { extractErrorMessage, isNotFoundError, isServerError, isNetworkError } from '@/lib/errorHandling';
import { toast } from 'sonner';

// Types
import type { GTTOrder, AggregatedOrderData, PriceData, Position } from '@/lib/types';

interface GTTOrderCardProps {
  symbol: string;
  orders: GTTOrder[];
  aggregatedData: AggregatedOrderData;
  companyName: string;
  currentPrice: PriceData | null;
  position: Position | null;
  isExpanded: boolean;
  isCrypto?: boolean;
  onToggleExpand: () => void;
  onDelete: (orderId: number) => void;
  onOrderUpdated?: () => void;
}

export function GTTOrderCard({
  symbol,
  orders,
  aggregatedData,
  companyName,
  currentPrice,
  position,
  isExpanded,
  isCrypto = false,
  onToggleExpand,
  onDelete,
  onOrderUpdated,
}: GTTOrderCardProps) {
  // Debug logging - only log on mount or when key props change (not every render)
  // Removed excessive render logging that was flooding console
  
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteProgress, setDeleteProgress] = useState(0);
  const [showProgress, setShowProgress] = useState(false);
  const [confirmingDeleteAll, setConfirmingDeleteAll] = useState(false);
  const [confirmingDeleteDetail, setConfirmingDeleteDetail] = useState<number | null>(null);
  const [editingDetail, setEditingDetail] = useState<number | null>(null);
  const [linkingDetail, setLinkingDetail] = useState<number | null>(null);
  const [linkOrderId, setLinkOrderId] = useState('');
  const [unlinkingDetail, setUnlinkingDetail] = useState<number | null>(null);
  const [editFormData, setEditFormData] = useState<{
    trigger_price?: number;
    quantity?: number;
    limit_price?: number;
    time_in_force?: string;
  } | null>(null);

  const handleDeleteDetail = async (orderId: number, detailId: number, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    const startTime = Date.now();
    setShowProgress(true);
    setDeleteProgress(0);
    
    try {
      await gttOrdersApi.deleteOrderDetail(orderId, detailId);
      toast.success('Order detail deleted successfully');
      onOrderUpdated?.();
    } catch (error: unknown) {
      debug.error('Delete order detail error:', { error, orderId, detailId });
      
      let errorMessage = extractErrorMessage(error, 'Failed to delete order detail');
      
      // Add context based on error type
      if (isNotFoundError(error)) {
        errorMessage = `Order detail ${detailId} not found for order ${orderId}. It may have already been deleted.`;
      } else if (isServerError(error)) {
        errorMessage = `Server error: ${errorMessage}. Check console for details.`;
      } else if (isNetworkError(error)) {
        errorMessage = `Network error: ${errorMessage}. Is the backend running?`;
      }
      
      toast.error(errorMessage, { duration: 6000 });
    } finally {
      const elapsed = Date.now() - startTime;
      if (elapsed < 500) {
        // If it was fast, hide progress immediately
        setShowProgress(false);
        setDeleteProgress(0);
      } else {
        // Otherwise, complete the progress bar
        setDeleteProgress(100);
        setTimeout(() => {
          setShowProgress(false);
          setDeleteProgress(0);
        }, 300);
      }
    }
  };

  const handleDeleteAll = async () => {
    const startTime = Date.now();
    setIsDeleting(true);
    setShowProgress(true);
    setDeleteProgress(0);
    
    try {
      // Get all deletable order details across all orders for this symbol
      // Only delete orders that are PENDING, CANCELLED, FAILED, or EXPIRED
      // Do NOT delete FILLED or PARTIALLY_FILLED orders
      const deletableDetails = aggregatedData.all_order_details.filter(
        (detail: any) => {
          const status = detail.status?.toUpperCase();
          return status !== 'FILLED' && status !== 'PARTIALLY_FILLED';
        }
      );
      
      if (deletableDetails.length === 0) {
        toast.info('No deletable orders to delete (only filled/partially filled orders exist)');
        setShowProgress(false);
        setDeleteProgress(0);
        setIsDeleting(false);
        return;
      }
      
      const totalDetails = deletableDetails.length;
      const failedDetails: Array<{ id: number; error: string }> = [];
      
      // Delete all deletable order details sequentially with progress updates
      const deletePromises = deletableDetails.map(async (detail: any, index: number) => {
        try {
          await gttOrdersApi.deleteOrderDetail(detail.gtt_order_id, detail.id);
          setDeleteProgress(((index + 1) / totalDetails) * 100);
        } catch (error: any) {
          debug.error(`Failed to delete order detail ${detail.id}:`, error);
          
          // Extract error message
          let errorMsg = 'Unknown error';
          if (error.response?.data?.detail) {
            errorMsg = error.response.data.detail;
          } else if (error.message) {
            errorMsg = error.message;
          } else if (error.response?.statusText) {
            errorMsg = `${error.response.statusText} (${error.response.status})`;
          }
          
          failedDetails.push({ id: detail.id, error: errorMsg });
        }
      });
      
      await Promise.all(deletePromises);
      
      if (failedDetails.length > 0) {
        const errorDetails = failedDetails.slice(0, 3).map(fd => `Order ${fd.id}: ${fd.error}`).join('; ');
        toast.error(
          `Failed to delete ${failedDetails.length} of ${totalDetails} deletable orders. ${errorDetails}${failedDetails.length > 3 ? '...' : ''}`,
          { duration: 6000 }
        );
      } else {
        toast.success(`Deleted all ${totalDetails} deletable orders for ${symbol} (filled and partially filled orders were preserved)`);
      }
      
      onOrderUpdated?.(); // Refresh the orders list once
    } catch (error: any) {
      debug.error('Delete all non-filled orders error:', error);
      
      let errorMessage = 'Failed to delete orders';
      if (error.response?.data?.detail) {
        errorMessage = error.response.data.detail;
      } else if (error.message) {
        errorMessage = error.message;
      }
      
      toast.error(errorMessage, { duration: 5000 });
    } finally {
      const elapsed = Date.now() - startTime;
      if (elapsed < 500) {
        setShowProgress(false);
        setDeleteProgress(0);
      } else {
        setDeleteProgress(100);
        setTimeout(() => {
          setShowProgress(false);
          setDeleteProgress(0);
        }, 300);
      }
      setIsDeleting(false);
    }
  };

  const completionPercentage = aggregatedData.total_count > 0 
    ? Math.round((aggregatedData.filled_count / aggregatedData.total_count) * 100) 
    : 0;
  
  // Calculate deletable order details count for delete button
  // Only delete orders that are PENDING, CANCELLED, FAILED, or EXPIRED
  // Do NOT delete FILLED or PARTIALLY_FILLED orders
  const deletableCount = aggregatedData.all_order_details.filter(
    (detail: any) => {
      const status = detail.status?.toUpperCase();
      return status !== 'FILLED' && status !== 'PARTIALLY_FILLED';
    }
  ).length;

  // Use consistent status badge utility
  const getStatusColor = getStatusBadgeVariant;

  return (
    <div className={cn(
      "glass-card overflow-hidden relative rounded-2xl transition-all duration-300",
      isCrypto 
        ? "gtt-card-crypto" 
        : "gtt-card-stock"
    )    } style={isCrypto 
      ? { 
          background: 'linear-gradient(to bottom right, rgba(219, 39, 119, 0.25), rgba(236, 72, 153, 0.2), rgba(219, 39, 119, 0.25)), rgba(26, 26, 28, 0.5)',
          borderColor: 'rgba(236, 72, 153, 0.5)',
          backdropFilter: 'blur(20px) saturate(180%)',
          WebkitBackdropFilter: 'blur(20px) saturate(180%)'
        }
      : { 
          background: 'linear-gradient(to bottom right, rgba(113, 63, 18, 0.3), rgba(113, 63, 18, 0.2), rgba(113, 63, 18, 0.3)), rgba(26, 26, 28, 0.4)',
          borderColor: 'rgba(161, 98, 7, 0.4)',
          backdropFilter: 'blur(20px) saturate(180%)',
          WebkitBackdropFilter: 'blur(20px) saturate(180%)'
        }
    }>
      {/* Progress Bar Overlay */}
      {showProgress && (
        <div className="absolute top-0 left-0 right-0 z-10">
          <Progress value={deleteProgress} className="h-1 rounded-none" />
        </div>
      )}
      
      {/* Header - Collapsed View */}
      <div
        className="p-1.5 cursor-pointer hover:bg-opacity-80 transition-all"
        onClick={onToggleExpand}
      >
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3 md:gap-2">
          <div className="flex items-center gap-2 flex-1 min-w-0">
            {/* Delete all non-filled orders button with inline checkmark confirmation */}
            <div className="flex items-center gap-1 flex-shrink-0" onClick={(e) => e.stopPropagation()}>
              <Button
                variant="ghost"
                size="icon"
                onClick={(e) => {
                  e.stopPropagation();
                  if (!confirmingDeleteAll && deletableCount > 0) {
                    setConfirmingDeleteAll(true);
                    // Auto-reset after 5 seconds if not confirmed
                    setTimeout(() => setConfirmingDeleteAll(false), 5000);
                  }
                }}
                disabled={deletableCount === 0 || isDeleting}
                className="h-6 w-6 text-status-error hover:text-status-error hover:bg-status-error/10 flex-shrink-0 disabled:opacity-50 disabled:cursor-not-allowed"
                title={deletableCount > 0 
                  ? `Delete all ${deletableCount} deletable orders for ${symbol} (preserves filled and partially filled orders)`
                  : `No deletable orders to delete for ${symbol} (only filled/partially filled orders exist)`
                }
              >
                <Trash2 className="h-3.5 w-3.5" />
              </Button>
              {confirmingDeleteAll && (
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleDeleteAll();
                    setConfirmingDeleteAll(false);
                  }}
                  className="h-6 w-6 text-status-error hover:text-status-error hover:bg-status-error/20 flex-shrink-0 transition-all duration-200 animate-in fade-in slide-in-from-left-2"
                  title="Click to confirm deletion"
                >
                  <Check className="h-3.5 w-3.5" />
                </Button>
              )}
            </div>
            
            {/* Chevron */}
            <div className="flex-shrink-0">
              {isExpanded ? (
                <ChevronUp className="h-4 w-4 text-text-secondary" />
              ) : (
                <ChevronDown className="h-4 w-4 text-text-secondary" />
              )}
            </div>
            
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <h3 className="text-base font-bold text-text-primary">{symbol}</h3>
              </div>
              <p className="text-xs text-text-secondary truncate">{companyName}</p>
            </div>
          </div>

          {/* Stats Grid - Clean horizontal layout with separators */}
          <div className="flex items-center gap-4 md:gap-6 w-full md:w-auto md:flex-shrink-0 flex-wrap">
            {/* 1. Live Price */}
            {currentPrice ? (
              <>
                <Tooltip 
                  content={
                    <div className="text-xs">
                      <div className="font-semibold mb-0.5 text-text-primary">
                        {currentPrice.isMarketOpen ? 'Live Price' : 'Last Price'}
                      </div>
                      <div className="text-text-tertiary">
                        Updated: {new Date(currentPrice.timestamp).toLocaleString('en-US', {
                          month: 'short',
                          day: 'numeric',
                          hour: 'numeric',
                          minute: '2-digit',
                          second: '2-digit',
                          hour12: true
                        })}
                      </div>
                      <div className="text-text-tertiary mt-0.5">
                        ({formatTimeAgo(currentPrice.timestamp)})
                      </div>
                    </div>
                  }
                  side="top"
                >
                  <div className="text-left md:text-right cursor-help">
                    <div className="text-[10px] text-text-tertiary uppercase tracking-wide mb-0.5">
                      {currentPrice.isMarketOpen ? 'Live Price' : 'Last Price'}
                    </div>
                    <div className="text-sm font-semibold text-text-primary font-numbers flex items-center gap-1.5 md:justify-end">
                      {/* Market Status Indicator */}
                      {currentPrice.isMarketOpen ? (
                        <Circle className="h-2 w-2 fill-status-success text-status-success animate-pulse" />
                      ) : (
                        <Clock className="h-2.5 w-2.5 text-text-tertiary" />
                      )}
                      <AnimatedPrice price={currentPrice.price} className="text-sm font-semibold" />
                    </div>
                  </div>
                </Tooltip>
                <div className="h-4 w-px bg-border-divider/50 hidden md:block" />
              </>
            ) : (
              <>
                <div className="text-left md:text-right">
                  <div className="text-[10px] text-text-tertiary uppercase tracking-wide mb-0.5">Price</div>
                  <div className="text-sm font-semibold text-text-tertiary font-numbers">—</div>
                </div>
                <div className="h-4 w-px bg-border-divider/50 hidden md:block" />
              </>
            )}

            {/* 2. Orders */}
            <div className="text-left md:text-right">
              <div className="text-[10px] text-text-tertiary uppercase tracking-wide mb-0.5">Orders</div>
              <div className="text-sm font-semibold text-text-primary font-numbers">
                {aggregatedData.total_count}
              </div>
            </div>

            <div className="h-4 w-px bg-border-divider/50 hidden md:block" />

            {/* 3. Completion */}
            <div className="text-left md:text-right">
              <div className="text-[10px] text-text-tertiary uppercase tracking-wide mb-0.5">Completed</div>
              <div className="text-sm font-semibold text-text-primary font-numbers">
                {completionPercentage}% ({aggregatedData.filled_count}/{aggregatedData.total_count})
              </div>
            </div>

            <div className="h-4 w-px bg-border-divider/50 hidden md:block" />

            {/* 4. Locked */}
            <Tooltip
              content={
                <div className="text-xs max-w-xs">
                  <div className="font-semibold mb-1 text-text-primary">Locked Buying Power</div>
                  <div className="text-text-tertiary mb-1">
                    Amount of buying power locked by orders SUBMITTED TO ALPACA.
                  </div>
                  <div className="text-text-secondary text-[10px] mt-1.5 pt-1.5 border-t border-border-divider">
                    <div className="font-semibold mb-0.5">Locks Buying Power:</div>
                    <div className="space-y-0.5">
                      <div>• Orders submitted to Alpaca:</div>
                      <div>• NEW, ACCEPTED, PENDING_NEW</div>
                      <div>• PARTIALLY_FILLED (remaining qty)</div>
                      <div>• PENDING_CANCEL, PENDING_REPLACE</div>
                    </div>
                    <div className="font-semibold mt-1.5 mb-0.5">Does NOT Lock:</div>
                    <div className="space-y-0.5">
                      <div>• Our PENDING (not triggered/submitted)</div>
                      <div>• FILLED (executed, money deducted)</div>
                      <div>• CANCELLED, EXPIRED, REJECTED</div>
                    </div>
                  </div>
                </div>
              }
              side="top"
            >
              <div className="text-left md:text-right cursor-help">
                <div className="text-[10px] text-text-tertiary uppercase tracking-wide mb-0.5">Locked</div>
                <div className="text-sm font-semibold text-text-primary font-numbers">
                  {formatCurrency(aggregatedData.locked_buying_power)}
                </div>
              </div>
            </Tooltip>

            <div className="h-4 w-px bg-border-divider/50 hidden md:block" />

            {/* 5. Total Value */}
            <div className="text-left md:text-right">
              <div className="text-[10px] text-text-tertiary uppercase tracking-wide mb-0.5">Total Value</div>
              <div className="text-sm font-semibold text-accent-cash font-numbers">
                {formatCurrency(aggregatedData.total_value)}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Position Info Section */}
      <div className="border-t border-border-divider/50 px-1.5 py-2">
        {position ? (
          <div className="flex items-center gap-4 md:gap-6 w-full md:justify-end flex-wrap">
            {/* 1. Qty Owned */}
            <div className="text-left md:text-right">
              <div className="text-[10px] text-text-tertiary uppercase tracking-wide mb-0.5">Qty Owned</div>
              <div className="text-sm font-semibold text-text-primary font-numbers">
                {formatPositionQuantity(position.quantity, isCrypto)}
              </div>
            </div>

            <div className="h-4 w-px bg-border-divider/50 hidden md:block" />

            {/* 2. Market Value */}
            <div className="text-left md:text-right">
              <div className="text-[10px] text-text-tertiary uppercase tracking-wide mb-0.5">Market Value</div>
              <div className="text-sm font-semibold text-text-primary font-numbers">
                {position.market_value ? formatCurrency(position.market_value) : '—'}
              </div>
            </div>

            <div className="h-4 w-px bg-border-divider/50 hidden md:block" />

            {/* 3. Cost Basis */}
            <div className="text-left md:text-right">
              <div className="text-[10px] text-text-tertiary uppercase tracking-wide mb-0.5">Cost Basis</div>
              <div className="text-sm font-semibold text-text-primary font-numbers">
                {formatCurrency(position.cost_basis)}
              </div>
            </div>

            <div className="h-4 w-px bg-border-divider/50 hidden md:block" />

            {/* 4. Total P/L %} */}
            <div className="text-left md:text-right">
              <div className="text-[10px] text-text-tertiary uppercase tracking-wide mb-0.5">Total P/L %</div>
              <div className={cn(
                "text-sm font-semibold font-numbers",
                position.unrealized_plpc !== null && position.unrealized_plpc >= 0
                  ? "text-status-success"
                  : position.unrealized_plpc !== null && position.unrealized_plpc < 0
                  ? "text-status-error"
                  : "text-text-secondary"
              )}>
                {position.unrealized_plpc !== null 
                  ? `${position.unrealized_plpc >= 0 ? '+' : ''}${position.unrealized_plpc.toFixed(2)}%`
                  : '—'}
              </div>
            </div>

            <div className="h-4 w-px bg-border-divider/50 hidden md:block" />

            {/* 5. Total P/L $ */}
            <div className="text-left md:text-right">
              <div className="text-[10px] text-text-tertiary uppercase tracking-wide mb-0.5">Total P/L $</div>
              <div className={cn(
                "text-sm font-semibold font-numbers",
                position.unrealized_pl !== null && position.unrealized_pl >= 0
                  ? "text-status-success"
                  : position.unrealized_pl !== null && position.unrealized_pl < 0
                  ? "text-status-error"
                  : "text-text-secondary"
              )}>
                {position.unrealized_pl !== null 
                  ? `${position.unrealized_pl >= 0 ? '+' : ''}${formatCurrency(Math.abs(position.unrealized_pl))}`
                  : '—'}
              </div>
            </div>
          </div>
        ) : (
          <div className="text-center py-1">
            <div className="text-sm text-text-tertiary">No positions found.</div>
          </div>
        )}
      </div>

      {/* Expanded Content */}
      {isExpanded && (
        <div className="border-t border-border-divider">
          {/* Order Details Table */}
          <div className="p-2">
            <h4 className="text-sm font-semibold mb-2">Order Details</h4>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-border-divider">
                    <th className="text-left py-1 px-2 text-xs font-medium text-text-secondary">Actions</th>
                    <th className="text-left py-1 px-2 text-xs font-medium text-text-secondary w-8">#</th>
                    <th className="text-left py-1 px-2 text-xs font-medium text-text-secondary">$ Trigger</th>
                    <th className="text-left py-1 px-2 text-xs font-medium text-text-secondary">Qty</th>
                    <th className="text-left py-1 px-2 text-xs font-medium text-text-secondary">Amount</th>
                    <th className="text-left py-1 px-2 text-xs font-medium text-text-secondary">Status</th>
                    <th className="text-left py-1 px-2 text-xs font-medium text-text-secondary">Filled Price</th>
                    <th className="text-left py-1 px-2 text-xs font-medium text-text-secondary">Alpaca Order</th>
                    <th className="text-left py-1 px-2 text-xs font-medium text-text-secondary">TIF</th>
                    <th className="text-left py-1 px-2 text-xs font-medium text-text-secondary">Submitted</th>
                    <th className="text-left py-1 px-2 text-xs font-medium text-text-secondary">Filled</th>
                    <th className="text-left py-1 px-2 text-xs font-medium text-text-secondary">Expired</th>
                  </tr>
                </thead>
                <tbody>
                  {aggregatedData.all_order_details
                    .sort((a: any, b: any) => b.trigger_price - a.trigger_price) // Sort by trigger price (highest to lowest)
                    .map((detail: any, index: number) => {
                    const canEdit = detail.status === 'PENDING' && !detail.is_manually_linked && !detail.alpaca_order_id;
                    const canLink = detail.status === 'PENDING' && !detail.is_manually_linked && !detail.alpaca_order_id;
                    const isLinked = detail.is_manually_linked || detail.alpaca_order_id;
                    
                    return (
                      <tr
                        key={`${detail.gtt_order_id}-${detail.id}`}
                        className="border-b border-border-divider hover:bg-bg-hover/50 transition-colors"
                      >
                        <td className="py-1 px-2">
                          <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
                            {/* Delete Button */}
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={(e) => {
                                e.stopPropagation();
                                if (!confirmingDeleteDetail || confirmingDeleteDetail !== detail.id) {
                                  setConfirmingDeleteDetail(detail.id);
                                  setTimeout(() => {
                                    setConfirmingDeleteDetail((prev) => prev === detail.id ? null : prev);
                                  }, 5000);
                                }
                              }}
                              className="h-6 w-6 text-status-error hover:text-status-error hover:bg-status-error/10"
                              title="Delete order"
                            >
                              <Trash2 className="h-3 w-3" />
                            </Button>
                            {confirmingDeleteDetail === detail.id && (
                              <Button
                                variant="ghost"
                                size="icon"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleDeleteDetail(detail.gtt_order_id, detail.id);
                                  setConfirmingDeleteDetail(null);
                                }}
                                className="h-6 w-6 text-status-error hover:text-status-error hover:bg-status-error/20 transition-all duration-200"
                                title="Confirm deletion"
                              >
                                <Check className="h-3 w-3" />
                              </Button>
                            )}
                            
                            {/* Edit Button - Only show for pending, non-linked orders */}
                            {canEdit && (
                              <Button
                                variant="ghost"
                                size="icon"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setEditingDetail(detail.id);
                                  setEditFormData({
                                    trigger_price: detail.trigger_price,
                                    quantity: detail.fractional_quantity || detail.quantity,
                                    limit_price: detail.limit_price,
                                    time_in_force: detail.time_in_force,
                                  });
                                }}
                                className="h-6 w-6 text-accent-orange hover:text-accent-orange hover:bg-accent-orange/10"
                                title="Edit order"
                              >
                                <Pencil className="h-3 w-3" />
                              </Button>
                            )}
                            
                            {/* Link Button - Only show for pending, non-linked orders */}
                            {canLink && (
                              <Button
                                variant="ghost"
                                size="icon"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setLinkingDetail(detail.id);
                                  setLinkOrderId('');
                                }}
                                className="h-6 w-6 text-accent-blue hover:text-accent-blue hover:bg-accent-blue/10"
                                title="Link to Alpaca order"
                              >
                                <Link2 className="h-3 w-3" />
                              </Button>
                            )}
                            
                            {/* Unlink Button - Only show for linked orders */}
                            {isLinked && (
                              <Button
                                variant="ghost"
                                size="icon"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setUnlinkingDetail(detail.id);
                                }}
                                className="h-6 w-6 text-status-error hover:text-status-error hover:bg-status-error/10"
                                title="Unlink from Alpaca order"
                              >
                                <Link2Off className="h-3 w-3" />
                              </Button>
                            )}
                          </div>
                        </td>
                        <td className="py-1 px-2 text-text-primary">
                          {index + 1}
                        </td>
                        <td className="py-1 px-2 text-text-primary font-medium font-numbers">
                          {formatCurrency(detail.trigger_price)}
                        </td>
                        <td className="py-1 px-2 text-text-primary font-numbers">{formatQuantity(detail.fractional_quantity || detail.quantity, isCrypto)}</td>
                        <td className="py-1 px-2 text-text-primary font-medium font-numbers">
                          {formatCurrency(detail.amount)}
                        </td>
                        <td className="py-1 px-2">
                          <Badge variant={getStatusColor(detail.status)} className="text-xs">
                            {formatStatusText(detail.status)}
                          </Badge>
                        </td>
                        <td className="py-1 px-2 text-text-primary font-numbers">
                          {detail.filled_avg_price ? formatCurrency(detail.filled_avg_price) : '-'}
                        </td>
                        <td className="py-1 px-2">
                          {detail.alpaca_order_id ? (
                            <a
                              href={`https://app.alpaca.markets/dashboard/order/${detail.alpaca_order_id}`}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="flex items-center gap-1 hover:text-text-primary transition-colors group"
                              title={`View order ${detail.alpaca_order_id} on Alpaca`}
                            >
                              <span className="text-text-secondary text-xs font-mono truncate max-w-[100px] group-hover:text-text-primary">
                                {detail.alpaca_order_id.substring(0, 8)}...
                              </span>
                              <ExternalLink className="h-3 w-3 text-text-tertiary group-hover:text-text-primary" />
                            </a>
                          ) : (
                            <span className="text-text-tertiary">-</span>
                          )}
                        </td>
                        <td className="py-1 px-2">
                          <Badge variant="success" className="text-xs">{detail.time_in_force}</Badge>
                        </td>
                        <td className="py-1 px-2 text-text-secondary text-xs font-datetime">
                          {detail.submitted_at ? formatDate(detail.submitted_at) : '-'}
                        </td>
                        <td className="py-1 px-2 text-text-secondary text-xs font-datetime">
                          {detail.filled_at ? formatDate(detail.filled_at) : '-'}
                        </td>
                        <td className="py-1 px-2 text-text-secondary text-xs font-datetime">
                          {detail.expired_at ? formatDate(detail.expired_at) : '-'}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            
            {/* Edit Modal */}
            {editingDetail && editFormData && (
              <EditOrderDetailModal
                detail={aggregatedData.all_order_details.find((d: any) => d.id === editingDetail)}
                formData={editFormData}
                onClose={() => {
                  setEditingDetail(null);
                  setEditFormData(null);
                }}
                onSave={async (data: any) => {
                  try {
                    const detail = aggregatedData.all_order_details.find((d: any) => d.id === editingDetail);
                    if (!detail) {
                      toast.error('Order detail not found');
                      return;
                    }
                    await gttOrdersApi.updateOrderDetail(detail.gtt_order_id, editingDetail, data);
                    toast.success('Order detail updated successfully');
                    setEditingDetail(null);
                    setEditFormData(null);
                    onOrderUpdated?.();
                  } catch (error: any) {
                    // Handle Pydantic validation errors (array of objects) vs string errors
                    const detail = error.response?.data?.detail;
                    let errorMsg = 'Failed to update order detail';
                    if (typeof detail === 'string') {
                      errorMsg = detail;
                    } else if (Array.isArray(detail) && detail.length > 0) {
                      errorMsg = detail.map((e: any) => e.msg || e.message).join(', ');
                    } else if (detail?.msg) {
                      errorMsg = detail.msg;
                    }
                    toast.error(errorMsg);
                  }
                }}
              />
            )}
            
            {/* Link Modal */}
            {linkingDetail && (
              <LinkOrderDetailModal
                detail={{
                  ...aggregatedData.all_order_details.find((d: any) => d.id === linkingDetail),
                  symbol: symbol // Pass symbol to modal
                }}
                onClose={() => {
                  setLinkingDetail(null);
                  setLinkOrderId('');
                }}
                onLink={async (alpacaOrderId: string) => {
                  try {
                    const detail = aggregatedData.all_order_details.find((d: any) => d.id === linkingDetail);
                    if (!detail) {
                      toast.error('Order detail not found');
                      return;
                    }
                    await gttOrdersApi.linkOrderDetail(detail.gtt_order_id, linkingDetail, alpacaOrderId);
                    toast.success('Order detail linked successfully');
                    setLinkingDetail(null);
                    setLinkOrderId('');
                    onOrderUpdated?.();
                  } catch (error: any) {
                    const detail = error.response?.data?.detail;
                    let errorMsg = 'Failed to link order detail';
                    if (typeof detail === 'string') {
                      errorMsg = detail;
                    } else if (Array.isArray(detail) && detail.length > 0) {
                      errorMsg = detail.map((e: any) => e.msg || e.message).join(', ');
                    }
                    toast.error(errorMsg);
                  }
                }}
              />
            )}
            
            {/* Unlink Confirmation Modal */}
            {unlinkingDetail && (
              <UnlinkOrderDetailModal
                detail={aggregatedData.all_order_details.find((d: any) => d.id === unlinkingDetail)}
                onClose={() => {
                  setUnlinkingDetail(null);
                }}
                onUnlink={async () => {
                  try {
                    const detail = aggregatedData.all_order_details.find((d: any) => d.id === unlinkingDetail);
                    if (!detail) {
                      toast.error('Order detail not found');
                      return;
                    }
                    await gttOrdersApi.unlinkOrderDetail(detail.gtt_order_id, unlinkingDetail);
                    toast.success('Order detail unlinked successfully');
                    setUnlinkingDetail(null);
                    onOrderUpdated?.();
                  } catch (error: any) {
                    const detail = error.response?.data?.detail;
                    let errorMsg = 'Failed to unlink order detail';
                    if (typeof detail === 'string') {
                      errorMsg = detail;
                    } else if (Array.isArray(detail) && detail.length > 0) {
                      errorMsg = detail.map((e: any) => e.msg || e.message).join(', ');
                    }
                    toast.error(errorMsg);
                  }
                }}
              />
            )}
          </div>

          {/* Price Chart */}
          <div className="p-2 border-t border-border-divider">
            <PriceChart 
              order={{ symbol, initial_trigger_price: orders[0]?.initial_trigger_price || 0 }} 
              orderDetails={aggregatedData.all_order_details} 
            />
          </div>
        </div>
      )}
    </div>
  );
}

// Edit Order Detail Modal
function EditOrderDetailModal({ detail, formData, onClose, onSave }: any) {
  const [data, setData] = useState(formData);
  
  const handleSave = () => {
    onSave(data);
  };
  
  return (
    <Dialog open={true} onOpenChange={onClose}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Edit Order Detail</DialogTitle>
          <DialogDescription>
            Update the order parameters. Changes will affect future monitoring.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4 py-4">
          <div>
            <Label htmlFor="trigger_price">Trigger Price ($)</Label>
            <Input
              id="trigger_price"
              type="number"
              step="0.01"
              value={data.trigger_price}
              onChange={(e) => setData({ ...data, trigger_price: parseFloat(e.target.value) || 0 })}
              className="mt-1"
            />
          </div>
          <div>
            <Label htmlFor="quantity">Quantity</Label>
            <Input
              id="quantity"
              type="number"
              step="0.01"
              value={data.quantity}
              onChange={(e) => setData({ ...data, quantity: parseFloat(e.target.value) || 0 })}
              className="mt-1"
            />
          </div>
          <div>
            <Label htmlFor="limit_price">Limit Price ($)</Label>
            <Input
              id="limit_price"
              type="number"
              step="0.01"
              value={data.limit_price}
              onChange={(e) => setData({ ...data, limit_price: parseFloat(e.target.value) || 0 })}
              className="mt-1"
            />
          </div>
          <div>
            <Label htmlFor="time_in_force">Time In Force</Label>
            <select
              id="time_in_force"
              value={data.time_in_force}
              onChange={(e) => setData({ ...data, time_in_force: e.target.value })}
              className="mt-1 flex h-10 w-full rounded-lg px-3 py-2 text-sm text-text-primary bg-bg-hover border border-border-divider focus:outline-none focus:ring-2 focus:ring-accent-blue"
            >
              <option value="DAY">DAY</option>
              <option value="GTC">GTC</option>
            </select>
          </div>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button onClick={handleSave}>Save Changes</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// Link Order Detail Modal
function LinkOrderDetailModal({ detail, onClose, onLink }: any) {
  const [alpacaOrderId, setAlpacaOrderId] = useState('');
  const [isLinking, setIsLinking] = useState(false);
  const [availableOrders, setAvailableOrders] = useState<any[]>([]);
  const [isLoadingOrders, setIsLoadingOrders] = useState(false);
  
  // Extract symbol from detail (it should have symbol from the parent order)
  const symbol = detail?.symbol || 'TSLA'; // Fallback to TSLA for testing
  
  useEffect(() => {
    // Fetch filled orders for this symbol
    const fetchOrders = async () => {
      setIsLoadingOrders(true);
      try {
        // Query with higher limit to ensure we get filled orders even if there are many expired/canceled orders
        // Note: We query ALL orders and filter for filled, so limit applies to total orders before filtering
        const response = await ordersApi.getAll('filled', symbol, 500);
        const orders = response.data || [];
        // Filter to only filled orders and sort by filled_at (most recent first)
        const filledOrders = orders
          .filter((o: any) => o.status?.toLowerCase() === 'filled')
          .sort((a: any, b: any) => {
            const dateA = a.filled_at ? new Date(a.filled_at).getTime() : 0;
            const dateB = b.filled_at ? new Date(b.filled_at).getTime() : 0;
            return dateB - dateA;
          });
        setAvailableOrders(filledOrders);
      } catch (error: any) {
        debug.error('Error fetching orders:', error);
        toast.error('Failed to load available orders');
      } finally {
        setIsLoadingOrders(false);
      }
    };
    
    fetchOrders();
  }, [symbol]);
  
  const handleLink = async () => {
    if (!alpacaOrderId.trim()) {
      toast.error('Please select or enter an Alpaca order ID');
      return;
    }
    
    setIsLinking(true);
    try {
      await onLink(alpacaOrderId.trim());
    } finally {
      setIsLinking(false);
    }
  };
  
  return (
    <Dialog open={true} onOpenChange={onClose}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Link to Alpaca Order</DialogTitle>
          <DialogDescription>
            Link this order detail to an executed Alpaca order. Once linked, this order will stop being monitored and the next order will be monitored instead.
            <br />
            <span className="text-status-warning font-medium">Note: Each Alpaca order can only be linked to one order detail.</span>
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4 py-4">
          {/* Available Orders List */}
          {isLoadingOrders ? (
            <div className="flex items-center justify-center p-4">
              <div className="text-sm text-text-secondary">Loading available orders...</div>
            </div>
          ) : availableOrders.length > 0 ? (
            <div>
              <Label className="text-sm font-medium mb-2 block">
                Available {symbol} Orders (Filled)
              </Label>
              <div className="space-y-1.5 max-h-64 overflow-y-auto border border-border-divider rounded-lg p-2">
                {availableOrders.map((order: any) => (
                  <div
                    key={order.id}
                    onClick={() => setAlpacaOrderId(order.id)}
                    className={cn(
                      "p-2 rounded cursor-pointer transition-colors",
                      alpacaOrderId === order.id
                        ? "bg-accent-blue/20 border border-accent-blue"
                        : "hover:bg-bg-hover border border-transparent"
                    )}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-mono text-text-primary">{order.id.substring(0, 8)}...</span>
                          <Badge variant={getStatusBadgeVariant('FILLED')} className="text-xs">FILLED</Badge>
                        </div>
                        <div className="text-xs text-text-secondary mt-1">
                          {order.quantity} shares @ {order.filled_qty ? `${order.filled_qty} filled` : 'N/A'}
                          {order.filled_at && (
                            <span className="ml-2">• {new Date(order.filled_at).toLocaleString()}</span>
                          )}
                        </div>
                      </div>
                      {alpacaOrderId === order.id && (
                        <Check className="h-4 w-4 text-accent-blue flex-shrink-0" />
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="p-4 text-center text-sm text-text-secondary border border-border-divider rounded-lg">
              No filled orders found for {symbol}. Create a test order or manually enter an order ID.
            </div>
          )}
          
          {/* Manual Input */}
          <div>
            <Label htmlFor="alpaca_order_id">Alpaca Order ID</Label>
            <Input
              id="alpaca_order_id"
              type="text"
              value={alpacaOrderId}
              onChange={(e) => setAlpacaOrderId(e.target.value)}
              placeholder="e.g., 7569a2e9-... or select from above"
              className="mt-1 font-mono"
            />
            <p className="text-xs text-text-tertiary mt-1">
              Select an order from above or manually enter the Alpaca order ID
            </p>
          </div>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose} disabled={isLinking}>Cancel</Button>
          <Button onClick={handleLink} disabled={isLinking || !alpacaOrderId.trim()}>
            {isLinking ? 'Linking...' : 'Link Order'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// Unlink Order Detail Confirmation Modal
function UnlinkOrderDetailModal({ detail, onClose, onUnlink }: any) {
  const [isUnlinking, setIsUnlinking] = useState(false);
  
  const handleUnlink = async () => {
    setIsUnlinking(true);
    try {
      await onUnlink();
    } finally {
      setIsUnlinking(false);
    }
  };
  
  if (!detail) return null;
  
  return (
    <Dialog open={true} onOpenChange={onClose}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Unlink Order Detail</DialogTitle>
          <DialogDescription>
            Are you sure you want to unlink order detail #{detail.id} from Alpaca order {detail.alpaca_order_id?.substring(0, 8)}...?
            <br />
            <span className="text-status-warning font-medium mt-2 block">
              This will clear all linked data (status, filled price, timestamps) and the order will return to PENDING status.
            </span>
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose} disabled={isUnlinking}>
            Cancel
          </Button>
          <Button 
            variant="destructive" 
            onClick={handleUnlink} 
            disabled={isUnlinking}
            className="bg-status-error hover:bg-status-error/90"
          >
            {isUnlinking ? 'Unlinking...' : 'Unlink Order'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

