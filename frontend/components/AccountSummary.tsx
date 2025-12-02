'use client';

import { useEffect, useState, useCallback, useRef } from 'react';
import { accountApi } from '@/services/api';
import { useConnectivity } from '@/hooks/useConnectivity';
import { GlassCard } from '@/components/glass';
import { Button } from '@/components/ui/button';
import { RefreshCcw, Circle, Clock, LogOut } from 'lucide-react';
import { toast } from 'sonner';
import { debug } from '@/lib/debug';
import { cn } from '@/lib/utils';
import type { PortfolioPLSummary } from '@/lib/types';

interface AccountData {
  cash: number;
  stockValue: number;
  cryptoValue: number;
  total: number;
  unsettledFunds?: number;
  pendingTransferIn?: number;
  pendingTransferOut?: number;
  longMarketValue?: number;
  shortMarketValue?: number;
  nonTradableAssets?: number;
}

interface AccountSummaryProps {
  marketIsOpen?: boolean;
  onRefreshAccount?: () => void;
  onLogout?: () => void;
}

export function AccountSummary({ marketIsOpen = false, onRefreshAccount, onLogout }: AccountSummaryProps) {
  const [account, setAccount] = useState<AccountData | null>(null);
  const [isAccountLoading, setIsAccountLoading] = useState(false);
  const [portfolioPL, setPortfolioPL] = useState<Record<string, PortfolioPLSummary | null>>({
    today: null,
    weekly: null,
    monthly: null,
    yearly: null,
    all_time: null,
  });
  const [isLoadingPL, setIsLoadingPL] = useState(false);
  const { isBackendReachable } = useConnectivity();
  const hasInitialLoadRef = useRef(false);

  const fetchAccountData = useCallback(async (isAutoRefresh = false) => {
    // Skip if backend is known to be unreachable
    if (!isBackendReachable) {
      debug.log('[AccountSummary] Backend unreachable, skipping account fetch');
      return;
    }

    try {
      if (!isAutoRefresh) {
        setIsAccountLoading(true);
      }
      
      const [accountRes, positionsRes] = await Promise.all([
        accountApi.getAccount(),
        accountApi.getPositions(),
      ]);

      const accountData = accountRes.data;
      const positions = positionsRes.data || [];
      
      // Mark as successfully loaded
      hasInitialLoadRef.current = true;

      // Use long_market_value directly from API (authoritative source)
      const longMarketValue = accountData.long_market_value ?? 0;
      const shortMarketValue = accountData.short_market_value ?? 0;

      // Calculate stock/ETF and crypto values from positions for display purposes only
      // Note: These are approximations for UI display, not used in calculations
      const stockValue = positions
        .filter((p: any) => !p.symbol.includes('/') && p.market_value)
        .reduce((sum: number, p: any) => sum + Math.abs(p.market_value || 0), 0);

      const cryptoValue = positions
        .filter((p: any) => p.symbol.includes('/') && p.market_value)
        .reduce((sum: number, p: any) => sum + Math.abs(p.market_value || 0), 0);

      // Use equity as primary total (more standard than portfolio_value)
      // Fallback to portfolio_value if equity is missing, then calculate if both missing
      const total = accountData.equity ?? accountData.portfolio_value ?? (
        accountData.cash 
        + longMarketValue 
        - shortMarketValue 
        + (accountData.non_tradable_assets || 0)
        + (accountData.unsettled_funds || 0)
      );

      // Validation: Log warnings if values don't match expectations
      if (accountData.equity && accountData.portfolio_value) {
        const diff = Math.abs(accountData.equity - accountData.portfolio_value);
        if (diff > 0.01) {
          debug.warn(
            `[Account] Equity (${accountData.equity}) and portfolio_value (${accountData.portfolio_value}) differ by $${diff.toFixed(2)}`
          );
        }
      }

      // Validation: Compare long_market_value with sum of positions
      if (longMarketValue > 0 && positions.length > 0) {
        const calculatedLongValue = positions
          .filter((p: any) => p.market_value)
          .reduce((sum: number, p: any) => sum + Math.abs(p.market_value || 0), 0);
        const diff = Math.abs(longMarketValue - calculatedLongValue);
        if (diff > 1.0) { // Allow $1 difference for rounding/timing
          debug.warn(
            `[Account] long_market_value (${longMarketValue}) doesn't match sum of positions (${calculatedLongValue}), diff: $${diff.toFixed(2)}`
          );
        }
      }

      setAccount({
        cash: accountData.cash || 0,
        stockValue, // For display only
        cryptoValue, // For display only
        total, // Use equity/portfolio_value from API
        unsettledFunds: accountData.unsettled_funds ?? undefined,
        pendingTransferIn: accountData.pending_transfer_in ?? undefined,
        pendingTransferOut: accountData.pending_transfer_out ?? undefined,
        longMarketValue: longMarketValue > 0 ? longMarketValue : undefined,
        shortMarketValue: shortMarketValue > 0 ? shortMarketValue : undefined,
        nonTradableAssets: accountData.non_tradable_assets ?? undefined,
      });

      // Notify parent if callback provided
      if (onRefreshAccount) {
        onRefreshAccount();
      }
    } catch (error: any) {
      debug.error('Error fetching account data:', error);
      
      // Only show toast if:
      // 1. We haven't loaded data yet (user needs to know why)
      // 2. It's NOT a connectivity/timeout error (which are handled by auto-retry)
      // 3. It wasn't an auto-refresh (silence background errors)
      const isNetworkError = error.message === 'Network Error' || error.code === 'ECONNABORTED' || (error as any).isCircuitBreakerOpen;
      
      if (!hasInitialLoadRef.current || (!isAutoRefresh && !isNetworkError)) {
        toast.error('Failed to refresh account data', {
          description: error.response?.data?.detail || error.message || 'Please try again',
        });
      } else {
        debug.log('[AccountSummary] Suppressed account fetch error toast');
      }
    } finally {
      setIsAccountLoading(false);
    }
  }, [onRefreshAccount, isBackendReachable]);

  const fetchPortfolioPL = useCallback(async () => {
    // Skip if backend is unreachable
    if (!isBackendReachable) return;

    try {
      setIsLoadingPL(true);
      const periods = ['today', 'weekly', 'monthly', 'yearly', 'all_time'];
      const results = await Promise.allSettled(
        periods.map(period => accountApi.getPortfolioPL(period))
      );
      
      const plData: Record<string, PortfolioPLSummary | null> = {};
      let successCount = 0;
      let errorCount = 0;
      
      periods.forEach((period, index) => {
        const result = results[index];
        if (result.status === 'fulfilled') {
          plData[period] = result.value.data;
          successCount++;
        } else {
          debug.error(`[AccountSummary] Error fetching ${period} P/L:`, result.reason);
          plData[period] = null;
          errorCount++;
        }
      });
      
      setPortfolioPL(plData);
      
      // Only log summary to reduce console noise
      if (errorCount > 0) {
        debug.log(`[AccountSummary] Portfolio P/L fetch complete: ${successCount} succeeded, ${errorCount} failed`);
      }
    } catch (error: any) {
      debug.error('[AccountSummary] Error fetching portfolio P/L:', error);
      // Don't show toast - this is background data
    } finally {
      setIsLoadingPL(false);
    }
  }, []);

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(value);
  };

  useEffect(() => {
    // Only fetch if backend is reachable
    if (isBackendReachable) {
      fetchAccountData();
      
      // Fetch P/L data after a short delay to avoid overwhelming the API
      const plTimeout = setTimeout(() => {
        fetchPortfolioPL();
      }, 1000);
      
      return () => clearTimeout(plTimeout);
    }
  }, [isBackendReachable, fetchAccountData, fetchPortfolioPL]); // Re-run when backend becomes reachable

  useEffect(() => {
    // Auto-refresh account every 30 seconds
    const accountInterval = setInterval(() => {
      if (isBackendReachable) {
        fetchAccountData(true); // Pass true for isAutoRefresh
      }
    }, 30000);
    
    // Auto-refresh P/L every 60 seconds (less frequent)
    const plInterval = setInterval(() => {
      if (isBackendReachable) {
        debug.log('[AccountSummary] Auto-refreshing portfolio P/L data...');
        fetchPortfolioPL();
      }
    }, 60000);
    
    return () => {
      clearInterval(accountInterval);
      clearInterval(plInterval);
    };
  }, [isBackendReachable, fetchAccountData, fetchPortfolioPL]);

  if (!account) {
    return (
      <GlassCard className="p-1.5 sm:p-2.5">
        <div className="flex items-center justify-center py-4">
          <RefreshCcw className="h-4 w-4 animate-spin text-text-secondary" />
        </div>
      </GlassCard>
    );
  }

  return (
    <GlassCard className="p-1.5 sm:p-2.5">
      {/* Two-row layout for mobile, single row for larger screens */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 sm:gap-3 md:gap-4">
        {/* Row 1: Account Summary */}
        <div className="flex items-center gap-2 sm:gap-3 md:gap-4 flex-1 min-w-0 overflow-x-auto">
          {/* Total Portfolio Value */}
          <div className="flex items-baseline gap-1 sm:gap-1.5 md:gap-2 whitespace-nowrap flex-shrink-0">
            <div className="text-[10px] sm:text-xs text-text-tertiary font-medium">Total</div>
            <div className="text-sm sm:text-base md:text-lg font-bold text-text-primary font-numbers">
              {formatCurrency(account.total)}
            </div>
          </div>

          {/* Divider */}
          <div className="h-4 sm:h-5 w-px bg-border-divider flex-shrink-0" />

          {/* Cash */}
          <div className="flex items-baseline gap-1 sm:gap-1.5 whitespace-nowrap flex-shrink-0">
            <div className="text-[9px] sm:text-[10px] text-text-tertiary uppercase tracking-wide">Cash</div>
            <div className="text-xs sm:text-sm font-semibold text-accent-cash font-numbers">
              {formatCurrency(account.cash)}
            </div>
          </div>

          {/* Stock/ETF */}
          <div className="flex items-baseline gap-1 sm:gap-1.5 whitespace-nowrap flex-shrink-0">
            <div className="text-[9px] sm:text-[10px] text-text-tertiary uppercase tracking-wide">Stocks</div>
            <div className="text-xs sm:text-sm font-semibold text-accent-stock font-numbers">
              {formatCurrency(account.stockValue)}
            </div>
          </div>

          {/* Crypto - only show if > 0 */}
          {account.cryptoValue > 0 && (
            <>
              <div className="h-4 sm:h-5 w-px bg-border-divider flex-shrink-0" />
              <div className="flex items-baseline gap-1 sm:gap-1.5 whitespace-nowrap flex-shrink-0">
                <div className="text-[9px] sm:text-[10px] text-text-tertiary uppercase tracking-wide">Crypto</div>
                <div className="text-xs sm:text-sm font-semibold text-accent-crypto font-numbers">
                  {formatCurrency(account.cryptoValue)}
                </div>
              </div>
            </>
          )}

          {/* Additional fields - Hidden on mobile, shown on tablet+ */}
          {/* Unsettled Funds */}
          {account.unsettledFunds && account.unsettledFunds !== 0 && (
            <>
              <div className="h-5 w-px bg-border-divider hidden md:block flex-shrink-0" />
              <div className="hidden md:flex items-baseline gap-1.5 flex-shrink-0">
                <div className="text-[10px] text-text-tertiary uppercase tracking-wide">Unsettled</div>
                <div className="text-sm font-semibold text-text-secondary font-numbers">
                  {formatCurrency(account.unsettledFunds)}
                </div>
              </div>
            </>
          )}

          {/* Pending Transfers */}
          {(account.pendingTransferIn && account.pendingTransferIn > 0) || 
           (account.pendingTransferOut && account.pendingTransferOut > 0) ? (
            <>
              <div className="h-5 w-px bg-border-divider hidden md:block flex-shrink-0" />
              <div className="hidden md:flex items-baseline gap-1.5 flex-shrink-0">
                <div className="text-[10px] text-text-tertiary uppercase tracking-wide">Pending</div>
                <div className="text-sm font-semibold text-text-secondary font-numbers">
                  {formatCurrency((account.pendingTransferIn || 0) - (account.pendingTransferOut || 0))}
                </div>
              </div>
            </>
          ) : null}

          {/* Short Positions */}
          {account.shortMarketValue && account.shortMarketValue > 0 && (
            <>
              <div className="h-5 w-px bg-border-divider hidden md:block flex-shrink-0" />
              <div className="hidden md:flex items-baseline gap-1.5 flex-shrink-0">
                <div className="text-[10px] text-text-tertiary uppercase tracking-wide">Short</div>
                <div className="text-sm font-semibold text-red-400 font-numbers">
                  {formatCurrency(account.shortMarketValue)}
                </div>
              </div>
            </>
          )}

          {/* Non-Tradable Assets / Other */}
          {account.nonTradableAssets && account.nonTradableAssets > 0 && (
            <>
              <div className="h-5 w-px bg-border-divider hidden md:block flex-shrink-0" />
              <div className="hidden md:flex items-baseline gap-1.5 flex-shrink-0">
                <div className="text-[10px] text-text-tertiary uppercase tracking-wide">Other</div>
                <div className="text-sm font-semibold text-text-secondary font-numbers">
                  {formatCurrency(account.nonTradableAssets)}
                </div>
              </div>
            </>
          )}
        </div>

        {/* Row 2: Market Status and Refresh Button */}
        <div className="flex items-center justify-between sm:justify-end gap-2 sm:gap-2 md:gap-3 flex-shrink-0">
          {/* Market Status */}
          <div className="flex items-center gap-1.5">
            {marketIsOpen ? (
              <Circle className="h-2 w-2 fill-status-success text-status-success animate-pulse" />
            ) : (
              <Clock className="h-3 w-3 text-text-tertiary" />
            )}
            <span className="text-[10px] sm:text-xs font-medium text-text-primary uppercase tracking-wide">
              {marketIsOpen ? 'Market Open' : 'Market Closed'}
            </span>
          </div>

          <div className="h-4 w-px bg-border-divider" />

          {/* Refresh Account */}
          <Button
            variant="ghost"
            size="sm"
            onClick={() => fetchAccountData(false)}
            disabled={isAccountLoading || !isBackendReachable}
            className="h-7 px-2 gap-1.5 text-text-secondary hover:text-text-primary hover:bg-bg-hover"
            title="Refresh Account"
          >
            <RefreshCcw className={`h-4 w-4 ${isAccountLoading ? 'animate-spin' : ''}`} />
            <span className="text-xs font-medium">Account</span>
          </Button>

          {/* Logout */}
          {onLogout && (
            <>
              <div className="h-4 w-px bg-border-divider" />
              <Button 
                variant="ghost" 
                size="icon" 
                onClick={onLogout} 
                className="h-7 w-7 text-status-error hover:text-status-error hover:bg-status-error/10"
                title="Logout"
              >
                <LogOut className="h-3.5 w-3.5" />
              </Button>
            </>
          )}
        </div>
      </div>

      {/* Portfolio P/L Section */}
      <div className="border-t border-border-divider/50 px-1.5 py-2 mt-1 min-h-[2.5rem]">
        <div className="flex items-center gap-2 sm:gap-3 md:gap-4 lg:gap-6 w-full md:justify-end flex-wrap">
          {/* Today */}
          {portfolioPL.today && (
            <>
              <div className="text-left md:text-right">
                <div className="text-[9px] sm:text-[10px] text-text-tertiary uppercase tracking-wide mb-0.5">Today</div>
                <div className="flex items-baseline gap-1">
                  <div className={cn(
                    "text-xs sm:text-sm font-semibold font-numbers",
                    portfolioPL.today.profit_loss_dollars >= 0
                      ? "text-status-success"
                      : "text-status-error"
                  )}>
                    {portfolioPL.today.profit_loss_dollars >= 0 ? '+' : ''}
                    {formatCurrency(portfolioPL.today.profit_loss_dollars)}
                  </div>
                  <div className={cn(
                    "text-[10px] sm:text-xs font-semibold font-numbers",
                    portfolioPL.today.profit_loss_percent >= 0
                      ? "text-status-success"
                      : "text-status-error"
                  )}>
                    ({portfolioPL.today.profit_loss_percent >= 0 ? '+' : ''}
                    {portfolioPL.today.profit_loss_percent.toFixed(2)}%)
                  </div>
                </div>
              </div>
              <div className="h-4 w-px bg-border-divider/50 hidden md:block" />
            </>
          )}

          {/* Weekly */}
          {portfolioPL.weekly && (
            <>
              <div className="text-left md:text-right">
                <div className="text-[9px] sm:text-[10px] text-text-tertiary uppercase tracking-wide mb-0.5">Weekly</div>
                <div className="flex items-baseline gap-1">
                  <div className={cn(
                    "text-xs sm:text-sm font-semibold font-numbers",
                    portfolioPL.weekly.profit_loss_dollars >= 0
                      ? "text-status-success"
                      : "text-status-error"
                  )}>
                    {portfolioPL.weekly.profit_loss_dollars >= 0 ? '+' : ''}
                    {formatCurrency(portfolioPL.weekly.profit_loss_dollars)}
                  </div>
                  <div className={cn(
                    "text-[10px] sm:text-xs font-semibold font-numbers",
                    portfolioPL.weekly.profit_loss_percent >= 0
                      ? "text-status-success"
                      : "text-status-error"
                  )}>
                    ({portfolioPL.weekly.profit_loss_percent >= 0 ? '+' : ''}
                    {portfolioPL.weekly.profit_loss_percent.toFixed(2)}%)
                  </div>
                </div>
              </div>
              <div className="h-4 w-px bg-border-divider/50 hidden md:block" />
            </>
          )}

          {/* Monthly */}
          {portfolioPL.monthly && (
            <>
              <div className="text-left md:text-right">
                <div className="text-[9px] sm:text-[10px] text-text-tertiary uppercase tracking-wide mb-0.5">Monthly</div>
                <div className="flex items-baseline gap-1">
                  <div className={cn(
                    "text-xs sm:text-sm font-semibold font-numbers",
                    portfolioPL.monthly.profit_loss_dollars >= 0
                      ? "text-status-success"
                      : "text-status-error"
                  )}>
                    {portfolioPL.monthly.profit_loss_dollars >= 0 ? '+' : ''}
                    {formatCurrency(portfolioPL.monthly.profit_loss_dollars)}
                  </div>
                  <div className={cn(
                    "text-[10px] sm:text-xs font-semibold font-numbers",
                    portfolioPL.monthly.profit_loss_percent >= 0
                      ? "text-status-success"
                      : "text-status-error"
                  )}>
                    ({portfolioPL.monthly.profit_loss_percent >= 0 ? '+' : ''}
                    {portfolioPL.monthly.profit_loss_percent.toFixed(2)}%)
                  </div>
                </div>
              </div>
              <div className="h-4 w-px bg-border-divider/50 hidden md:block" />
            </>
          )}

          {/* Yearly */}
          {portfolioPL.yearly && (
            <>
              <div className="text-left md:text-right">
                <div className="text-[9px] sm:text-[10px] text-text-tertiary uppercase tracking-wide mb-0.5">Yearly</div>
                <div className="flex items-baseline gap-1">
                  <div className={cn(
                    "text-xs sm:text-sm font-semibold font-numbers",
                    portfolioPL.yearly.profit_loss_dollars >= 0
                      ? "text-status-success"
                      : "text-status-error"
                  )}>
                    {portfolioPL.yearly.profit_loss_dollars >= 0 ? '+' : ''}
                    {formatCurrency(portfolioPL.yearly.profit_loss_dollars)}
                  </div>
                  <div className={cn(
                    "text-[10px] sm:text-xs font-semibold font-numbers",
                    portfolioPL.yearly.profit_loss_percent >= 0
                      ? "text-status-success"
                      : "text-status-error"
                  )}>
                    ({portfolioPL.yearly.profit_loss_percent >= 0 ? '+' : ''}
                    {portfolioPL.yearly.profit_loss_percent.toFixed(2)}%)
                  </div>
                </div>
              </div>
              <div className="h-4 w-px bg-border-divider/50 hidden md:block" />
            </>
          )}

          {/* All-Time */}
          {portfolioPL.all_time && (
            <div className="text-left md:text-right">
              <div className="text-[9px] sm:text-[10px] text-text-tertiary uppercase tracking-wide mb-0.5">All-Time</div>
              <div className="flex items-baseline gap-1">
                <div className={cn(
                  "text-xs sm:text-sm font-semibold font-numbers",
                  portfolioPL.all_time.profit_loss_dollars >= 0
                    ? "text-status-success"
                    : "text-status-error"
                )}>
                  {portfolioPL.all_time.profit_loss_dollars >= 0 ? '+' : ''}
                  {formatCurrency(portfolioPL.all_time.profit_loss_dollars)}
                </div>
                <div className={cn(
                  "text-[10px] sm:text-xs font-semibold font-numbers",
                  portfolioPL.all_time.profit_loss_percent >= 0
                    ? "text-status-success"
                    : "text-status-error"
                )}>
                  ({portfolioPL.all_time.profit_loss_percent >= 0 ? '+' : ''}
                  {portfolioPL.all_time.profit_loss_percent.toFixed(2)}%)
                </div>
              </div>
            </div>
          )}

          {/* Loading state */}
          {isLoadingPL && Object.values(portfolioPL).every(v => v === null) && (
            <div className="text-center text-xs text-text-tertiary py-1 w-full">
              Loading P/L data...
            </div>
          )}
          
          {/* Show message if no data after loading completes */}
          {!isLoadingPL && Object.values(portfolioPL).every(v => v === null) && (
            <div className="text-center text-xs text-text-tertiary py-1 w-full">
              No P/L data available
            </div>
          )}
        </div>
      </div>
    </GlassCard>
  );
}

