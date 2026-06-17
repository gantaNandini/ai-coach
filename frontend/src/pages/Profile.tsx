import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  User, Award, TrendingUp, Edit2, Check, X, Loader2, Flame, Star,
  Lock, Trophy, Eye, EyeOff, AlertTriangle, Sun, Moon,
} from 'lucide-react'
import Layout from '@/components/Layout'
import { api } from '@/lib/api'
import { useAuthStore } from '@/stores/auth'
import { useThemeStore } from '@/stores/theme'
import { useNavigate } from 'react-router-dom'

function getLevelFromXP(xp: number) {
  return Math.floor(xp / 100) + 1
}

function getAchievementEmoji(icon: string): string {
  const map: Record<string, string> = {
    Award: '🏆', TrendingUp: '📈', BookOpen: '📚', Star: '⭐',
    Zap: '⚡', Flame: '🔥', MessageCircle: '💬', Target: '🎯',
    CheckCircle: '✅', Users: '👥',
  }
  return map[icon] ?? '🎖️'
}

export default function Profile() {
  const { user, setAuth, accessToken, refreshToken, clearAuth } = useAuthStore()
  const { theme, toggleTheme } = useThemeStore()
  const navigate = useNavigate()
  const qc = useQueryClient()

  const [editing, setEditing] = useState(false)
  const [fullName, setFullName] = useState(user?.full_name || '')

  // Password form
  const [currentPw, setCurrentPw] = useState('')
  const [newPw, setNewPw] = useState('')
  const [confirmPw, setConfirmPw] = useState('')
  const [showCurrentPw, setShowCurrentPw] = useState(false)
  const [showNewPw, setShowNewPw] = useState(false)
  const [pwError, setPwError] = useState('')
  const [pwSuccess, setPwSuccess] = useState(false)

  // Delete account
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [deleteConfirmText, setDeleteConfirmText] = useState('')

  const { data: progress } = useQuery({
    queryKey: ['progress'],
    queryFn: () => api.get('/progress/').then(r => r.data as any[]),
  })

  const { data: sessions } = useQuery({
    queryKey: ['sessions-profile'],
    queryFn: () => api.get('/sessions/coaching', { params: { page_size: 100 } }).then(r => r.data),
  })

  const { data: allAchievements } = useQuery({
    queryKey: ['achievements'],
    queryFn: () => api.get('/progress/achievements').then(r => r.data as any[]),
  })

  const { data: myAchievements } = useQuery({
    queryKey: ['achievements', 'mine'],
    queryFn: () => api.get('/progress/achievements/mine').then(r => r.data as any[]),
  })

  const updateMutation = useMutation({
    mutationFn: (name: string) => api.patch('/users/me', { full_name: name }),
    onSuccess: async () => {
      const { data } = await api.get('/auth/me')
      if (accessToken && refreshToken) setAuth(data, accessToken, refreshToken)
      setEditing(false)
      qc.invalidateQueries({ queryKey: ['me'] })
    },
  })

  const passwordMutation = useMutation({
    mutationFn: (payload: { current_password: string; new_password: string }) =>
      api.post('/users/me/change-password', payload),
    onSuccess: () => {
      setPwSuccess(true)
      setCurrentPw('')
      setNewPw('')
      setConfirmPw('')
      setPwError('')
      setTimeout(() => setPwSuccess(false), 3000)
    },
    onError: (err: any) => {
      setPwError(err?.response?.data?.detail || 'Failed to change password')
    },
  })

  const handlePasswordChange = () => {
    setPwError('')
    if (!currentPw || !newPw || !confirmPw) { setPwError('All fields required'); return }
    if (newPw !== confirmPw) { setPwError('New passwords do not match'); return }
    if (newPw.length < 8) { setPwError('Password must be at least 8 characters'); return }
    passwordMutation.mutate({ current_password: currentPw, new_password: newPw })
  }

  // Stats
  const totalSessions = sessions?.total ?? 0
  const bestScore = progress?.reduce((a: number, p: any) => Math.max(a, p.best_score ?? 0), 0) ?? 0
  const maxStreak = progress?.reduce((a: number, p: any) => Math.max(a, p.streak_days ?? 0), 0) ?? 0

  const earnedMap = new Map((myAchievements || []).map((ua: any) => [ua.achievement_id, ua]))
  const totalXP = (myAchievements || []).reduce((sum: number, ua: any) => sum + (ua.points || 0), 0)
  const currentLevel = getLevelFromXP(totalXP)

  const initials = user?.full_name
    ? user.full_name.split(' ').map(n => n[0]).slice(0, 2).join('').toUpperCase()
    : (user?.email?.[0]?.toUpperCase() ?? 'U')

  const memberSince = user?.created_at
    ? new Date(user.created_at).toLocaleDateString('en', { month: 'long', year: 'numeric' })
    : null

  return (
    <Layout>
      <div className="max-w-3xl mx-auto space-y-6">

        {/* Profile card */}
        <div className="bg-card border border-border rounded-2xl p-6 md:p-8">
          <div className="flex flex-col sm:flex-row items-start gap-6">
            {/* Avatar */}
            <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-primary/30 to-primary/10 flex items-center justify-center text-3xl font-bold text-primary flex-shrink-0 border border-primary/20">
              {initials}
            </div>

            <div className="flex-1 min-w-0">
              {/* Name edit */}
              {editing ? (
                <div className="flex items-center gap-2 mb-1">
                  <input
                    value={fullName}
                    onChange={e => setFullName(e.target.value)}
                    className="flex-1 bg-muted rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                    autoFocus
                    onKeyDown={e => e.key === 'Enter' && updateMutation.mutate(fullName)}
                  />
                  <button
                    onClick={() => updateMutation.mutate(fullName)}
                    disabled={updateMutation.isPending}
                    className="p-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors"
                  >
                    {updateMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}
                  </button>
                  <button onClick={() => { setEditing(false); setFullName(user?.full_name || '') }}
                    className="p-2 hover:bg-muted rounded-lg transition-colors">
                    <X className="h-4 w-4" />
                  </button>
                </div>
              ) : (
                <div className="flex items-center gap-2 mb-1">
                  <h1 className="text-xl font-bold">{user?.full_name}</h1>
                  <button onClick={() => setEditing(true)} className="p-1.5 hover:bg-muted rounded-lg transition-colors">
                    <Edit2 className="h-3.5 w-3.5 text-muted-foreground" />
                  </button>
                </div>
              )}

              <p className="text-muted-foreground text-sm">{user?.email}</p>
              {memberSince && <p className="text-xs text-muted-foreground mt-0.5">Member since {memberSince}</p>}

              <div className="flex flex-wrap items-center gap-2 mt-3">
                {user?.is_superadmin && (
                  <span className="text-xs px-2 py-0.5 bg-orange-500/10 text-orange-500 rounded-full font-medium border border-orange-500/20">
                    Superadmin
                  </span>
                )}
                <span className="flex items-center gap-1 text-xs px-2 py-0.5 bg-yellow-500/10 text-yellow-600 dark:text-yellow-400 rounded-full font-medium border border-yellow-500/20">
                  <Star className="h-3 w-3" fill="currentColor" />
                  Level {currentLevel}
                </span>
                {totalXP > 0 && (
                  <span className="text-xs px-2 py-0.5 bg-primary/10 text-primary rounded-full font-medium border border-primary/20">
                    {totalXP} XP
                  </span>
                )}
              </div>
            </div>
          </div>

          {/* Stats */}
          <div className="grid grid-cols-4 gap-3 mt-6 pt-6 border-t border-border">
            {[
              { icon: MessageSquare, label: 'Sessions', value: totalSessions, color: 'text-blue-500' },
              { icon: Award, label: 'Best Score', value: `${bestScore.toFixed(0)}%`, color: 'text-yellow-500' },
              { icon: Flame, label: 'Best Streak', value: `${maxStreak}d`, color: 'text-orange-500' },
              { icon: Trophy, label: 'Achievements', value: earnedMap.size, color: 'text-purple-500' },
            ].map(({ icon: Icon, label, value, color }) => (
              <div key={label} className="text-center">
                <Icon className={`h-4 w-4 ${color} mx-auto mb-1.5`} />
                <div className="text-xl font-bold">{value}</div>
                <div className="text-xs text-muted-foreground">{label}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Achievement gallery */}
        {allAchievements && allAchievements.length > 0 && (
          <div className="bg-card border border-border rounded-xl p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-semibold">
                Achievements
                <span className="ml-2 text-sm font-normal text-muted-foreground">
                  {earnedMap.size}/{allAchievements.length} earned
                </span>
              </h2>
              <span className="text-sm text-muted-foreground">{totalXP} XP total</span>
            </div>
            <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 gap-3">
              {allAchievements.map((a: any) => {
                const earned = earnedMap.has(a.id)
                return (
                  <div
                    key={a.id}
                    className={`flex flex-col items-center text-center p-3 rounded-xl border transition-all ${
                      earned
                        ? 'border-yellow-500/40 bg-yellow-500/5 shadow-sm'
                        : 'border-border bg-muted/20 opacity-50'
                    }`}
                  >
                    <div className={`text-2xl mb-1.5 ${earned ? '' : 'grayscale'}`}>
                      {getAchievementEmoji(a.icon)}
                    </div>
                    {earned ? (
                      <Check className="h-3 w-3 text-yellow-500 mb-1" />
                    ) : (
                      <Lock className="h-3 w-3 text-muted-foreground/50 mb-1" />
                    )}
                    <div className="text-xs font-medium leading-tight">{a.name}</div>
                    <div className="text-xs text-muted-foreground mt-0.5">{a.points} XP</div>
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {/* Settings card */}
        <div className="bg-card border border-border rounded-xl p-6 space-y-6">
          <h2 className="font-semibold">Settings</h2>

          {/* Theme toggle */}
          <div>
            <h3 className="text-sm font-medium mb-3">Appearance</h3>
            <button
              onClick={toggleTheme}
              className="flex items-center gap-3 w-full px-4 py-3 rounded-xl border border-border hover:bg-accent transition-colors"
            >
              {theme === 'dark' ? <Sun className="h-4 w-4 text-yellow-500" /> : <Moon className="h-4 w-4 text-blue-500" />}
              <div className="text-left">
                <div className="text-sm font-medium">{theme === 'dark' ? 'Light Mode' : 'Dark Mode'}</div>
                <div className="text-xs text-muted-foreground">
                  {theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
                </div>
              </div>
              <div className={`ml-auto w-10 h-5 rounded-full transition-colors ${theme === 'dark' ? 'bg-primary' : 'bg-muted'}`}>
                <div className={`w-4 h-4 rounded-full bg-white shadow transition-transform mt-0.5 ${theme === 'dark' ? 'translate-x-5' : 'translate-x-0.5'}`} />
              </div>
            </button>
          </div>

          {/* Change password */}
          <div>
            <h3 className="text-sm font-medium mb-3">Change Password</h3>
            <div className="space-y-3">
              <div className="relative">
                <input
                  type={showCurrentPw ? 'text' : 'password'}
                  placeholder="Current password"
                  value={currentPw}
                  onChange={e => setCurrentPw(e.target.value)}
                  className="w-full bg-muted rounded-lg px-3 py-2.5 text-sm pr-10 focus:outline-none focus:ring-2 focus:ring-primary"
                />
                <button onClick={() => setShowCurrentPw(!showCurrentPw)}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground">
                  {showCurrentPw ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
              <div className="relative">
                <input
                  type={showNewPw ? 'text' : 'password'}
                  placeholder="New password (min 8 chars)"
                  value={newPw}
                  onChange={e => setNewPw(e.target.value)}
                  className="w-full bg-muted rounded-lg px-3 py-2.5 text-sm pr-10 focus:outline-none focus:ring-2 focus:ring-primary"
                />
                <button onClick={() => setShowNewPw(!showNewPw)}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground">
                  {showNewPw ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
              <input
                type="password"
                placeholder="Confirm new password"
                value={confirmPw}
                onChange={e => setConfirmPw(e.target.value)}
                className="w-full bg-muted rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              />

              {pwError && (
                <div className="flex items-center gap-2 text-destructive text-sm">
                  <AlertTriangle className="h-4 w-4 flex-shrink-0" />
                  {pwError}
                </div>
              )}
              {pwSuccess && (
                <div className="flex items-center gap-2 text-green-600 dark:text-green-400 text-sm">
                  <Check className="h-4 w-4" /> Password updated successfully
                </div>
              )}

              <button
                onClick={handlePasswordChange}
                disabled={passwordMutation.isPending}
                className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 transition-colors disabled:opacity-50"
              >
                {passwordMutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
                Update Password
              </button>
            </div>
          </div>

          {/* Danger zone */}
          <div className="pt-4 border-t border-border">
            <h3 className="text-sm font-medium text-destructive mb-3">Danger Zone</h3>
            {!showDeleteConfirm ? (
              <button
                onClick={() => setShowDeleteConfirm(true)}
                className="px-4 py-2 border border-destructive/40 text-destructive text-sm rounded-lg hover:bg-destructive/5 transition-colors"
              >
                Delete Account
              </button>
            ) : (
              <div className="border border-destructive/30 rounded-xl p-4 bg-destructive/5 space-y-3">
                <div className="flex items-start gap-2">
                  <AlertTriangle className="h-4 w-4 text-destructive mt-0.5 flex-shrink-0" />
                  <p className="text-sm text-destructive">
                    This action is permanent. Type <strong>DELETE</strong> to confirm.
                  </p>
                </div>
                <input
                  type="text"
                  placeholder="Type DELETE to confirm"
                  value={deleteConfirmText}
                  onChange={e => setDeleteConfirmText(e.target.value)}
                  className="w-full bg-background rounded-lg px-3 py-2 text-sm border border-destructive/30 focus:outline-none focus:ring-2 focus:ring-destructive"
                />
                <div className="flex gap-2">
                  <button
                    onClick={async () => {
                      if (deleteConfirmText !== 'DELETE') return
                      try {
                        await api.delete('/users/me')
                        clearAuth()
                        navigate('/login')
                      } catch {
                        // If endpoint doesn't exist just logout
                        clearAuth()
                        navigate('/login')
                      }
                    }}
                    disabled={deleteConfirmText !== 'DELETE'}
                    className="px-4 py-2 bg-destructive text-destructive-foreground text-sm rounded-lg hover:bg-destructive/90 transition-colors disabled:opacity-40"
                  >
                    Delete My Account
                  </button>
                  <button
                    onClick={() => { setShowDeleteConfirm(false); setDeleteConfirmText('') }}
                    className="px-4 py-2 border border-border text-sm rounded-lg hover:bg-accent transition-colors"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </Layout>
  )
}

// Need this icon for stats
function MessageSquare({ className }: { className?: string }) {
  return (
    <svg className={className} xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
    </svg>
  )
}
