'use client';

import { useState, useEffect, useRef } from 'react';
import { gttOrdersApi } from '@/services/api';
import { assetApi } from '@/services/api';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { GlassCard, GlassInput } from '@/components/glass';
import { Search, Loader2, CheckCircle2, AlertTriangle, TriangleAlert, Coins, TrendingUp } from 'lucide-react';
import { toast } from 'sonner';
import { formatCurrency } from '@/lib/formatters';
import { Progress } from '@/components/ui/progress';
import { GTTOrderPreviewTable } from '@/components/GTTOrderPreviewTable';
import { useDebounce } from '@/hooks/useDebounce';
import { useRealtimeUpdates } from '@/hooks/useRealtimeUpdates';
import { debug } from '@/lib/debug';
import { cn } from '@/lib/utils';

interface AddGTTOrderModalProps {
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export function AddGTTOrderModal({ open, onClose, onSuccess }: AddGTTOrderModalProps) {
  const [symbol, setSymbol] = useState('');
  const [initialQuantity, setInitialQuantity] = useState('1');
  
  // Debounce symbol to avoid API spam while typing
  const debouncedSymbol = useDebounce(symbol, 500);
  
  const [initialPrice, setInitialPrice] = useState('');
  const [incrementQtyMultiplier, setIncrementQtyMultiplier] = useState('1.2');
  const [decrementPriceMultiplier, setDecrementPriceMultiplier] = useState('0.9');
  const [iterations, setIterations] = useState('5');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [progress, setProgress] = useState(0);
  const [currentStep, setCurrentStep] = useState('');
  const [symbolSearchResults, setSymbolSearchResults] = useState<any[]>([]);
  const [showSymbolSearch, setShowSymbolSearch] = useState(false);
  const [isFractionable, setIsFractionable] = useState<boolean | null>(null);
  const [currentPrice, setCurrentPrice] = useState<number | null>(null);
  const [assetName, setAssetName] = useState<string>('');
  const [isLoadingAsset, setIsLoadingAsset] = useState(false);
  const [duplicateInfo, setDuplicateInfo] = useState<any>(null);
  const [confirmDuplicates, setConfirmDuplicates] = useState(false);
  const [existingTriggerPrices, setExistingTriggerPrices] = useState<Set<number>>(new Set());
  
  // Ref to cancel progress simulation
  const abortSimulationRef = useRef(false);
  const orderCreatedRef = useRef(false); // Track if order creation completed, waiting for SSE event
  const fallbackTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  
  // Listen for SSE events to close modal when order is actually created
  useRealtimeUpdates({
    onOrderCreated: () => {
      debug.log('[Add Order Modal] Order created event received - closing modal');
      // Only close if we're waiting for the event (order creation completed)
      if (orderCreatedRef.current) {
        orderCreatedRef.current = false;
        // Clear fallback timeout
        if (fallbackTimeoutRef.current) {
          clearTimeout(fallbackTimeoutRef.current);
          fallbackTimeoutRef.current = null;
        }
        // Close immediately - orders will refresh via SSE
        onSuccess();
        onClose();
      }
    },
  });
  
  // Cleanup: Reset state when modal closes
  useEffect(() => {
    if (!open) {
      // Reset order creation flag
      orderCreatedRef.current = false;
      // Clear any pending timeout
      if (fallbackTimeoutRef.current) {
        clearTimeout(fallbackTimeoutRef.current);
        fallbackTimeoutRef.current = null;
      }
      // Reset form
      setSymbol('');
      setInitialQuantity('1');
      setInitialPrice('');
      setIncrementQtyMultiplier('1.2');
      setDecrementPriceMultiplier('0.9');
      setIterations('5');
      setProgress(0);
      setCurrentStep('');
      setDuplicateInfo(null);
      setConfirmDuplicates(false);
      setSymbolSearchResults([]);
      setShowSymbolSearch(false);
    }
  }, [open]);

  // Check if asset supports fractional trading and fetch current price when symbol changes
  useEffect(() => {
    const checkAssetInfo = async () => {
      const symbolTrimmed = debouncedSymbol.trim();
      
      if (!symbolTrimmed) {
        setIsFractionable(null);
        setCurrentPrice(null);
        setAssetName('');
        return;
      }

      const symbolUpper = symbolTrimmed.toUpperCase();
      
      // Skip API call if crypto symbol is incomplete (e.g., "XRP/" or "XRP/U" or "XRP/US")
      // Only call API when we have a complete crypto symbol (e.g., "XRP/USD") or a stock symbol
      if (symbolUpper.includes('/')) {
        // For crypto symbols, check if it's complete (has both base and quote)
        const parts = symbolUpper.split('/');
        if (parts.length !== 2 || parts[0].length === 0 || parts[1].length === 0) {
          // Incomplete crypto symbol - don't call API yet
          setIsFractionable(null);
          setCurrentPrice(null);
          setAssetName('');
          setIsLoadingAsset(false);
          return;
        }
        // Also check if quote currency is incomplete (e.g., "XRP/U" or "XRP/US" instead of "XRP/USD")
        const validQuotes = ['USD', 'USDT', 'USDC', 'BTC', 'ETH'];
        if (parts.length === 2 && !validQuotes.some(quote => parts[1] === quote || parts[1].startsWith(quote))) {
          // Quote currency looks incomplete - don't call API yet
          setIsFractionable(null);
          setCurrentPrice(null);
          setAssetName('');
          setIsLoadingAsset(false);
          return;
        }
      }

      setIsLoadingAsset(true);
      try {
        const response = await assetApi.getAssetInfo(symbolUpper);
        const assetData = response.data;
        
        const fractionable = assetData?.fractionable ?? false;
        setIsFractionable(fractionable);
        setAssetName(assetData?.name || symbolUpper);
        
        // Set current price if available
        if (assetData?.current_price) {
          setCurrentPrice(assetData.current_price);
          // Auto-populate price field if empty
          if (!initialPrice) {
            setInitialPrice(assetData.current_price.toFixed(2));
          }
        } else {
          setCurrentPrice(null);
        }
      } catch (error) {
        // Asset might not exist yet, don't show error
        setIsFractionable(null);
        setCurrentPrice(null);
        setAssetName('');
      } finally {
        setIsLoadingAsset(false);
      }
    };

    checkAssetInfo();
  }, [debouncedSymbol, initialPrice]);

  // Helper to normalize crypto symbols (BTCUSD -> BTC/USD) for consistent comparison
  const normalizeCryptoSymbol = (symbol: string): string => {
    const upper = symbol.toUpperCase().trim();
    // Already normalized (has /)
    if (upper.includes('/')) return upper;
    // Try to normalize crypto pairs (BTCUSD -> BTC/USD)
    const cryptoQuotes = ['USD', 'USDT', 'USDC'];
    for (const quote of cryptoQuotes) {
      if (upper.endsWith(quote) && upper.length > quote.length) {
        const base = upper.slice(0, -quote.length);
        // Common crypto bases
        const commonBases = ['BTC', 'ETH', 'SOL', 'DOGE', 'MATIC', 'AVAX', 'LINK', 'ALGO', 'SHIB', 'ADA', 'DOT', 'LTC', 'XRP', 'BCH', 'ETC'];
        if (commonBases.includes(base)) {
          return `${base}/${quote}`;
        }
      }
    }
    return upper;
  };

  // Fetch existing trigger prices for the symbol to detect duplicates at row level
  useEffect(() => {
    const fetchExistingPrices = async () => {
      if (!debouncedSymbol.trim()) {
        setExistingTriggerPrices(new Set());
        return;
      }

      try {
        const response = await gttOrdersApi.getAll();
        const allOrders = response.data || [];
        
        // Normalize the search symbol for consistent comparison
        const normalizedSearchSymbol = normalizeCryptoSymbol(debouncedSymbol);
        
        // Get all trigger prices for this symbol from all order details
        const prices = new Set<number>();
        allOrders
          .filter((order: any) => {
            // Normalize both symbols for comparison (handles BTCUSD vs BTC/USD)
            const normalizedOrderSymbol = normalizeCryptoSymbol(order.symbol || '');
            return normalizedOrderSymbol === normalizedSearchSymbol;
          })
          .forEach((order: any) => {
            if (order.order_details && Array.isArray(order.order_details)) {
              order.order_details.forEach((detail: any) => {
                if (detail.trigger_price) {
                  prices.add(Number(detail.trigger_price));
                }
              });
            }
          });
        
        setExistingTriggerPrices(prices);
      } catch (error) {
        // Silently fail - this is just for UI hints
        setExistingTriggerPrices(new Set());
      }
    };

    fetchExistingPrices();
  }, [debouncedSymbol]);

  const steps = [
    { label: 'Validating order', progress: 20 },
    { label: 'Creating GTT order', progress: 40 },
    { label: 'Generating order ladder', progress: 60 },
    { label: 'Submitting to Alpaca', progress: 80 },
    { label: 'Finalizing', progress: 100 },
  ];

  const calculateValue = () => {
    const qty = parseFloat(initialQuantity) || 0;
    const price = parseFloat(initialPrice) || 0;
    return qty * price;
  };

  // Calculate the order ladder for preview
  const calculateLadder = () => {
    const qty = parseFloat(initialQuantity);
    const price = parseFloat(initialPrice);
    const qtyMult = parseFloat(incrementQtyMultiplier);
    const priceMult = parseFloat(decrementPriceMultiplier);
    const iter = parseInt(iterations);

    if (!qty || !price || !qtyMult || !priceMult || !iter) {
      return [];
    }

    const ladder = [];
    let currentQty = qty;
    let currentPrice = price;

    for (let i = 0; i < iter; i++) {
      const needsRounding = isFractionable === false && currentQty !== Math.floor(currentQty);
      const finalQty = needsRounding ? Math.round(currentQty) : currentQty;
      
      // DAY for fractional, GTC for whole shares
      // Check the ACTUAL quantity (not the rounded one) to determine TIF
      const isActuallyFractional = Math.abs(currentQty - Math.floor(currentQty)) > 0.000001;
      const timeInForce = isActuallyFractional ? 'DAY' : 'GTC';
      
      ladder.push({
        level: i + 1,
        quantity: currentQty,
        price: currentPrice,
        value: currentQty * currentPrice,
        needsRounding,
        roundedQuantity: Math.round(currentQty),
        timeInForce
      });
      currentQty = currentQty * qtyMult;
      currentPrice = currentPrice * priceMult;
    }

    return ladder;
  };

  const ladder = calculateLadder();

  const validateForm = () => {
    const errors: string[] = [];
    if (!symbol.trim()) errors.push('Symbol is required');
    const qty = parseFloat(initialQuantity);
    const isCrypto = isCryptoSymbol(symbol);
    const minQty = isCrypto ? 0.0001 : (isFractionable === false ? 1 : 0.01);
    if (!initialQuantity || qty <= 0 || qty < minQty) {
      errors.push(`Initial quantity must be >= ${minQty}${isCrypto ? ' (crypto)' : ''}`);
    }
    if (!initialPrice || parseFloat(initialPrice) <= 0) errors.push('Initial price must be > 0');
    if (!incrementQtyMultiplier || parseFloat(incrementQtyMultiplier) <= 0) errors.push('Increment multiplier must be > 0');
    if (!decrementPriceMultiplier || parseFloat(decrementPriceMultiplier) <= 0 || parseFloat(decrementPriceMultiplier) >= 1) {
      errors.push('Decrement multiplier must be between 0 and 1');
    }
    if (!iterations || parseInt(iterations) <= 0 || parseInt(iterations) > 20) {
      errors.push('Iterations must be between 1 and 20');
    }
    
    return errors;
  };

  const simulateProgress = async () => {
    abortSimulationRef.current = false;
    for (let i = 0; i < steps.length; i++) {
      if (abortSimulationRef.current) return;
      
      setCurrentStep(steps[i].label);
      setProgress(steps[i].progress);
      // Simulate realistic delays for each step
      const delay = i === 0 ? 300 : i === steps.length - 1 ? 500 : 400;
      await new Promise(resolve => setTimeout(resolve, delay));
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const errors = validateForm();
    if (errors.length > 0) {
      toast.error(errors[0]);
      return;
    }
    
    // Client-side duplicate check to prevent 400 errors
    const currentLadder = calculateLadder();
    const hasDuplicates = currentLadder.some(level => existingTriggerPrices.has(Number(level.price.toFixed(2))));
    
    // If duplicates exist and we haven't confirmed them (duplicateInfo is null)
    if (hasDuplicates && !duplicateInfo) {
       setDuplicateInfo({ 
         message: "Duplicate orders detected",
         duplicate: true // Signal to UI that duplicates exist
       });
       toast.warning("Duplicate orders detected. Please confirm to proceed.");
       return; 
    }
    
    setIsSubmitting(true);
    setProgress(0);
    setCurrentStep('');
    abortSimulationRef.current = false;

    // Start progress simulation (without awaiting it immediately)
    const progressPromise = simulateProgress();

    try {
      // If duplicateInfo exists, user is clicking "Create Duplicate" button
      // So we automatically confirm duplicates
      const shouldConfirmDuplicates = !!duplicateInfo;
      
      // Run API call
      await gttOrdersApi.create({
        symbol: symbol.toUpperCase().trim(),
        initial_trigger_price: parseFloat(initialPrice),
        initial_quantity: parseFloat(initialQuantity),
        increment_qty_multiplier: parseFloat(incrementQtyMultiplier),
        decrement_price_multiplier: parseFloat(decrementPriceMultiplier),
        iterations: parseInt(iterations),
        // time_in_force auto-calculated by backend
        confirm_rounding: true,
        confirm_duplicates: shouldConfirmDuplicates,
      });

      // Wait for simulation to finish only if successful
      await progressPromise;

      if (abortSimulationRef.current) return;

      setProgress(100);
      setCurrentStep('Order created successfully');
      await new Promise(resolve => setTimeout(resolve, 500));
      
      toast.success('GTT order created successfully');
      
      // Mark order creation as completed - wait for SSE event to close modal
      orderCreatedRef.current = true;
      debug.log('[Add Order Modal] Order creation completed, waiting for SSE event to close modal');
      
      // Fallback: If SSE event doesn't arrive within 2 seconds, close anyway
      fallbackTimeoutRef.current = setTimeout(() => {
        if (orderCreatedRef.current) {
          debug.warn('[Add Order Modal] SSE event timeout - closing modal anyway');
          orderCreatedRef.current = false;
          fallbackTimeoutRef.current = null;
          onSuccess();
          onClose();
        }
      }, 2000);
      
      // Note: Modal will close when SSE event arrives or after 5 second timeout
      // Form reset happens in useEffect cleanup when modal closes
    } catch (error: any) {
      // Stop progress immediately
      abortSimulationRef.current = true;
      setProgress(0);
      setCurrentStep('');
      
      const errorData = error.response?.data?.detail;
      
      // Check if it's a duplicate warning (fallback if client-side check missed it)
      if (typeof errorData === 'object' && errorData.duplicate) {
        setDuplicateInfo(errorData.duplicate);
        // Don't show error toast, just show the warning in the preview
      } else {
        const message = typeof errorData === 'string' ? errorData : errorData?.detail || 'Failed to create order';
        toast.error(message);
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSymbolSearch = async (query: string) => {
    setSymbol(query);
    if (query.length >= 1) {
      setShowSymbolSearch(true);
      try {
        const response = await assetApi.search(query);
        // Backend returns list of asset objects with full data
        setSymbolSearchResults(response.data);
      } catch (error) {
        // Silent fail for search
        setSymbolSearchResults([]);
      }
    } else {
      setShowSymbolSearch(false);
      setSymbolSearchResults([]);
    }
  };


  const selectSymbol = (selectedSymbol: string) => {
    setSymbol(selectedSymbol);
    setShowSymbolSearch(false);
  };

  const isCryptoSymbol = (symbol: string) => symbol.includes('/');

  const errors = validateForm();
  const missingFields = errors.length;

  return (
    <>
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
        <DialogHeader className="pb-3 border-b border-border-divider">
          <DialogTitle className="text-lg font-semibold">Add Manual GTT Order</DialogTitle>
          <DialogDescription className="text-sm text-text-secondary">
            Create a new Good-Till-Triggered (GTT) order ladder.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Row 1: Symbol (full-width) */}
          <div className="space-y-2">
            <Label htmlFor="symbol" className="text-sm font-medium text-text-primary">Symbol *</Label>
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-text-tertiary" />
              <Input
                id="symbol"
                value={symbol}
                onChange={(e) => handleSymbolSearch(e.target.value)}
                onFocus={() => symbol.length >= 1 && setShowSymbolSearch(true)}
                onBlur={() => setTimeout(() => setShowSymbolSearch(false), 200)}
                placeholder="Search symbol (e.g., AAPL, TSLA, BTC/USD)"
                className="pl-10"
                required
                autoComplete="off"
              />
              {isLoadingAsset && (
                <Loader2 className="absolute right-3 top-1/2 transform -translate-y-1/2 h-4 w-4 animate-spin text-text-tertiary" />
              )}
              
              {/* Search Results Dropdown */}
              {showSymbolSearch && symbolSearchResults.length > 0 && (
                <div className="absolute z-50 w-full mt-1 bg-bg-card border border-border-primary rounded-md shadow-lg max-h-60 overflow-y-auto">
                  {symbolSearchResults.map((asset) => {
                    const assetSymbol = typeof asset === 'string' ? asset : asset.symbol;
                    const assetName = typeof asset === 'string' ? '' : asset.name || '';
                    const isCrypto = isCryptoSymbol(assetSymbol);
                    return (
                      <div 
                        key={assetSymbol}
                        className="px-4 py-2 hover:bg-bg-secondary cursor-pointer text-sm text-text-primary transition-colors flex items-center justify-between group"
                        onClick={() => selectSymbol(assetSymbol)}
                      >
                        <div className="flex items-center gap-2 flex-1 min-w-0">
                          <span className="font-medium">{assetSymbol}</span>
                          {assetName && (
                            <span className="text-xs text-text-secondary truncate">{assetName}</span>
                          )}
                        </div>
                        <Badge 
                          variant={isCrypto ? 'success' : 'secondary'} 
                          className="ml-2 flex-shrink-0 text-xs"
                        >
                          {isCrypto ? (
                            <>
                              <Coins className="h-2.5 w-2.5 mr-1" />
                              Crypto
                            </>
                          ) : (
                            <>
                              <TrendingUp className="h-2.5 w-2.5 mr-1" />
                              Stock
                            </>
                          )}
                        </Badge>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
            {assetName && (
              <div className="flex items-center gap-2 text-xs text-text-secondary">
                <span className="truncate">{assetName}</span>
                <span className="text-text-tertiary">•</span>
                {isFractionable !== null && (
                  <span className={`px-1.5 py-0.5 rounded text-xs font-medium whitespace-nowrap ${
                    isFractionable 
                      ? 'bg-status-success/20 text-status-success' 
                      : 'bg-status-warning/20 text-status-warning'
                  }`}>
                    {isFractionable ? 'Fractional ✓' : 'Whole Shares Only'}
                  </span>
                )}
              </div>
            )}
          </div>

          {/* Row 2: Qty × Price = Value */}
          <div className="grid grid-cols-12 gap-3 items-end">
            {/* Initial Quantity */}
            <div className="col-span-3 space-y-2">
              <Label htmlFor="initialQuantity" className="text-sm font-medium text-text-primary">Qty. *</Label>
              <Input
                id="initialQuantity"
                type="number"
                value={initialQuantity}
                onChange={(e) => setInitialQuantity(e.target.value)}
                min={isCryptoSymbol(symbol) ? "0.0001" : (isFractionable === false ? "1" : "0.01")}
                step={isCryptoSymbol(symbol) ? "0.0001" : (isFractionable === false ? "1" : "0.01")}
                className="font-numbers"
                required
              />
            </div>

            {/* Multiplication symbol */}
            <div className="col-span-1 flex items-center justify-center pb-2 text-text-tertiary text-lg">
              ×
            </div>

            {/* Initial Price */}
            <div className="col-span-4 space-y-2">
              <div className="flex items-center justify-between">
                <Label htmlFor="initialPrice" className="text-sm font-medium text-text-primary">Price *</Label>
                {currentPrice && (() => {
                  const priceMatches = initialPrice && Math.abs(parseFloat(initialPrice) - currentPrice) < 0.01;
                  return (
                    <button
                      type="button"
                      onClick={() => setInitialPrice(currentPrice.toFixed(2))}
                      className={cn(
                        "text-xs font-medium last-price-button relative",
                        priceMatches 
                          ? "text-text-tertiary" 
                          : "text-accent-yellow hover:text-accent-yellow/90"
                      )}
                      title={`Get Latest Price: ${formatCurrency(currentPrice)}`}
                      data-price-matches={priceMatches ? "true" : "false"}
                    >
                      <span className="relative z-10">Get Latest Price</span>
                    </button>
                  );
                })()}
              </div>
              <Input
                id="initialPrice"
                type="number"
                step="0.01"
                value={initialPrice}
                onChange={(e) => setInitialPrice(e.target.value)}
                placeholder={currentPrice ? currentPrice.toFixed(2) : "150.00"}
                min="0.01"
                className="font-numbers"
                required
              />
            </div>

            {/* Equals symbol */}
            <div className="col-span-1 flex items-center justify-center pb-2 text-text-tertiary text-lg">
              =
            </div>

            {/* Value (calculated) */}
            <div className="col-span-3 space-y-2">
              <Label className="text-sm font-medium text-text-primary">Value</Label>
              <Input
                value={formatCurrency(calculateValue())}
                disabled
                className="bg-bg-secondary font-numbers"
              />
            </div>
          </div>

          {/* Row 2: Multipliers and Iterations */}
          <div className="grid grid-cols-3 gap-4">

            {/* Increment Qty Multiplier */}
            <div className="space-y-2">
              <Label htmlFor="incrementQty" className="text-sm font-medium text-text-primary">Increment Qty By *</Label>
              <Input
                id="incrementQty"
                type="number"
                step="0.01"
                value={incrementQtyMultiplier}
                onChange={(e) => setIncrementQtyMultiplier(e.target.value)}
                placeholder="1.2"
                min="0.01"
                required
              />
              <p className="text-xs text-text-tertiary">
                Multiplier (e.g., 1.2, 1.5, 2.0)
              </p>
            </div>

            {/* Decrement Price Multiplier */}
            <div className="space-y-2">
              <Label htmlFor="decrementPrice" className="text-sm font-medium text-text-primary">Decrement Price By *</Label>
              <Input
                id="decrementPrice"
                type="number"
                step="0.01"
                value={decrementPriceMultiplier}
                onChange={(e) => setDecrementPriceMultiplier(e.target.value)}
                placeholder="0.9"
                min="0.01"
                max="0.99"
                required
              />
              <p className="text-xs text-text-tertiary">
                Multiplier (0-1, e.g., 0.9 = 10% decrease)
              </p>
            </div>

            {/* Number of Iterations */}
            <div className="space-y-2">
              <Label htmlFor="iterations" className="text-sm font-medium text-text-primary">Number of Iterations *</Label>
              <Input
                id="iterations"
                type="number"
                value={iterations}
                onChange={(e) => setIterations(e.target.value)}
                min="1"
                max="20"
                required
              />
              <p className="text-xs text-text-tertiary">
                Integer &gt; 0 (max 20)
              </p>
            </div>
          </div>

          {/* Info note about Time In Force */}
          <div className="bg-bg-card border border-border-primary rounded-lg p-3 text-xs text-text-secondary">
            <p>
              <strong className="text-text-primary">Time In Force:</strong> Orders are automatically set to <strong>DAY</strong> for fractional quantities or <strong>GTC</strong> for whole shares.{' '}
              <a 
                href="https://docs.alpaca.markets/docs/fractional-trading" 
                target="_blank" 
                rel="noopener noreferrer"
                className="text-accent-blue hover:underline"
              >
                Learn more →
              </a>
            </p>
          </div>

          {missingFields > 0 && (
            <div className="text-xs text-text-tertiary text-right">
              Fill out all fields ({missingFields} missing)
            </div>
          )}

          {/* Order Ladder Preview */}
          {ladder.length > 0 && (
            <div className="space-y-3 pt-4 border-t border-border-divider">
              <h3 className="text-sm font-medium text-text-primary">Order Preview</h3>
              <GTTOrderPreviewTable
                isCrypto={isCryptoSymbol(symbol)}
                orders={ladder.map(level => ({
                  ...level,
                  timeInForce: level.timeInForce as 'DAY' | 'GTC',
                  isDuplicate: duplicateInfo ? existingTriggerPrices.has(Number(level.price.toFixed(2))) : false
                }))}
                showDuplicates={!!duplicateInfo}
                totalValue={ladder.reduce((sum, level) => sum + level.value, 0)}
              />
            </div>
          )}

          {/* Progress Indicator */}
          {isSubmitting && (
            <div className="space-y-1.5 pt-2 border-t border-border-divider">
              <div className="flex items-center justify-between text-xs">
                <span className="text-text-secondary flex items-center gap-2">
                  {progress < 100 ? (
                    <>
                      <Loader2 className="h-3 w-3 animate-spin" />
                      {currentStep || 'Processing...'}
                    </>
                  ) : (
                    <>
                      <CheckCircle2 className="h-3 w-3 text-status-success" />
                      {currentStep || 'Complete'}
                    </>
                  )}
                </span>
                <span className="text-text-tertiary">{Math.round(progress)}%</span>
              </div>
              <Progress value={progress} className="h-1" />
            </div>
          )}

          <DialogFooter className="gap-2 pt-3">
            <Button 
              type="button" 
              variant="outline" 
              onClick={onClose}
              disabled={isSubmitting}
              className="min-w-[90px] h-9 text-sm"
            >
              Cancel
            </Button>
            
            {/* Compact fractional warning in footer */}
            {ladder.some(l => l.needsRounding) && (
              <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-lg px-3 py-2 mr-auto">
                <div className="flex items-center gap-2">
                  <AlertTriangle className="h-3.5 w-3.5 text-yellow-500 flex-shrink-0" />
                  <div className="flex flex-col gap-0.5">
                    <span className="text-xs font-medium text-text-primary">Fractions Rounded</span>
                    <a 
                      href="https://docs.alpaca.markets/docs/fractional-trading" 
                      target="_blank" 
                      rel="noopener noreferrer"
                      className="text-[10px] text-accent-blue hover:underline"
                    >
                      Learn more →
                    </a>
                  </div>
                </div>
              </div>
            )}
            
            <Button 
              type="submit" 
              disabled={isSubmitting || missingFields > 0}
              className={`min-w-[140px] h-9 text-sm font-medium shadow-lg transition-all ${
                duplicateInfo 
                  ? 'bg-red-600 hover:bg-red-700 text-white' 
                  : 'bg-accent-yellow hover:opacity-90 text-bg-primary'
              }`}
            >
              {isSubmitting ? (
                <span className="flex items-center gap-2">
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  Creating...
                </span>
              ) : duplicateInfo ? (
                <span className="flex items-center gap-2">
                  <AlertTriangle className="h-3.5 w-3.5" />
                  Create Duplicates
                </span>
              ) : (
                'Create Order'
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>

    </>
  );
}
