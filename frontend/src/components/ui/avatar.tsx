import { cn } from "@/lib/utils"

const sizeClasses = {
  xs: "size-6 text-tiny",
  sm: "size-8 text-caption",
  md: "size-10 text-body",
  lg: "size-16 text-heading",
}

interface AvatarProps {
  placeholderInitials?: string
  img?: string
  rounded?: boolean
  size?: keyof typeof sizeClasses
  className?: string
}

function Avatar({ placeholderInitials, img, rounded = false, size = "md", className }: AvatarProps) {
  const shape = rounded ? "rounded-full" : "rounded-lg"

  if (img) {
    return (
      <img
        src={img}
        className={cn("shrink-0 object-cover", shape, sizeClasses[size], className)}
        alt=""
      />
    )
  }

  return (
    <div
      className={cn(
        "flex shrink-0 items-center justify-center bg-[#F2F4F6] font-medium text-[#8B95A1]",
        "dark:bg-[#2C2C34] dark:text-gray-400",
        shape,
        sizeClasses[size],
        className,
      )}
    >
      {placeholderInitials || ""}
    </div>
  )
}

export { Avatar }
