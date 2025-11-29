/**
 * TypeScript type definitions matching backend schemas
 * These types ensure type safety across the frontend
 */

export interface GTTOrderDetail {
  id: number;
  gtt_order_id: number;
  order_index: number;
  trigger_price: number;
  quantity: number;
  fractional_quantity: number | null;
  limit_price: number;
  amount: number;
  alpaca_order_id: string | null;
  is_manually_linked: boolean;
  time_in_force: string;
  status: string | null;
  submitted_at: string | null;
  filled_at: string | null;
  expired_at: string | null;
  filled_avg_price: number | null;
}

export interface GTTOrder {
  id: number;
  symbol: string;
  initial_trigger_price: number;
  initial_quantity: number;
  increment_qty_multiplier: number;
  decrement_price_multiplier: number;
  iterations: number;
  status: string;
  filled_count: number;
  total_count: number;
  total_value: number;
  locked_buying_power: number;
  created_at: string;
  updated_at: string;
  order_details: GTTOrderDetail[];
}

export interface GTTOrderCreate {
  symbol: string;
  initial_trigger_price: number;
  initial_quantity: number;
  increment_qty_multiplier: number;
  decrement_price_multiplier: number;
  iterations: number;
  time_in_force?: string;
  confirm_rounding?: boolean;
  confirm_duplicates?: boolean;
}

export interface GTTOrderDetailUpdate {
  trigger_price?: number;
  quantity?: number;
  limit_price?: number;
  time_in_force?: string;
}

export interface PriceData {
  price: number;
  timestamp: string;
  isMarketOpen: boolean;
}

export interface MarketStatus {
  is_open: boolean;
  timestamp?: string;
  next_open?: string;
  next_close?: string;
}

export interface AccountData {
  buying_power: number;
  cash: number;
  portfolio_value: number;
  equity: number;
  day_trading_buying_power: number;
  // Comprehensive account fields
  long_market_value?: number | null;
  short_market_value?: number | null;
  unsettled_funds?: number | null;
  pending_transfer_in?: number | null;
  pending_transfer_out?: number | null;
  non_marginable_buying_power?: number | null;
  regt_buying_power?: number | null;
  initial_margin?: number | null;
  maintenance_margin?: number | null;
  last_equity?: number | null;
  accrued_fees?: number | null;
  non_tradable_assets?: number | null;
  sma?: number | null; // Special Memorandum Account
}

export interface Position {
  symbol: string;
  quantity: number;
  avg_entry_price: number;
  current_price: number | null;
  market_value: number | null;
  cost_basis: number;
  unrealized_pl: number | null;
  unrealized_plpc: number | null;
}

export interface PortfolioPLSummary {
  period: string; // "today", "weekly", "monthly", "yearly", "all_time"
  profit_loss_dollars: number;
  profit_loss_percent: number;
  equity: number;
  base_value: number;
  base_value_asof: string | null;
  data_points: number;
}

export interface AggregatedOrderData {
  total_value: number;
  locked_buying_power: number;
  filled_count: number;
  total_count: number;
  all_order_details: GTTOrderDetail[];
}

export interface CSVUploadResponse {
  success?: boolean;
  requires_confirmation?: boolean;
  rounding_warnings?: Array<{
    symbol: string;
    error: string;
  }>;
  duplicate_warnings?: Array<{
    symbol: string;
    trigger_price: number;
    existing_order_id: number;
    message: string;
  }>;
  message?: string;
  orders?: GTTOrder[]; // Created orders
  created_orders?: GTTOrder[]; // Alternative field name
  created_count?: number;
  failed_count?: number;
  warnings?: Array<{
    symbol: string;
    error: string;
    warning?: boolean;
    requires_confirmation?: boolean;
  }>;
  failed_orders?: Array<{
    symbol: string;
    error: string;
  }>;
}

