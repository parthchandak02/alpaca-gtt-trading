'use client';

import { AlertTriangle, TriangleAlert } from 'lucide-react';
import { formatCurrency, formatQuantity } from '@/lib/formatters';

interface OrderLevel {
  level: number;
  quantity: number;
  roundedQuantity?: number;
  needsRounding: boolean;
  price: number;
  value: number;
  timeInForce: 'DAY' | 'GTC';
  isDuplicate?: boolean;
}

interface GTTOrderPreviewTableProps {
  orders: OrderLevel[];
  showDuplicates?: boolean;
  totalValue: number;
  isCrypto?: boolean; // Whether this is a crypto order (for dynamic decimal formatting)
}

export function GTTOrderPreviewTable({ 
  orders, 
  showDuplicates = false,
  totalValue,
  isCrypto = false
}: GTTOrderPreviewTableProps) {
  return (
    <div className="bg-bg-card border border-border-primary rounded-lg overflow-hidden">
      <table className="w-full text-xs">
        <thead className="bg-bg-secondary border-b border-border-divider">
          <tr>
            <th className="px-4 py-2.5 text-left text-text-tertiary font-medium w-16">Level</th>
            <th className="px-4 py-2.5 text-right text-text-tertiary font-medium min-w-[120px]">Quantity</th>
            <th className="px-4 py-2.5 text-right text-text-tertiary font-medium min-w-[100px]">Price</th>
            <th className="px-4 py-2.5 text-right text-text-tertiary font-medium min-w-[100px]">Value</th>
            <th className="px-4 py-2.5 text-center text-text-tertiary font-medium w-20">TIF</th>
            {showDuplicates && <th className="px-4 py-2.5 text-center text-text-tertiary font-medium w-20">Duplicates</th>}
          </tr>
        </thead>
        <tbody className="divide-y divide-border-divider">
          {orders.map((order) => (
            <tr key={order.level} className="hover:bg-bg-secondary/50">
              <td className="px-4 py-2.5 text-text-secondary">{order.level}</td>
              <td className="px-4 py-2.5 text-right font-numbers text-text-primary">
                {order.needsRounding ? (
                  <span className="flex items-center justify-end gap-1">
                    <span className="line-through text-red-400">{formatQuantity(order.quantity, isCrypto)}</span>
                    <span>→</span>
                    <span className="text-green-400 font-medium">{order.roundedQuantity}</span>
                  </span>
                ) : (
                  formatQuantity(order.quantity, isCrypto)
                )}
              </td>
              <td className="px-4 py-2.5 text-right font-numbers text-text-primary">
                {formatCurrency(order.price)}
              </td>
              <td className="px-4 py-2.5 text-right font-numbers text-text-primary">
                {formatCurrency(order.value)}
              </td>
              <td className="px-4 py-2.5 text-center">
                <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                  order.timeInForce === 'DAY' 
                    ? 'bg-status-warning/20 text-status-warning' 
                    : 'bg-status-success/20 text-status-success'
                }`}>
                  {order.timeInForce}
                </span>
              </td>
              {showDuplicates && (
                <td className="px-4 py-2.5">
                  <div className="flex items-center justify-center">
                    {order.isDuplicate && (
                      <TriangleAlert className="h-3.5 w-3.5 text-red-500" />
                    )}
                  </div>
                </td>
              )}
            </tr>
          ))}
        </tbody>
        <tfoot className="bg-yellow-950/40 border-t-2 border-yellow-900/50">
          <tr>
            <td colSpan={3} className="px-4 py-2.5 text-left font-medium text-text-primary">
              Total Investment
            </td>
            <td className="px-4 py-2.5 text-right font-numbers font-bold text-yellow-400 text-sm">
              {formatCurrency(totalValue)}
            </td>
            <td className="px-4 py-2.5"></td>
            {showDuplicates && <td className="px-4 py-2.5"></td>}
          </tr>
        </tfoot>
      </table>
    </div>
  );
}

