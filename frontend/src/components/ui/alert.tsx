import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

const alertVariants = cva(
  "rounded-lg p-4 text-body",
  {
    variants: {
      color: {
        info: "bg-[#E8F3FF] text-[#3182F6] dark:bg-[#3182F6]/15 dark:text-[#3182F6]",
        success: "bg-[#E8FAF5] text-[#00C9A7] dark:bg-[#00C9A7]/15 dark:text-[#00C9A7]",
        warning: "bg-[#FFF5E6] text-[#FF9F00] dark:bg-[#FF9F00]/15 dark:text-[#FF9F00]",
        failure: "bg-[#FFEBEE] text-[#F04452] dark:bg-[#F04452]/15 dark:text-[#F04452]",
      },
    },
    defaultVariants: {
      color: "info",
    },
  }
)

interface AlertProps
  extends Omit<React.HTMLAttributes<HTMLDivElement>, "color">,
    VariantProps<typeof alertVariants> {}

function Alert({ className, color, children, ...props }: AlertProps) {
  return (
    <div className={cn(alertVariants({ color, className }))} role="alert" {...props}>
      {children}
    </div>
  )
}

export { Alert }
