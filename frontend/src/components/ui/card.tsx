import * as React from "react"

import { cn } from "@/lib/utils"

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {}

const Card = React.forwardRef<HTMLDivElement, CardProps>(
  ({ className, children, ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={cn(
          "flex rounded-2xl bg-white dark:bg-[#1E1E24]",
          className,
        )}
        {...props}
      >
        <div className="flex h-full w-full flex-col gap-4 p-5">
          {children}
        </div>
      </div>
    )
  }
)
Card.displayName = "Card"

export { Card }
