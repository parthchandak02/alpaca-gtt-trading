/**
 * Chart.js plugin for drawing trigger price labels directly on the trigger lines
 * Labels are positioned on the right side of the chart to avoid tooltip interference
 * Multiple orders at the same price are arranged horizontally along the line
 */

import { Chart } from 'chart.js';
import { formatCurrency } from '@/lib/formatters';
import { chartFonts } from '@/lib/fonts';
import { theme } from '@/lib/theme';
import { debug } from '@/lib/debug';

interface OrderDetail {
  order_index: number;
  trigger_price: number;
  status: string;
  quantity: number;
  filled_avg_price?: number | null;
}

interface ColorAxisLabelsPluginOptions {
  orderDetails: OrderDetail[];
  backgroundColor?: string;
}

// Get theme colors - matches the logic used in PriceChart.tsx
const getThemeColor = (key: keyof typeof theme.cssVariables.dark): string => {
  return theme.cssVariables.dark[key];
};

// Convert hex to rgba for background colors
const hexToRgba = (hex: string, alpha: number): string => {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
};

// Get color for label based on order status - matches trigger line colors
// Handles all Alpaca order statuses: PENDING, FILLED, PARTIALLY_FILLED, CANCELLED, FAILED, EXPIRED
const getLabelColor = (status: string): { color: string; bgColor: string } => {
  const normalizedStatus = status.toUpperCase();
  
  switch (normalizedStatus) {
    case 'FILLED':
      const filledColor = getThemeColor('chart-filled'); // Green
      return {
        color: filledColor,
        bgColor: hexToRgba(filledColor, 0.25),
      };
    case 'PARTIALLY_FILLED':
      // Light green for partially filled orders
      const partialFilledColor = '#32d74b'; // Light green
      return {
        color: partialFilledColor,
        bgColor: hexToRgba(partialFilledColor, 0.25),
      };
    case 'CANCELLED':
    case 'FAILED':
    case 'EXPIRED':
      const canceledColor = getThemeColor('chart-canceled'); // Red
      return {
        color: canceledColor,
        bgColor: hexToRgba(canceledColor, 0.25),
      };
    case 'PENDING':
    default: // Default to PENDING for unknown statuses
      const pendingColor = getThemeColor('chart-pending'); // Yellow
      return {
        color: pendingColor,
        bgColor: hexToRgba(pendingColor, 0.25),
      };
  }
};

// Helper function to draw labels directly on trigger lines
const drawTriggerLabels = (chart: Chart) => {
    const ctx = chart.ctx;
    const y1Axis = chart.scales.y1;
    const xAxis = chart.scales.x;
    // Access plugin options via index signature to avoid TypeScript errors
    const pluginOptions = (chart.options.plugins as any)?.colorAxisLabels as ColorAxisLabelsPluginOptions | undefined;
    const orderDetails = pluginOptions?.orderDetails;
    
    // Check if scales exist and are properly initialized
    if (!y1Axis || !xAxis) {
      debug.warn('[colorAxisLabelsPlugin] Required scales not found');
      return;
    }
    
    if (!orderDetails || orderDetails.length === 0) {
      return;
    }
    
    // Get chart area - check once at the beginning
    const chartArea = chart.chartArea;
    if (!chartArea) {
      debug.warn('[colorAxisLabelsPlugin] Chart area not available');
      return;
    }
    
    // Ensure scales have valid dimensions
    if (
      y1Axis.top === undefined || 
      y1Axis.bottom === undefined ||
      xAxis.left === undefined ||
      xAxis.right === undefined ||
      isNaN(y1Axis.top) ||
      isNaN(y1Axis.bottom) ||
      isNaN(xAxis.left) ||
      isNaN(xAxis.right)
    ) {
      debug.warn('[colorAxisLabelsPlugin] Scale dimensions invalid');
      return;
    }
    
    // Sort order details by display price (filled_avg_price for filled, trigger_price for others)
    // Highest to lowest - matches table sorting
    // This ensures chart labels match table order numbers
    const sortedDetails = [...orderDetails].sort((a, b) => {
      const priceA = a.status === 'FILLED' && a.filled_avg_price != null ? a.filled_avg_price : a.trigger_price;
      const priceB = b.status === 'FILLED' && b.filled_avg_price != null ? b.filled_avg_price : b.trigger_price;
      return priceB - priceA;
    });
    
    // Assign display order numbers based on sorted position (matches table logic)
    // Table uses: index + 1 where index is position in sorted array
    const detailsWithDisplayOrder = sortedDetails.map((detail, index) => ({
      ...detail,
      displayOrder: index + 1, // This matches the table's display number
    }));
    
    // Group orders by display price (with tolerance for floating point differences)
    // This handles cases where multiple orders have the same price
    const PRICE_TOLERANCE = 0.01; // 1 cent tolerance
    const priceGroups: Array<{ normalizedPrice: number; details: Array<OrderDetail & { displayOrder: number }> }> = [];
    
    detailsWithDisplayOrder.forEach((detail) => {
      // Use filled_avg_price for filled orders, trigger_price for others
      // Handle null/undefined status (unlinked orders default to PENDING)
      const status = detail.status || 'PENDING';
      const displayPrice = status === 'FILLED' && detail.filled_avg_price != null
        ? detail.filled_avg_price
        : detail.trigger_price;
      
      // Find existing group for this price (within tolerance)
      let foundGroup = false;
      for (const group of priceGroups) {
        if (Math.abs(displayPrice - group.normalizedPrice) < PRICE_TOLERANCE) {
          group.details.push(detail);
          foundGroup = true;
          break;
        }
      }
      
      // Create new group if no matching price found
      // Use the actual display price as the normalized price for this group
      if (!foundGroup) {
        priceGroups.push({
          normalizedPrice: displayPrice,
          details: [detail]
        });
      }
    });
    
    // Calculate horizontal position for labels (rightmost edge of chart to avoid tooltip)
    // Position labels at the right edge of the chart area
    const labelXPosition = xAxis.right; // Rightmost edge of the chart
    const rightMargin = 4; // Small margin from the absolute edge for readability
    
    // Draw labels for each price group
    // For groups with multiple orders, arrange them horizontally along the line
    priceGroups.forEach((group) => {
      const { normalizedPrice, details: groupDetails } = group;
      
      // Sort details within group by displayOrder (matches table order)
      // This ensures labels show the same numbers as the table
      const sortedGroupDetails = [...groupDetails].sort((a, b) => a.displayOrder - b.displayOrder);
      
      // Calculate Y position for this trigger price line
      let labelY: number;
      
      try {
        labelY = y1Axis.getPixelForValue(normalizedPrice);
      } catch (error) {
        debug.warn('[colorAxisLabelsPlugin] Error getting pixel for value', normalizedPrice, error);
        return;
      }
      
      // Validate calculated position
      if (isNaN(labelY)) {
        debug.warn('[colorAxisLabelsPlugin] Invalid labelY for trigger price', normalizedPrice);
        return;
      }
      
      // Check if position is outside chart bounds - skip drawing labels for out-of-bounds
      // Out-of-bounds triggers will be shown in summary box instead
      const margin = 5;
      if (labelY < y1Axis.top - margin || labelY > y1Axis.bottom + margin) {
        // Skip drawing labels for out-of-bounds triggers
        return;
      }
      
      // Constants for label sizing
      const horizontalSpacing = 8; // Space between labels horizontally
      const lineGapPadding = 4; // Extra padding around labels to create gap in line
      
      // Calculate total width needed for all labels in this group FIRST
      ctx.save();
      ctx.font = `11px ${chartFonts.mono}`;
      let totalLabelsWidth = 0;
      const labelWidths: number[] = [];
      const labelTexts: string[] = [];
      
      sortedGroupDetails.forEach((detail) => {
        // Use displayOrder which matches the table's order number
        const orderNum = detail.displayOrder;
        // For filled orders, show filled_avg_price; for others, show trigger_price
        // But normalizedPrice already has the correct value from grouping logic above
        const formattedPrice = formatCurrency(normalizedPrice);
        const label = `#${orderNum}: ${formattedPrice}`;
        
        const textWidth = ctx.measureText(label).width;
        labelWidths.push(textWidth);
        labelTexts.push(label);
        totalLabelsWidth += textWidth;
      });
      
      // Add spacing between labels
      totalLabelsWidth += (sortedGroupDetails.length - 1) * horizontalSpacing;
      
      // Calculate starting X position (right-align labels at the rightmost edge)
      // Position labels so they end exactly at the right edge of the chart
      let currentX = labelXPosition - totalLabelsWidth - rightMargin;
      
      // Draw background cover to hide trigger lines behind labels
      // This creates a clean gap between line end and label start
      const bgColor = getThemeColor('bg-primary');
      const gapPadding = 8; // Extra space between line end and label start
      
      // Draw background cover to hide trigger lines behind labels
      ctx.fillStyle = bgColor;
      ctx.fillRect(
        currentX - gapPadding,  // Start a bit before labels for clean gap
        labelY - 10,            // Top (covers line)
        totalLabelsWidth + gapPadding + rightMargin, // Width to cover all labels + gap
        20                      // Height to cover line
      );
      
      // Draw each label text
      sortedGroupDetails.forEach((detail, groupIndex) => {
        // Get color based on status - matches the trigger line colors
        const labelColor = getLabelColor(detail.status).color;
        const label = labelTexts[groupIndex];
        const textWidth = labelWidths[groupIndex];
        
        // Draw colored text
        ctx.fillStyle = labelColor;
        ctx.textAlign = 'left';
        ctx.textBaseline = 'middle';
        ctx.fillText(label, currentX, labelY);
        
        // Move to next label position
        currentX += textWidth + horizontalSpacing;
      });
      
      ctx.restore();
    });
};

// Tooltip z-index is handled via CSS in globals.css
// Chart.js tooltips are DOM elements, not canvas elements, so CSS z-index is the correct solution

export const colorAxisLabelsPlugin = {
  id: 'colorAxisLabels',
  // Use only afterDraw - this is the final hook called after ALL chart elements
  // including scales (grid lines), datasets, tooltips, and other plugins
  // This ensures our labels are drawn on top of everything
  afterDraw: (chart: Chart) => {
    // Draw trigger labels
    drawTriggerLabels(chart);
    // Tooltip z-index is handled via CSS - Chart.js tooltips are DOM elements
  },
};

// Note: Plugin options are accessed via type assertion in the code above
// Type declaration removed due to Chart.js v4 type compatibility issues
// The plugin works correctly with the type assertion: `as ColorAxisLabelsPluginOptions | undefined`

