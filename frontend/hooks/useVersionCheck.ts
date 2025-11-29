'use client';

import { useEffect, useState, useCallback, useRef } from 'react';
import { debug } from '@/lib/debug';

interface VersionInfo {
  version: string;
  buildTime: string;
  buildTimeReadable: string;
  gitCommit: string;
  gitCommitShort: string;
  gitBranch: string;
}

const CHECK_INTERVAL = 2 * 60 * 1000; // Check every 2 minutes (reduced from 5 minutes for faster detection)
const REFRESH_COOLDOWN = 30 * 1000; // 30 seconds cooldown after refresh (stored in localStorage to persist across reloads)
const STORAGE_KEY = 'alpaca_app_version';
const COOLDOWN_KEY = 'alpaca_version_check_cooldown';

/**
 * Check if we're running in production/Cloudflare environment.
 * Version checks should only run on Cloudflare deployments, not in local development.
 */
const isProductionEnvironment = (): boolean => {
  if (typeof window === 'undefined') return false;
  
  const hostname = window.location.hostname;
  // Only run version checks on production domain (Cloudflare Pages)
  // Skip on localhost, 127.0.0.1, and other local domains
  const isLocal = hostname === 'localhost' || 
                  hostname === '127.0.0.1' || 
                  hostname.startsWith('192.168.') ||
                  hostname.startsWith('10.') ||
                  hostname.endsWith('.local');
  
  return !isLocal;
};

/**
 * Hook to check for version updates.
 * 
 * Uses frontend version.json (from static build) as source of truth.
 * This only changes on Cloudflare deployments, not on backend restarts.
 * Compares current frontend version with stored version in localStorage.
 * 
 * IMPORTANT: Only runs in production/Cloudflare environment, not in local development.
 */
export function useVersionCheck() {
  const [currentVersion, setCurrentVersion] = useState<string | null>(null);
  const [latestVersion, setLatestVersion] = useState<string | null>(null);
  const [showUpdateDialog, setShowUpdateDialog] = useState(false);
  const [versionInfo, setVersionInfo] = useState<VersionInfo | null>(null);
  const isRefreshingRef = useRef<boolean>(false);
  
  // Get cooldown from localStorage (persists across page reloads)
  const getCooldown = useCallback((): number => {
    if (typeof window === 'undefined') return 0;
    try {
      const stored = localStorage.getItem(COOLDOWN_KEY);
      return stored ? parseInt(stored, 10) : 0;
    } catch {
      return 0;
    }
  }, []);
  
  const setCooldown = useCallback((timestamp: number) => {
    if (typeof window === 'undefined') return;
    try {
      localStorage.setItem(COOLDOWN_KEY, timestamp.toString());
    } catch {
      // Ignore localStorage errors
    }
  }, []);

  const fetchFrontendVersion = useCallback(async (): Promise<VersionInfo | null> => {
    try {
      // Fetch frontend version.json from static build (only changes on Cloudflare deployment)
      // Add cache busting to ensure fresh version check
      const response = await fetch(`/version.json?t=${Date.now()}`, {
        cache: 'no-store',
        headers: {
          'Cache-Control': 'no-cache',
        },
      });
      
      if (!response.ok) {
        debug.warn('[Version] Frontend version.json not available (may be in development)');
        return null;
      }
      
      const data: VersionInfo = await response.json();
      debug.log('[Version] Frontend version:', data.version);
      return data;
    } catch (error) {
      debug.error('[Version] Error fetching frontend version:', error);
      return null;
    }
  }, []);

  const getStoredVersion = useCallback((): string | null => {
    if (typeof window === 'undefined') return null;
    try {
      return localStorage.getItem(STORAGE_KEY);
    } catch (error) {
      debug.error('[Version] Error reading localStorage:', error);
      return null;
    }
  }, []);

  const setStoredVersion = useCallback((version: string) => {
    if (typeof window === 'undefined') return;
    try {
      localStorage.setItem(STORAGE_KEY, version);
    } catch (error) {
      debug.error('[Version] Error writing localStorage:', error);
    }
  }, []);

  const checkVersion = useCallback(async () => {
    // Only run version checks in production/Cloudflare environment
    if (!isProductionEnvironment()) {
      debug.log('[Version] Skipping version check - running in development/local environment');
      return;
    }

    // Skip check if we're in cooldown period after refresh (check localStorage)
    const cooldownUntil = getCooldown();
    if (Date.now() < cooldownUntil) {
      debug.log('[Version] Skipping check - in refresh cooldown period');
      return;
    }

    const frontendData = await fetchFrontendVersion();
    if (!frontendData) {
      // In development, version.json may not exist - skip version check
      debug.log('[Version] Unable to fetch frontend version (likely in development mode)');
      return;
    }

    const frontendVersion = frontendData.version;
    const storedVersion = getStoredVersion();

    // Initialize: store current version if not set
    if (!currentVersion && !storedVersion) {
      setCurrentVersion(frontendVersion);
      setStoredVersion(frontendVersion);
      setVersionInfo(frontendData);
      debug.log('[Version] Initial version set:', frontendVersion);
      return; // Don't show dialog on first load
    }

    // Use stored version as reference (more reliable than state)
    const referenceVersion = storedVersion || currentVersion;

    if (!referenceVersion) {
      // Shouldn't happen, but handle gracefully
      setCurrentVersion(frontendVersion);
      setStoredVersion(frontendVersion);
      setVersionInfo(frontendData);
      return;
    }

    // Check if frontend version is different from stored version
    // This only happens on Cloudflare deployments, not backend restarts
    if (frontendVersion !== referenceVersion) {
      debug.log(`[Version] New version detected! Stored: ${referenceVersion}, Frontend: ${frontendVersion}`);
      setLatestVersion(frontendVersion);
      setVersionInfo(frontendData);
      
      // Always show dialog when new version is detected (even if already showing)
      setShowUpdateDialog(true);
    } else {
      // Versions match - ensure dialog is dismissed
      if (showUpdateDialog) {
        debug.log('[Version] Versions match - dismissing dialog');
        setShowUpdateDialog(false);
      }
      
      // Update current version if it was null
      if (!currentVersion) {
        setCurrentVersion(frontendVersion);
      }
      
      // Update version info
      setVersionInfo(frontendData);
    }
  }, [currentVersion, showUpdateDialog, fetchFrontendVersion, getStoredVersion, setStoredVersion]);

  const refreshPage = useCallback(() => {
    if (isRefreshingRef.current) {
      debug.log('[Version] Refresh already in progress, ignoring');
      return;
    }

    debug.log('[Version] User requested hard refresh');
    isRefreshingRef.current = true;
    
    // Set cooldown in localStorage to prevent immediate re-check after refresh (persists across reloads)
    setCooldown(Date.now() + REFRESH_COOLDOWN);
    
    // Update stored version to latest before refresh (so we don't immediately detect mismatch)
    if (latestVersion) {
      setStoredVersion(latestVersion);
      setCurrentVersion(latestVersion);
    }
    
    // Force hard refresh with cache bypass
    // Clear any service worker cache if present
    if ('caches' in window) {
      caches.keys().then(names => {
        names.forEach(name => caches.delete(name));
      }).catch(() => {
        // Ignore errors
      });
    }
    
    // Use location.replace with cache-busting to force fresh load
    const url = new URL(window.location.href);
    // Remove any existing refresh param
    url.searchParams.delete('_refresh');
    url.searchParams.set('_refresh', Date.now().toString());
    
    // Use replace to avoid adding to history
    window.location.replace(url.toString());
  }, [latestVersion, setStoredVersion]);

  const dismissDialog = useCallback(() => {
    debug.log('[Version] User dismissed update dialog');
    setShowUpdateDialog(false);
    
    // Update stored version to latest to prevent immediate re-prompt
    if (latestVersion) {
      setStoredVersion(latestVersion);
      setCurrentVersion(latestVersion);
    }
  }, [latestVersion, setStoredVersion]);

  useEffect(() => {
    // Only run version checks in production/Cloudflare environment
    if (!isProductionEnvironment()) {
      debug.log('[Version] Version check disabled - running in development/local environment');
      return;
    }

    // Check for refresh param BEFORE cleaning it up
    let hadRefreshParam = false;
    if (typeof window !== 'undefined') {
      const url = new URL(window.location.href);
      hadRefreshParam = url.searchParams.has('_refresh');
      
      // Clean up refresh param from URL if present (we just refreshed, don't check again)
      if (hadRefreshParam) {
        debug.log('[Version] Refresh param detected - cleaning up URL and skipping initial check');
        url.searchParams.delete('_refresh');
        // Use replaceState to remove param without reload
        window.history.replaceState({}, '', url.toString());
        // Skip version check for a bit since we just refreshed
        setCooldown(Date.now() + REFRESH_COOLDOWN);
      }
    }

    // Initialize from localStorage on mount
    const stored = getStoredVersion();
    if (stored) {
      setCurrentVersion(stored);
    }

    // Initial version check (with delay to avoid race conditions)
    // Skip if refresh param was present (we just refreshed)
    const initialTimeout = setTimeout(() => {
      if (!hadRefreshParam) {
        checkVersion();
      } else {
        debug.log('[Version] Skipping initial check - page just refreshed');
      }
    }, 1000);

    // Periodic version check
    const interval = setInterval(checkVersion, CHECK_INTERVAL);

    // Check immediately when page becomes visible (user switches back to tab/window)
    // This ensures users see updates quickly when they return to the app
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        debug.log('[Version] Page became visible - checking for updates');
        // Small delay to avoid race conditions
        setTimeout(() => {
          checkVersion();
        }, 500);
      }
    };

    // Check when window regains focus (user switches back to tab/window)
    const handleFocus = () => {
      // Rate limit focus checks to avoid spamming (max once every 60 seconds)
      const lastCheck = parseInt(sessionStorage.getItem('alpaca_last_focus_check') || '0');
      const now = Date.now();
      
      if (now - lastCheck < 60000) {
        return;
      }
      
      sessionStorage.setItem('alpaca_last_focus_check', now.toString());
      debug.log('[Version] Window gained focus - checking for updates');
      
      // Small delay to avoid race conditions
      setTimeout(() => {
        checkVersion();
      }, 500);
    };

    // Add event listeners for visibility and focus changes
    document.addEventListener('visibilitychange', handleVisibilityChange);
    window.addEventListener('focus', handleFocus);

    return () => {
      clearTimeout(initialTimeout);
      clearInterval(interval);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      window.removeEventListener('focus', handleFocus);
    };
  }, [checkVersion, getStoredVersion, getCooldown, setCooldown]);

  return {
    currentVersion,
    latestVersion,
    showUpdateDialog,
    versionInfo,
    refreshPage,
    dismissDialog,
    checkNow: checkVersion,
  };
}


