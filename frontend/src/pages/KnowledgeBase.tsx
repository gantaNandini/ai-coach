import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Database, Plus, Upload, FileText, Link as LinkIcon, Trash2, Loader2, ChevronDown, ChevronUp, Check, X, RefreshCw, AlertTriangle } from 'lucide-react'
import Layout from '@/components/Layout'
import ErrorBoundary from '@/components/ErrorBoundary'
import { KbListSkeleton } from '@/components/LoadingSkeleton'
import { knowledgeApi } from '@/lib/api'

function SourceStatusBadge({ status }: { status: string }) {
  const cfg = {
    completed: 'bg-green-500/10 text-green-600',
    failed: 'bg-red-500/10 text-red-600',
    processing: 'bg-blue-500/10 text-blue-600 animate-pulse',
    pending: 'bg-yellow-500/10 text-yellow-600',
  }[status] ?? 'bg-muted text-muted-foreground'
  return <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${cfg}`}>{status}</span>
}

export default function KnowledgeBase() {
  const qc = useQueryClient()
  const [selectedKb, setSelectedKb] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)
  const [newKbName, setNewKbName] = useState('')
  const [addingText, setAddingText] = useState(false)
  const [addingUrl, setAddingUrl] = useState(false)
  const [textTitle, setTextTitle] = useState('')
  const [textContent, setTextContent] = useState('')
  const [urlTitle, setUrlTitle] = useState('')
  const [urlValue, setUrlValue] = useState('')

  const { data: kbs, isLoading, isError } = useQuery({
    queryKey: ['knowledge-bases'],
    queryFn: () => knowledgeApi.list().then(r => r.data),
  })

  // Poll sources every 3s when any source is pending/processing
  const { data: sources } = useQuery({
    queryKey: ['sources', selectedKb],
    queryFn: () => knowledgeApi.listSources(selectedKb!).then(r => r.data),
    enabled: !!selectedKb,
    refetchInterval: (data: any) => {
      const items = data?.state?.data?.items ?? []
      const needsPoll = items.some((s: any) => s.status === 'pending' || s.status === 'processing')
      return needsPoll ? 3000 : false
    },
  })

  const createKb = useMutation({
    mutationFn: (name: string) => knowledgeApi.create(name),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['knowledge-bases'] }); setCreating(false); setNewKbName('') },
  })

  const deleteKb = useMutation({
    mutationFn: (id: string) => knowledgeApi.delete(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['knowledge-bases'] }); setSelectedKb(null) },
  })

  const addText = useMutation({
    mutationFn: () => knowledgeApi.addText(selectedKb!, textTitle, textContent),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['sources', selectedKb] })
      qc.invalidateQueries({ queryKey: ['knowledge-bases'] })
      setAddingText(false); setTextTitle(''); setTextContent('')
    },
  })

  const addUrl = useMutation({
    mutationFn: () => knowledgeApi.addUrl(selectedKb!, urlTitle, urlValue),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['sources', selectedKb] })
      qc.invalidateQueries({ queryKey: ['knowledge-bases'] })
      setAddingUrl(false); setUrlTitle(''); setUrlValue('')
    },
  })

  const deleteSource = useMutation({
    mutationFn: ({ kbId, srcId }: { kbId: string; srcId: string }) => knowledgeApi.deleteSource(kbId, srcId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['sources', selectedKb] })
      qc.invalidateQueries({ queryKey: ['knowledge-bases'] })
    },
  })

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!selectedKb || !e.target.files?.[0]) return
    const file = e.target.files[0]
    const form = new FormData()
    form.append('file', file)
    await fetch(`/api/v1/knowledge/${selectedKb}/sources/upload`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${localStorage.getItem('access_token')}` },
      body: form,
    })
    qc.invalidateQueries({ queryKey: ['sources', selectedKb] })
    qc.invalidateQueries({ queryKey: ['knowledge-bases'] })
    e.target.value = ''
  }

  return (
    <ErrorBoundary>
      <Layout>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">Knowledge Base</h1>
            <p className="text-muted-foreground mt-1">Upload company knowledge to power AI coaching</p>
          </div>
          <button onClick={() => setCreating(true)}
            className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 transition-colors">
            <Plus className="h-4 w-4" /> New KB
          </button>
        </div>

        {creating && (
          <div className="bg-card border border-border rounded-xl p-5">
            <h3 className="font-medium mb-3">Create Knowledge Base</h3>
            <div className="flex gap-3">
              <input value={newKbName} onChange={e => setNewKbName(e.target.value)}
                placeholder="Knowledge base name..."
                className="flex-1 bg-muted rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary" />
              <button onClick={() => createKb.mutate(newKbName)} disabled={!newKbName.trim() || createKb.isPending}
                className="px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm disabled:opacity-50 hover:bg-primary/90">
                {createKb.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}
              </button>
              <button onClick={() => setCreating(false)} className="px-3 py-2 hover:bg-muted rounded-lg"><X className="h-4 w-4" /></button>
            </div>
          </div>
        )}

        {isLoading && <KbListSkeleton />}

        {isError && !isLoading && (
          <div className="flex items-center gap-3 p-6 bg-card border border-border rounded-xl text-muted-foreground">
            <AlertTriangle className="h-5 w-5 text-destructive opacity-70 flex-shrink-0" />
            <p className="text-sm">Failed to load knowledge bases. Please refresh the page.</p>
          </div>
        )}

        {kbs?.items?.length === 0 && !isLoading && !isError && (
          <div className="text-center py-20 text-muted-foreground">
            <Database className="h-12 w-12 mx-auto mb-4 opacity-20" />
            <p>No knowledge bases yet. Create one to upload documents.</p>
          </div>
        )}

        <div className="space-y-3">
          {kbs?.items?.map((kb: any) => (
            <div key={kb.id} className="bg-card border border-border rounded-xl overflow-hidden">
              <button
                className="w-full flex items-center justify-between px-6 py-4 hover:bg-muted/50 transition-colors text-left"
                onClick={() => setSelectedKb(selectedKb === kb.id ? null : kb.id)}>
                <div className="flex items-center gap-3">
                  <Database className="h-5 w-5 text-primary" />
                  <div>
                    <div className="font-medium">{kb.name}</div>
                    <div className="text-xs text-muted-foreground mt-0.5">{kb.chunk_count} chunks · {kb.scope}</div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <button onClick={e => { e.stopPropagation(); deleteKb.mutate(kb.id) }}
                    className="p-1.5 hover:bg-destructive/10 hover:text-destructive rounded-lg transition-colors text-muted-foreground">
                    <Trash2 className="h-4 w-4" />
                  </button>
                  {selectedKb === kb.id ? <ChevronUp className="h-4 w-4 text-muted-foreground" /> : <ChevronDown className="h-4 w-4 text-muted-foreground" />}
                </div>
              </button>

              {selectedKb === kb.id && (
                <div className="border-t border-border px-6 py-4 space-y-4">
                  <div className="flex flex-wrap gap-2">
                    <button onClick={() => { setAddingText(!addingText); setAddingUrl(false) }}
                      className="flex items-center gap-2 px-3 py-2 bg-secondary text-secondary-foreground rounded-lg text-sm hover:bg-secondary/80 transition-colors">
                      <FileText className="h-4 w-4" /> Paste text
                    </button>
                    <label className="flex items-center gap-2 px-3 py-2 bg-secondary text-secondary-foreground rounded-lg text-sm hover:bg-secondary/80 transition-colors cursor-pointer">
                      <Upload className="h-4 w-4" /> Upload file
                      <input type="file" accept=".pdf,.docx,.pptx,.txt,.md" className="hidden" onChange={handleFileUpload} />
                    </label>
                    <button onClick={() => { setAddingUrl(!addingUrl); setAddingText(false) }}
                      className="flex items-center gap-2 px-3 py-2 bg-secondary text-secondary-foreground rounded-lg text-sm hover:bg-secondary/80 transition-colors">
                      <LinkIcon className="h-4 w-4" /> Add URL
                    </button>
                    <button onClick={() => qc.invalidateQueries({ queryKey: ['sources', selectedKb] })}
                      className="flex items-center gap-2 px-3 py-2 hover:bg-muted rounded-lg text-sm text-muted-foreground">
                      <RefreshCw className="h-3.5 w-3.5" /> Refresh
                    </button>
                  </div>

                  {addingText && (
                    <div className="space-y-3 bg-muted/50 rounded-lg p-4">
                      <input value={textTitle} onChange={e => setTextTitle(e.target.value)} placeholder="Source title..."
                        className="w-full bg-background rounded-lg px-3 py-2 text-sm border border-border focus:outline-none focus:ring-2 focus:ring-primary" />
                      <textarea value={textContent} onChange={e => setTextContent(e.target.value)} placeholder="Paste your content here..." rows={5}
                        className="w-full bg-background rounded-lg px-3 py-2 text-sm border border-border focus:outline-none focus:ring-2 focus:ring-primary resize-none" />
                      <div className="flex gap-2">
                        <button onClick={() => addText.mutate()} disabled={!textTitle.trim() || !textContent.trim() || addText.isPending}
                          className="px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm disabled:opacity-50 hover:bg-primary/90">
                          {addText.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Ingest'}
                        </button>
                        <button onClick={() => setAddingText(false)} className="px-3 py-2 hover:bg-muted rounded-lg text-sm">Cancel</button>
                      </div>
                    </div>
                  )}

                  {addingUrl && (
                    <div className="space-y-3 bg-muted/50 rounded-lg p-4">
                      <input value={urlTitle} onChange={e => setUrlTitle(e.target.value)} placeholder="Source title..."
                        className="w-full bg-background rounded-lg px-3 py-2 text-sm border border-border focus:outline-none focus:ring-2 focus:ring-primary" />
                      <input value={urlValue} onChange={e => setUrlValue(e.target.value)} placeholder="https://..."
                        className="w-full bg-background rounded-lg px-3 py-2 text-sm border border-border focus:outline-none focus:ring-2 focus:ring-primary" />
                      <div className="flex gap-2">
                        <button onClick={() => addUrl.mutate()} disabled={!urlTitle.trim() || !urlValue.trim() || addUrl.isPending}
                          className="px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm disabled:opacity-50 hover:bg-primary/90">
                          {addUrl.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Crawl & Ingest'}
                        </button>
                        <button onClick={() => setAddingUrl(false)} className="px-3 py-2 hover:bg-muted rounded-lg text-sm">Cancel</button>
                      </div>
                    </div>
                  )}

                  {sources?.items?.length === 0 && <p className="text-sm text-muted-foreground py-2">No sources yet. Add text, upload a file, or crawl a URL.</p>}
                  <div className="space-y-2">
                    {sources?.items?.map((s: any) => (
                      <div key={s.id} className="flex items-center justify-between py-2.5 border-b border-border last:border-0">
                        <div className="flex-1 min-w-0 pr-4">
                          <div className="text-sm font-medium truncate">{s.title}</div>
                          <div className="flex items-center gap-2 mt-1">
                            <span className="text-xs text-muted-foreground capitalize">{s.type}</span>
                            <span className="text-xs text-muted-foreground">·</span>
                            <span className="text-xs text-muted-foreground">{s.chunk_count} chunks</span>
                            <SourceStatusBadge status={s.status} />
                          </div>
                        </div>
                        <button onClick={() => deleteSource.mutate({ kbId: kb.id, srcId: s.id })}
                          className="p-1.5 hover:bg-destructive/10 hover:text-destructive rounded-lg transition-colors text-muted-foreground flex-shrink-0">
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </Layout>
    </ErrorBoundary>
  )
}