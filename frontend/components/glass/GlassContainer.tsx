import * as React from "react"
import { cn } from "@/lib/utils"

export interface GlassContainerProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "light" | "medium" | "heavy"
  tint?: "default" | "blue" | "purple" | "green"
  hover?: boolean
}

const GlassContainer = React.forwardRef<HTMLDivElement, GlassContainerProps>(
  ({ className, variant = "medium", tint = "default", hover = true, ...props }, ref) => {
    const variantClasses = {
      light: "glass-light",
      medium: "glass-medium",
      heavy: "glass-heavy",
    }
    
    const tintClasses = {
      default: "",
      blue: "glass-tint-blue",
      purple: "glass-tint-purple",
      green: "glass-tint-green",
    }
    
    return (
      <div
        ref={ref}
        className={cn(
          variantClasses[variant],
          tintClasses[tint],
          hover && "hover:bg-opacity-80 hover:border-opacity-20",
          "rounded-xl p-6 transition-all",
          className
        )}
        {...props}
      />
    )
  }
)
GlassContainer.displayName = "GlassContainer"

export { GlassContainer }

