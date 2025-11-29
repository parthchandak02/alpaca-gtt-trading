import * as React from "react"
import { cn } from "@/lib/utils"
import { Input, InputProps } from "@/components/ui/input"

interface GlassInputProps extends InputProps {}

const GlassInput = React.forwardRef<HTMLInputElement, GlassInputProps>(
  ({ className, ...props }, ref) => {
    return (
      <Input
        ref={ref}
        className={cn(className)}
        {...props}
      />
    )
  }
)
GlassInput.displayName = "GlassInput"

export { GlassInput }

