import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { TrendingUp, Award, MessageSquare, Flame, BookOpen, ArrowRight, AlertTriangle } from 'lucide-react'
import Layout from '@/components/Layout'
import ErrorBoundary from '@/components/ErrorBoundary'
import { StatCardsSkeleton, ListItemSkeleton } from '@/components/LoadingSkeleton'
import { progressApi, sessionsApi, modulesApi } from '@/lib/api'
import { useAuthStore } from '@/stores/auth'

export default function Dashboard() {
  const user = useAuthStore((s) => s.user)

  const { data: progress, isError: progressError } = useQuery({
    queryKey: ['progress'],
    queryFn: () => progressApi.list().then(r => r.data as any[]),
  })

  const { data: sessions, isLoading: sessionsLoading, isError: sessionsError } = useQuery({
    queryKey: ['sessions', 'coaching'],
    queryFn: () => sessionsApi.listCoaching({ page_size: 5 }).then(r => r.data),
  })

  const { data: modules } = useQuery({
    queryKey: ['modules'],
    queryFn: () => modulesApi.list({ status: 'published' }).then(r => r.data),
  })

  // Build module name lookup
  const moduleNames: Record<string, string> = {}
  modules?.items?.forEach((m: any) => { moduleNames[m.id] = m.name })

  const totalSessions = sessions?.total ?? 0
  const completed = progress?.reduce((a: number, p: any) => a + (p.sessions_completed ?? 0), 0) ?? 0
  const bestScore = progress?.reduce((a: number, p: any) => Math.max(a, p.best_score ?? 0), 0) ?? 0
  const maxStreak = progress?.reduce((a: number, p: any) => Math.max(a, p.streak_days ?? 0), 0) ?? 0

  const firstName = user?.full_name?.split(' ')[0] ?? 'there'

  return (
    <ErrorBoundary>
      <Layout>
        <div className="space-y-8">
          <div>
            <h1 className="text-2xl font-bold">Good to see you, {firstName} 👋</h1>
            <p className="text-muted-foreground mt-1">Here's your coaching overview</p>
          </div>

          {/* Stats */}
          {sessionsLoading ? (
            <StatCardsSkeleton />
          ) : (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {[
                { icon: MessageSquare, label: 'Total Sessions', value: totalSessions, color: 'text-blue-500' },
                { icon: TrendingUp, label: 'Completed', value: completed, color: 'text-green-500' },
                { icon: Award, label: 'Best Score', value: `${bestScore.toFixed(0)}%`, color: 'text-yellow-500' },
                { icon: Flame, label: 'Max Streak', value: `${maxStreak}d`, color: 'text-orange-500' },
              ].map(({ icon: Icon, label, value, color }) => (
                <div key={label} className="bg-card border border-border rounded-xl p-5">
                  <Icon className={`h-5 w-5 ${color} mb-3`} />
                  <div className="text-2xl font-bold">{value}</div>
                  <div className="text-sm text-muted-foreground mt-0.5">{label}</div>
                </div>
              ))}
            </div>
          )}

          {/* Recent sessions */}
          <div className="bg-card border border-border rounded-xl">
            <div className="flex items-center justify-between px-6 py-4 border-b border-border">
              <h2 className="font-semibold">Recent Sessions</h2>
              <Link to="/modules" className="text-sm text-primary flex items-center gap-1 hover:gap-2 transition-all">
                Start new <ArrowRight className="h-3.5 w-3.5" />
              </Link>
            </div>
            <div className="divide-y divide-border">
              {sessionsLoading && <ListItemSkeleton rows={3} />}

              {sessionsError && !sessionsLoading && (
                <div className="flex items-center gap-3 px-6 py-10 text-muted-foreground">
                  <AlertTriangle className="h-5 w-5 text-destructive opacity-70 flex-shrink-0" />
                  <p className="text-sm">Failed to load sessions. Please refresh the page.</p>
                </div>
              )}

              {!sessionsLoading && !sessionsError && sessions?.items?.length === 0 && (
                <div className="text-center py-10 text-muted-foreground">
                  <BookOpen className="h-8 w-8 mx-auto mb-3 opacity-30" />
                  <p className="text-sm">No sessions yet. Start your first coaching session.</p>
                </div>
              )}

              {!sessionsLoading && !sessionsError && sessions?.items?.map((s: any) => (
                <div key={s.id} className="flex items-center justify-between px-6 py-4">
                  <div>
                    <div className="font-medium text-sm">
                      {moduleNames[s.module_id] || 'Coaching Session'}
                    </div>
                    <div className="text-xs text-muted-foreground mt-0.5">
                      {s.created_at ? new Date(s.created_at).toLocaleDateString() : '—'}
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    {s.final_score != null && (
                      <span className={`text-sm font-semibold ${Number(s.final_score) >= 80 ? 'text-green-500' : Number(s.final_score) >= 60 ? 'text-yellow-500' : 'text-red-500'}`}>
                        {Number(s.final_score).toFixed(0)}%
                      </span>
                    )}
                    {s.status && (
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                        s.status === 'completed' ? 'bg-green-500/10 text-green-600' :
                        s.status === 'in_progress' ? 'bg-blue-500/10 text-blue-600' :
                        'bg-slate-500/10 text-slate-500'
                      }`}>{s.status}</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </Layout>
    </ErrorBoundary>
  )
}