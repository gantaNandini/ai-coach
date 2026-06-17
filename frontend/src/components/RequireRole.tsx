import { Navigate } from 'react-router-dom'
import { useRole } from '@/hooks/useRole'

interface RequireRoleProps {
  role: 'admin' | 'learner' | 'superadmin'
  children: React.ReactNode
  fallback?: string
}

/**
 * RequireRole — renders children only if the current user has the required role.
 * Redirects to /dashboard with a state message if not authorized.
 */
export default function RequireRole({ role, children, fallback = '/dashboard' }: RequireRoleProps) {
  const { isAdmin, isLearner, isSuperadmin } = useRole()

  const allowed =
    (role === 'admin' && isAdmin) ||
    (role === 'learner' && (isLearner || isAdmin)) ||
    (role === 'superadmin' && isSuperadmin)

  if (!allowed) {
    return <Navigate to={fallback} state={{ restricted: true, required: role }} replace />
  }

  return <>{children}</>
}
