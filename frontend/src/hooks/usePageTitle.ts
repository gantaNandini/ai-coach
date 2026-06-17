import { useLocation } from 'react-router-dom'

const PAGE_TITLES: Record<string, string> = {
  '/dashboard': 'Dashboard',
  '/modules': 'Modules',
  '/coaching-history': 'Coaching History',
  '/knowledge': 'Knowledge Base',
  '/analytics': 'Analytics',
  '/achievements': 'Achievements',
  '/profile': 'Profile',
  '/billing': 'Billing',
  '/settings': 'Settings',
  '/admin': 'System Admin',
  '/modules/new': 'Module Builder',
}

export function usePageTitle(): string {
  const { pathname } = useLocation()
  if (pathname.startsWith('/sessions/coaching/')) return 'Coaching Session'
  if (pathname.startsWith('/sessions/roleplay/')) return 'Roleplay Session'
  if (pathname.startsWith('/feedback/')) return 'Feedback Report'
  return PAGE_TITLES[pathname] ?? 'AI Coach'
}
