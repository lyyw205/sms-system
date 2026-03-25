import * as React from "react"

import { cn } from "@/lib/utils"

interface TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {}

const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, ...props }, ref) => {
    return (
      <textarea
        ref={ref}
        className={cn(
          "block w-full rounded-lg border border-[#E5E8EB] bg-white p-2.5 text-body text-[#191F28] outline-none transition-colors",
          "focus:border-[#3182F6] focus:ring-1 focus:ring-[#3182F6]",
          "dark:border-gray-600 dark:bg-[#1E1E24] dark:text-gray-100",
          "dark:focus:border-[#3182F6] dark:focus:ring-[#3182F6]",
          className,
        )}
        {...props}
      />
    )
  }
)
Textarea.displayName = "Textarea"

export { Textarea }
