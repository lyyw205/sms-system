import * as React from "react"

import { cn } from "@/lib/utils"

/* ── Tabs ── */

interface TabsProps {
  variant?: "underline"
  onActiveTabChange?: (index: number) => void
  children: React.ReactNode
  className?: string
}

function Tabs({ onActiveTabChange, children, className }: TabsProps) {
  const items = React.Children.toArray(children).filter(React.isValidElement) as React.ReactElement<TabItemProps>[]

  const defaultIndex = items.findIndex((item) => item.props.active)
  const [activeIndex, setActiveIndex] = React.useState(defaultIndex >= 0 ? defaultIndex : 0)

  const handleTabChange = (index: number) => {
    setActiveIndex(index)
    onActiveTabChange?.(index)
  }

  return (
    <div className={className}>
      {/* Tab list */}
      <div role="tablist" aria-label="Tabs" className="flex border-b border-[#F2F4F6] dark:border-gray-800">
        {items.map((item, index) => (
          <button
            key={index}
            role="tab"
            aria-selected={activeIndex === index}
            onClick={() => handleTabChange(index)}
            className={cn(
              "-mb-px border-b-2 p-4 text-body font-medium transition-colors",
              activeIndex === index
                ? "border-[#3182F6] text-[#3182F6] dark:border-[#3182F6] dark:text-[#3182F6]"
                : "border-transparent text-[#8B95A1] hover:border-[#B0B8C1] hover:text-[#4E5968] dark:text-gray-500",
            )}
          >
            {item.props.title}
          </button>
        ))}
      </div>

      {/* Tab panel */}
      <div role="tabpanel">
        {items[activeIndex]?.props.children}
      </div>
    </div>
  )
}

/* ── TabItem ── */

interface TabItemProps {
  active?: boolean
  title: React.ReactNode
  children: React.ReactNode
}

function TabItem({ children }: TabItemProps) {
  return <>{children}</>
}

export { Tabs, TabItem }
