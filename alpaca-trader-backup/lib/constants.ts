/**
 * Application-wide constants
 * Centralized constants for consistency across the frontend
 */

// Time intervals (in milliseconds)
export const INTERVALS = {
  MARKET_OPEN_POLL: 10000, // 10 seconds
  MARKET_CLOSED_POLL: 300000, // 5 minutes
  ACCOUNT_REFRESH: 30000, // 30 seconds
  MARKET_STATUS_CHECK: 60000, // 60 seconds
} as const;

// Price formatting
export const PRICE_FORMATTING = {
  MIN_DECIMALS: 2,
  MAX_DECIMALS: 2,
} as const;


