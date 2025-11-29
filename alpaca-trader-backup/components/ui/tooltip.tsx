'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import { cn } from '@/lib/utils';

interface TooltipProps {
  content: string | React.ReactNode;
  children: React.ReactNode;
  side?: 'top' | 'bottom' | 'left' | 'right';
  className?: string;
}

export function Tooltip({ content, children, side = 'top', className }: TooltipProps) {
  const [isVisible, setIsVisible] = useState(false);
  const [position, setPosition] = useState({ top: 0, left: 0 });
  const [mousePosition, setMousePosition] = useState({ x: 0, y: 0 });
  const triggerRef = useRef<HTMLDivElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);

  const updatePosition = useCallback(() => {
    if (!triggerRef.current || !tooltipRef.current) return;

    // Use requestAnimationFrame to ensure tooltip is rendered before measuring
    requestAnimationFrame(() => {
      if (!triggerRef.current || !tooltipRef.current) return;

      const triggerRect = triggerRef.current.getBoundingClientRect();
      const tooltipRect = tooltipRef.current.getBoundingClientRect();
      const gap = 8;

      let top = 0;
      let left = 0;

      // Always position relative to trigger element center
      const triggerCenterX = triggerRect.left + triggerRect.width / 2;
      const triggerCenterY = triggerRect.top + triggerRect.height / 2;

      switch (side) {
        case 'top':
          top = triggerCenterY - tooltipRect.height - gap;
          left = triggerCenterX - tooltipRect.width / 2;
          break;
        case 'bottom':
          top = triggerRect.bottom + gap;
          left = triggerCenterX - tooltipRect.width / 2;
          break;
        case 'left':
          top = triggerCenterY - tooltipRect.height / 2;
          left = triggerRect.left - tooltipRect.width - gap;
          break;
        case 'right':
          top = triggerCenterY - tooltipRect.height / 2;
          left = triggerRect.right + gap;
          break;
      }

      // Keep tooltip within viewport
      const padding = 8;
      top = Math.max(padding, Math.min(top, window.innerHeight - tooltipRect.height - padding));
      left = Math.max(padding, Math.min(left, window.innerWidth - tooltipRect.width - padding));

      setPosition({ top, left });
    });
  }, [side]);

  const showTooltip = useCallback((e?: React.MouseEvent) => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }
    // Capture mouse position immediately
    if (e) {
      setMousePosition({ x: e.clientX, y: e.clientY });
    }
    timeoutRef.current = setTimeout(() => {
      setIsVisible(true);
      // Update position after a brief delay to ensure tooltip is rendered
      setTimeout(() => updatePosition(), 10);
    }, 100); // Small delay to prevent flicker
  }, [updatePosition]);

  const hideTooltip = useCallback(() => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }
    setIsVisible(false);
  }, []);

  const handleClick = useCallback((e: React.MouseEvent) => {
    // On mobile, toggle tooltip on tap
    if (window.innerWidth < 768) {
      e.preventDefault();
      e.stopPropagation();
      setIsVisible((prev) => {
        if (prev) {
          return false;
        } else {
          updatePosition();
          // Auto-hide after 3 seconds on mobile
          setTimeout(() => setIsVisible(false), 3000);
          return true;
        }
      });
    }
  }, [updatePosition]);

  useEffect(() => {
    if (isVisible) {
      // Update position after tooltip is rendered
      const timeoutId = setTimeout(() => {
        updatePosition();
      }, 0);
      
      const handleResize = () => updatePosition();
      const handleMouseMove = (e: MouseEvent) => {
        setMousePosition({ x: e.clientX, y: e.clientY });
        updatePosition();
      };
      
      window.addEventListener('resize', handleResize);
      window.addEventListener('mousemove', handleMouseMove);
      
      return () => {
        clearTimeout(timeoutId);
        window.removeEventListener('resize', handleResize);
        window.removeEventListener('mousemove', handleMouseMove);
      };
    }
  }, [isVisible, updatePosition]);

  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  return (
    <>
      <div
        ref={triggerRef}
        onMouseEnter={(e) => showTooltip(e)}
        onMouseMove={(e) => {
          setMousePosition({ x: e.clientX, y: e.clientY });
          if (isVisible) updatePosition();
        }}
        onMouseLeave={hideTooltip}
        onFocus={(e) => showTooltip(e as any)}
        onBlur={hideTooltip}
        onClick={handleClick}
        className="inline-flex items-center"
      >
        {children}
      </div>
      {isVisible && (
        <div
          ref={tooltipRef}
          className={cn(
            'fixed z-50 px-2 py-1.5 text-xs font-medium',
            typeof content === 'string' ? 'whitespace-nowrap' : '',
            'bg-bg-elevated text-text-primary rounded-md',
            'border border-border-divider shadow-lg',
            'pointer-events-none',
            'animate-tooltip-in',
            className
          )}
          style={{
            top: `${position.top}px`,
            left: `${position.left}px`,
          }}
          role="tooltip"
        >
          {content}
          <div
            className={cn(
              'absolute w-2 h-2 bg-bg-elevated border-border-divider',
              side === 'top' && 'bottom-[-4px] left-1/2 -translate-x-1/2 border-r border-b rotate-45',
              side === 'bottom' && 'top-[-4px] left-1/2 -translate-x-1/2 border-l border-t rotate-45',
              side === 'left' && 'right-[-4px] top-1/2 -translate-y-1/2 border-r border-t rotate-45',
              side === 'right' && 'left-[-4px] top-1/2 -translate-y-1/2 border-l border-b rotate-45'
            )}
          />
        </div>
      )}
    </>
  );
}

