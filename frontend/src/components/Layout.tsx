import { Link, useLocation, useNavigate } from 'react-router-dom'
import { Brain, LayoutDashboard, BookOpen, Database, BarChart2, User, LogOut, Sun, Moon, Bell, Shield, CreditCard } from 'lucide-react'
import { useAuthStore } from '@/stores/auth'
import { useThemeStore } from '@/stores/theme'
import { authApi, notificationsApi } from '@/lib/api'
import { useQuery } from '@tanstack/react-query'

const nav = [
  { href: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
  { href: '/modules', icon: BookOpen, label: 'Modules' },
  { href: '/knowledge', icon: Database, label: 'Knowledge' },
  { href: '/analytics', icon: BarChart2, label: 'Analytics' },
  { href: '/profile', icon: User, label: 'Profile' },
  { href: '/billing', icon: CreditCard, label: 'Billing' },
]

export default function Layout({ children }: { children: React.ReactNode }) {
  const location = useLocation()
  const navigate = useNavigate()
  const { user, clearAuth, refreshToken } = useAuthStore()
  const { theme, toggleTheme } = useThemeStore()

  const { data: unread } = useQuery({
    queryKey: ['unread-count'],
    queryFn: () => notificationsApi.unreadCount().then(r => r.data),
    refetchInterval: 30000,
  })

  const handleLogout = async () => {
    if (refreshToken) await authApi.logout(refreshToken).catch(() => {})
    clearAuth()
    navigate('/login')
  }

  return (
    <div className="flex h-screen bg-background">
      {/* Sidebar */}
      <aside className="w-64 border-r border-border flex flex-col">
        <div className="flex items-center gap-2 px-6 py-5 border-b border-border">
          <Brain className="h-6 w-6 text-primary" />
          <span className="text-lg font-bold">AI Coach</span>
        </div>
        <nav className="flex-1 px-4 py-4 space-y-1">
          {nav.map(({ href, icon: Icon, label }) => {
            const active = location.pathname.startsWith(href)
            return (
              <Link key={href} to={href}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${active ? 'bg-primary/10 text-primary' : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground'}`}>
                <Icon className="h-4 w-4" />
                {label}
              </Link>
            )
          })}
          {/* Admin link for superadmins */}
          {user?.is_superadmin && (
            <Link to="/admin"
              className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${location.pathname === '/admin' ? 'bg-orange-500/10 text-orange-500' : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground'}`}>
              <Shield className="h-4 w-4" />
              System Admin
            </Link>
          )}
        </nav>
        <div className="px-4 py-4 border-t border-border space-y-1">
          <button onClick={toggleTheme}
            className="flex items-center gap-3 w-full px-3 py-2.5 rounded-lg text-sm text-muted-foreground hover:bg-accent hover:text-accent-foreground transition-colors">
            {theme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            {theme === 'dark' ? 'Light mode' : 'Dark mode'}
          </button>
          <button onClick={handleLogout}
            className="flex items-center gap-3 w-full px-3 py-2.5 rounded-lg text-sm text-muted-foreground hover:bg-destructive/10 hover:text-destructive transition-colors">
            <LogOut className="h-4 w-4" />
            Sign out
          </button>
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 flex flex-col overflow-hidden">
        <header className="h-16 border-b border-border px-8 flex items-center justify-between flex-shrink-0">
          <div />
          <div className="flex items-center gap-3">
            <Link to="/profile" className="relative p-2 rounded-lg hover:bg-accent transition-colors">
              <Bell className="h-5 w-5 text-muted-foreground" />
              {unread?.count > 0 && (
                <span className="absolute top-1 right-1 w-4 h-4 bg-destructive text-destructive-foreground text-[10px] rounded-full flex items-center justify-center font-bold">
                  {unread.count > 9 ? '9+' : unread.count}
                </span>
              )}
            </Link>
            <Link to="/profile" className="flex items-center gap-2 hover:opacity-80 transition-opacity">
              <div className="w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center text-xs font-semibold text-primary">
                {user?.full_name?.[0]?.toUpperCase() || 'U'}
              </div>
              <span className="text-sm font-medium">{user?.full_name}</span>
            </Link>
          </div>
        </header>
        <div className="flex-1 overflow-y-auto p-8">{children}</div>
      </main>
    </div>
  )
}
