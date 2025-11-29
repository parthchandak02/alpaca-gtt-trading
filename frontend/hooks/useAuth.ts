'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { authApi } from '@/services/api';

const AUTH_KEY = 'alpaca_authenticated';

export function useAuth() {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const router = useRouter();

  // Check authentication status on mount
  useEffect(() => {
    checkAuth();
  }, []);

  const checkAuth = useCallback(() => {
    if (typeof window === 'undefined') {
      setIsLoading(false);
      return;
    }
    
    const authStatus = localStorage.getItem(AUTH_KEY);
    const authenticated = authStatus === 'true';
    setIsAuthenticated(authenticated);
    setIsLoading(false);
  }, []);

  const login = useCallback(async (password: string): Promise<{ success: boolean; error?: string }> => {
    try {
      setIsLoading(true);
      await authApi.login(password);
      
      // Set authentication flag
      localStorage.setItem(AUTH_KEY, 'true');
      setIsAuthenticated(true);
      
      return { success: true };
    } catch (error: any) {
      const errorMessage = error.response?.data?.detail || 'Login failed. Please try again.';
      return { success: false, error: errorMessage };
    } finally {
      setIsLoading(false);
    }
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem(AUTH_KEY);
    setIsAuthenticated(false);
    router.push('/login');
  }, [router]);

  return {
    isAuthenticated,
    isLoading,
    login,
    logout,
    checkAuth,
  };
}

