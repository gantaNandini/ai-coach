import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
  TrendingUp, Award, MessageSquare, Flame, BookOpen,
  ArrowRight, Loader2, Play, MessageCircle, Trophy, Zap,
} from 'lucide-react'
import Layout from '@/components/Layout'
import { progressApi, sessionsApi, modulesApi, api } from '@/lib/api'
import { useAuthStore } from '@/stores/auth'
import { useRole } from '@/hooks/useRole'

function StatCard({ icon: Icon, label, value, color, sub }: any) {
  return (
    <div className="bg-card border border-border rounded-xl p-5 flex gap-4 items-start">
      <div className={`w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 ${color}`}>
        <Icon className="h-5 w-5" />
      </div>
      <div>
        <div className="text-2xl font-bold">{value}</div>
        <div className="text-sm text-muted-foreground">{label}</div>
        {sub && <div className="text-xs text-muted-foreground/60 mt-0.5">{sub}</div>}
      </div>
    </div>
  )
}

export default function Dashboard() {
  const user = useAuthStore(s => s.user)
  const { isAdmin } = useRole()

  const { data: progress } = useQuery({
    queryKey: ['progress'],
    queryFn: () => progressApi.list().then(r => r.data as any[]),
  })

  const { data: sessions } = useQuery({
    queryKey: ['sessions-dashboard'],
    queryFn: () => sessionsApi.listCoaching({ page_size: 5 }).then(r => r.data),
  })

  const { data: modules } = useQuery({
    queryKey: ['modules-published'],
    queryFn: () => modulesApi.list({ status: 'published' }).then(r => r.data),
  })

  const { data: myAchievements } = useQuery({
    queryKey: ['achievements-mine'],
    queryFn: () => api.get('/progress/achievements/mine').then(r => r.data as any[]),
  })

  const { data: analytics } = useQuery({
    queryKey: ['analytics-dashboard'],
    queryFn: () => api.get('/analytics/dashboard').then(r => r.data),
    enabled: isAdmin, // only fetch for admins — learners get 403
  })

  const moduleNames: Record<string, string> = {}
  modules?.items?.forEach((m: any) => { moduleNames[m.id] = m.name })

  const totalSessions = sessions?.total || 0
  const completed = progress?.reduce((a: number, p: any) => a + (p.sessions_completed || 0), 0) || 0
  const bestScore = progress?.reduce((a: number, p: any) => Math.max(a, Number(p.best_score) || 0), 0) || 0
  const maxStreak = progress?.reduce((a: number, p: any) => Math.max(a, p.streak_days || 0), 0) || 0
  const achievementsEarned = myAchievements?.length || 0

  const greet = () => {
    const h = new Date().getHours()
    if (h < 12) return 'Good morning'
    if (h < 17) return 'Good afternoon'
    return 'Good evening'
  }

  return (
    <Layout>
      <div className="space-y-8">
        {/* Hero */}
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-bold">
              {greet()}, {user?.full_name?.split(' ')[0]} 👋
            </h1>
            <p className="text-muted-foreground mt-1">Here's your coaching overview today</p>
          </div>
          {maxStreak > 0 && (
            <div className="flex items-center gap-1.5 bg-orange-500/10 text-orange-500 px-3 py-1.5 rounded-full text-sm font-semibold">
              <Flame className="h-4 w-4" />
              {maxStreak} day streak
            </div>
          )}
        </div>

        {/* Stats row */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard icon={MessageSquare} label="Total Sessions" value={totalSessions} color="bg-blue-500/10 text-blue-500" />
          <StatCard icon={TrendingUp} label="Completed" value={completed} color="bg-green-500/10 text-green-500" sub={`${totalSessions > 0 ? Math.round(completed/totalSessions*100) : 0}% rate`} />
          <StatCard icon={Award} label="Best Score" value={bestScore > 0 ? `${bestScore.toFixed(0)}%` : '—'} color="bg-yellow-500/10 text-yellow-500" />
          <StatCard icon={Trophy} label="Achievements" value={achievementsEarned} color="bg-purple-500/10 text-purple-500" sub="earned" />
        </div>

        {/* Quick actions */}
        <div>
          <h2 className="font-semibold mb-3">Quick Start</h2>
          <div className="grid sm:grid-cols-3 gap-3">
            <Link to="/modules"
              className="group flex items-center gap-4 p-4 bg-primary rounded-xl text-primary-foreground hover:bg-primary/90 transition-all hover:shadow-lg hover:shadow-primary/20">
              <div className="w-10 h-10 bg-white/20 rounded-lg flex items-center justify-center">
                <Play className="h-5 w-5" />
              </div>
              <div>
                <div className="font-semibold text-sm">Start Session</div>
                <div className="text-xs text-primary-foreground/70">SBI, GROW & more</div>
              </div>
              <ArrowRight className="h-4 w-4 ml-auto opacity-0 group-hover:opacity-100 transition-opacity" />
            </Link>
            <Link to="/modules"
              className="group flex items-center gap-4 p-4 bg-card border border-border rounded-xl hover:border-primary/50 transition-all">
              <div className="w-10 h-10 bg-violet-500/10 rounded-lg flex items-center justify-center">
                <MessageCircle className="h-5 w-5 text-violet-500" />
              </div>
              <div>
                <div className="font-semibold text-sm">Roleplay Practice</div>
                <div className="text-xs text-muted-foreground">AI conversation partner</div>
              </div>
              <ArrowRight className="h-4 w-4 ml-auto opacity-0 group-hover:opacity-100 transition-opacity text-muted-foreground" />
            </Link>
            {isAdmin && (
              <Link to="/knowledge"
                className="group flex items-center gap-4 p-4 bg-card border border-border rounded-xl hover:border-primary/50 transition-all">
                <div className="w-10 h-10 bg-green-500/10 rounded-lg flex items-center justify-center">
                  <BookOpen className="h-5 w-5 text-green-500" />
                </div>
                <div>
                  <div className="font-semibold text-sm">Knowledge Base</div>
                  <div className="text-xs text-muted-foreground">Upload company docs</div>
                </div>
                <ArrowRight className="h-4 w-4 ml-auto opacity-0 group-hover:opacity-100 transition-opacity text-muted-foreground" />
              </Link>
            )}
          </div>
        </div>

        <div className="grid lg:grid-cols-2 gap-6">
          {/* Recent sessions */}
          <div className="bg-card border border-border rounded-xl overflow-hidden">
            <div className="flex items-center justify-between px-5 py-4 border-b border-border">
              <h2 className="font-semibold">Recent Sessions</h2>
              <Link to="/modules" className="text-xs text-primary hover:underline">Start new</Link>
            </div>
            <div className="divide-y divide-border">
              {!sessions && (
                <div className="flex justify-center py-8"><Loader2 className="h-5 w-5 animate-spin text-muted-foreground" /></div>
              )}
              {sessions?.items?.length === 0 && (
                <div className="text-center py-10 text-muted-foreground">
                  <BookOpen className="h-8 w-8 mx-auto mb-2 opacity-20" />
                  <p className="text-sm">No sessions yet — start your first one!</p>
                </div>
              )}
              {sessions?.items?.map((s: any) => (
                <div key={s.id} className="flex items-center justify-between px-5 py-3.5">
                  <div className="min-w-0">
                    <div className="text-sm font-medium truncate">{moduleNames[s.module_id] || 'Coaching Session'}</div>
                    <div className="text-xs text-muted-foreground mt-0.5">{new Date(s.created_at).toLocaleDateString('en', {month:'short',day:'numeric',year:'numeric'})}</div>
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0 ml-4">
                    {s.final_score != null && (
                      <span className={`text-sm font-bold ${Number(s.final_score)>=80?'text-green-500':Number(s.final_score)>=60?'text-yellow-500':'text-red-500'}`}>
                        {Number(s.final_score).toFixed(0)}%
                      </span>
                    )}
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                      s.status==='completed'?'bg-green-500/10 text-green-600':
                      s.status==='in_progress'?'bg-blue-500/10 text-blue-600':
                      'bg-muted text-muted-foreground'}`}>
                      {s.status}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Module progress + analytics */}
          <div className="space-y-4">
            {/* Analytics mini */}
            {analytics && (
              <div className="bg-card border border-border rounded-xl p-5">
                <h2 className="font-semibold mb-4">Last 30 Days</h2>
                <div className="grid grid-cols-2 gap-3">
                  <div className="text-center">
                    <div className="text-2xl font-bold">{analytics.completion_rate?.toFixed(0) || 0}%</div>
                    <div className="text-xs text-muted-foreground">Completion rate</div>
                  </div>
                  <div className="text-center">
                    <div className="text-2xl font-bold">{analytics.avg_score ? Number(analytics.avg_score).toFixed(0) : '—'}</div>
                    <div className="text-xs text-muted-foreground">Avg score</div>
                  </div>
                </div>
              </div>
            )}

            {/* Module progress */}
            {progress && progress.length > 0 && (
              <div className="bg-card border border-border rounded-xl p-5">
                <h2 className="font-semibold mb-4">Module Progress</h2>
                <div className="space-y-3">
                  {progress.slice(0,3).map((p: any) => (
                    <div key={p.id}>
                      <div className="flex justify-between text-sm mb-1">
                        <span className="truncate text-muted-foreground">{moduleNames[p.module_id] || 'Module'}</span>
                        <span className="ml-2 font-medium">{Number(p.completion_percent).toFixed(0)}%</span>
                      </div>
                      <div className="h-1.5 bg-muted rounded-full overflow-hidden">
                        <div className="h-full bg-primary rounded-full" style={{width:`${p.completion_percent}%`}} />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </Layout>
  )
}
