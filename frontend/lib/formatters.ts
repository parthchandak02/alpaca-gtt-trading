import { PRICE_FORMATTING } from './constants';

export function formatCurrency(value: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: PRICE_FORMATTING.MIN_DECIMALS,
    maximumFractionDigits: PRICE_FORMATTING.MAX_DECIMALS,
  }).format(value);
}

export function formatDate(dateString: string): string {
  const date = new Date(dateString);
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  }).format(date);
}

export function formatTimeAgo(timestamp: string): string {
  const date = new Date(timestamp);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSecs = Math.floor(diffMs / 1000);
  const diffMins = Math.floor(diffSecs / 60);
  
  if (diffSecs < 60) {
    return `Just now`;
  } else if (diffMins < 60) {
    return `${diffMins}m ago`;
  } else {
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) {
      return `${diffHours}h ago`;
    } else {
      return formatDate(timestamp);
    }
  }
}

/**
 * Format quantity with dynamic decimal precision
 * - For crypto or quantities < 1: Shows up to 6 decimals (for crypto like 0.0006 BTC)
 * - For stocks (>= 1): Shows 2 decimals
 * - Removes trailing zeros for cleaner display
 */
export function formatQuantity(quantity: number, isCrypto: boolean = false): string {
  if (isCrypto || quantity < 1) {
    // For crypto or small quantities, show up to 6 decimals, remove trailing zeros
    return quantity.toFixed(6).replace(/\.?0+$/, '');
  } else {
    // For stocks (>= 1), show 2 decimals
    return quantity.toFixed(2);
  }
}

/**
 * Format position quantity - shows decimals with appropriate precision
 * - For crypto: Shows up to 4 decimals (removes trailing zeros)
 * - For stocks: Shows up to 2 decimals (removes trailing zeros)
 */
export function formatPositionQuantity(quantity: number, isCrypto: boolean = false): string {
  if (isCrypto) {
    // Crypto: show up to 4 decimals, remove trailing zeros
    return quantity.toFixed(4).replace(/\.?0+$/, '');
  } else {
    // Stocks: show up to 2 decimals, remove trailing zeros
    return quantity.toFixed(2).replace(/\.?0+$/, '');
  }
}

