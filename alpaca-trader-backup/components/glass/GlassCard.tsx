import * as React from "react"
import { cn } from "@/lib/utils"

interface GlassCardProps extends React.HTMLAttributes<HTMLDivElement> {
  hover?: boolean
  interactive?: boolean
}

const GlassCard = React.forwardRef<HTMLDivElement, GlassCardProps>(
  ({ className, hover = true, interactive = false, ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={cn(
          "glass-card",
          hover && "hover:bg-opacity-75 hover:border-opacity-25",
          interactive && "cursor-pointer",
          className
        )}
        {...props}
      />
    )
  }
)
GlassCard.displayName = "GlassCard"

export { GlassCard }

