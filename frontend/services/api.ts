/**
 * API client for backend communication
 * Framework-agnostic environment variable support:
 * - Next.js: NEXT_PUBLIC_API_URL
 * - Standard: API_URL (for other frameworks)
 * - Runtime: window.__API_URL__
 */
import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios';
import axiosRetry, { exponentialDelay } from 'axios-retry';
import { debug } from '@/lib/debug';
import type { AccountData, Position, PriceData, MarketStatus, PortfolioPLSummary } from '@/lib/types';

// Circuit breaker state
let circuitBreakerOpen = false;
let circuitBreakerFailures = 0;
const CIRCUIT_BREAKER_THRESHOLD = 5; // Open after 5 consecutive failures
const CIRCUIT_BREAKER_RESET_TIME = 30000; // Reset after 30 seconds

// Simplified: Always use production API URL via Cloudflare Tunnel
// Tunnel is always active and routes api-trading.parthchandak.info -> localhost:8000
// This eliminates the need for environment-specific configuration
const getApiUrl = () => {
  // Priority 1: Runtime injection from window (set in layout.tsx)
  if (typeof window !== 'undefined' && (window as any).__API_URL__) {
    return (window as any).__API_URL__;
  }
  // Always use production URL - tunnel handles routing
  return 'https://api-trading.parthchandak.info';
};

// Initialize with production URL - tunnel routes to localhost:8000 when running locally
const api = axios.create({
  baseURL: 'https://api-trading.parthchandak.info',
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000, // 30 second timeout - allow more time for mobile/cold starts
});

// Configure retry logic with exponential backoff
axiosRetry(api, {
  retries: 3,
  retryDelay: exponentialDelay, // Exponential backoff: 1s, 2s, 4s
  retryCondition: (error: AxiosError) => {
    // Only retry on network errors or 5xx server errors
    // Don't retry on 4xx client errors (bad request, unauthorized, etc.)
    if (error.code === 'ECONNABORTED' || error.code === 'ETIMEDOUT' || !error.response) {
      return true; // Network/timeout errors - retry
    }
    const status = error.response?.status;
    return status ? status >= 500 && status < 600 : false; // Only retry 5xx errors
  },
  onRetry: (retryCount, error) => {
    debug.log(`[API] Retrying request (attempt ${retryCount}/3):`, error.config?.url);
  },
});

// Interceptor to set baseURL dynamically for each request
// This ensures window.__API_URL__ is checked at request time, not module load time
api.interceptors.request.use(
  (config) => {
    const dynamicBaseUrl = getApiUrl();
    if (dynamicBaseUrl) {
      config.baseURL = dynamicBaseUrl;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Add request interceptor for logging (runs after baseURL is set)
api.interceptors.request.use(
  (config) => {
    // Reduced logging - only log price fetches in verbose mode
    // Price fetches happen frequently and create console noise
    return config;
  },
  (error) => {
    debug.error('[API] Request error:', error);
    return Promise.reject(error);
  }
);

// Add response interceptor for logging and circuit breaker
api.interceptors.response.use(
  (response) => {
    // Reset circuit breaker on success
    if (circuitBreakerOpen) {
      debug.log('[API] Circuit breaker reset - backend is back online');
      circuitBreakerOpen = false;
      circuitBreakerFailures = 0;
    }
    // Reduced logging - price responses are frequent and create console noise
    return response;
  },
  (error: AxiosError) => {
    // Track failures for circuit breaker
    if (!error.response || (error.response.status >= 500 && error.response.status < 600)) {
      circuitBreakerFailures++;
      if (circuitBreakerFailures >= CIRCUIT_BREAKER_THRESHOLD && !circuitBreakerOpen) {
        circuitBreakerOpen = true;
        debug.error(`[API] Circuit breaker opened after ${circuitBreakerFailures} failures`);
        // Auto-reset after timeout
        setTimeout(() => {
          if (circuitBreakerOpen) {
            debug.log('[API] Circuit breaker auto-reset - attempting to reconnect');
            circuitBreakerOpen = false;
            circuitBreakerFailures = 0;
          }
        }, CIRCUIT_BREAKER_RESET_TIME);
      }
    }
    
    // Reject immediately if circuit breaker is open
    if (circuitBreakerOpen) {
      const circuitError = new Error('Backend is temporarily unavailable. Please try again in a moment.');
      (circuitError as any).isCircuitBreakerOpen = true;
      return Promise.reject(circuitError);
    }
    
    if (error.config?.url?.includes('/api/prices')) {
      debug.error('[API] Prices fetch error:', error.response?.data || error.message);
    }
    return Promise.reject(error);
  }
);

// Log API URL after a short delay to ensure window.__API_URL__ is set
if (typeof window !== 'undefined') {
  setTimeout(() => {
    debug.log('[API] Initialized with base URL:', getApiUrl());
  }, 100);
}

// Separate axios instance for file uploads (without Content-Type header)
const fileUploadApi = axios.create({
  baseURL: 'https://api-trading.parthchandak.info', // Production fallback
  // Don't set Content-Type - browser will set it automatically with boundary for FormData
});

// Interceptor to set baseURL dynamically for file uploads too
fileUploadApi.interceptors.request.use(
  (config) => {
    const dynamicBaseUrl = getApiUrl();
    if (dynamicBaseUrl) {
      config.baseURL = dynamicBaseUrl;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

import type { GTTOrder, GTTOrderCreate, GTTOrderDetailUpdate, CSVUploadResponse } from '@/lib/types';

// GTT Orders
export const gttOrdersApi = {
  getAll: () => api.get<GTTOrder[]>('/api/gtt-orders'),
  getById: (id: number) => api.get<GTTOrder>(`/api/gtt-orders/${id}`),
  create: (data: GTTOrderCreate) => {
    // Extract query params from data
    const { confirm_rounding, confirm_duplicates, ...bodyData } = data;
    
    // Build query string
    const params = new URLSearchParams();
    if (confirm_rounding !== undefined) params.append('confirm_rounding', String(confirm_rounding));
    if (confirm_duplicates !== undefined) params.append('confirm_duplicates', String(confirm_duplicates));
    
    const queryString = params.toString();
    const url = queryString ? `/api/gtt-orders?${queryString}` : '/api/gtt-orders';
    
    return api.post<GTTOrder>(url, bodyData);
  },
  createBulk: (orders: GTTOrderCreate[]) => api.post<GTTOrder[]>('/api/gtt-orders/bulk', orders),
  uploadCSV: (
    file: File, 
    confirmRounding: boolean = false, 
    confirmDuplicates: boolean = false,
    onUploadProgress?: (progressEvent: { loaded: number; total: number; percent: number }) => void
  ) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('confirm_rounding', confirmRounding.toString());
    formData.append('confirm_duplicates', confirmDuplicates.toString());
    // Use separate axios instance without Content-Type header
    // Browser will automatically set Content-Type with boundary for multipart/form-data
    return fileUploadApi.post<CSVUploadResponse>('/api/gtt-orders/upload-csv', formData, {
      timeout: 60000, // 60 second timeout (reduced from 5 min - if backend is down, fail fast)
      onUploadProgress: (progressEvent) => {
        try {
          // Defensive checks: ensure progressEvent exists and has valid properties
          if (!progressEvent || !onUploadProgress) return;
          if (typeof progressEvent.loaded !== 'number' || typeof progressEvent.total !== 'number') return;
          if (progressEvent.total <= 0) return; // Avoid division by zero
          
          const percent = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          onUploadProgress({
            loaded: progressEvent.loaded,
            total: progressEvent.total,
            percent,
          });
        } catch (error) {
          // Always log errors, even in production
          console.error('[API] Error in upload progress callback:', error);
        }
      },
    });
  },
  delete: (id: number) => api.delete(`/api/gtt-orders/${id}`),
  deleteOrderDetail: (orderId: number, detailId: number) => api.delete(`/api/gtt-orders/${orderId}/details/${detailId}`),
  updateOrderDetail: (orderId: number, detailId: number, data: GTTOrderDetailUpdate) => api.put<GTTOrderDetailUpdate>(`/api/gtt-orders/${orderId}/details/${detailId}`, data),
  linkOrderDetail: (orderId: number, detailId: number, alpacaOrderId: string) => api.post(`/api/gtt-orders/${orderId}/details/${detailId}/link`, { alpaca_order_id: alpacaOrderId }),
  unlinkOrderDetail: (orderId: number, detailId: number) => api.delete(`/api/gtt-orders/${orderId}/details/${detailId}/link`),
  getCSVTemplate: () => api.get('/api/csv-template', { responseType: 'blob' }), // Legacy - use getStocksTemplate or getCryptoTemplate
  getStocksTemplate: () => api.get('/api/csv-template/stocks', { responseType: 'blob' }),
  getCryptoTemplate: () => api.get('/api/csv-template/crypto', { responseType: 'blob' }),
};

// Authentication
export const authApi = {
  login: (password: string) => {
    const formData = new URLSearchParams();
    formData.append('password', password);
    return api.post('/api/auth/login', formData, {
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
    });
  },
};

// Account & Positions
export const accountApi = {
  getAccount: () => api.get<AccountData>('/api/account'),
  getPositions: () => api.get<Position[]>('/api/positions'),
  getPortfolioPL: (period: string) => api.get<PortfolioPLSummary>(`/api/portfolio-pl?period=${period}`),
};

// Prices
export const pricesApi = {
  getPrices: (symbols: string | string[]) => {
    const params = symbols 
      ? { symbols: typeof symbols === 'string' ? symbols : symbols.join(',') } 
      : {};
    return api.get<{ prices: PriceData[] }>('/api/prices', { params });
  },
};

// Market Clock
export const marketApi = {
  getMarketClock: () => api.get<MarketStatus>('/api/market-clock'),
};

// Historical Bars
export const historicalBarsApi = {
  getBars: (symbol: string, days: number = 30, timeframe: string = 'Day', signal?: AbortSignal) => {
    // Use query parameter for crypto symbols (contain '/') to avoid URL path issues
    if (symbol.includes('/')) {
      return api.get(`/api/historical-bars`, {
        params: { symbol, days, timeframe },
        signal
      });
    }
    return api.get(`/api/historical-bars/${symbol}`, {
      params: { days, timeframe },
      signal
    });
  },
};

// Orders
export const ordersApi = {
  getAll: (status: string | null = null, symbol: string | null = null, limit: number = 100) => {
    const params: any = { limit };
    if (status) params.status = status;
    if (symbol) params.symbol = symbol;
    return api.get('/api/orders', { params });
  },
};

// Asset Info
export const assetApi = {
  getAssetInfo: (symbol: string) => {
    // Use query parameter for crypto symbols (contain '/') to avoid URL path issues
    if (symbol.includes('/')) {
      return api.get(`/api/asset`, { params: { symbol } });
    }
    return api.get(`/api/asset/${symbol}`);
  },
  getInfo: (symbol: string) => {
    // Use query parameter for crypto symbols (contain '/') to avoid URL path issues
    if (symbol.includes('/')) {
      return api.get(`/api/asset`, { params: { symbol } });
    }
    return api.get(`/api/asset/${symbol}`);
  }, // Alias for compatibility
  search: (query: string, assetType?: 'crypto' | 'stock') => 
    api.get<any[]>('/api/assets/search', { 
      params: { 
        q: query, 
        ...(assetType && { asset_type: assetType })
      } 
    }),
};


