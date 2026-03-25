import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "inline-flex items-center justify-center text-center font-medium transition-colors focus:z-10 focus:outline-none disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:shrink-0",
  {
    variants: {
      color: {
        blue: "bg-[#3182F6] text-white hover:bg-[#1B64DA] focus:ring-2 focus:ring-[#3182F6]/30",
        light:
          "bg-[#F2F4F6] text-[#191F28] hover:bg-[#E5E8EB] dark:bg-[#2C2C34] dark:text-gray-200 dark:hover:bg-[#35353E]",
        failure:
          "bg-[#FFEBEE] text-[#F04452] hover:bg-[#FECDD3] dark:bg-[#F04452]/15 dark:text-[#F04452] dark:hover:bg-[#F04452]/25",
        ghost:
          "text-[#8B95A1] hover:bg-[#F2F4F6] hover:text-[#4E5968] dark:text-gray-500 dark:hover:bg-[#1E1E24]",
      },
      size: {
        xs: "rounded-lg px-2 py-1 text-caption min-h-[36px] [&_svg:not([class*='size-'])]:size-3.5",
        sm: "rounded-lg px-3 py-1.5 text-body [&_svg:not([class*='size-'])]:size-3.5",
        md: "rounded-lg px-4 py-2 text-body [&_svg:not([class*='size-'])]:size-4",
        lg: "rounded-lg px-5 py-2.5 text-body [&_svg:not([class*='size-'])]:size-4",
      },
    },
    defaultVariants: {
      color: "blue",
      size: "md",
    },
  }
)

type ButtonVariantProps = VariantProps<typeof buttonVariants>

interface ButtonProps
  extends Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, "color">,
    ButtonVariantProps {}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, color, size, ...props }, ref) => {
    return (
      <button
        ref={ref}
        className={cn(buttonVariants({ color, size, className }))}
        {...props}
      />
    )
  }
)
Button.displayName = "Button"

export { Button, buttonVariants }
export type { ButtonProps }
