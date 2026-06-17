import { forwardRef } from 'react'
import { Loader2 } from 'lucide-react'

type Variant = 'primary' | 'secondary' | 'destructive' | 'ghost' | 'outline'
type Size = 'sm' | 'md' | 'lg' | 'icon'

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  size?: Size
  loading?: boolean
  children: React.ReactNode
}

const variantClasses: Record<Variant, string> = {
  primary:     'bg-primary text-primary-foreground hover:bg-primary/90 shadow-sm',
  secondary:   'bg-secondary text-secondary-foreground hover:bg-secondary/80',
  destructive: 'bg-destructive text-destructive-foreground hover:bg-destructive/90',
  ghost:       'hover:bg-accent hover:text-accent-foreground',
  outline:     'border border-border bg-transparent hover:bg-accent hover:text-accent-foreground',
}

const sizeClasses: Record<Size, string> = {
  sm:   'h-8 px-3 text-xs rounded-md gap-1.5',
  md:   'h-9 px-4 text-sm rounded-lg gap-2',
  lg:   'h-11 px-6 text-sm rounded-lg gap-2',
  icon: 'h-9 w-9 rounded-lg',
}

const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = 'primary', size = 'md', loading = false, disabled, className = '', children, ...props }, ref) => {
    return (
      <button
        ref={ref}
        disabled={disabled || loading}
        className={`
          inline-flex items-center justify-center font-medium
          transition-colors focus-visible:outline-none focus-visible:ring-2
          focus-visible:ring-ring focus-visible:ring-offset-2
          disabled:pointer-events-none disabled:opacity-50
          ${variantClasses[variant]} ${sizeClasses[size]} ${className}
        `.trim()}
        {...props}
      >
        {loading && <Loader2 className="h-3.5 w-3.5 animate-spin flex-shrink-0" />}
        {children}
      </button>
    )
  }
)
Button.displayName = 'Button'

export { Button }
export type { ButtonProps }
