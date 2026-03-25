import * as React from "react"

import { cn } from "@/lib/utils"

interface TooltipProps {
  content: string
  placement?: "top" | "bottom" | "left" | "right"
  children: React.ReactNode
  className?: string
}

function Tooltip({ content, placement = "top", children, className }: TooltipProps) {
  const [show, setShow] = React.useState(false)

  const placementClasses: Record<string, string> = {
    top: "bottom-full left-1/2 mb-2 -translate-x-1/2",
    bottom: "top-full left-1/2 mt-2 -translate-x-1/2",
    left: "right-full top-1/2 mr-2 -translate-y-1/2",
    right: "left-full top-1/2 ml-2 -translate-y-1/2",
  }

  return (
    <div
      className="relative inline-block"
      onMouseEnter={() => setShow(true)}
      onMouseLeave={() => setShow(false)}
    >
      {children}
      {show && (
        <div
          className={cn(
            "pointer-events-none absolute z-[60] whitespace-nowrap rounded-lg bg-[#191F28] px-3 py-1.5 text-caption font-medium text-white shadow-lg",
            "dark:bg-[#2C2C34] dark:text-gray-100",
            placementClasses[placement],
            className,
          )}
        >
          {content}
        </div>
      )}
    </div>
  )
}

export { Tooltip }
