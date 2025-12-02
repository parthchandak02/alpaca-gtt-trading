import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { debug } from '@/lib/debug';

// Configuration
const HEALTH_CHECK_INTERVAL = 30000; // Check every 30 seconds
const HEALTH_CHECK_TIMEOUT = 5000; // 5 second timeout for health checks

interface ConnectivityState {
  isOnline: boolean; // Browser network status
  isBackendReachable: boolean; // Backend health status
  lastChecked: number | null;
}

export function useConnectivity() {
  const [state, setState] = useState<ConnectivityState>({
    isOnline: typeof navigator !== 'undefined' ? navigator.onLine : true,
    isBackendReachable: true, // Assume true initially to avoid flash of error
    lastChecked: null,
  });

  // Get API URL from window or default
  const getHealthUrl = useCallback(() => {
    if (typeof window !== 'undefined' && (window as any).__API_URL__) {
      return `${(window as any).__API_URL__}/health`;
    }
    return 'https://api-trading.parthchandak.info/health';
  }, []);

  // Check backend health
  const checkHealth = useCallback(async () => {
    if (!navigator.onLine) {
      setState(prev => ({ ...prev, isOnline: false, isBackendReachable: false, lastChecked: Date.now() }));
      return false;
    }

    try {
      const url = getHealthUrl();
      await axios.get(url, { timeout: HEALTH_CHECK_TIMEOUT });
      
      setState(prev => {
        if (!prev.isBackendReachable) {
          debug.log('[Connectivity] Backend recovered');
        }
        return { ...prev, isOnline: true, isBackendReachable: true, lastChecked: Date.now() };
      });
      return true;
    } catch (error) {
      debug.log('[Connectivity] Health check failed:', error);
      setState(prev => ({ ...prev, isOnline: true, isBackendReachable: false, lastChecked: Date.now() }));
      return false;
    }
  }, [getHealthUrl]);

  // Listen for network status changes
  useEffect(() => {
    const handleOnline = () => {
      debug.log('[Connectivity] Browser is online');
      setState(prev => ({ ...prev, isOnline: true }));
      checkHealth();
    };

    const handleOffline = () => {
      debug.log('[Connectivity] Browser is offline');
      setState(prev => ({ ...prev, isOnline: false }));
    };

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, [checkHealth]);

  // Check health on visibility change (tab focus/resume)
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        debug.log('[Connectivity] Tab visible - checking health');
        checkHealth();
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => document.removeEventListener('visibilitychange', handleVisibilityChange);
  }, [checkHealth]);

  // Periodic health check
  useEffect(() => {
    checkHealth(); // Initial check
    const interval = setInterval(checkHealth, HEALTH_CHECK_INTERVAL);
    return () => clearInterval(interval);
  }, [checkHealth]);

  return {
    ...state,
    checkHealth,
  };
}


