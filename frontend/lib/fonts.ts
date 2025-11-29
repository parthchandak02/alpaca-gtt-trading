/**
 * Standardized font configuration
 * Centralized font definitions for consistent typography across the application
 */

export const fonts = {
  // Primary sans-serif font for UI text
  sans: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
  
  // Numbers font - optimized for tabular numbers
  numbers: "'Roboto', -apple-system, BlinkMacSystemFont, sans-serif",
  
  // Monospace font for code, timestamps, and technical data
  mono: "'Roboto Mono', monospace",
} as const;

// Chart.js compatible font strings (without quotes around font names)
export const chartFonts = {
  sans: "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
  numbers: "Roboto, -apple-system, BlinkMacSystemFont, sans-serif",
  mono: "Roboto Mono, monospace",
} as const;

