'use client';

import { useVersionCheck } from '@/hooks/useVersionCheck';
import { GlassCard } from '@/components/glass';
import { Button } from '@/components/ui/button';
import { RefreshCw, X, Info } from 'lucide-react';

/**
 * Version Update Dialog
 * 
 * Shows a dialog when a new version is detected, prompting user to refresh.
 */
export function VersionUpdateDialog() {
  const {
    showUpdateDialog,
    latestVersion,
    versionInfo,
    refreshPage,
    dismissDialog,
  } = useVersionCheck();

  if (!showUpdateDialog) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <GlassCard className="max-w-md p-6 space-y-4 animate-in fade-in zoom-in duration-200">
        {/* Header */}
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-accent-primary/20">
              <Info className="h-5 w-5 text-accent-primary" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-text-primary">
                New Version Available
              </h2>
              <p className="text-sm text-text-secondary">
                Please refresh to get the latest updates
              </p>
            </div>
          </div>
          <Button
            variant="ghost"
            size="icon"
            onClick={dismissDialog}
            className="h-8 w-8 text-text-tertiary hover:text-text-primary"
          >
            <X className="h-4 w-4" />
          </Button>
        </div>

        {/* Version Info */}
        {versionInfo && (
          <div className="space-y-2 p-3 rounded-lg bg-bg-tertiary/50 border border-border-divider">
            <div className="flex justify-between text-sm">
              <span className="text-text-tertiary">Current Version:</span>
              <span className="font-mono text-text-secondary">{versionInfo.version}</span>
            </div>
            {latestVersion && (
              <div className="flex justify-between text-sm">
                <span className="text-text-tertiary">New Version:</span>
                <span className="font-mono text-accent-success">{latestVersion}</span>
              </div>
            )}
            <div className="flex justify-between text-sm">
              <span className="text-text-tertiary">Last Build:</span>
              <span className="text-text-secondary">{versionInfo.buildTimeReadable}</span>
            </div>
          </div>
        )}

        {/* Message */}
        <p className="text-sm text-text-secondary">
          A new version has been deployed. To ensure you have the latest features and fixes, 
          please refresh your browser.
        </p>

        {/* Actions */}
        <div className="flex gap-3 pt-2">
          <Button
            onClick={refreshPage}
            className="flex-1 gap-2"
          >
            <RefreshCw className="h-4 w-4" />
            Refresh Now
          </Button>
          <Button
            variant="ghost"
            onClick={dismissDialog}
            className="flex-1 text-text-secondary hover:text-text-primary"
          >
            Later
          </Button>
        </div>
      </GlassCard>
    </div>
  );
}


