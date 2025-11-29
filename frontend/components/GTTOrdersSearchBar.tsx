'use client';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { GlassCard } from '@/components/glass';
import { Search, ArrowUp, ArrowDown, RefreshCw, ChevronDown, ChevronUp } from 'lucide-react';
import { cn } from '@/lib/utils';

type SortField = 'name' | 'price' | 'dateCreated' | 'lastActivity';
type FilterType = 'all' | 'stocks' | 'crypto';

interface GTTOrdersSearchBarProps {
  searchQuery: string;
  onSearchChange: (query: string) => void;
  sortField: SortField | null;
  sortDirection: 'asc' | 'desc';
  onSort: (field: SortField) => void;
  filterType: FilterType;
  onFilterChange: (type: FilterType) => void;
  onRefresh?: () => void;
  expandAll?: boolean;
  onToggleExpandAll?: () => void;
}

export function GTTOrdersSearchBar({
  searchQuery,
  onSearchChange,
  sortField,
  sortDirection,
  onSort,
  filterType,
  onFilterChange,
  onRefresh,
  expandAll,
  onToggleExpandAll,
}: GTTOrdersSearchBarProps) {
  return (
    <GlassCard className="p-2">
      <div className="flex flex-col sm:flex-row gap-2 sm:gap-3 items-stretch sm:items-center">
        {/* Search */}
        <div className="relative flex-1 min-w-0 flex items-center gap-1.5">
          <div className="relative flex-1 min-w-0">
            <Search className="absolute left-2 top-1/2 transform -translate-y-1/2 h-3.5 w-3.5 text-text-tertiary pointer-events-none" />
            <Input
              placeholder="Search by symbol or company..."
              value={searchQuery}
              onChange={(e) => onSearchChange(e.target.value)}
              className="pl-8 h-7 text-xs w-full"
            />
          </div>
          
          {/* Sort Buttons */}
          <div className="flex items-center gap-0.5 flex-shrink-0 flex-wrap">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onSort('name')}
              className={cn(
                "h-7 px-1.5 text-[10px] transition-all rounded-md border flex items-center gap-0.5 whitespace-nowrap",
                sortField === 'name'
                  ? "bg-bg-card text-text-primary border-border-primary"
                  : "text-text-secondary hover:text-text-primary hover:bg-bg-hover/50 border-transparent"
              )}
              title="Sort by Name"
            >
              Name
              {sortField === 'name' && (
                sortDirection === 'asc' ? (
                  <ArrowUp className="h-2.5 w-2.5" />
                ) : (
                  <ArrowDown className="h-2.5 w-2.5" />
                )
              )}
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onSort('price')}
              className={cn(
                "h-7 px-1.5 text-[10px] transition-all rounded-md border flex items-center gap-0.5 whitespace-nowrap",
                sortField === 'price'
                  ? "bg-bg-card text-text-primary border-border-primary"
                  : "text-text-secondary hover:text-text-primary hover:bg-bg-hover/50 border-transparent"
              )}
              title="Sort by Price"
            >
              Price
              {sortField === 'price' && (
                sortDirection === 'asc' ? (
                  <ArrowUp className="h-2.5 w-2.5" />
                ) : (
                  <ArrowDown className="h-2.5 w-2.5" />
                )
              )}
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onSort('dateCreated')}
              className={cn(
                "h-7 px-1.5 text-[10px] transition-all rounded-md border flex items-center gap-0.5 whitespace-nowrap",
                sortField === 'dateCreated'
                  ? "bg-bg-card text-text-primary border-border-primary"
                  : "text-text-secondary hover:text-text-primary hover:bg-bg-hover/50 border-transparent"
              )}
              title="Sort by Date Created"
            >
              Created
              {sortField === 'dateCreated' && (
                sortDirection === 'asc' ? (
                  <ArrowUp className="h-2.5 w-2.5" />
                ) : (
                  <ArrowDown className="h-2.5 w-2.5" />
                )
              )}
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onSort('lastActivity')}
              className={cn(
                "h-7 px-1.5 text-[10px] transition-all rounded-md border flex items-center gap-0.5 whitespace-nowrap",
                sortField === 'lastActivity'
                  ? "bg-bg-card text-text-primary border-border-primary"
                  : "text-text-secondary hover:text-text-primary hover:bg-bg-hover/50 border-transparent"
              )}
              title="Sort by Last Activity"
            >
              Activity
              {sortField === 'lastActivity' && (
                sortDirection === 'asc' ? (
                  <ArrowUp className="h-2.5 w-2.5" />
                ) : (
                  <ArrowDown className="h-2.5 w-2.5" />
                )
              )}
            </Button>
          </div>
        </div>
        
        {/* Filter Toggle */}
        <div className="flex items-center gap-0.5 bg-bg-tertiary rounded-md p-0.5 border border-border-divider flex-shrink-0">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onFilterChange('all')}
            className={cn(
              "h-6 px-3 text-xs transition-all rounded-md",
              filterType === 'all'
                ? "bg-bg-card text-text-primary shadow-sm"
                : "text-text-secondary hover:text-text-primary hover:bg-bg-hover/50"
            )}
          >
            All
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onFilterChange('stocks')}
            className={cn(
              "h-6 px-3 text-xs transition-all rounded-md",
              filterType === 'stocks'
                ? "bg-yellow-900/30 text-text-primary shadow-sm border border-yellow-800/40"
                : "text-yellow-700/70 hover:text-yellow-600 hover:bg-yellow-900/20 border border-yellow-900/20"
            )}
          >
            Stocks
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onFilterChange('crypto')}
            className={cn(
              "h-6 px-3 text-xs transition-all rounded-md",
              filterType === 'crypto'
                ? "bg-gradient-to-br from-[rgba(219,39,119,0.25)] via-[rgba(236,72,153,0.2)] to-[rgba(219,39,119,0.25)] text-text-primary shadow-sm border border-[rgba(236,72,153,0.5)] backdrop-blur-[20px]"
                : "text-[rgba(236,72,153,0.7)] hover:text-[rgba(236,72,153,0.9)] hover:bg-[rgba(219,39,119,0.15)] border border-[rgba(236,72,153,0.2)]"
            )}
          >
            Crypto
          </Button>
        </div>

        {/* Prices Refresh and Expand/Collapse */}
        {(onRefresh || onToggleExpandAll) && (
          <div className="flex items-center gap-2 flex-shrink-0">
            {onRefresh && (
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
            )}
            
            {onToggleExpandAll && (
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
            )}
          </div>
        )}
      </div>
    </GlassCard>
  );
}

