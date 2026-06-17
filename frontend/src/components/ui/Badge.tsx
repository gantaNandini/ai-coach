type BadgeVariant = 'default' | 'success' | 'warning' | 'destructive' | 'info' | 'outline'

interface BadgeProps {
  children: React.ReactNode
  variant?: BadgeVariant
  className?: string
}

const variantClasses: Record<BadgeVariant, string> = {
  default:     'bg-primary/10 text-primary',
  success:     'bg-green-500/10 text-green-600 dark:text-green-400',
  warning:     'bg-yellow-500/10 text-yellow-600 dark:text-yellow-400',
  destructive: 'bg-red-500/10 text-red-600 dark:text-red-400',
  info:        'bg-blue-500/10 text-blue-600 dark:text-blue-400',
  outline:     'border border-border text-muted-foreground',
}

export function Badge({ children, variant = 'default', className = '' }: BadgeProps) {
  return (
    <span className={`inline-flex items-center text-xs font-medium px-2 py-0.5 rounded-full ${variantClasses[variant]} ${className}`}>
      {children}
    </span>
  )
}

export type { BadgeVariant, BadgeProps }
