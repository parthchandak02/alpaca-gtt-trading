/**
 * Beautiful, standardized theme configuration
 * Refined colors, spacing, and design tokens for a polished UI
 */

export const theme = {
  cssVariables: {
    dark: {
      // Background colors - refined with better depth
      'bg-primary': '#0d0d0d',           // Slightly lighter for better contrast
      'bg-secondary': '#161618',         // Header/secondary backgrounds
      'bg-tertiary': '#1c1c1e',          // Tertiary backgrounds
      'bg-card': '#1a1a1c',              // Card backgrounds with subtle elevation
      'bg-hover': '#252528',              // Hover states
      'bg-elevated': '#222225',           // Elevated surfaces
      'bg-overlay': 'rgba(0, 0, 0, 0.6)', // Modal overlays
      
      // Text colors - improved hierarchy
      'text-primary': '#ffffff',
      'text-secondary': '#b3b3b6',       // Better contrast
      'text-tertiary': '#8e8e93',        // Muted text
      'text-disabled': '#636366',        // Disabled text
      
      // Accent colors - refined palette
      'accent-cash': '#34c759',          // Vibrant green for cash
      'accent-stock': '#ffcc00',         // Bright yellow for stock/ETF
      'accent-crypto': '#ec4899',        // Bright pink for crypto (matches crypto cards)
      'accent-yellow': '#ffcc00',        // Bright yellow for primary actions
      'accent-blue': '#007aff',          // System blue for links/actions
      'accent-orange': '#ff9500',        // Orange for warnings
      
      // Status colors - refined with better contrast
      'status-success': '#34c759',       // Success green
      'status-warning': '#ff9500',       // Warning orange
      'status-error': '#ff3b30',         // Error red
      'status-pending': '#ffcc00',       // Pending yellow
      'status-filled': '#34c759',        // Filled green
      'status-info': '#007aff',          // Info blue
      
      // Border colors - subtle and refined
      'border-primary': '#2c2c2e',       // Primary borders
      'border-secondary': '#1c1c1e',     // Secondary borders
      'border-divider': '#38383a',       // Dividers
      
      // Shadow colors for depth
      'shadow-sm': '0 1px 2px rgba(0, 0, 0, 0.3)',
      'shadow-md': '0 4px 6px rgba(0, 0, 0, 0.4)',
      'shadow-lg': '0 10px 15px rgba(0, 0, 0, 0.5)',
      'shadow-xl': '0 20px 25px rgba(0, 0, 0, 0.6)',
      
      // Chart colors - refined palette
      'chart-line': '#ffffff',
      'chart-grid': '#2c2c2e',
      'chart-pending': '#ffcc00',
      'chart-placed': '#007aff',
      'chart-filled': '#34c759',
      'chart-canceled': '#ff3b30',
      
      // Interactive states
      'focus-ring': '#007aff',
      'focus-ring-offset': '#1a1a1c',
    }
  }
}

// Generate CSS variables
export function generateThemeCSS(): string {
  const vars: string[] = []
  for (const [key, value] of Object.entries(theme.cssVariables.dark)) {
    vars.push(`  --${key}: ${value};`)
  }
  return `:root {\n${vars.join('\n')}\n}`
}

