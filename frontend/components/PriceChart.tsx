'use client';

import { useEffect, useState, useRef, useMemo, useCallback } from 'react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler,
  ChartOptions,
  ChartData,
  TooltipItem,
} from 'chart.js';
import { Line } from 'react-chartjs-2';
import { historicalBarsApi } from '@/services/api';
import { formatCurrency } from '@/lib/formatters';
import { debug } from '@/lib/debug';
import { chartFonts } from '@/lib/fonts';
import { theme } from '@/lib/theme';
import { colorAxisLabelsPlugin } from '@/lib/chart-plugin';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
);

// Type definitions
interface Bar {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
}

interface OrderDetail {
  order_index: number;
  trigger_price: number;
  quantity: number;
  status: 'PENDING' | 'FILLED' | 'PARTIALLY_FILLED' | 'CANCELLED' | 'FAILED' | 'EXPIRED' | string | null;
  filled_avg_price?: number | null;
}

interface Order {
  symbol: string;
  initial_trigger_price: number;
}

interface PriceChartProps {
  order: Order;
  orderDetails: OrderDetail[];
}

interface ChartDataWithBars extends ChartData<'line'> {
  bars?: Bar[];
}

type Timeframe = '1D' | '1W' | '1M' | '3M' | '6M' | '1Y' | 'MAX';

const TIMEFRAMES: Timeframe[] = ['1D', '1W', '1M', '3M', '6M', '1Y', 'MAX'];

const TIMEFRAME_DAYS: Record<Timeframe, number> = {
  '1D': 1,
  '1W': 7,
  '1M': 30,
  '3M': 90,
  '6M': 180,
  '1Y': 365,
  'MAX': 2555, // ~7 years (Alpaca provides 7+ years of historical data)
};

// Get theme colors as RGB values for Chart.js
const getThemeColor = (key: keyof typeof theme.cssVariables.dark): string => {
  return theme.cssVariables.dark[key];
};

const hexToRgba = (hex: string, alpha: number): string => {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
};

export function PriceChart({ order, orderDetails }: PriceChartProps) {
  const [chartData, setChartData] = useState<ChartDataWithBars | null>(null);
  const [timeframe, setTimeframe] = useState<Timeframe>('1M');
  const [isLoading, setIsLoading] = useState(true);
  const [lastFetchTime, setLastFetchTime] = useState<Date | null>(null);
  const chartRef = useRef<ChartJS<'line'>>(null);
  const chartCacheRef = useRef<Map<string, ChartDataWithBars>>(new Map());

  // Dynamic date formatter based on timeframe
  const formatDateLabel = useCallback((timestamp: string, currentTimeframe: Timeframe): string => {
    const date = new Date(timestamp);
    
    switch (currentTimeframe) {
      case '1D':
        // For 1 day, show time (hour:minute)
        return date.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true });
      case '1W':
        // For 1 week, show day name and date
        return date.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
      case '1M':
        // For 1 month, show month and day
        return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
      case '3M':
      case '6M':
        // For 3-6 months, show month and day (more spacing needed)
        return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
      case '1Y':
        // For 1 year, show month and year
        return date.toLocaleDateString('en-US', { month: 'short', year: 'numeric' });
      case 'MAX':
        // For MAX (7+ years), show month and year
        return date.toLocaleDateString('en-US', { month: 'short', year: 'numeric' });
      default:
        return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    }
  }, []);

  // Memoized function to process chart data
  const processChartData = useCallback((bars: Bar[]) => {
    debug.group('Processing chart data');
    debug.log('Processing', bars.length, 'bars');
    
    const labels = bars.map(bar => formatDateLabel(bar.timestamp, timeframe));

    const closePrices = bars.map(bar => bar.close);
    
    debug.log('Price ranges:', {
      close: { min: Math.min(...closePrices), max: Math.max(...closePrices) },
    });

    // Create datasets - price line uses left Y-axis
    const datasets: ChartData<'line'>['datasets'] = [
      {
        label: 'Close Price',
        data: closePrices,
        borderColor: getThemeColor('chart-line'),
        backgroundColor: hexToRgba(getThemeColor('chart-line'), 0.06),
        borderWidth: 2,
        fill: true,
        tension: 0.1,
        pointRadius: 0,
        pointHoverRadius: 4,
        pointHoverBackgroundColor: getThemeColor('chart-line'),
        pointHoverBorderColor: getThemeColor('chart-line'),
        pointHoverBorderWidth: 2,
        yAxisID: 'y',
      },
    ];

    // Add order trigger lines - they will use right Y-axis
    // Lines are full-width; the plugin will cover the right end with labels
    orderDetails.forEach((detail) => {
      // For FILLED orders, use filled_avg_price; for others, use trigger_price
      const displayPrice = detail.status === 'FILLED' && detail.filled_avg_price != null
        ? detail.filled_avg_price
        : detail.trigger_price;
      const triggerLine = new Array(bars.length).fill(displayPrice);
      
      let borderColor: string;
      let borderDash: number[] = [5, 5];
      
      // Handle null/undefined status (unlinked orders default to PENDING)
      const status = detail.status || 'PENDING';
      switch (status) {
        case 'FILLED':
          borderColor = getThemeColor('chart-filled'); // Green solid line
          borderDash = [];
          break;
        case 'PARTIALLY_FILLED':
          borderColor = '#32d74b'; // Light green for partially filled
          borderDash = [3, 3]; // Shorter dashes to differentiate from fully filled
          break;
        case 'CANCELLED':
        case 'FAILED':
        case 'EXPIRED':
          borderColor = getThemeColor('chart-canceled'); // Red dashed line
          borderDash = [10, 5];
          break;
        default: // PENDING or null/undefined
          borderColor = getThemeColor('chart-pending'); // Yellow dashed line
          borderDash = [5, 5];
      }

      // Label shows filled price for filled orders, trigger price for others
      const priceLabel = detail.status === 'FILLED' && detail.filled_avg_price != null
        ? formatCurrency(detail.filled_avg_price)
        : formatCurrency(detail.trigger_price);

      datasets.push({
        label: `#${detail.order_index + 1}: ${detail.quantity}@${priceLabel}`,
        data: triggerLine,
        borderColor,
        backgroundColor: 'transparent',
        borderWidth: 1.5,
        borderDash,
        pointRadius: 0,
        pointHoverRadius: 0,
        yAxisID: 'y1',
      });
    });

    debug.log('Order details for chart:', orderDetails.length);
    orderDetails.forEach((detail, idx) => {
      debug.log(`Order #${idx + 1}:`, {
        trigger: detail.trigger_price,
        status: detail.status,
      });
    });
    
    const processedData = {
      labels,
      datasets,
      bars, // Store bars for tooltip
    };
    
    setChartData(processedData);
    
    // Cache the bars data (keyed by symbol and timeframe)
    // Note: We cache bars, not the full chartData, because orderDetails change
    const cacheKey = `${order.symbol}-${timeframe}`;
    chartCacheRef.current.set(cacheKey, processedData);
    
    // Limit cache size to prevent memory issues (keep last 10)
    if (chartCacheRef.current.size > 10) {
      const firstKey = chartCacheRef.current.keys().next().value;
      if (firstKey !== undefined) {
        chartCacheRef.current.delete(firstKey);
      }
    }
    
    debug.groupEnd();
  }, [orderDetails, timeframe, formatDateLabel, order.symbol]);

  // Fetch chart data
  useEffect(() => {
    const abortController = new AbortController();
    let isMounted = true;

    const fetchChartData = async () => {
      try {
        setIsLoading(true);
        const days = TIMEFRAME_DAYS[timeframe];
        
        // Check cache first (cache key includes symbol and timeframe)
        const cacheKey = `${order.symbol}-${timeframe}`;
        const cachedData = chartCacheRef.current.get(cacheKey);
        if (cachedData) {
          debug.log(`Using cached chart data for ${cacheKey}`);
          setChartData(cachedData);
          setIsLoading(false);
          return;
        }
        
        debug.group(`Fetching chart data for ${order.symbol}`);
        debug.log('Timeframe:', timeframe, 'Days:', days);
        
        // For 1D, use minute bars for intraday data
        // For other timeframes, use daily bars
        let alpacaTimeframe: string;
        let requestDays: number;
        
        if (timeframe === '1D') {
          // Request minute bars for intraday view
          // Market hours: 9:30 AM - 4:00 PM ET = 6.5 hours = 390 minutes
          // Request 1 day but use minute timeframe
          alpacaTimeframe = 'Minute';
          requestDays = 1; // Still use 1 day for the date range
        } else {
          // Use daily bars for weekly/monthly/yearly views
          alpacaTimeframe = 'Day';
          requestDays = days;
        }
        
        debug.log('Alpaca timeframe:', alpacaTimeframe, 'Request days:', requestDays);
        
        // Add timeout to prevent hanging
        const timeoutPromise = new Promise((_, reject) => {
          setTimeout(() => reject(new Error('Chart data fetch timeout')), 8000); // 8s timeout
        });
        
        const response = await Promise.race([
          historicalBarsApi.getBars(order.symbol, requestDays, alpacaTimeframe, abortController.signal),
          timeoutPromise,
        ]) as any;
        
        const bars = response.data.bars || [];
        
        // Check if component is still mounted before updating state
        if (!isMounted) return;
        
        debug.log('Received bars:', bars.length);
        if (bars.length > 0) {
          debug.log('First bar:', bars[0]);
          debug.log('Last bar:', bars[bars.length - 1]);
          debug.log('Price range:', {
            min: Math.min(...bars.map((b: Bar) => b.close)),
            max: Math.max(...bars.map((b: Bar) => b.close)),
          });
        }

        if (bars.length === 0) {
          debug.warn('No historical bars received from Alpaca API');
          setChartData(null);
        } else {
          debug.log('Processing real Alpaca data:', bars.length, 'bars');
          processChartData(bars);
          setLastFetchTime(new Date());
        }
      } catch (error: any) {
        // Don't log AbortError as an error - it's expected when component unmounts
        if (error.name === 'AbortError' || error.name === 'CanceledError' || error.code === 'ERR_CANCELED') {
          debug.log('Chart data fetch cancelled (component unmounted)');
          return;
        }
        // Only update state if component is still mounted
        if (isMounted) {
          debug.error('Error fetching chart data:', error);
          setChartData(null);
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
          debug.groupEnd();
        }
      }
    };

    fetchChartData();

    // Cleanup: abort request when component unmounts or dependencies change
    return () => {
      isMounted = false;
      abortController.abort();
    };
  }, [order.symbol, order.initial_trigger_price, orderDetails, timeframe, processChartData]);

  // Fix tooltip z-index - Chart.js tooltips are DOM elements, not canvas
  useEffect(() => {
    const fixTooltipZIndex = () => {
      const chartContainer = document.getElementById('chart-container');
      if (!chartContainer) return;

      // Chart.js tooltips are appended as divs to the canvas parent
      const tooltips = chartContainer.querySelectorAll('canvas + div, div[class*="tooltip"]');
      tooltips.forEach((tooltip) => {
        if (tooltip instanceof HTMLElement) {
          tooltip.style.zIndex = '9999';
          tooltip.style.pointerEvents = 'none';
        }
      });
    };

    // Fix z-index immediately and on mutations (when tooltips are created)
    fixTooltipZIndex();
    const observer = new MutationObserver(fixTooltipZIndex);
    const chartContainer = document.getElementById('chart-container');
    if (chartContainer) {
      observer.observe(chartContainer, { childList: true, subtree: true });
    }

    return () => observer.disconnect();
  }, [chartData]);

  // Calculate price range from chart data for axis synchronization
  const priceRange = useMemo(() => {
    if (!chartData || !chartData.datasets || chartData.datasets.length === 0) {
      return { min: undefined, max: undefined };
    }
    
    // Get close prices from the first dataset (price line)
    const closePriceDataset = chartData.datasets[0];
    if (!closePriceDataset.data || closePriceDataset.data.length === 0) {
      return { min: undefined, max: undefined };
    }
    
    const prices = closePriceDataset.data as number[];
    const minPrice = Math.min(...prices);
    const maxPrice = Math.max(...prices);
    
    // Add padding (5% on each side) for better visualization
    const padding = (maxPrice - minPrice) * 0.05;
    
    return {
      min: minPrice - padding,
      max: maxPrice + padding,
    };
  }, [chartData]);

  // Memoized chart options for performance
  const chartOptions = useMemo<ChartOptions<'line'>>(() => {
    const bgPrimary = getThemeColor('bg-primary');
    const textPrimary = getThemeColor('text-primary');
    const textSecondary = getThemeColor('text-secondary');
    const textTertiary = getThemeColor('text-tertiary');
    const borderDivider = getThemeColor('border-divider');

    return {
      responsive: true,
      maintainAspectRatio: false,
      // Disable animations for better performance
      animation: {
        duration: 0,
      },
      transitions: {
        active: {
          animation: {
            duration: 0,
          },
        },
      },
      interaction: {
        mode: 'index',
        intersect: false,
      },
      plugins: {
        legend: {
          display: false,
        },
        colorAxisLabels: {
          orderDetails: orderDetails,
          backgroundColor: bgPrimary,
        },
        tooltip: {
          enabled: true,
          mode: 'index',
          intersect: false,
          backgroundColor: bgPrimary, // Fully opaque - no transparency so grid lines don't show through
          titleColor: textPrimary,
          bodyColor: textSecondary,
          borderColor: hexToRgba(textPrimary, 0.12),
          borderWidth: 1,
          cornerRadius: 6,
          padding: {
            top: 8,
            bottom: 8,
            left: 12,
            right: 12,
          },
        titleFont: {
          size: 12,
          weight: 'bold' as const,
          family: chartFonts.numbers,
        },
          bodyFont: {
            size: 11,
            family: chartFonts.mono,
          },
          boxPadding: 4,
          titleSpacing: 6,
          bodySpacing: 4,
          displayColors: true,
          usePointStyle: true,
          callbacks: {
            title: (items: TooltipItem<'line'>[]) => {
              if (!chartData || items.length === 0) return '';
              const index = items[0].dataIndex;
              return chartData.labels?.[index]?.toString() || '';
            },
            filter: (tooltipItem: TooltipItem<'line'>) => {
              // Only show tooltip for the price line, hide order lines
              return tooltipItem.datasetIndex === 0;
            },
            label: (context: TooltipItem<'line'>) => {
              const datasetLabel = context.dataset.label || '';
              
              // Only show OHLC data for price line
              if (datasetLabel === 'Close Price' && chartData?.bars) {
                const bar = chartData.bars[context.dataIndex];
                if (bar) {
                  return [
                    `Open: ${formatCurrency(bar.open)}`,
                    `High: ${formatCurrency(bar.high)}`,
                    `Low: ${formatCurrency(bar.low)}`,
                    `Close: ${formatCurrency(bar.close)}`,
                  ];
                }
              }
              
              return [];
            },
            labelTextColor: (context: TooltipItem<'line'>) => {
              const datasetLabel = context.dataset.label || '';
              const labelText = context.label || '';
              
              // Color code OHLC data based on price direction
              if (datasetLabel === 'Close Price' && chartData?.bars) {
                const bar = chartData.bars[context.dataIndex];
                if (bar) {
                  const isBullish = bar.close > bar.open;
                  const isBearish = bar.close < bar.open;
                  
                  // Determine color based on which OHLC value this label represents
                  if (labelText.startsWith('Open:')) {
                    return textSecondary; // Open - neutral gray
                  } else if (labelText.startsWith('High:')) {
                    return getThemeColor('status-success'); // High - green
                  } else if (labelText.startsWith('Low:')) {
                    return getThemeColor('status-error'); // Low - red
                  } else if (labelText.startsWith('Close:')) {
                    // Close - directional color based on bullish/bearish
                    return isBullish 
                      ? getThemeColor('status-success') 
                      : isBearish 
                        ? getThemeColor('status-error') 
                        : textSecondary;
                  }
                }
              }
              
              return textPrimary;
            },
          },
        },
      },
      scales: {
        x: {
          grid: {
            color: hexToRgba(textPrimary, 0.03),
            drawBorder: false,
            lineWidth: 1,
          },
          ticks: {
            color: textTertiary,
            font: {
              size: 11,
              family: chartFonts.mono,
            },
            maxRotation: timeframe === '1D' ? 0 : 45,
            minRotation: timeframe === '1D' ? 0 : 45,
            padding: 6,
            // Show fewer ticks for longer timeframes to avoid crowding
            maxTicksLimit: timeframe === '1D' ? 12 : 
                          timeframe === '1W' ? 7 :
                          timeframe === '1M' ? 10 :
                          timeframe === '3M' ? 8 :
                          timeframe === '6M' ? 8 :
                          timeframe === '1Y' ? 12 :
                          timeframe === 'MAX' ? 14 : 10,
          },
        },
        y: {
          type: 'linear',
          position: 'left',
          grid: {
            color: hexToRgba(textPrimary, 0.03),
            drawBorder: false,
            lineWidth: 1,
          },
          ticks: {
            color: textPrimary,
            font: {
              size: 11,
              family: chartFonts.mono,
            },
            padding: 8,
            callback: function(value) {
              return formatCurrency(Number(value));
            },
          },
        },
        y1: {
          type: 'linear',
          position: 'right',
          // Synchronize with y axis scale - use same min/max as price data
          // This ensures trigger lines align correctly with the price chart
          min: priceRange.min,
          max: priceRange.max,
          // Keep scale visible for plugin access, but hide all visual elements
          // Labels are now drawn directly on the trigger lines in the middle of the chart
          display: true,
          grid: {
            display: false,
            drawBorder: false,
          },
          ticks: {
            display: false, // Hide all ticks - labels are on the lines themselves
          },
          // Hide the axis line itself
          border: {
            display: false,
          },
        },
      },
    };
  }, [orderDetails, chartData, priceRange]);

  return (
    <div>
      {/* Time period selector - always visible */}
      <div className="flex items-center justify-end mb-2">
        <div className="flex gap-1" role="tablist" aria-label="Chart timeframe selector">
          {TIMEFRAMES.map((tf) => (
            <button
              key={tf}
              onClick={() => setTimeframe(tf)}
              role="tab"
              aria-selected={timeframe === tf}
              aria-controls="chart-container"
              className={`px-2 py-0.5 rounded text-xs font-medium transition-colors ${
                timeframe === tf
                  ? 'bg-accent-yellow text-black'
                  : 'bg-bg-hover text-text-secondary hover:text-text-primary'
              }`}
            >
              {tf}
            </button>
          ))}
        </div>
      </div>

      {/* Chart content */}
      {isLoading ? (
        <div className="h-64 sm:h-80 flex items-center justify-center" role="status" aria-label="Loading chart data">
          <div className="text-text-secondary">Loading chart...</div>
        </div>
      ) : !chartData ? (
        <div className="h-64 sm:h-80 flex items-center justify-center" role="status" aria-label="No chart data available">
          <div className="text-text-secondary">No chart data available</div>
        </div>
      ) : (
        <div 
          className="h-64 sm:h-80 relative min-h-0" 
          id="chart-container"
          role="img" 
          aria-label={`Price chart for ${order.symbol} showing ${timeframe} timeframe with ${orderDetails.length} trigger orders`}
        >
          <Line 
            ref={chartRef} 
            data={chartData} 
            options={chartOptions}
            plugins={[colorAxisLabelsPlugin]}
            updateMode="none" // Use 'none' for better performance, or 'default' for animations
          />
        </div>
      )}
      
      {/* Legend and Out-of-Bounds Summary */}
      <div className="flex items-center flex-wrap justify-center gap-2 sm:gap-4 mt-3 text-[10px] sm:text-xs" role="list" aria-label="Chart legend">
        <div className="flex items-center gap-1 sm:gap-1.5" role="listitem">
          <div className="w-5 sm:w-6 h-0.5 bg-white flex-shrink-0" aria-hidden="true"></div>
          <span className="text-text-secondary whitespace-nowrap">Close Price</span>
        </div>
        <div className="flex items-center gap-1 sm:gap-1.5" role="listitem">
          <div className="w-5 sm:w-6 h-0.5 border-t-2 border-dashed border-status-warning flex-shrink-0" aria-hidden="true"></div>
          <span className="text-text-secondary whitespace-nowrap">
            <span className="hidden sm:inline">Pending Triggers</span>
            <span className="sm:hidden">Pending</span>
          </span>
        </div>
        <div className="flex items-center gap-1 sm:gap-1.5" role="listitem">
          <div className="w-5 sm:w-6 h-0.5 border-t-2 border-dashed border-status-success flex-shrink-0" aria-hidden="true"></div>
          <span className="text-text-secondary whitespace-nowrap">
            <span className="hidden sm:inline">Filled Triggers</span>
            <span className="sm:hidden">Filled</span>
          </span>
        </div>
        <div className="flex items-center gap-1 sm:gap-1.5" role="listitem">
          <div className="w-5 sm:w-6 h-0.5 border-t-2 border-dashed border-status-error flex-shrink-0" aria-hidden="true"></div>
          <span className="text-text-secondary whitespace-nowrap">
            <span className="hidden sm:inline">Canceled Triggers</span>
            <span className="sm:hidden">Canceled</span>
          </span>
        </div>
        
        {/* Out-of-Bounds Summary Box - now on same line */}
        {(() => {
          if (!chartData || !priceRange.min || !priceRange.max) return null;
          
          // Calculate out-of-bounds triggers
          const triggersAbove = orderDetails.filter(d => d.trigger_price > priceRange.max).length;
          const triggersBelow = orderDetails.filter(d => d.trigger_price < priceRange.min).length;
          
          if (triggersAbove === 0 && triggersBelow === 0) return null;
          
          return (
            <>
              {triggersAbove > 0 && (
                <div className="flex items-center gap-1 sm:gap-1.5 px-1.5 sm:px-2 py-0.5 sm:py-1 rounded bg-bg-card border border-border-primary flex-shrink-0" role="listitem">
                  <span className="text-status-warning">↑</span>
                  <span className="text-text-secondary whitespace-nowrap">
                    <span className="text-text-primary font-medium">{triggersAbove}</span>
                    <span className="hidden sm:inline"> above range</span>
                  </span>
                </div>
              )}
              {triggersBelow > 0 && (
                <div className="flex items-center gap-1 sm:gap-1.5 px-1.5 sm:px-2 py-0.5 sm:py-1 rounded bg-bg-card border border-border-primary flex-shrink-0" role="listitem">
                  <span className="text-status-warning">↓</span>
                  <span className="text-text-secondary whitespace-nowrap">
                    <span className="text-text-primary font-medium">{triggersBelow}</span>
                    <span className="hidden sm:inline"> below range</span>
                  </span>
                </div>
              )}
            </>
          );
        })()}
      </div>
    </div>
  );
}
