'use client';

import { useEffect, useRef, useState } from 'react';
import { formatCurrency } from '@/lib/formatters';
import { cn } from '@/lib/utils';

interface AnimatedPriceProps {
  price: number;
  className?: string;
}

/**
 * AnimatedPrice component that shows smooth number animation when price changes.
 * Features:
 * - Smooth interpolation animation using requestAnimationFrame
 * - Color indication (green for up, red for down)
 * - Subtle scale animation on change
 * - Respects prefers-reduced-motion
 */
export function AnimatedPrice({ price, className }: AnimatedPriceProps) {
  const [displayPrice, setDisplayPrice] = useState(price);
  const [direction, setDirection] = useState<'up' | 'down' | null>(null);
  const [isAnimating, setIsAnimating] = useState(false);
  const prevPriceRef = useRef<number>(price);
  const animationRef = useRef<number | null>(null);
  const prefersReducedMotion = useRef<boolean>(false);

  // Check for reduced motion preference
  useEffect(() => {
    if (typeof window !== 'undefined') {
      prefersReducedMotion.current = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    }
  }, []);

  useEffect(() => {
    const prevPrice = prevPriceRef.current;
    
    // Only animate if price actually changed
    if (prevPrice !== price && Math.abs(prevPrice - price) > 0.001) {
      // Determine direction
      const newDirection = price > prevPrice ? 'up' : 'down';
      setDirection(newDirection);
      setIsAnimating(true);
      
      // Clear any existing animation
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
      
      // If reduced motion, skip animation
      if (prefersReducedMotion.current) {
        setDisplayPrice(price);
        prevPriceRef.current = price;
        setTimeout(() => {
          setDirection(null);
          setIsAnimating(false);
        }, 300);
        return;
      }
      
      // Animate the number change
      const startTime = performance.now();
      const duration = 500; // 500ms animation
      const startPrice = prevPrice;
      const endPrice = price;
      
      const animate = (currentTime: number) => {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        
        // Ease-out cubic for smooth deceleration
        const eased = 1 - Math.pow(1 - progress, 3);
        
        const currentPrice = startPrice + (endPrice - startPrice) * eased;
        setDisplayPrice(currentPrice);
        
        if (progress < 1) {
          animationRef.current = requestAnimationFrame(animate);
        } else {
          setDisplayPrice(endPrice);
          setIsAnimating(false);
          // Clear direction indicator after animation
          setTimeout(() => setDirection(null), 400);
          animationRef.current = null;
        }
      };
      
      animationRef.current = requestAnimationFrame(animate);
      prevPriceRef.current = price;
    }
  }, [price]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
    };
  }, []);

  const formattedPrice = formatCurrency(displayPrice);
  
  return (
    <span
      className={cn(
        'font-numbers transition-all duration-300 inline-block',
        direction === 'up' && 'text-status-success',
        direction === 'down' && 'text-status-error',
        direction === null && 'text-text-primary',
        isAnimating && 'scale-105',
        className
      )}
      style={{
        transition: 'color 0.3s ease, transform 0.2s ease',
      }}
    >
      {formattedPrice}
    </span>
  );
}

