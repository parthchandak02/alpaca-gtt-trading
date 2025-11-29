import { useCallback } from 'react';
import { gttOrdersApi } from '@/services/api';
import { toast } from 'sonner';
import { debug } from '@/lib/debug';

/**
 * Hook to handle template downloads (stocks and crypto)
 * Provides download handlers for CSV templates
 */
export function useTemplateDownloads() {
  const handleDownloadStocksTemplate = useCallback(async () => {
    try {
      const response = await gttOrdersApi.getStocksTemplate();
      // Handle blob response correctly
      const blob = response.data instanceof Blob 
        ? response.data 
        : new Blob([response.data], { type: 'text/csv' });
      
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'gtt_template_stocks.csv';
      a.style.display = 'none';
      document.body.appendChild(a);
      a.click();
      
      // Clean up
      setTimeout(() => {
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
      }, 100);
      
      toast.success('Stocks template downloaded successfully');
    } catch (error: any) {
      debug.error('Download stocks template error:', error);
      toast.error('Failed to download stocks template', {
        description: error.response?.data?.detail || error.message || 'Please try again',
      });
    }
  }, []);

  const handleDownloadCryptoTemplate = useCallback(async () => {
    try {
      const response = await gttOrdersApi.getCryptoTemplate();
      // Handle blob response correctly
      const blob = response.data instanceof Blob 
        ? response.data 
        : new Blob([response.data], { type: 'text/csv' });
      
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'gtt_template_crypto.csv';
      a.style.display = 'none';
      document.body.appendChild(a);
      a.click();
      
      // Clean up
      setTimeout(() => {
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
      }, 100);
      
      toast.success('Crypto template downloaded successfully');
    } catch (error: any) {
      debug.error('Download crypto template error:', error);
      toast.error('Failed to download crypto template', {
        description: error.response?.data?.detail || error.message || 'Please try again',
      });
    }
  }, []);

  return {
    handleDownloadStocksTemplate,
    handleDownloadCryptoTemplate,
  };
}

