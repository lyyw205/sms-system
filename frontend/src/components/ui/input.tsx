import * as React from "react"

import { cn } from "@/lib/utils"

interface TextInputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  sizing?: "sm" | "md"
  icon?: React.ComponentType<{ className?: string }>
  rightIcon?: React.ComponentType<{ className?: string }>
  color?: "gray" | "failure"
}

const TextInput = React.forwardRef<HTMLInputElement, TextInputProps>(
  ({ className, sizing = "md", icon: Icon, rightIcon: RightIcon, color, ...props }, ref) => {
    const sizeClasses = sizing === "sm" ? "p-2 text-body" : "p-2.5 text-body"

    const input = (
      <input
        ref={ref}
        className={cn(
          "block w-full rounded-lg border border-[#E5E8EB] bg-white text-[#191F28] outline-none transition-colors",
          "focus:border-[#3182F6] focus:ring-1 focus:ring-[#3182F6]",
          "dark:border-gray-600 dark:bg-[#1E1E24] dark:text-gray-100",
          "dark:focus:border-[#3182F6] dark:focus:ring-[#3182F6]",
          color === "failure" && "border-[#F04452] focus:border-[#F04452] focus:ring-[#F04452]",
          sizeClasses,
          Icon && "pl-10",
          RightIcon && "pr-10",
          className,
        )}
        {...props}
      />
    )

    if (!Icon && !RightIcon) return input

    return (
      <div className="relative">
        {Icon && (
          <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3">
            <Icon className="size-4 text-[#8B95A1]" />
          </div>
        )}
        {input}
        {RightIcon && (
          <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-3">
            <RightIcon className="size-4 text-[#8B95A1]" />
          </div>
        )}
      </div>
    )
  }
)
TextInput.displayName = "TextInput"

export { TextInput }
