import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { BookOpen, Play, Loader2, MessageSquare, ChevronDown, ChevronUp, GitBranch } from 'lucide-react'
import Layout from '@/components/Layout'
import { modulesApi, sessionsApi } from '@/lib/api'

const FRAMEWORK_COLORS: Record<string, string> = {
  SBI: 'bg-blue-500/10 text-blue-600',
  GROW: 'bg-green-500/10 text-green-600',
}

export default function Modules() {
  const navigate = useNavigate()
  const [expanded, setExpanded] = useState<string | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['modules'],
    queryFn: () => modulesApi.list({ status: 'published' }).then(r => r.data),
  })

  // Load full module detail when expanded
  const { data: moduleDetail } = useQuery({
    queryKey: ['module-detail', expanded],
    queryFn: () => modulesApi.get(expanded!).then(r => r.data),
    enabled: !!expanded,
  })

  const startCoaching = useMutation({
    mutationFn: (moduleId: string) => sessionsApi.createCoaching(moduleId),
    onSuccess: (res) => navigate(`/sessions/coaching/${res.data.id}`),
  })

  const startRoleplay = useMutation({
    mutationFn: (moduleId: string) => sessionsApi.createRoleplay(moduleId),
    onSuccess: (res) => navigate(`/sessions/roleplay/${res.data.id}`),
  })

  return (
    <Layout>
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold">Coaching Modules</h1>
          <p className="text-muted-foreground mt-1">Choose a framework to start practicing</p>
        </div>

        {isLoading && <div className="flex justify-center py-20"><Loader2 className="h-6 w-6 animate-spin text-muted-foreground" /></div>}

        {data?.items?.length === 0 && (
          <div className="text-center py-20 text-muted-foreground">
            <BookOpen className="h-12 w-12 mx-auto mb-4 opacity-20" />
            <p>No modules available yet.</p>
          </div>
        )}

        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-5">
          {data?.items?.map((m: any) => {
            const detail = expanded === m.id ? moduleDetail : null
            const framework = detail?.framework_name || m.key?.split('_')[0]?.toUpperCase() || ''
            const steps = detail?.framework_steps || []
            const intakeFields = detail?.intake_schema || []
            const isOpen = expanded === m.id

            return (
              <div key={m.id}
                className={`bg-card border rounded-xl transition-colors ${isOpen ? 'border-primary/50' : 'border-border hover:border-primary/30'}`}>
                <div className="p-6">
                  <div className="flex items-start justify-between mb-3">
                    <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
                      <BookOpen className="h-5 w-5 text-primary" />
                    </div>
                    {framework && (
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${FRAMEWORK_COLORS[framework] || 'bg-muted text-muted-foreground'}`}>
                        {framework}
                      </span>
                    )}
                  </div>

                  <h3 className="font-semibold mb-1">{m.name}</h3>
                  {m.blurb && <p className="text-sm text-muted-foreground mb-3">{m.blurb}</p>}

                  {/* Expandable details */}
                  {isOpen && detail && (
                    <div className="mt-3 mb-4 space-y-3">
                      {steps.length > 0 && (
                        <div>
                          <div className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground mb-2">
                            <GitBranch className="h-3.5 w-3.5" /> Framework Steps
                          </div>
                          <div className="space-y-1">
                            {steps.sort((a: any, b: any) => a.step_order - b.step_order).map((s: any, i: number) => (
                              <div key={s.id} className="flex gap-2 text-xs">
                                <span className="w-5 h-5 rounded-full bg-primary/10 text-primary flex items-center justify-center flex-shrink-0 font-bold">{i + 1}</span>
                                <div>
                                  <span className="font-medium">{s.title}</span>
                                  {s.description && <p className="text-muted-foreground mt-0.5">{s.description}</p>}
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {intakeFields.length > 0 && (
                        <div>
                          <div className="text-xs font-medium text-muted-foreground mb-1.5">Intake Fields</div>
                          <div className="flex flex-wrap gap-1">
                            {intakeFields.map((f: any) => (
                              <span key={f.key} className="text-xs px-2 py-0.5 bg-muted rounded-full">
                                {f.label}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  <div className="flex gap-2 mt-4">
                    <button
                      onClick={() => startCoaching.mutate(m.id)}
                      disabled={startCoaching.isPending}
                      className="flex-1 flex items-center justify-center gap-2 px-3 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 transition-colors disabled:opacity-60">
                      {startCoaching.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
                      Coach
                    </button>
                    <button
                      onClick={() => startRoleplay.mutate(m.id)}
                      disabled={startRoleplay.isPending}
                      className="flex-1 flex items-center justify-center gap-2 px-3 py-2 bg-secondary text-secondary-foreground rounded-lg text-sm font-medium hover:bg-secondary/80 transition-colors disabled:opacity-60">
                      {startRoleplay.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <MessageSquare className="h-3.5 w-3.5" />}
                      Roleplay
                    </button>
                    <button
                      onClick={() => setExpanded(isOpen ? null : m.id)}
                      className="px-2 py-2 hover:bg-muted rounded-lg text-muted-foreground transition-colors">
                      {isOpen ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                    </button>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </Layout>
  )
}
