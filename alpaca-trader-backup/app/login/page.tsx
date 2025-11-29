'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/hooks/useAuth';
import { GlassCard } from '@/components/glass';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';

export default function LoginPage() {
  const router = useRouter();
  const { isAuthenticated, isLoading: authLoading, login } = useAuth();
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Redirect if already authenticated
  useEffect(() => {
    if (!authLoading && isAuthenticated) {
      router.push('/gtt');
    }
  }, [isAuthenticated, authLoading, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsLoading(true);

    const result = await login(password);
    
    if (result.success) {
      router.push('/gtt');
    } else {
      setError(result.error || 'Login failed');
      setIsLoading(false);
    }
  };

  if (authLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-text-secondary">Loading...</div>
      </div>
    );
  }

  return (
    <div className="flex items-center justify-center min-h-screen p-4">
      <GlassCard className="p-8 w-full max-w-md">
        <h1 className="text-2xl font-bold mb-6 text-center">Alpaca GTT Tracker</h1>
        
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="password" className="block text-sm font-medium mb-2 text-text-primary">
              Password
            </label>
            <Input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter password"
              required
              disabled={isLoading}
            />
          </div>

          {error && (
            <div className="text-status-error text-sm">{error}</div>
          )}

          <Button
            type="submit"
            disabled={isLoading || !password}
            className="w-full"
          >
            {isLoading ? 'Logging in...' : 'Login'}
          </Button>
        </form>
      </GlassCard>
    </div>
  );
}

