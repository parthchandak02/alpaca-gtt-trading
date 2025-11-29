/**
 * Centralized error handling utilities
 * Provides consistent error extraction and formatting across the application
 */

interface ApiError {
  response?: {
    status?: number;
    statusText?: string;
    data?: {
      detail?: string | Record<string, unknown>;
      message?: string;
      errors?: Array<{ field: string; message: string }>;
    };
  };
  message?: string;
  request?: unknown;
}

/**
 * Extract a user-friendly error message from an API error
 */
export function extractErrorMessage(error: unknown, defaultMessage: string = 'An error occurred'): string {
  if (!error) return defaultMessage;
  
  const apiError = error as ApiError;
  
  // Check for response data detail
  if (apiError.response?.data?.detail) {
    const detail = apiError.response.data.detail;
    return typeof detail === 'string' ? detail : JSON.stringify(detail);
  }
  
  // Check for response data message
  if (apiError.response?.data?.message) {
    return apiError.response.data.message;
  }
  
  // Check for error message
  if (apiError.message) {
    return apiError.message;
  }
  
  // Check for status text
  if (apiError.response?.statusText && apiError.response?.status) {
    return `${apiError.response.statusText} (${apiError.response.status})`;
  }
  
  // Check if error is a string
  if (typeof error === 'string') {
    return error;
  }
  
  return defaultMessage;
}

/**
 * Check if error is a network error (no response received)
 */
export function isNetworkError(error: unknown): boolean {
  const apiError = error as ApiError;
  return !!apiError.request && !apiError.response;
}

/**
 * Check if error is a 404 Not Found
 */
export function isNotFoundError(error: unknown): boolean {
  const apiError = error as ApiError;
  return apiError.response?.status === 404;
}

/**
 * Check if error is a server error (5xx)
 */
export function isServerError(error: unknown): boolean {
  const apiError = error as ApiError;
  const status = apiError.response?.status;
  return status !== undefined && status >= 500 && status < 600;
}

