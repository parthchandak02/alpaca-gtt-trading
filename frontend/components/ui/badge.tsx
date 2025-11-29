import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

const badgeVariants = cva(
  "inline-flex items-center justify-center rounded-full border px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wide transition-colors focus:outline-none focus:ring-2 focus:ring-accent-blue focus:ring-offset-2",
  {
    variants: {
      variant: {
        default:
          "glass-badge border-border-primary text-text-primary",
        secondary:
          "glass-badge border-border-secondary text-text-secondary",
        destructive:
          "bg-status-error/30 text-status-error border-status-error/50",
        success:
          "bg-status-success/30 text-status-success border-status-success/50",
        warning:
          "bg-status-warning/30 text-status-warning border-status-warning/50",
        outline: "glass-badge text-text-primary",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props} />
  )
}

export { Badge, badgeVariants }

