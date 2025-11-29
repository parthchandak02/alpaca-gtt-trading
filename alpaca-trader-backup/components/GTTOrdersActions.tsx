'use client';

import { Button } from '@/components/ui/button';
import { Plus, Upload, Download } from 'lucide-react';

interface GTTOrdersActionsProps {
  onAddOrder: () => void;
  onUploadCSV: () => void;
  onDownloadStocksTemplate: () => void;
  onDownloadCryptoTemplate: () => void;
}

export function GTTOrdersActions({
  onAddOrder,
  onUploadCSV,
  onDownloadStocksTemplate,
  onDownloadCryptoTemplate,
}: GTTOrdersActionsProps) {
  return (
    <div className="flex flex-wrap gap-2">
      <Button onClick={onAddOrder} className="gap-1.5 text-xs h-7 px-3">
        <Plus className="h-3 w-3" />
        Add GTT Order
      </Button>
      <Button 
        onClick={onUploadCSV} 
        className="gap-1.5 text-xs h-7 px-3 bg-status-success/20 text-status-success border border-status-success/40 hover:bg-status-success/30 hover:border-status-success/50"
      >
        <Upload className="h-3 w-3" />
        Upload CSV
      </Button>
      <Button 
        onClick={onDownloadStocksTemplate} 
        className="gap-1.5 text-xs h-7 px-3 bg-status-success/20 text-status-success border border-dashed border-status-success/40 hover:bg-status-success/30 hover:border-status-success/50"
      >
        <Download className="h-3 w-3" />
        Stocks Template
      </Button>
      <Button 
        onClick={onDownloadCryptoTemplate} 
        className="gap-1.5 text-xs h-7 px-3 bg-status-success/20 text-status-success border border-dashed border-status-success/40 hover:bg-status-success/30 hover:border-status-success/50"
      >
        <Download className="h-3 w-3" />
        Crypto Template
      </Button>
    </div>
  );
}

