import { useAuthStore } from '@/stores/auth'

/**
 * useRole — derive role flags from the auth store.
 *
 * Usage:
 *   const { isAdmin, isLearner, hasRole } = useRole()
 */
export function useRole() {
  const roles = useAuthStore((s) => s.roles)
  const user = useAuthStore((s) => s.user)

  const hasRole = (role: string) =>
    roles.includes(role) || (user?.is_superadmin ?? false)

  return {
    roles,
    isAdmin: hasRole('tenant_admin') || hasRole('program_owner') || (user?.is_superadmin ?? false),
    isLearner: hasRole('learner'),
    isSuperadmin: user?.is_superadmin ?? false,
    hasRole,
  }
}
