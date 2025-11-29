'use client';

import { useState, useEffect, useRef } from 'react';
import { Button } from '@/components/ui/button';
import { Trash2, Check } from 'lucide-react';

interface ConfirmDeleteButtonProps {
  onConfirm: () => Promise<void> | void;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
  title?: string;
  variant?: 'ghost' | 'destructive';
}

export function ConfirmDeleteButton({
  onConfirm,
  size = 'md',
  className = '',
  title = 'Delete',
  variant = 'ghost',
}: ConfirmDeleteButtonProps) {
  const [isConfirming, setIsConfirming] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);

  // Cleanup timeout on unmount
  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  const sizeClasses = {
    sm: 'h-6 w-6',
    md: 'h-6 w-6',
    lg: 'h-8 w-8',
  };

  const iconSizes = {
    sm: 'h-3 w-3',
    md: 'h-3.5 w-3.5',
    lg: 'h-4 w-4',
  };

  const handleClick = async (e: React.MouseEvent) => {
    e.stopPropagation();
    
    if (!isConfirming) {
      // First click: show confirmation
      setIsConfirming(true);
      // Clear any existing timeout
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
      // Reset after 3 seconds if not confirmed
      timeoutRef.current = setTimeout(() => {
        setIsConfirming(false);
        timeoutRef.current = null;
      }, 3000);
      return;
    }

    // Second click: confirm and delete
    // Clear the timeout
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
    setIsConfirming(false);
    setIsDeleting(true);
    
    try {
      await onConfirm();
    } catch (error) {
      // Error handling is done by the parent component
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <Button
      variant={variant}
      size="icon"
      onClick={handleClick}
      disabled={isDeleting}
      className={`${sizeClasses[size]} ${
        isConfirming 
          ? 'text-status-error bg-status-error/20 hover:bg-status-error/30' 
          : 'text-status-error hover:text-status-error hover:bg-status-error/10'
      } ${className}`}
      title={isConfirming ? 'Click again to confirm' : title}
    >
      {isDeleting ? (
        <div className={`${iconSizes[size]} animate-spin border-2 border-status-error border-t-transparent rounded-full`} />
      ) : isConfirming ? (
        <Check className={iconSizes[size]} />
      ) : (
        <Trash2 className={iconSizes[size]} />
      )}
    </Button>
  );
}

