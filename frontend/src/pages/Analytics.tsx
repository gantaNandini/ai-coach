import { useQuery } from '@tanstack/react-query'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, LineChart, Line, PieChart, Pie, Cell, Legend,
} from 'recharts'
import { TrendingUp, Users, MessageSquare, Zap, Award, Loader2 } from 'lucide-react'
import Layout from '@/components/Layout'
import { api } from '@/lib/api'

const COLORS = ['hsl(var(--primary))', '#22c55e', '#f59e0b', '#ef4444', '#8b5cf6']

export default function Analytics() {
  const { data: dashboard, isLoading } = useQuery({
    queryKey: ['analytics-dashboard'],
    queryFn: () => api.get('/analytics/dashboard').then(r => r.data),
    refetchInterval: 30000,
  })

  const { data: sessions } = useQuery({
    queryKey: ['sessions-all'],
    queryFn: () => api.get('/sessions/coaching', { params: { page_size: 100 } }).then(r => r.data),
  })

  const { data: modulePerf } = useQuery({
    queryKey: ['module-performance'],
    queryFn: () => api.get('/analytics/module-performance').then(r => r.data),
  })

  // Score trend from real completed sessions
  const scoreTrend = (sessions?.items || [])
    .filter((s: any) => s.final_score != null && s.status === 'completed')
    .slice(-15)
    .map((s: any, i: number) => ({
      session: i + 1,
      score: parseFloat(Number(s.final_score).toFixed(1)),
      date: new Date(s.created_at).toLocaleDateString('en', { month: 'short', day: 'numeric' }),
    }))

  // Session funnel data for pie chart
  const funnelData = dashboard ? [
    { name: 'Completed', value: dashboard.sessions_completed },
    { name: 'In Progress', value: Math.max(0, dashboard.sessions_started - dashboard.sessions_completed - dashboard.sessions_abandoned) },
    { name: 'Abandoned', value: dashboard.sessions_abandoned },
  ].filter(d => d.value > 0) : []

  const stats = [
    { label: 'Sessions Started', value: dashboard?.sessions_started ?? 0, icon: MessageSquare, color: 'text-blue-500' },
    { label: 'Sessions Completed', value: dashboard?.sessions_completed ?? 0, icon: TrendingUp, color: 'text-green-500' },
    { label: 'Active Users', value: dashboard?.active_users ?? 0, icon: Users, color: 'text-purple-500' },
    { label: 'Avg Score', value: dashboard?.avg_score ? `${Number(dashboard.avg_score).toFixed(1)}%` : '—', icon: Award, color: 'text-yellow-500' },
  ]

  return (
    <Layout>
      <div className="space-y-8">
        <div>
          <h1 className="text-2xl font-bold">Analytics</h1>
          <p className="text-muted-foreground mt-1">
            Real-time coaching performance — last {dashboard?.period_days ?? 30} days
          </p>
        </div>

        {isLoading && (
          <div className="flex justify-center py-16">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        )}

        {/* KPI cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {stats.map(({ label, value, icon: Icon, color }) => (
            <div key={label} className="bg-card border border-border rounded-xl p-5">
              <Icon className={`h-5 w-5 ${color} mb-3`} />
              <div className="text-2xl font-bold">{value}</div>
              <div className="text-sm text-muted-foreground mt-0.5">{label}</div>
            </div>
          ))}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Completion rate */}
          {dashboard && (
            <div className="bg-card border border-border rounded-xl p-6">
              <h2 className="font-semibold mb-4">Completion Rate</h2>
              <div className="flex items-center gap-4">
                <div className={`text-4xl font-bold ${dashboard.completion_rate >= 70 ? 'text-green-500' : dashboard.completion_rate >= 40 ? 'text-yellow-500' : 'text-red-500'}`}>
                  {dashboard.completion_rate.toFixed(1)}%
                </div>
                <div>
                  <div className="text-sm text-muted-foreground">
                    {dashboard.sessions_completed} completed of {dashboard.sessions_started} started
                  </div>
                  <div className="mt-2 h-2 w-40 bg-muted rounded-full overflow-hidden">
                    <div className="h-full bg-primary rounded-full transition-all"
                      style={{ width: `${Math.min(100, dashboard.completion_rate)}%` }} />
                  </div>
                </div>
              </div>
              {funnelData.length > 0 && (
                <div className="mt-6">
                  <ResponsiveContainer width="100%" height={160}>
                    <PieChart>
                      <Pie data={funnelData} cx="50%" cy="50%" innerRadius={40} outerRadius={65}
                        paddingAngle={3} dataKey="value">
                        {funnelData.map((_, i) => (
                          <Cell key={i} fill={COLORS[i % COLORS.length]} />
                        ))}
                      </Pie>
                      <Tooltip />
                      <Legend iconSize={8} wrapperStyle={{ fontSize: '12px' }} />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              )}
            </div>
          )}

          {/* Avg score gauge */}
          {dashboard && (
            <div className="bg-card border border-border rounded-xl p-6">
              <h2 className="font-semibold mb-4">Average Score</h2>
              <div className="flex items-center gap-4">
                <div className={`text-4xl font-bold ${Number(dashboard.avg_score) >= 75 ? 'text-green-500' : Number(dashboard.avg_score) >= 50 ? 'text-yellow-500' : 'text-muted-foreground'}`}>
                  {dashboard.avg_score ? `${Number(dashboard.avg_score).toFixed(1)}%` : '—'}
                </div>
                <div className="text-sm text-muted-foreground">
                  {dashboard.avg_score > 0 ? 'across all completed sessions' : 'Complete sessions to see average score'}
                </div>
              </div>
              {dashboard.avg_score > 0 && (
                <div className="mt-4 h-3 w-full bg-muted rounded-full overflow-hidden">
                  <div className={`h-full rounded-full transition-all ${Number(dashboard.avg_score) >= 75 ? 'bg-green-500' : Number(dashboard.avg_score) >= 50 ? 'bg-yellow-500' : 'bg-red-500'}`}
                    style={{ width: `${Math.min(100, Number(dashboard.avg_score))}%` }} />
                </div>
              )}
              {dashboard.total_ai_tokens > 0 && (
                <div className="mt-4 flex items-center gap-2 text-sm text-muted-foreground">
                  <Zap className="h-4 w-4 text-orange-400" />
                  {dashboard.total_ai_tokens.toLocaleString()} AI tokens used
                </div>
              )}
            </div>
          )}
        </div>

        {/* Score trend */}
        {scoreTrend.length > 1 && (
          <div className="bg-card border border-border rounded-xl p-6">
            <h2 className="font-semibold mb-6">Score Trend</h2>
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={scoreTrend}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                <YAxis domain={[0, 100]} tick={{ fontSize: 12 }} tickFormatter={v => `${v}%`} />
                <Tooltip formatter={(v: any) => [`${v}%`, 'Score']} />
                <Line type="monotone" dataKey="score" stroke="hsl(var(--primary))" strokeWidth={2}
                  dot={{ r: 4 }} activeDot={{ r: 6 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Module performance */}
        {modulePerf?.items?.length > 0 && (
          <div className="bg-card border border-border rounded-xl p-6">
            <h2 className="font-semibold mb-6">Module Performance</h2>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={modulePerf.items}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                <XAxis dataKey="module_id" tick={{ fontSize: 10 }}
                  tickFormatter={v => v.slice(0, 8) + '...'} />
                <YAxis tick={{ fontSize: 12 }} tickFormatter={v => `${v}%`} />
                <Tooltip formatter={(v: any, name: string) => [`${Number(v).toFixed(1)}%`, name === 'avg_score' ? 'Avg Score' : 'Completion']} />
                <Bar dataKey="avg_score" name="avg_score" fill="hsl(var(--primary))" radius={[4, 4, 0, 0]} />
                <Bar dataKey="completion_rate" name="completion_rate" fill="#22c55e" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Recent scores bar chart */}
        {scoreTrend.length > 0 && (
          <div className="bg-card border border-border rounded-xl p-6">
            <h2 className="font-semibold mb-6">Recent Session Scores</h2>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={scoreTrend}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                <YAxis domain={[0, 100]} tick={{ fontSize: 12 }} tickFormatter={v => `${v}%`} />
                <Tooltip formatter={(v: any) => [`${v}%`, 'Score']} />
                <Bar dataKey="score" fill="hsl(var(--primary))" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}

        {!isLoading && dashboard?.sessions_started === 0 && (
          <div className="text-center py-12 text-muted-foreground">
            <TrendingUp className="h-10 w-10 mx-auto mb-3 opacity-20" />
            <p>No session data yet. Complete a coaching session to see analytics.</p>
          </div>
        )}
      </div>
    </Layout>
  )
}
