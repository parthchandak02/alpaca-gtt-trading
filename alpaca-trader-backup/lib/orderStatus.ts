/**
 * Order status utilities for consistent badge styling
 * Yellow = Pending, Green = Filled, Red = Cancelled/Failed/Expired
 */

type OrderStatus = 
  | 'PENDING'
  | 'FILLED'
  | 'PARTIALLY_FILLED'
  | 'CANCELLED'
  | 'FAILED'
  | 'EXPIRED';

type BadgeVariant = 'success' | 'warning' | 'destructive' | 'secondary';

/**
 * Get the badge variant for an order status
 * Yellow = Pending, Green = Filled, Red = Cancelled/Failed/Expired
 */
export function getStatusBadgeVariant(status: string): BadgeVariant {
  const normalizedStatus = status.toUpperCase();
  
  switch (normalizedStatus) {
    case 'FILLED':
      return 'success'; // Green
    case 'PENDING':
      return 'warning'; // Yellow
    case 'PARTIALLY_FILLED':
      return 'success'; // Green (light green would be ideal but we'll use success)
    case 'CANCELLED':
    case 'FAILED':
    case 'EXPIRED':
      return 'destructive'; // Red
    default:
      return 'secondary'; // Gray for unknown statuses
  }
}

/**
 * Format status text for display (always uppercase)
 */
export function formatStatusText(status: string): string {
  const normalizedStatus = status.toUpperCase();
  
  switch (normalizedStatus) {
    case 'PARTIALLY_FILLED':
      return 'PARTIALLY FILLED';
    case 'CANCELLED':
      return 'CANCELLED';
    case 'FAILED':
      return 'FAILED';
    case 'EXPIRED':
      return 'EXPIRED';
    case 'PENDING':
      return 'PENDING';
    case 'FILLED':
      return 'FILLED';
    default:
      return normalizedStatus; // Return uppercase for unknown statuses
  }
}

