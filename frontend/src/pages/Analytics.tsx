import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, LineChart, Line, PieChart, Pie, Cell, Legend,
} from 'recharts'
import { TrendingUp, Users, MessageSquare, Award, AlertTriangle, Calendar } from 'lucide-react'
import Layout from '@/components/Layout'
import ErrorBoundary from '@/components/ErrorBoundary'
import { StatCardsSkeleton, ChartSkeleton } from '@/components/LoadingSkeleton'
import { api } from '@/lib/api'

const COLORS = ['hsl(var(--primary))', '#22c55e', '#f59e0b', '#ef4444', '#8b5cf6']
const DATE_OPTIONS = [
  { label: 'Last 7 days', value: 7 },
  { label: 'Last 30 days', value: 30 },
  { label: 'Last 90 days', value: 90 },
]

export default function Analytics() {
  const [days, setDays] = useState(30)

  const { data: dashboard, isLoading, isError } = useQuery({
    queryKey: ['analytics-dashboard', days],
    queryFn: () => api.get('/analytics/dashboard', { params: { days } }).then(r => r.data),
    refetchInterval: 30000,
  })

  const { data: trendData } = useQuery({
    queryKey: ['session-trend', days],
    queryFn: () => api.get('/analytics/session-trend', { params: { days } }).then(r => r.data),
  })

  const { data: modulePerf } = useQuery({
    queryKey: ['module-performance', days],
    queryFn: () => api.get('/analytics/module-performance', { params: { days } }).then(r => r.data),
  })

  const sessionTrend = (trendData?.items || []).map((d: any) => ({
    date: new Date(d.date).toLocaleDateString('en', { month: 'short', day: 'numeric' }),
    count: d.count,
  }))

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
    <ErrorBoundary>
      <Layout>
        <div className="space-y-8">
          {/* Header + date range */}
          <div className="flex items-center justify-between flex-wrap gap-4">
            <div>
              <h1 className="text-2xl font-bold">Analytics</h1>
              <p className="text-muted-foreground mt-1">
                Real-time coaching performance
              </p>
            </div>
            <div className="flex items-center gap-2 bg-card border border-border rounded-lg p-1">
              <Calendar className="h-4 w-4 text-muted-foreground ml-2" />
              {DATE_OPTIONS.map(opt => (
                <button
                  key={opt.value}
                  onClick={() => setDays(opt.value)}
                  className={`px-3 py-1.5 text-sm rounded-md transition-colors ${
                    days === opt.value
                      ? 'bg-primary text-primary-foreground font-medium'
                      : 'text-muted-foreground hover:text-foreground'
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          {isLoading && (
            <div className="space-y-6">
              <StatCardsSkeleton />
              <ChartSkeleton height={240} />
            </div>
          )}

          {isError && !isLoading && (
            <div className="flex items-center gap-3 p-6 bg-card border border-border rounded-xl text-muted-foreground">
              <AlertTriangle className="h-5 w-5 text-destructive opacity-70 flex-shrink-0" />
              <p className="text-sm">Failed to load analytics data. Please refresh the page.</p>
            </div>
          )}

          {!isLoading && !isError && (
            <>
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

              {/* Sessions per day — line chart from real /session-trend endpoint */}
              {sessionTrend.length > 1 && (
                <div className="bg-card border border-border rounded-xl p-6">
                  <h2 className="font-semibold mb-6">Sessions per Day</h2>
                  <ResponsiveContainer width="100%" height={220}>
                    <LineChart data={sessionTrend}>
                      <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                      <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                      <YAxis allowDecimals={false} tick={{ fontSize: 12 }} />
                      <Tooltip />
                      <Line type="monotone" dataKey="count" name="Sessions"
                        stroke="hsl(var(--primary))" strokeWidth={2}
                        dot={{ r: 3 }} activeDot={{ r: 5 }} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              )}

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Completion funnel */}
                {dashboard && dashboard.sessions_started > 0 && (
                  <div className="bg-card border border-border rounded-xl p-6">
                    <h2 className="font-semibold mb-4">Completion Rate</h2>
                    <div className="flex items-center gap-4 mb-4">
                      <div className={`text-4xl font-bold ${dashboard.completion_rate >= 70 ? 'text-green-500' : dashboard.completion_rate >= 40 ? 'text-yellow-500' : 'text-red-500'}`}>
                        {Number(dashboard.completion_rate ?? 0).toFixed(1)}%
                      </div>
                      <div className="text-sm text-muted-foreground">
                        {dashboard.sessions_completed} completed of {dashboard.sessions_started} started
                      </div>
                    </div>
                    {funnelData.length > 0 && (
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
                    )}
                  </div>
                )}

                {/* Avg score */}
                {dashboard && (
                  <div className="bg-card border border-border rounded-xl p-6">
                    <h2 className="font-semibold mb-4">Average Score</h2>
                    <div className={`text-4xl font-bold mb-3 ${Number(dashboard.avg_score) >= 75 ? 'text-green-500' : Number(dashboard.avg_score) >= 50 ? 'text-yellow-500' : 'text-muted-foreground'}`}>
                      {dashboard.avg_score ? `${Number(dashboard.avg_score).toFixed(1)}%` : '—'}
                    </div>
                    {dashboard.avg_score > 0 && (
                      <div className="h-3 w-full bg-muted rounded-full overflow-hidden">
                        <div className={`h-full rounded-full transition-all ${Number(dashboard.avg_score) >= 75 ? 'bg-green-500' : Number(dashboard.avg_score) >= 50 ? 'bg-yellow-500' : 'bg-red-500'}`}
                          style={{ width: `${Math.min(100, Number(dashboard.avg_score))}%` }} />
                      </div>
                    )}
                    <p className="text-sm text-muted-foreground mt-3">
                      {dashboard.avg_score > 0 ? 'Across all completed sessions' : 'Complete sessions to see average score'}
                    </p>
                  </div>
                )}
              </div>

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

              {!isLoading && dashboard?.sessions_started === 0 && (
                <div className="text-center py-12 text-muted-foreground">
                  <TrendingUp className="h-10 w-10 mx-auto mb-3 opacity-20" />
                  <p>No session data yet. Complete a coaching session to see analytics.</p>
                </div>
              )}
            </>
          )}
        </div>
      </Layout>
    </ErrorBoundary>
  )
}
