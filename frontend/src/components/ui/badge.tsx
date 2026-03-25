import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

const badgeVariants = cva(
  "inline-flex h-fit items-center gap-1 rounded-lg px-2 py-0.5 font-medium",
  {
    variants: {
      color: {
        info: "bg-[#E8F3FF] text-[#3182F6] dark:bg-[#3182F6]/15 dark:text-[#3182F6]",
        success: "bg-[#E8FAF5] text-[#00C9A7] dark:bg-[#00C9A7]/15 dark:text-[#00C9A7]",
        warning: "bg-[#FFF5E6] text-[#FF9F00] dark:bg-[#FF9F00]/15 dark:text-[#FF9F00]",
        failure: "bg-[#FFEBEE] text-[#F04452] dark:bg-[#F04452]/15 dark:text-[#F04452]",
        gray: "bg-[#F2F4F6] text-[#8B95A1] dark:bg-[#2C2C34] dark:text-gray-400",
        purple: "bg-[#F3E8FF] text-[#8B5CF6] dark:bg-[#8B5CF6]/15 dark:text-[#8B5CF6]",
      },
      size: {
        xs: "text-tiny",
        sm: "text-caption",
      },
    },
    defaultVariants: {
      color: "info",
      size: "sm",
    },
  }
)

interface BadgeProps
  extends Omit<React.HTMLAttributes<HTMLSpanElement>, "color">,
    VariantProps<typeof badgeVariants> {
  icon?: React.ComponentType<{ className?: string }>
}

function Badge({ className, color, size, icon: Icon, children, ...props }: BadgeProps) {
  return (
    <span className={cn(badgeVariants({ color, size, className }))} {...props}>
      {Icon && <Icon className="size-3" />}
      {children}
    </span>
  )
}

export { Badge, badgeVariants }
