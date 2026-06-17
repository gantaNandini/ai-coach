import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import {
  Brain, LayoutDashboard, BookOpen, Database, BarChart2,
  User, LogOut, Sun, Moon, Bell, Shield, CreditCard,
  MessageSquare, Trophy, Settings, ChevronLeft, ChevronRight,
  PlusCircle, Menu,
} from 'lucide-react'
import { useAuthStore } from '@/stores/auth'
import { useThemeStore } from '@/stores/theme'
import { useRole } from '@/hooks/useRole'
import { authApi, notificationsApi } from '@/lib/api'
import { useQuery } from '@tanstack/react-query'

export default function Layout({ children }: { children: React.ReactNode }) {
  const location = useLocation()
  const navigate = useNavigate()
  const { user, clearAuth, refreshToken } = useAuthStore()
  const { theme, toggleTheme } = useThemeStore()
  const { isAdmin, isSuperadmin } = useRole()
  const [collapsed, setCollapsed] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)

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

  const isActive = (href: string) =>
    location.pathname === href || location.pathname.startsWith(href + '/')

  // Base nav — all authenticated users
  const baseGroups = [
    {
      label: 'LEARN',
      items: [
        { href: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
        { href: '/modules', icon: BookOpen, label: 'Modules' },
      ],
    },
    {
      label: 'INSIGHTS',
      items: [
        { href: '/achievements', icon: Trophy, label: 'Achievements' },
      ],
    },
    {
      label: 'ACCOUNT',
      items: [
        { href: '/profile', icon: User, label: 'Profile' },
        { href: '/billing', icon: CreditCard, label: 'Billing' },
        { href: '/settings', icon: Settings, label: 'Settings' },
      ],
    },
  ]

  // Admin-only nav additions
  const adminGroups = isAdmin
    ? [
        {
          label: 'KNOWLEDGE',
          items: [
            { href: '/knowledge', icon: Database, label: 'Knowledge Base' },
          ],
        },
        {
          label: 'INSIGHTS',
          extraItems: [
            { href: '/analytics', icon: BarChart2, label: 'Analytics' },
          ],
        },
      ]
    : []

  // Merge INSIGHTS group with admin extras
  const navGroups = baseGroups.map(g => {
    if (g.label === 'INSIGHTS' && isAdmin) {
      return { ...g, items: [...g.items, { href: '/analytics', icon: BarChart2, label: 'Analytics' }] }
    }
    return g
  })

  // Insert KNOWLEDGE group before INSIGHTS for admins
  const finalGroups = isAdmin
    ? [
        navGroups[0], // LEARN
        { label: 'KNOWLEDGE', items: [{ href: '/knowledge', icon: Database, label: 'Knowledge Base' }] },
        navGroups[1], // INSIGHTS (with analytics)
        navGroups[2], // ACCOUNT
      ]
    : navGroups

  const SidebarContent = () => (
    <div className="flex flex-col h-full">
      {/* Logo */}
      <div className={`flex items-center gap-2.5 px-5 py-5 border-b border-border ${collapsed ? 'justify-center' : ''}`}>
        <div className="w-8 h-8 bg-primary rounded-lg flex items-center justify-center flex-shrink-0">
          <Brain className="h-5 w-5 text-primary-foreground" />
        </div>
        {!collapsed && <span className="text-lg font-bold tracking-tight">AI Coach</span>}
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-5">
        {finalGroups.map(group => (
          <div key={group.label}>
            {!collapsed && (
              <div className="px-2 mb-1.5 text-[10px] font-semibold text-muted-foreground/60 uppercase tracking-wider">
                {group.label}
              </div>
            )}
            <div className="space-y-0.5">
              {group.items.map(({ href, icon: Icon, label }) => {
                const active = isActive(href)
                return (
                  <Link key={href} to={href}
                    onClick={() => setMobileOpen(false)}
                    title={collapsed ? label : undefined}
                    className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
                      active
                        ? 'bg-primary text-primary-foreground shadow-sm'
                        : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground'
                    } ${collapsed ? 'justify-center' : ''}`}>
                    <Icon className="h-4 w-4 flex-shrink-0" />
                    {!collapsed && label}
                  </Link>
                )
              })}
            </div>
          </div>
        ))}

        {/* Admin section — superadmin or tenant_admin */}
        {isAdmin && (
          <div>
            {!collapsed && (
              <div className="px-2 mb-1.5 text-[10px] font-semibold text-orange-500/70 uppercase tracking-wider">
                ADMIN
              </div>
            )}
            <div className="space-y-0.5">
              {[
                ...(isSuperadmin ? [{ href: '/admin', icon: Shield, label: 'System Admin' }] : []),
                { href: '/modules/new', icon: PlusCircle, label: 'Module Builder' },
              ].map(({ href, icon: Icon, label }) => {
                const active = isActive(href)
                return (
                  <Link key={href} to={href}
                    onClick={() => setMobileOpen(false)}
                    title={collapsed ? label : undefined}
                    className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
                      active
                        ? 'bg-orange-500/15 text-orange-500'
                        : 'text-muted-foreground hover:bg-orange-500/10 hover:text-orange-500'
                    } ${collapsed ? 'justify-center' : ''}`}>
                    <Icon className="h-4 w-4 flex-shrink-0" />
                    {!collapsed && label}
                  </Link>
                )
              })}
            </div>
          </div>
        )}
      </nav>

      {/* Bottom actions */}
      <div className={`border-t border-border p-3 space-y-1 ${collapsed ? 'flex flex-col items-center' : ''}`}>
        <button onClick={toggleTheme} title={collapsed ? 'Toggle theme' : undefined}
          className={`flex items-center gap-3 w-full px-3 py-2.5 rounded-lg text-sm text-muted-foreground hover:bg-accent hover:text-accent-foreground transition-colors ${collapsed ? 'justify-center w-auto' : ''}`}>
          {theme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          {!collapsed && (theme === 'dark' ? 'Light mode' : 'Dark mode')}
        </button>
        <button onClick={handleLogout} title={collapsed ? 'Sign out' : undefined}
          className={`flex items-center gap-3 w-full px-3 py-2.5 rounded-lg text-sm text-muted-foreground hover:bg-destructive/10 hover:text-destructive transition-colors ${collapsed ? 'justify-center w-auto' : ''}`}>
          <LogOut className="h-4 w-4" />
          {!collapsed && 'Sign out'}
        </button>
      </div>
    </div>
  )

  return (
    <div className="flex h-screen bg-background overflow-hidden">
      {/* Desktop sidebar */}
      <aside className={`hidden md:flex flex-col border-r border-border bg-card transition-all duration-200 flex-shrink-0 relative ${collapsed ? 'w-16' : 'w-60'}`}>
        <SidebarContent />
        {/* Collapse toggle */}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="absolute -right-3 top-20 w-6 h-6 rounded-full bg-card border border-border flex items-center justify-center shadow-sm hover:bg-accent transition-colors z-10">
          {collapsed ? <ChevronRight className="h-3 w-3" /> : <ChevronLeft className="h-3 w-3" />}
        </button>
      </aside>

      {/* Mobile sidebar overlay */}
      {mobileOpen && (
        <div className="md:hidden fixed inset-0 z-50 flex">
          <div className="absolute inset-0 bg-black/50" onClick={() => setMobileOpen(false)} />
          <aside className="relative w-64 bg-card border-r border-border h-full z-10">
            <SidebarContent />
          </aside>
        </div>
      )}

      {/* Main content */}
      <main className="flex-1 flex flex-col overflow-hidden min-w-0">
        {/* Top header */}
        <header className="h-14 border-b border-border px-5 flex items-center justify-between flex-shrink-0 bg-card/50 backdrop-blur">
          <div className="flex items-center gap-3">
            <button onClick={() => setMobileOpen(true)} className="md:hidden p-1.5 rounded-lg hover:bg-accent">
              <Menu className="h-5 w-5" />
            </button>
          </div>
          <div className="flex items-center gap-2">
            <Link to="/profile" className="relative p-2 rounded-lg hover:bg-accent transition-colors">
              <Bell className="h-4 w-4 text-muted-foreground" />
              {(unread?.count ?? 0) > 0 && (
                <span className="absolute top-1 right-1 w-3.5 h-3.5 bg-destructive text-[9px] text-white rounded-full flex items-center justify-center font-bold">
                  {unread!.count > 9 ? '9+' : unread!.count}
                </span>
              )}
            </Link>
            <Link to="/profile" className="flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-accent transition-colors">
              <div className="w-7 h-7 rounded-full bg-primary/20 flex items-center justify-center text-xs font-bold text-primary flex-shrink-0">
                {user?.full_name?.[0]?.toUpperCase() ?? 'U'}
              </div>
              <span className="text-sm font-medium hidden sm:block max-w-32 truncate">{user?.full_name}</span>
            </Link>
          </div>
        </header>

        {/* Page content */}
        <div className="flex-1 overflow-y-auto">
          <div className="p-6 max-w-7xl mx-auto">
            {children}
          </div>
        </div>
      </main>
    </div>
  )
}
