import type { Config } from "tailwindcss";
import { fonts } from "./lib/fonts";

// Extract font names from fonts.ts (remove quotes and use array format for Tailwind)
const getFontArray = (fontString: string): string[] => {
  // Remove quotes and split by comma, then clean up
  return fontString
    .replace(/'/g, '')
    .split(',')
    .map(f => f.trim());
};

const config: Config = {
  darkMode: ["class"],
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: getFontArray(fonts.sans),
        numbers: getFontArray(fonts.numbers),
        mono: getFontArray(fonts.mono),
      },
      colors: {
        // Background colors
        'bg-primary': 'var(--bg-primary)',
        'bg-secondary': 'var(--bg-secondary)',
        'bg-tertiary': 'var(--bg-tertiary)',
        'bg-card': 'var(--bg-card)',
        'bg-hover': 'var(--bg-hover)',
        'bg-elevated': 'var(--bg-elevated)',
        'bg-overlay': 'var(--bg-overlay)',
        
        // Text colors
        'text-primary': 'var(--text-primary)',
        'text-secondary': 'var(--text-secondary)',
        'text-tertiary': 'var(--text-tertiary)',
        'text-disabled': 'var(--text-disabled)',
        
        // Accent colors
        'accent-cash': 'var(--accent-cash)',
        'accent-stock': 'var(--accent-stock)',
        'accent-crypto': 'var(--accent-crypto)',
        'accent-yellow': 'var(--accent-yellow)',
        'accent-blue': 'var(--accent-blue)',
        'accent-orange': 'var(--accent-orange)',
        
        // Status colors
        'status-success': 'var(--status-success)',
        'status-warning': 'var(--status-warning)',
        'status-error': 'var(--status-error)',
        'status-pending': 'var(--status-pending)',
        'status-filled': 'var(--status-filled)',
        'status-info': 'var(--status-info)',
        
        // Border colors
        'border-primary': 'var(--border-primary)',
        'border-secondary': 'var(--border-secondary)',
        'border-divider': 'var(--border-divider)',
        
        // Chart colors
        'chart-line': 'var(--chart-line)',
        'chart-grid': 'var(--chart-grid)',
        'chart-pending': 'var(--chart-pending)',
        'chart-placed': 'var(--chart-placed)',
        'chart-filled': 'var(--chart-filled)',
        'chart-canceled': 'var(--chart-canceled)',
        
        // shadcn/ui defaults
        background: 'var(--bg-primary)',
        foreground: 'var(--text-primary)',
        ring: 'var(--focus-ring)',
      },
      boxShadow: {
        'sm': 'var(--shadow-sm)',
        'md': 'var(--shadow-md)',
        'lg': 'var(--shadow-lg)',
        'xl': 'var(--shadow-xl)',
      },
    },
  },
  plugins: [],
};

export default config;

