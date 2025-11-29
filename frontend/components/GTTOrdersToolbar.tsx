'use client';

import { Button } from '@/components/ui/button';
import { GlassCard } from '@/components/glass';
import { RefreshCw, ChevronDown, ChevronUp, LogOut } from 'lucide-react';

interface GTTOrdersToolbarProps {
  onRefresh: () => void;
  expandAll: boolean;
  onToggleExpandAll: () => void;
  onLogout: () => void;
}

export function GTTOrdersToolbar({
  onRefresh,
  expandAll,
  onToggleExpandAll,
  onLogout,
}: GTTOrdersToolbarProps) {
  return (
    <GlassCard className="p-1.5 sm:p-2.5">
      <div className="flex items-center justify-between gap-2 sm:gap-2 md:gap-3">
        {/* Refresh Prices */}
        <Button
          variant="ghost"
          size="sm"
          onClick={onRefresh}
          className="h-7 px-2 gap-1.5 text-text-secondary hover:text-text-primary hover:bg-bg-hover"
          title="Refresh Prices"
        >
          <RefreshCw className="h-4 w-4" />
          <span className="text-xs font-medium">Prices</span>
        </Button>
        
        {/* Expand/Collapse All */}
        <Button
          variant="ghost"
          size="sm"
          onClick={onToggleExpandAll}
          className="h-7 px-2 gap-1.5 rounded-md border border-border-divider/50 text-text-secondary hover:text-text-primary hover:bg-bg-hover hover:border-border-divider"
          title={expandAll ? 'Collapse All' : 'Expand All'}
        >
          {expandAll ? (
            <ChevronUp className="h-4 w-4" />
          ) : (
            <ChevronDown className="h-4 w-4" />
          )}
          <span className="text-xs font-medium">{expandAll ? 'Collapse' : 'Expand'}</span>
        </Button>
        
        {/* Logout */}
        <Button 
          variant="ghost" 
          size="icon" 
          onClick={onLogout} 
          className="h-7 w-7 text-status-error hover:text-status-error hover:bg-status-error/10"
          title="Logout"
        >
          <LogOut className="h-3.5 w-3.5" />
        </Button>
      </div>
    </GlassCard>
  );
}

