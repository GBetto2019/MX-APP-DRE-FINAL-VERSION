import { cn } from '@/lib/utils'

interface SkeletonProps { className?: string; variant?: 'line' | 'card' | 'table' }

export function Skeleton({ className, variant = 'line' }: SkeletonProps) {
  if (variant === 'card') {
    return (
      <div className={cn('animate-pulse rounded-lg bg-gray-100 p-6', className)}>
        <div className="h-4 w-1/3 rounded bg-gray-200" />
        <div className="mt-4 h-8 w-1/2 rounded bg-gray-200" />
        <div className="mt-2 h-3 w-2/3 rounded bg-gray-200" />
      </div>
    )
  }
  if (variant === 'table') {
    return (
      <div className={cn('animate-pulse space-y-3', className)}>
        {Array.from({ length: 8 }).map((_, i) => (
          <div key={i} className="flex gap-4">
            <div className="h-4 flex-1 rounded bg-gray-200" />
            <div className="h-4 w-32 rounded bg-gray-200" />
            <div className="h-4 w-24 rounded bg-gray-200" />
          </div>
        ))}
      </div>
    )
  }
  return <div className={cn('animate-pulse rounded bg-gray-200', className)} />
}
