import * as React from "react"
import { cn } from "@/lib/utils"
import { Button, ButtonProps } from "@/components/ui/button"

export interface GlassButtonProps extends ButtonProps {
  variant?: "glass" | "default" | "outline" | "secondary" | "ghost" | "destructive"
}

const GlassButton = React.forwardRef<HTMLButtonElement, GlassButtonProps>(
  ({ className, variant = "glass", ...props }, ref) => {
    return (
      <Button
        ref={ref}
        variant={variant}
        className={cn(className)}
        {...props}
      />
    )
  }
)
GlassButton.displayName = "GlassButton"

export { GlassButton }

