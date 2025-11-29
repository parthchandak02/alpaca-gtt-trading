'use client';

import { useState, useRef, useCallback, useEffect } from 'react';
import { gttOrdersApi, assetApi } from '@/services/api';
import Papa from 'papaparse';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { GlassCard } from '@/components/glass';
import { Upload, FileText, ChevronUp, ChevronDown, RefreshCw, Loader2, CheckCircle2, X, AlertTriangle } from 'lucide-react';
import { toast } from 'sonner';
import { formatCurrency } from '@/lib/formatters';
import { debug } from '@/lib/debug';
import { useRealtimeUpdates } from '@/hooks/useRealtimeUpdates';

// Helper to format bytes
const formatBytes = (bytes: number, decimals: number = 2): string => {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
};
import { Progress } from '@/components/ui/progress';
import { cn } from '@/lib/utils';
import { GTTOrderPreviewTable } from '@/components/GTTOrderPreviewTable';

interface CSVUploadModalProps {
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

interface PreviewRow {
  symbol: string;
  company?: string;
  isFractionable?: boolean;
  orders: Array<{
    level: number;
    price: number;
    quantity: number;
    roundedQuantity?: number;
    needsRounding: boolean;
    amount: number;
    timeInForce: 'DAY' | 'GTC';
    isDuplicate?: boolean;
  }>;
  totalOrders: number;
  totalQuantity: number;
  totalValue: number;
}

export function CSVUploadModal({ open, onClose, onSuccess }: CSVUploadModalProps) {
  const [file, setFile] = useState<File | null>(null);
  const [previewData, setPreviewData] = useState<PreviewRow[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0); // File upload progress (0-50%)
  const [processingProgress, setProcessingProgress] = useState(0); // Backend processing progress (50-100%)
  const [currentStep, setCurrentStep] = useState('');
  const [expandedSymbols, setExpandedSymbols] = useState<Set<string>>(new Set());
  const [isDragging, setIsDragging] = useState(false);
  const [roundingWarnings, setRoundingWarnings] = useState<any[]>([]);
  const [duplicateWarnings, setDuplicateWarnings] = useState<any[]>([]);
  const [uploadedBytes, setUploadedBytes] = useState(0);
  const [totalBytes, setTotalBytes] = useState(0);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const uploadCompletedRef = useRef(false); // Track if upload completed, waiting for SSE event
  const fallbackTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  
  // Listen for SSE events to confirm orders are created and close modal
  useRealtimeUpdates({
    onOrdersBulkCreated: () => {
      debug.log('[CSV Upload Modal] Bulk orders created event received - confirming and closing modal');
      // Only process if we're waiting for the event (upload completed)
      if (uploadCompletedRef.current) {
        uploadCompletedRef.current = false;
        
        // Clear fallback timeout
        if (fallbackTimeoutRef.current) {
          clearTimeout(fallbackTimeoutRef.current);
          fallbackTimeoutRef.current = null;
        }
        
        // Complete progress bar
        setProcessingProgress(100);
        setCurrentStep('Orders created successfully');
        
        // Get success info and show toast
        const successInfo = (uploadCompletedRef as any).successInfo;
        if (successInfo) {
          if (successInfo.failedCount > 0) {
            const errorMessages = successInfo.failedOrders.slice(0, 3).map((fo: any) => `${fo.symbol}: ${fo.error}`).join('; ');
            const dupMessage = successInfo.duplicateWarningsData.length > 0 
              ? ` (${successInfo.duplicateWarningsData.length} duplicate${successInfo.duplicateWarningsData.length > 1 ? 's' : ''} skipped)`
              : '';
            toast.warning(
              `Created ${successInfo.createdCount} orders${dupMessage}, but ${successInfo.failedCount} failed. ${errorMessages}${successInfo.failedOrders.length > 3 ? '...' : ''}`,
              { duration: 8000 }
            );
          } else {
            const dupMessage = successInfo.duplicateWarningsData.length > 0 
              ? ` (${successInfo.duplicateWarningsData.length} duplicate${successInfo.duplicateWarningsData.length > 1 ? 's' : ''} skipped)`
              : '';
            toast.success(`Successfully created ${successInfo.createdCount} GTT order${successInfo.createdCount > 1 ? 's' : ''}${dupMessage}`);
          }
        }
        
        // Close after brief delay to show completion
        setTimeout(() => {
          onSuccess();
          onClose();
        }, 500);
      }
    },
  });
  
  // Cleanup: Reset state when modal closes
  useEffect(() => {
    if (!open) {
      // Reset upload completion flag
      uploadCompletedRef.current = false;
      // Clear any pending timeout
      if (fallbackTimeoutRef.current) {
        clearTimeout(fallbackTimeoutRef.current);
        fallbackTimeoutRef.current = null;
      }
      // Reset state
      setFile(null);
      setPreviewData([]);
      setExpandedSymbols(new Set());
      setRoundingWarnings([]);
      setDuplicateWarnings([]);
      setUploadProgress(0);
      setProcessingProgress(0);
      setCurrentStep('');
      setUploadedBytes(0);
      setTotalBytes(0);
    }
  }, [open]);

  // Calculate total progress: 50% for file upload, 50% for processing
  const totalProgress = Math.min(100, uploadProgress * 0.5 + processingProgress * 0.5);

  const handleFileSelect = useCallback((selectedFile: File) => {
    if (!selectedFile.name.endsWith('.csv')) {
      toast.error('Please select a CSV file');
      return;
    }

    setFile(selectedFile);
    parseCSV(selectedFile);
  }, []);

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (selectedFile) {
      handleFileSelect(selectedFile);
    }
  };

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);

    const droppedFile = e.dataTransfer.files?.[0];
    if (droppedFile) {
      handleFileSelect(droppedFile);
    }
  }, [handleFileSelect]);

  const handleRemoveFile = () => {
    setFile(null);
    setPreviewData([]);
    setExpandedSymbols(new Set());
    setRoundingWarnings([]);
    setDuplicateWarnings([]);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const parseCSV = async (file: File) => {
    Papa.parse(file, {
      header: true,
      skipEmptyLines: true,
      complete: async (results) => {
        try {
          if (results.errors && results.errors.length > 0) {
            debug.error('[CSV Upload] Papa.parse errors:', results.errors);
            toast.error(`CSV parsing warnings: ${results.errors.length} error(s). Check console for details.`);
          }

          const rows = results.data as any[];
          
          if (!rows || rows.length === 0) {
            debug.error('[CSV Upload] No rows found in CSV');
            toast.error('CSV file appears to be empty or invalid');
            setPreviewData([]);
            return;
          }

          // Collect all unique symbols first
          const symbols = new Set<string>();
          rows.forEach((row) => {
            const symbol = (row.Symbol || row.symbol || '').toUpperCase().trim();
            if (symbol) {
              symbols.add(symbol);
            }
          });

          if (symbols.size === 0) {
            debug.error('[CSV Upload] No symbols found. Available columns:', rows.length > 0 ? Object.keys(rows[0]) : []);
            toast.error('No symbols found in CSV. Please ensure the CSV has a "Symbol" column.');
            setPreviewData([]);
            return;
          }

          // Parse CSV and show preview IMMEDIATELY (don't wait for asset info)
          const preview: PreviewRow[] = [];
          const initialAssetInfoMap = new Map<string, boolean>(); // Start with all false (non-fractionable)

          rows.forEach((row) => {
            // Handle various symbol column name formats
            // Priority: Account column (for crypto CSVs), then Symbol column
            // If Symbol column contains a number, it's likely the first amount, not the symbol
            let symbol = (
              row.Account || 
              row.account || 
              row['Account'] || 
              row['account'] ||
              row['Account '] || // Handle trailing spaces
              ''
            ).toString().toUpperCase().trim();
            
            // Fallback to Symbol column if Account not found
            if (!symbol) {
              symbol = (
                row.Symbol || 
                row.symbol || 
                row['Symbol'] || 
                row['symbol'] ||
                row['Symbol '] || // Handle trailing spaces
                ''
              ).toString().toUpperCase().trim();
            }
            
            // If symbol looks like a number (e.g., "0.03159"), it's probably the first amount
            // Try Account column instead
            if (symbol && !isNaN(parseFloat(symbol)) && symbol.includes('.')) {
              // This is likely a quantity, try Account column
              const accountSymbol = (
                row.Account || 
                row.account || 
                row['Account'] || 
                row['account'] ||
                row['Account '] ||
                ''
              ).toString().toUpperCase().trim();
              if (accountSymbol) {
                symbol = accountSymbol;
              }
            }
            
            if (!symbol) return;

            // Use initial map (will be updated later when asset info arrives)
            const isFractionable = initialAssetInfoMap.get(symbol) || false;
            const orders: PreviewRow['orders'] = [];
            
            // Try ladder format first (Amt 1, Price 1, etc.)
            // Handle various column name formats (with/without spaces, different cases)
            // Special case: If Symbol column contains a number, treat it as Amt 1
            let firstAmtFromSymbol = null;
            const symbolColumnValue = (
              row.Symbol || 
              row.symbol || 
              row['Symbol'] || 
              row['symbol'] ||
              row['Symbol '] ||
              ''
            ).toString().trim();
            
            // Check if Symbol column is actually the first amount (numeric)
            if (symbolColumnValue && !isNaN(parseFloat(symbolColumnValue)) && symbolColumnValue.includes('.')) {
              firstAmtFromSymbol = parseFloat(symbolColumnValue.replace(/[,$]/g, ''));
            }
            
            for (let i = 1; i <= 8; i++) { // Support up to 8 levels
              const amtKeyVariations = [`Amt ${i}`, `amt ${i}`, `Amt ${i} `, `amt ${i} `];
              const priceKeyVariations = [`Price ${i}`, `price ${i}`, `Price ${i} `, `price ${i} `];
              
              let amtValue: any = null;
              let priceValue: any = null;
              
              // Special handling for first amount: use Symbol column if it's numeric
              if (i === 1 && firstAmtFromSymbol !== null) {
                amtValue = firstAmtFromSymbol;
              } else {
                // Try each variation until we find a match
                for (const key of amtKeyVariations) {
                  if (row[key] !== undefined && row[key] !== null && row[key] !== '') {
                    amtValue = row[key];
                    break;
                  }
                }
              }
              
              for (const key of priceKeyVariations) {
                if (row[key] !== undefined && row[key] !== null && row[key] !== '') {
                  priceValue = row[key];
                  break;
                }
              }
              
              const amt = parseFloat((amtValue || '').toString().replace(/[,$]/g, ''));
              const price = parseFloat((priceValue || '').toString().replace(/[,$]/g, ''));

              if (amt && price && amt > 0 && price > 0 && !isNaN(amt) && !isNaN(price)) {
                // Check if rounding is needed
                const isActuallyFractional = Math.abs(amt - Math.floor(amt)) > 0.000001;
                const needsRounding = !isFractionable && isActuallyFractional;
                const roundedQty = needsRounding ? Math.round(amt) : amt;
                
                // Determine TIF: Crypto always uses GTC, stocks use DAY for fractional, GTC for whole
                const isCrypto = symbol.includes('/');
                const timeInForce: 'DAY' | 'GTC' = isCrypto 
                  ? 'GTC'  // Crypto only supports GTC and IOC
                  : (isActuallyFractional ? 'DAY' : 'GTC');  // Stocks: DAY for fractional, GTC for whole

                orders.push({
                  level: i,
                  quantity: amt,
                  roundedQuantity: needsRounding ? roundedQty : undefined,
                  needsRounding,
                  price,
                  amount: amt * price,
                  timeInForce,
                  isDuplicate: false, // Will be set after backend validation
                });
              }
            }

            if (orders.length > 0) {
              preview.push({
                symbol,
                company: row.Company || row.company || '',
                isFractionable,
                orders,
                totalOrders: orders.length,
                totalQuantity: orders.reduce((sum, o) => sum + o.quantity, 0),
                totalValue: orders.reduce((sum, o) => sum + o.amount, 0),
              });
            }
          });

          if (preview.length === 0) {
            debug.error('[CSV Upload] No valid orders found. Checked', rows.length, 'rows. First row columns:', rows.length > 0 ? Object.keys(rows[0]) : []);
            toast.error('No valid orders found in CSV. Please check that columns "Amt 1", "Price 1", etc. contain valid numbers.');
            setPreviewData([]);
            return;
          }

          // Show preview IMMEDIATELY (before fetching asset info)
          setPreviewData(preview);
          toast.success(`Preview successful: ${preview.length} symbol(s) found with ${preview.reduce((sum, p) => sum + p.totalOrders, 0)} total orders`);

          // Fetch asset info in the background and update preview as it arrives
          // Use a timeout to prevent hanging on slow/failed requests
          const fetchAssetInfo = async () => {
            const assetInfoMap = new Map<string, boolean>();
            const fetchPromises = Array.from(symbols).map(async (symbol) => {
              try {
                // Add timeout to prevent hanging (5 seconds per request)
                const timeoutPromise = new Promise((_, reject) => 
                  setTimeout(() => reject(new Error('Timeout')), 5000)
                );
                const response = await Promise.race([
                  assetApi.getAssetInfo(symbol).catch(err => {
                    // Gracefully handle 404s (symbol not found)
                    if (err?.response?.status === 404) {
                      return { data: { fractionable: false } }; // Default to non-fractionable
                    }
                    throw err;
                  }),
                  timeoutPromise
                ]) as any;
                assetInfoMap.set(symbol, response.data?.fractionable || false);
              } catch (error) {
                // Only log server errors (500+), not timeouts or network errors
                if (error && typeof error === 'object' && 'response' in error && (error as any).response?.status >= 500) {
                  debug.error(`[CSV Upload] Server error fetching asset info for ${symbol}:`, error);
                }
                assetInfoMap.set(symbol, false); // Default to not fractionable
              }
            });

            // Wait for all requests with a maximum timeout (30 seconds total)
            await Promise.race([
              Promise.all(fetchPromises),
              new Promise(resolve => setTimeout(resolve, 30000))
            ]);

            // Update preview with asset info
            setPreviewData(prevPreview => 
              prevPreview.map(row => ({
                ...row,
                isFractionable: assetInfoMap.get(row.symbol) || false,
                orders: row.orders.map(order => {
                  const isActuallyFractional = Math.abs(order.quantity - Math.floor(order.quantity)) > 0.000001;
                  const needsRounding = !(assetInfoMap.get(row.symbol) || false) && isActuallyFractional;
                  return {
                    ...order,
                    needsRounding,
                    roundedQuantity: needsRounding ? Math.round(order.quantity) : undefined,
                  };
                })
              }))
            );
          };

          // Fetch asset info in background (don't await)
          fetchAssetInfo().catch(err => {
            debug.error('[CSV Upload] Error fetching asset info:', err);
            // Preview already shown, so this is non-critical
          });

        } catch (error) {
          debug.error('[CSV Upload] Error parsing CSV:', error);
          toast.error(`Failed to parse CSV file: ${error instanceof Error ? error.message : 'Unknown error'}`);
          setPreviewData([]);
        }
      },
      error: (error) => {
        debug.error('[CSV Upload] Papa.parse error:', error);
        toast.error(`CSV parsing failed: ${error.message || 'Unknown error'}`);
        setPreviewData([]);
      },
    });
  };

  const handleUpload = async () => {
    if (!file) {
      toast.error('Please select a file first');
      return;
    }

    if (previewData.length === 0) {
      debug.error('[CSV Upload] Upload attempted but no preview data available');
      toast.error('Please ensure CSV file is parsed correctly. No valid orders found.');
      return;
    }
    
    const totalOrdersCount = previewData.reduce((sum, row) => sum + row.totalOrders, 0);
    if (totalOrdersCount === 0) {
      debug.error('[CSV Upload] Upload attempted but total orders is 0');
      toast.error('No valid orders found in CSV. Please check the file format.');
      return;
    }
    
    setIsUploading(true);
    setUploadProgress(0);
    setProcessingProgress(0);
    setUploadedBytes(0);
    setTotalBytes(file.size);
    setCurrentStep('Uploading file...');

    // Track progress timeout for cleanup (must be outside try block for catch access)
    let progressTimeout: NodeJS.Timeout | null = null;

    try {
      // Same logic as manual orders: if duplicateWarnings exist, clicking the button confirms them
      const shouldConfirmDuplicates = duplicateWarnings.length > 0;
      
      // For small files, show immediate feedback since progress might not fire
      const isSmallFile = file.size < 10000; // Less than 10KB
      
      // Start a fallback progress indicator for small files
      if (isSmallFile) {
        // Show 10% immediately to indicate upload started
        setUploadProgress(10);
        setUploadedBytes(Math.floor(file.size * 0.1));
        
        // Simulate progress for small files (since real progress might not fire)
        progressTimeout = setInterval(() => {
          setUploadProgress(prev => {
            if (prev < 90) {
              return Math.min(90, prev + 10);
            }
            return prev;
          });
        }, 200);
      }
      
      // Track file upload progress
      const handleUploadProgress = (progressEvent: { loaded: number; total: number; percent: number }) => {
        // Clear fallback timer if real progress is firing
        if (progressTimeout) {
          clearInterval(progressTimeout);
          progressTimeout = null;
        }
        
        // Defensive checks to prevent errors
        if (!progressEvent || typeof progressEvent.loaded !== 'number' || typeof progressEvent.total !== 'number') {
          return;
        }
        
        const percent = progressEvent.percent ?? Math.round((progressEvent.loaded * 100) / (progressEvent.total || 1));
        
        setUploadedBytes(progressEvent.loaded);
        setTotalBytes(progressEvent.total);
        setUploadProgress(percent);
        
        if (percent < 100) {
          setCurrentStep(`Uploading file... ${Math.round(percent)}%`);
        } else {
          // Upload complete, switch to processing
          setCurrentStep('Processing orders...');
          setProcessingProgress(10);
        }
      };

      // Simulate processing progress while API call is in progress
      // Use a flag to track when upload completes
      let uploadFinished = false;
      const originalHandleProgress = handleUploadProgress;
      const enhancedHandleProgress = (progressEvent: { loaded: number; total: number; percent: number }) => {
        try {
          originalHandleProgress(progressEvent);
          const percent = progressEvent.percent ?? Math.round((progressEvent.loaded * 100) / (progressEvent.total || 1));
          if (percent >= 100) {
            uploadFinished = true;
          }
        } catch (error) {
          debug.error('[CSV Upload] Error in upload progress handler:', error);
        }
      };

      const simulateProcessing = async () => {
        const steps = [
          { label: 'Validating CSV data', progress: 20 },
          { label: 'Processing orders', progress: 40 },
          { label: 'Creating GTT orders', progress: 60 },
          { label: 'Generating order ladders', progress: 80 },
        ];
        
        // Wait for upload to complete first (check every 200ms)
        while (!uploadFinished) {
          await new Promise(resolve => setTimeout(resolve, 200));
        }
        
        // Then simulate processing steps (but stop at 80% - wait for SSE for final confirmation)
        for (let i = 0; i < steps.length; i++) {
          setCurrentStep(steps[i].label);
          setProcessingProgress(steps[i].progress);
          await new Promise(resolve => setTimeout(resolve, 300)); // Slightly faster, more realistic
        }
        
        // Don't go to 95% here - let the API response handler set it to 95% and wait for SSE
      };

      // Start processing simulation in parallel
      const processingPromise = simulateProcessing();

      // Make API call with real upload progress tracking
      // Add timeout wrapper to detect if backend is down
      const uploadPromise = gttOrdersApi.uploadCSV(
        file, 
        true, // Always confirm rounding
        shouldConfirmDuplicates,
        enhancedHandleProgress
      );
      
      // Add a timeout to detect if backend is not responding
      const timeoutPromise = new Promise((_, reject) => {
        setTimeout(() => {
          reject(new Error('Upload timeout: Backend may not be running. Please check if the backend server is started.'));
        }, 10000); // 10 second timeout
      });
      
      const apiResponse = await Promise.race([uploadPromise, timeoutPromise]) as any;

      // Clear any fallback timer
      if (progressTimeout) {
        clearInterval(progressTimeout);
        progressTimeout = null;
      }

      // Stop processing simulation
      uploadFinished = true;

      // Ensure upload shows 100%
      setUploadProgress(100);
      setUploadedBytes(file.size);
      
      // Set processing to 95% - wait for SSE to confirm before completing
      setProcessingProgress(95);
      setCurrentStep('Waiting for confirmation...');

      const response = apiResponse.data;
      const createdCount = response.created_count || response.orders?.length || 0;
      const failedCount = response.failed_count || 0;
      const duplicateWarningsData = response.duplicate_warnings || [];
      const roundingWarningsData = response.rounding_warnings || [];
      
      // First call: Check if we have NEW warnings (not yet confirmed)
      // If we already confirmed duplicates (shouldConfirmDuplicates=true), these are just informational
      if (!shouldConfirmDuplicates && duplicateWarningsData.length > 0) {
        setDuplicateWarnings(duplicateWarningsData);
        setRoundingWarnings(roundingWarningsData); // Always show rounding info
        setUploadProgress(0);
        setProcessingProgress(0);
        setCurrentStep('');
        setIsUploading(false);
        return;
      }
      
      // Success path: All confirmed, proceed
      setRoundingWarnings([]);
      setDuplicateWarnings([]);
      
      // Store success info for toast (will show after SSE confirmation)
      const successInfo = {
        createdCount,
        failedCount,
        duplicateWarningsData,
        failedOrders: response.failed_orders || [],
      };
      
      // Mark upload as completed - wait for SSE event to confirm and close modal
      uploadCompletedRef.current = true;
      (uploadCompletedRef as any).successInfo = successInfo; // Store success info
      debug.log('[CSV Upload Modal] Upload completed, waiting for SSE event to confirm');
      
      // Fallback: If SSE event doesn't arrive within 3 seconds, complete anyway
      fallbackTimeoutRef.current = setTimeout(() => {
        if (uploadCompletedRef.current) {
          debug.warn('[CSV Upload Modal] SSE event timeout - completing anyway');
          // Complete progress and show toast
          setProcessingProgress(100);
          setCurrentStep('Orders created successfully');
          
          // Show toast
          if (successInfo.failedCount > 0) {
            const errorMessages = successInfo.failedOrders.slice(0, 3).map((fo: any) => `${fo.symbol}: ${fo.error}`).join('; ');
            const dupMessage = successInfo.duplicateWarningsData.length > 0 
              ? ` (${successInfo.duplicateWarningsData.length} duplicate${successInfo.duplicateWarningsData.length > 1 ? 's' : ''} skipped)`
              : '';
            toast.warning(
              `Created ${successInfo.createdCount} orders${dupMessage}, but ${successInfo.failedCount} failed. ${errorMessages}${successInfo.failedOrders.length > 3 ? '...' : ''}`,
              { duration: 8000 }
            );
          } else {
            const dupMessage = successInfo.duplicateWarningsData.length > 0 
              ? ` (${successInfo.duplicateWarningsData.length} duplicate${successInfo.duplicateWarningsData.length > 1 ? 's' : ''} skipped)`
              : '';
            toast.success(`Successfully created ${successInfo.createdCount} GTT order${successInfo.createdCount > 1 ? 's' : ''}${dupMessage}`);
          }
          
          // Close after brief delay
          setTimeout(() => {
            uploadCompletedRef.current = false;
            fallbackTimeoutRef.current = null;
            onSuccess();
            onClose();
          }, 500);
        }
      }, 3000);
      
      // Note: Modal will close when SSE event arrives or after 5 second timeout
      // State reset happens in useEffect cleanup when modal closes
      // Don't reset state here - let useEffect handle it when modal closes
    } catch (error: any) {
      // Clear any fallback timer
      if (progressTimeout) {
        clearInterval(progressTimeout);
        progressTimeout = null;
      }
      
      // Stop progress on error
      setUploadProgress(0);
      setProcessingProgress(0);
      setCurrentStep('');
      
      // Better error handling
      let errorMessage = 'Failed to upload CSV';
      
      if (error.code === 'ECONNABORTED' || error.message?.includes('timeout') || error.message?.includes('Backend may not be running')) {
        errorMessage = error.message || 'Upload timed out. The backend server may not be running. Please start the backend server and try again.';
      } else if (error.code === 'ERR_NETWORK' || error.message?.includes('Network Error')) {
        errorMessage = 'Cannot connect to backend server. Please ensure the backend is running on http://localhost:8000';
      } else if (error.response?.data?.detail) {
        errorMessage = error.response.data.detail;
      } else if (error.message) {
        errorMessage = error.message;
      }
      
      debug.error('[CSV Upload] Upload error:', error);
      toast.error(errorMessage, { duration: 10000 });
    } finally {
      setIsUploading(false);
    }
  };

  const toggleExpand = (symbol: string) => {
    const newExpanded = new Set(expandedSymbols);
    if (newExpanded.has(symbol)) {
      newExpanded.delete(symbol);
    } else {
      newExpanded.add(symbol);
    }
    setExpandedSymbols(newExpanded);
  };

  const totalOrders = previewData.reduce((sum, row) => sum + row.totalOrders, 0);

  const handleClose = () => {
    // Clear all state when modal closes
    setRoundingWarnings([]);
    setDuplicateWarnings([]);
    onClose();
  };

  return (
    <>
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
        <DialogHeader className="pb-2 border-b border-border-divider">
          <DialogTitle className="text-lg font-semibold mb-2 flex items-center gap-2">
            {roundingWarnings.length > 0 && (
              <AlertTriangle className="h-5 w-5 text-yellow-500 flex-shrink-0" />
            )}
            Upload Stocks/ETFs CSV
          </DialogTitle>
          <DialogDescription className="hidden">
            Upload a CSV file to create multiple GTT orders at once.
          </DialogDescription>
          
          {/* File Name & Preview in Header */}
          <div className="flex items-center justify-between gap-3 text-sm">
            {file ? (
              <div className="flex items-center gap-2 flex-1 min-w-0">
                <FileText className="h-4 w-4 text-accent-blue flex-shrink-0" />
                <span className="text-text-primary truncate">{file.name}</span>
                <span className="text-text-tertiary">({(file.size / 1024).toFixed(2)} KB)</span>
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleRemoveFile();
                  }}
                  className="flex-shrink-0 p-1 rounded hover:bg-bg-hover text-text-tertiary hover:text-text-primary transition-colors"
                  aria-label="Remove file"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              </div>
            ) : (
              <div className="flex items-center gap-2 text-text-tertiary">
                <Upload className="h-4 w-4" />
                <span>Drag & drop CSV file or click to browse</span>
              </div>
            )}
            
            {previewData.length > 0 && (
              <div className="flex items-center gap-2 flex-shrink-0">
                {roundingWarnings.length === 0 && duplicateWarnings.length === 0 ? (
                  <CheckCircle2 className="h-4 w-4 text-status-success" />
                ) : (
                  <AlertTriangle className="h-4 w-4 text-yellow-500" />
                )}
                <span className="text-text-primary font-medium">
                  {previewData.length} symbol(s) • {totalOrders} orders
                </span>
              </div>
            )}
          </div>
        </DialogHeader>

        <div className="space-y-3">
          {/* File Upload - Modern Drag & Drop */}
          {!file && (
            <div className="space-y-2">
              <Label className="text-sm font-medium text-text-primary">CSV File</Label>
              
              {/* Drag & Drop Zone */}
              <div
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                className={cn(
                  "relative border-2 border-dashed rounded-lg transition-all duration-200",
                  isDragging
                    ? "border-accent-blue bg-accent-blue/5 scale-[1.02]"
                    : "border-border-primary hover:border-border-divider",
                  "bg-bg-secondary/50 cursor-pointer"
                )}
                onClick={() => fileInputRef.current?.click()}
              >
                <input
                  ref={fileInputRef}
                  id="csv-file"
                  type="file"
                  accept=".csv"
                  onChange={handleFileInputChange}
                  className="hidden"
                />
                
                <div className="flex flex-col items-center justify-center p-4 text-center">
                  <div className="mb-2 p-2 rounded-full bg-bg-card border border-border-primary">
                    <Upload className="h-5 w-5 text-text-tertiary" />
                  </div>
                  <p className="text-sm font-medium text-text-primary mb-0.5">
                    Drag & drop your CSV file here
                  </p>
                  <p className="text-xs text-text-tertiary">
                    or click to browse
                  </p>
                </div>
              </div>
            </div>
          )}



          {/* Fractional Rounding Warning */}
          {roundingWarnings.length > 0 && (
            <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-lg p-3">
              <div className="flex items-start gap-2">
                <AlertTriangle className="h-4 w-4 text-yellow-500 flex-shrink-0 mt-0.5" />
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-medium text-text-primary mb-1">
                    Fractional Quantities Auto-Rounded
                  </p>
                  <p className="text-xs text-text-secondary">
                    {roundingWarnings.length} stock{roundingWarnings.length > 1 ? 's' : ''} don't support fractional quantities. Quantities will be rounded to whole numbers.
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Duplicate Orders Warning */}
          {duplicateWarnings.length > 0 && (
            <div className="bg-accent-orange/10 border border-accent-orange/30 rounded-lg p-3">
              <div className="flex items-start gap-2">
                <AlertTriangle className="h-4 w-4 text-accent-orange flex-shrink-0 mt-0.5" />
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-medium text-text-primary mb-1">
                    Duplicate Orders Detected
                  </p>
                  <p className="text-xs text-text-secondary">
                    {duplicateWarnings.length} order{duplicateWarnings.length > 1 ? 's' : ''} already exist with the same symbol and trigger price. They will be skipped to prevent duplicates.
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Preview Cards */}
          {previewData.length > 0 && (
            <div className="space-y-1.5 max-h-96 overflow-y-auto">
                {previewData.map((row, index) => (
                  <GlassCard key={`${row.symbol}-${index}`} className="p-2 hover:border-border-divider transition-colors">
                    <div
                      className="flex items-center justify-between cursor-pointer group"
                      onClick={() => toggleExpand(row.symbol)}
                    >
                      <div className="flex items-center gap-2.5 flex-1 min-w-0">
                        <div className="flex-shrink-0 w-7 h-7 rounded-lg bg-accent-stock/10 border border-accent-stock/20 flex items-center justify-center">
                          <span className="text-xs font-bold text-accent-stock">{row.symbol.charAt(0)}</span>
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-3">
                            <h4 className="font-semibold text-text-primary text-sm">{row.symbol}</h4>
                            {row.company && (
                              <span className="text-xs text-text-secondary truncate">{row.company}</span>
                            )}
                          </div>
                          <div className="flex items-center gap-4 text-xs mt-0.5">
                            <span className="text-text-tertiary">Total Value • Orders:</span>
                            <span className="text-accent-cash font-semibold font-numbers">{formatCurrency(row.totalValue)}</span>
                            <span className="text-text-primary font-semibold font-numbers">• {row.totalOrders}</span>
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center flex-shrink-0 ml-3">
                        <div className="p-1 rounded-lg group-hover:bg-bg-hover transition-colors">
                          {expandedSymbols.has(row.symbol) ? (
                            <ChevronUp className="h-3.5 w-3.5 text-text-secondary" />
                          ) : (
                            <ChevronDown className="h-3.5 w-3.5 text-text-secondary" />
                          )}
                        </div>
                      </div>
                    </div>

                    {expandedSymbols.has(row.symbol) && (
                      <div className="mt-2 pt-2 border-t border-border-divider">
                        <GTTOrderPreviewTable
                          orders={row.orders.map(order => ({
                            ...order,
                            value: order.amount,
                            isDuplicate: duplicateWarnings.some(
                              (dup: any) => dup.symbol === row.symbol && Math.abs(dup.trigger_price - order.price) < 0.01
                            )
                          }))}
                          showDuplicates={duplicateWarnings.length > 0}
                          totalValue={row.totalValue}
                        />
                      </div>
                    )}
                  </GlassCard>
                ))}
            </div>
          )}
        </div>

        {/* Progress Indicator */}
        {isUploading && (
          <div className="space-y-2 pt-2 border-t border-border-divider">
            <div className="flex items-center justify-between text-xs">
              <span className="text-text-secondary flex items-center gap-2">
                {totalProgress < 100 ? (
                  <>
                    <Loader2 className="h-3 w-3 animate-spin" />
                    {currentStep || 'Processing...'}
                  </>
                ) : (
                  <>
                    <CheckCircle2 className="h-3 w-3 text-status-success" />
                    {currentStep || 'Complete'}
                  </>
                )}
              </span>
              <span className="text-text-tertiary font-mono">{Math.round(totalProgress)}%</span>
            </div>
            <Progress value={totalProgress} className="h-1.5" />
            
            {/* Detailed progress info */}
            {uploadProgress < 100 && totalBytes > 0 && (
              <div className="flex items-center justify-between text-[10px] text-text-tertiary">
                <span>Uploading: {formatBytes(uploadedBytes)} / {formatBytes(totalBytes)}</span>
                <span>{Math.round(uploadProgress)}% uploaded</span>
              </div>
            )}
            
            {uploadProgress >= 100 && processingProgress < 100 && (
              <div className="flex items-center justify-between text-[10px] text-text-tertiary">
                <span>Processing {previewData.length} symbol(s) • {totalOrders} orders</span>
                <span>{Math.round(processingProgress)}% processed</span>
              </div>
            )}
          </div>
        )}

        {/* Footer - Different buttons based on warnings state */}
        <DialogFooter className="gap-2 pt-3">
          <Button 
            type="button" 
            variant="outline" 
            onClick={handleClose}
            disabled={isUploading}
            className="min-w-[90px] h-9 text-sm"
          >
            Cancel
          </Button>
          
          {/* Compact fractional warning in footer */}
          {previewData.some(row => row.orders.some(o => o.needsRounding)) && (
            <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-lg px-3 py-2 mr-auto">
              <div className="flex items-center gap-2">
                <AlertTriangle className="h-3.5 w-3.5 text-yellow-500 flex-shrink-0" />
                <div className="flex flex-col gap-0.5">
                  <span className="text-xs font-medium text-text-primary">Fractions Rounded</span>
                  <a 
                    href="https://docs.alpaca.markets/docs/fractional-trading" 
                    target="_blank" 
                    rel="noopener noreferrer"
                    className="text-[10px] text-accent-blue hover:underline"
                  >
                    Learn more →
                  </a>
                </div>
              </div>
            </div>
          )}
          
          <Button
            onClick={handleUpload}
            disabled={isUploading || previewData.length === 0 || totalOrders === 0}
            className={`gap-2 min-w-[160px] h-9 text-sm font-medium shadow-lg transition-all ${
              duplicateWarnings.length > 0
                ? 'bg-red-600 hover:bg-red-700 text-white'
                : 'bg-accent-yellow hover:opacity-90 text-bg-primary'
            }`}
          >
            {isUploading ? (
              <>
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                Uploading...
              </>
            ) : duplicateWarnings.length > 0 ? (
              <>
                <AlertTriangle className="h-3.5 w-3.5" />
                Create Duplicates
              </>
            ) : (
              <>
                <Upload className="h-3.5 w-3.5" />
                Create {totalOrders} GTT orders
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
    </>
  );
}

