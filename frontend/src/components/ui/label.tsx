import * as React from "react"

import { cn } from "@/lib/utils"

interface LabelProps extends React.LabelHTMLAttributes<HTMLLabelElement> {}

const Label = React.forwardRef<HTMLLabelElement, LabelProps>(
  ({ className, ...props }, ref) => {
    return (
      <label
        ref={ref}
        className={cn("mb-1.5 block text-label font-medium text-[#191F28] dark:text-gray-300", className)}
        {...props}
      />
    )
  }
)
Label.displayName = "Label"

export { Label }
