import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/**
 * Check if a symbol is crypto
 * Matches backend logic: checks for '/' separator or common crypto symbols
 * NOTE: Ambiguous symbols (BCH, LINK, SOL) are NOT included here - they need asset class check
 */
export function isCryptoSymbol(symbol: string): boolean {
  const symbolUpper = symbol.toUpperCase();
  
  // Check for '/' separator (trading format: BTC/USD, ETH/USD) - definitely crypto
  if (symbolUpper.includes('/')) {
    return true;
  }
  
  // Check for common crypto symbols (without /USD suffix)
  // Excluded ambiguous symbols: BCH (Bitcoin Cash vs Banco de Chile), 
  // LINK (Chainlink vs Interlink Electronics), SOL (Solana vs Emeren Group)
  const commonCryptoSymbols = [
    'BTC', 'ETH', 'DOGE', 'MATIC', 'AVAX', 'ALGO', 
    'SHIB', 'ADA', 'DOT', 'LTC', 'XRP', 'ETC', 'TRUMP',
    'BTCUSD', 'ETHUSD', 'DOGEUSD', 'XRPUSD'
  ];
  
  return commonCryptoSymbols.includes(symbolUpper);
}

