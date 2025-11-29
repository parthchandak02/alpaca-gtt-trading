/**
 * Debug logging utility
 * Logs to console in development mode, silent in production
 * Errors always log (even in production) for debugging
 * 
 * To enable debug logs in production, set NEXT_PUBLIC_DEBUG=true in your .env file
 */

// Enable debug logs if in dev mode OR if explicitly enabled via env var
const isDev = process.env.NODE_ENV === 'development';
const debugEnabled = isDev || process.env.NEXT_PUBLIC_DEBUG === 'true';

export const debug = {
  log: (...args: any[]) => {
    if (debugEnabled) {
      console.log('[DEBUG]', ...args);
    }
  },
  
  error: (...args: any[]) => {
    // Always log errors, even in production, for debugging
    // Extract error messages to avoid verbose stack traces in console
    const cleanedArgs = args.map(arg => {
      if (arg instanceof Error) {
        // Extract just the message and name, avoid full stack trace spam
        // Stack traces are still available in browser dev tools if needed
        const errorInfo: any = {
          name: arg.name,
          message: arg.message,
        };
        
        // Only include limited stack trace in development
        if (isDev && arg.stack) {
          // Limit to first 5 lines of stack trace to reduce verbosity
          const stackLines = arg.stack.split('\n').slice(0, 6);
          errorInfo.stack = stackLines.join('\n');
        }
        
        return errorInfo;
      }
      return arg;
    });
    
    // Use console.error but with cleaned error objects to reduce stack trace spam
    console.error('[ERROR]', ...cleanedArgs);
  },
  
  warn: (...args: any[]) => {
    if (debugEnabled) {
      console.warn('[DEBUG WARN]', ...args);
    }
  },
  
  info: (...args: any[]) => {
    if (debugEnabled) {
      console.info('[DEBUG INFO]', ...args);
    }
  },
  
  group: (label: string) => {
    if (debugEnabled) {
      console.group(`[DEBUG] ${label}`);
    }
  },
  
  groupEnd: () => {
    if (debugEnabled) {
      console.groupEnd();
    }
  },
  
  table: (data: any) => {
    if (debugEnabled) {
      console.table(data);
    }
  },
  
  time: (label: string) => {
    if (debugEnabled) {
      console.time(`[DEBUG] ${label}`);
    }
  },
  
  timeEnd: (label: string) => {
    if (debugEnabled) {
      console.timeEnd(`[DEBUG] ${label}`);
    }
  },
};

