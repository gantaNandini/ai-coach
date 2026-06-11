import { useQuery } from '@tanstack/react-query'
import { Database, Cpu, Activity, Settings, CheckCircle, XCircle, AlertCircle, RefreshCw } from 'lucide-react'
import Layout from '@/components/Layout'
import { api } from '@/lib/api'
import { useAuthStore } from '@/stores/auth'

function StatusBadge({ status }: { status: string }) {
  if (status === 'ok' || status?.startsWith('ok')) return (
    <span className="flex items-center gap-1.5 text-green-600 text-sm">
      <CheckCircle className="h-4 w-4" /> {status}
    </span>
  )
  if (status === 'not_installed' || status?.startsWith('offline')) return (
    <span className="flex items-center gap-1.5 text-yellow-600 text-sm">
      <AlertCircle className="h-4 w-4" /> {status}
    </span>
  )
  if (status?.startsWith('error') || status?.startsWith('http_')) return (
    <span className="flex items-center gap-1.5 text-red-600 text-sm">
      <XCircle className="h-4 w-4" /> {status}
    </span>
  )
  return <span className="text-muted-foreground text-sm">{status ?? 'unknown'}</span>
}

export default function Admin() {
  const user = useAuthStore(s => s.user)

  const { data: health, refetch: refetchHealth, isLoading: loadingHealth } = useQuery({
    queryKey: ['monitoring-health'],
    queryFn: () => api.get('/monitoring/health').then(r => r.data),
    refetchInterval: 30000,
  })

  const { data: tasks, refetch: refetchTasks } = useQuery({
    queryKey: ['monitoring-tasks'],
    queryFn: () => api.get('/monitoring/tasks?limit=20').then(r => r.data),
    refetchInterval: 5000,
  })

  const { data: stats, refetch: refetchStats } = useQuery({
    queryKey: ['monitoring-stats'],
    queryFn: () => api.get('/monitoring/stats').then(r => r.data),
  })

  const { data: config } = useQuery({
    queryKey: ['monitoring-config'],
    queryFn: () => api.get('/monitoring/config').then(r => r.data),
  })

  const taskStatusColor = (s: string) => ({
    completed: 'text-green-600 bg-green-500/10',
    failed: 'text-red-600 bg-red-500/10',
    running: 'text-blue-600 bg-blue-500/10',
    queued: 'text-yellow-600 bg-yellow-500/10',
    retry_2: 'text-orange-600 bg-orange-500/10',
    retry_3: 'text-orange-600 bg-orange-500/10',
  }[s] || 'text-muted-foreground bg-muted')

  return (
    <Layout>
      <div className="space-y-8">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">System Monitor</h1>
            <p className="text-muted-foreground mt-1">Real-time component health and task status</p>
          </div>
          <button onClick={() => { refetchHealth(); refetchTasks(); refetchStats() }}
            className="flex items-center gap-2 px-3 py-2 bg-secondary text-secondary-foreground rounded-lg text-sm hover:bg-secondary/80">
            <RefreshCw className="h-4 w-4" /> Refresh
          </button>
        </div>

        {/* Component Health */}
        <div className="bg-card border border-border rounded-xl p-6">
          <div className="flex items-center gap-2 mb-4">
            <Activity className="h-5 w-5 text-primary" />
            <h2 className="font-semibold">Component Health</h2>
          </div>
          {loadingHealth ? (
            <div className="text-sm text-muted-foreground">Checking...</div>
          ) : (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {['database', 'pgvector', 'ollama', 'embeddings'].map(key => (
                <div key={key} className="p-3 bg-muted/50 rounded-lg">
                  <div className="text-xs text-muted-foreground uppercase mb-1.5">{key}</div>
                  <StatusBadge status={health?.components?.[key] ?? 'unknown'} />
                </div>
              ))}
            </div>
          )}
          <div className="flex gap-4 mt-4 text-xs text-muted-foreground">
            <span className={health?.rag_enabled ? 'text-green-600' : 'text-yellow-600'}>
              {health?.rag_enabled ? '✓ RAG vector search enabled' : '⚠ RAG: full-text fallback (pgvector missing)'}
            </span>
            <span className={health?.ai_enabled ? 'text-green-600' : 'text-yellow-600'}>
              {health?.ai_enabled ? '✓ AI generation enabled' : '⚠ AI: offline (Ollama not running)'}
            </span>
          </div>
        </div>

        {/* Background Tasks */}
        <div className="bg-card border border-border rounded-xl p-6">
          <div className="flex items-center gap-2 mb-4">
            <Cpu className="h-5 w-5 text-primary" />
            <h2 className="font-semibold">Background Tasks</h2>
            {tasks?.summary && (
              <div className="ml-auto flex gap-2">
                {Object.entries(tasks.summary).map(([status, count]: [string, any]) => (
                  <span key={status} className={`text-xs px-2 py-0.5 rounded-full font-medium ${taskStatusColor(status)}`}>
                    {status}: {count}
                  </span>
                ))}
              </div>
            )}
          </div>
          {tasks?.tasks?.length === 0 && (
            <p className="text-sm text-muted-foreground">No tasks yet. Ingest a knowledge source to see tasks here.</p>
          )}
          <div className="space-y-2">
            {tasks?.tasks?.map((t: any) => (
              <div key={t.id} className="flex items-center justify-between py-2 border-b border-border last:border-0">
                <div>
                  <span className="text-sm font-medium font-mono">{t.name}</span>
                  <span className="ml-2 text-xs text-muted-foreground">#{t.id}</span>
                  {t.error && <p className="text-xs text-red-500 mt-0.5 truncate max-w-sm">{t.error}</p>}
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-xs text-muted-foreground">{new Date(t.timestamp).toLocaleTimeString()}</span>
                  <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${taskStatusColor(t.status)}`}>{t.status}</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Database Stats */}
        {stats?.table_counts && (
          <div className="bg-card border border-border rounded-xl p-6">
            <div className="flex items-center gap-2 mb-4">
              <Database className="h-5 w-5 text-primary" />
              <h2 className="font-semibold">Database Row Counts</h2>
            </div>
            <div className="grid grid-cols-3 md:grid-cols-5 gap-3">
              {Object.entries(stats.table_counts).map(([table, count]: [string, any]) => (
                <div key={table} className="p-3 bg-muted/50 rounded-lg text-center">
                  <div className="text-xl font-bold">{count}</div>
                  <div className="text-xs text-muted-foreground mt-0.5 truncate">{table.replace('_', ' ')}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Config */}
        {config && (
          <div className="bg-card border border-border rounded-xl p-6">
            <div className="flex items-center gap-2 mb-4">
              <Settings className="h-5 w-5 text-primary" />
              <h2 className="font-semibold">Configuration</h2>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3 text-sm">
              {Object.entries(config).map(([key, val]: [string, any]) => (
                <div key={key} className="flex flex-col gap-0.5">
                  <span className="text-xs text-muted-foreground">{key}</span>
                  <span className="font-mono text-xs truncate">{String(val)}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </Layout>
  )
}
