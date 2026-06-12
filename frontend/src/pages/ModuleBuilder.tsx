import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, Trash2, Save, Rocket, ChevronDown, ChevronUp, Loader2, BookOpen, CheckCircle } from 'lucide-react'
import Layout from '@/components/Layout'
import { api, modulesApi } from '@/lib/api'

// ── Types ──────────────────────────────────────────────────────────────────

interface IntakeField {
  field_key: string
  label: string
  type: 'text' | 'longtext' | 'select'
  required: boolean
  placeholder: string
  options?: string[]
}

interface RubricDimension {
  name: string
  weight: number
  band_descriptors: Record<string, string>
}

interface FrameworkStep {
  label: string
  description: string
  scoring_hints: string
}

interface Persona {
  persona_name: string
  description: string
  system_prompt: string
  traits: string[]
  is_default: boolean
}

// ── Default values ─────────────────────────────────────────────────────────

const defaultField = (): IntakeField => ({
  field_key: `field_${Date.now()}`,
  label: '',
  type: 'longtext',
  required: true,
  placeholder: 'Enter your response...',
})

const defaultDimension = (): RubricDimension => ({
  name: '',
  weight: 0.25,
  band_descriptors: { '1': 'Poor', '2': 'Developing', '3': 'Proficient', '4': 'Excellent' },
})

const defaultStep = (): FrameworkStep => ({
  label: '',
  description: '',
  scoring_hints: '',
})

const defaultPersona = (): Persona => ({
  persona_name: '',
  description: '',
  system_prompt: 'You are a professional persona in a workplace scenario.',
  traits: ['direct', 'professional'],
  is_default: true,
})

// ── Component ──────────────────────────────────────────────────────────────

export default function ModuleBuilder() {
  const navigate = useNavigate()
  const qc = useQueryClient()

  const [step, setStep] = useState<'meta' | 'intake' | 'rubric' | 'steps' | 'personas' | 'preview'>('meta')
  const [saved, setSaved] = useState(false)

  // Meta
  const [name, setName] = useState('')
  const [key, setKey] = useState('')
  const [blurb, setBlurb] = useState('')
  const [frameworkName, setFrameworkName] = useState('')

  // Intake
  const [fields, setFields] = useState<IntakeField[]>([defaultField()])

  // Rubric
  const [dimensions, setDimensions] = useState<RubricDimension[]>([defaultDimension()])

  // Steps
  const [steps, setSteps] = useState<FrameworkStep[]>([defaultStep()])

  // Personas
  const [personas, setPersonas] = useState<Persona[]>([defaultPersona()])

  // Coaching prompt template
  const [coachingTemplate, setCoachingTemplate] = useState(
    `You are an expert coach. Review this {{framework}} feedback and respond with ONLY valid JSON.

Submission:
{{intake}}

Rubric:
{{rubric}}

{{knowledge}}

Respond with ONLY:
{"feedback_text":"2-3 sentences of coaching feedback","strengths":["strength"],"improvements":["improvement"],"recommendations":[{"priority":1,"area":"skill","suggestion":"tip"}],"next_steps":"concrete action"}`
  )

  // Create module + version
  const createModule = useMutation({
    mutationFn: async () => {
      // 1. Create the module
      const modResp = await api.post('/modules/', { key, name, blurb, icon: 'BookOpen' })
      const moduleId = modResp.data.id

      // 2. Validate rubric weights sum to 1.0
      const totalWeight = dimensions.reduce((s, d) => s + d.weight, 0)
      if (Math.abs(totalWeight - 1.0) > 0.01) {
        throw new Error(`Rubric weights must sum to 1.0 (currently ${totalWeight.toFixed(2)})`)
      }

      // 3. Create version with full definition
      const versionResp = await api.post(`/modules/${moduleId}/versions`, {
        framework_name: frameworkName,
        intake_schema: fields.map(f => ({
          field_key: f.field_key,
          label: f.label,
          type: f.type,
          required: f.required,
          placeholder: f.placeholder,
          options: f.options,
        })),
        scoring_rubric: { dimensions },
        framework_steps: steps.map((s, i) => ({
          label: s.label,
          description: s.description,
          scoring_hints: s.scoring_hints,
          step_order: i,
        })),
        prompt_templates: [
          {
            template_type: 'coaching',
            template_body: coachingTemplate,
            variables: ['framework', 'intake', 'rubric', 'knowledge'],
          },
        ],
        personas: personas.map(p => ({
          persona_name: p.persona_name,
          description: p.description,
          system_prompt: p.system_prompt,
          traits: p.traits,
          is_default: p.is_default,
        })),
      })

      // 4. Publish the version immediately
      await api.post(`/modules/${moduleId}/versions/${versionResp.data.id}/publish`)

      return { moduleId, versionId: versionResp.data.id }
    },
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ['modules'] })
      setSaved(true)
      setTimeout(() => navigate('/modules'), 2000)
    },
  })

  const totalWeight = dimensions.reduce((s, d) => s + d.weight, 0)
  const weightValid = Math.abs(totalWeight - 1.0) <= 0.01

  const STEPS = ['meta', 'intake', 'rubric', 'steps', 'personas', 'preview'] as const
  const stepIdx = STEPS.indexOf(step)

  // ── Helpers ──────────────────────────────────────────────────────────────

  const canAdvance = () => {
    if (step === 'meta') return name.trim() && key.trim() && frameworkName.trim()
    if (step === 'intake') return fields.length > 0 && fields.every(f => f.label.trim())
    if (step === 'rubric') return dimensions.length > 0 && weightValid && dimensions.every(d => d.name.trim())
    if (step === 'steps') return steps.length > 0 && steps.every(s => s.label.trim())
    if (step === 'personas') return true
    return true
  }

  if (saved) return (
    <Layout>
      <div className="max-w-lg mx-auto text-center py-24">
        <CheckCircle className="h-16 w-16 text-green-500 mx-auto mb-6" />
        <h2 className="text-2xl font-bold mb-3">Module Published!</h2>
        <p className="text-muted-foreground">Your module is live and ready for learners.</p>
      </div>
    </Layout>
  )

  return (
    <Layout>
      <div className="max-w-3xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">Module Builder</h1>
            <p className="text-muted-foreground mt-1">Create a new coaching module without writing code</p>
          </div>
        </div>

        {/* Progress */}
        <div className="flex items-center gap-2">
          {STEPS.map((s, i) => (
            <div key={s} className="flex items-center gap-1.5">
              <button
                onClick={() => i <= stepIdx && setStep(s)}
                className={`w-7 h-7 rounded-full text-xs font-bold flex items-center justify-center transition-colors ${
                  i < stepIdx ? 'bg-green-500 text-white cursor-pointer' :
                  i === stepIdx ? 'bg-primary text-primary-foreground' :
                  'bg-muted text-muted-foreground cursor-not-allowed'
                }`}>
                {i < stepIdx ? '✓' : i + 1}
              </button>
              <span className={`text-xs hidden sm:block ${i === stepIdx ? 'text-foreground font-medium' : 'text-muted-foreground'}`}>
                {s.charAt(0).toUpperCase() + s.slice(1)}
              </span>
              {i < STEPS.length - 1 && <div className="w-6 h-px bg-border" />}
            </div>
          ))}
        </div>

        {/* ── Step: Meta ── */}
        {step === 'meta' && (
          <div className="bg-card border border-border rounded-xl p-6 space-y-5">
            <h2 className="font-semibold text-lg">1. Module Details</h2>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-sm font-medium">Module Name *</label>
                <input value={name} onChange={e => { setName(e.target.value); setKey(e.target.value.toLowerCase().replace(/\s+/g, '_').replace(/[^a-z0-9_]/g, '')) }}
                  placeholder="e.g. SBI Feedback"
                  className="mt-1 w-full bg-muted rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary" />
              </div>
              <div>
                <label className="text-sm font-medium">Key (slug) *</label>
                <input value={key} onChange={e => setKey(e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, ''))}
                  placeholder="e.g. sbi_feedback"
                  className="mt-1 w-full bg-muted rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary font-mono" />
              </div>
              <div>
                <label className="text-sm font-medium">Framework Name *</label>
                <input value={frameworkName} onChange={e => setFrameworkName(e.target.value)}
                  placeholder="e.g. SBI, GROW, STAR"
                  className="mt-1 w-full bg-muted rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary" />
              </div>
              <div>
                <label className="text-sm font-medium">Description</label>
                <input value={blurb} onChange={e => setBlurb(e.target.value)}
                  placeholder="Brief description for learners"
                  className="mt-1 w-full bg-muted rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary" />
              </div>
            </div>
          </div>
        )}

        {/* ── Step: Intake ── */}
        {step === 'intake' && (
          <div className="bg-card border border-border rounded-xl p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="font-semibold text-lg">2. Intake Form Fields</h2>
              <button onClick={() => setFields([...fields, defaultField()])}
                className="flex items-center gap-1.5 text-sm text-primary hover:underline">
                <Plus className="h-4 w-4" /> Add field
              </button>
            </div>
            {fields.map((f, i) => (
              <div key={i} className="border border-border rounded-lg p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium text-muted-foreground">Field {i + 1}</span>
                  {fields.length > 1 && (
                    <button onClick={() => setFields(fields.filter((_, j) => j !== i))}
                      className="text-muted-foreground hover:text-destructive">
                      <Trash2 className="h-4 w-4" />
                    </button>
                  )}
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs text-muted-foreground">Label *</label>
                    <input value={f.label} onChange={e => setFields(fields.map((x, j) => j === i ? {...x, label: e.target.value, field_key: e.target.value.toLowerCase().replace(/\s+/g,'_')} : x))}
                      placeholder="e.g. Describe the Situation"
                      className="mt-1 w-full bg-muted rounded px-2 py-1.5 text-sm" />
                  </div>
                  <div>
                    <label className="text-xs text-muted-foreground">Type</label>
                    <select value={f.type} onChange={e => setFields(fields.map((x, j) => j === i ? {...x, type: e.target.value as any} : x))}
                      className="mt-1 w-full bg-muted rounded px-2 py-1.5 text-sm">
                      <option value="text">Short text</option>
                      <option value="longtext">Long text</option>
                      <option value="select">Select</option>
                    </select>
                  </div>
                </div>
                <div>
                  <label className="text-xs text-muted-foreground">Placeholder hint</label>
                  <input value={f.placeholder} onChange={e => setFields(fields.map((x, j) => j === i ? {...x, placeholder: e.target.value} : x))}
                    className="mt-1 w-full bg-muted rounded px-2 py-1.5 text-sm" />
                </div>
                <label className="flex items-center gap-2 text-sm cursor-pointer">
                  <input type="checkbox" checked={f.required} onChange={e => setFields(fields.map((x, j) => j === i ? {...x, required: e.target.checked} : x))} />
                  Required field
                </label>
              </div>
            ))}
          </div>
        )}

        {/* ── Step: Rubric ── */}
        {step === 'rubric' && (
          <div className="bg-card border border-border rounded-xl p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="font-semibold text-lg">3. Scoring Rubric</h2>
              <button onClick={() => setDimensions([...dimensions, defaultDimension()])}
                className="flex items-center gap-1.5 text-sm text-primary hover:underline">
                <Plus className="h-4 w-4" /> Add dimension
              </button>
            </div>
            <div className={`text-sm font-medium ${weightValid ? 'text-green-600' : 'text-red-500'}`}>
              Total weight: {totalWeight.toFixed(2)} {weightValid ? '✓' : '— must equal 1.00'}
            </div>
            {dimensions.map((d, i) => (
              <div key={i} className="border border-border rounded-lg p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium text-muted-foreground">Dimension {i + 1}</span>
                  {dimensions.length > 1 && (
                    <button onClick={() => setDimensions(dimensions.filter((_, j) => j !== i))}
                      className="text-muted-foreground hover:text-destructive"><Trash2 className="h-4 w-4" /></button>
                  )}
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs text-muted-foreground">Name *</label>
                    <input value={d.name} onChange={e => setDimensions(dimensions.map((x, j) => j === i ? {...x, name: e.target.value} : x))}
                      placeholder="e.g. Situation Clarity"
                      className="mt-1 w-full bg-muted rounded px-2 py-1.5 text-sm" />
                  </div>
                  <div>
                    <label className="text-xs text-muted-foreground">Weight (0–1)</label>
                    <input type="number" min="0" max="1" step="0.05" value={d.weight}
                      onChange={e => setDimensions(dimensions.map((x, j) => j === i ? {...x, weight: parseFloat(e.target.value) || 0} : x))}
                      className="mt-1 w-full bg-muted rounded px-2 py-1.5 text-sm" />
                  </div>
                </div>
                <div>
                  <label className="text-xs text-muted-foreground">Band descriptors (1=Poor → 4=Excellent)</label>
                  {[1, 2, 3, 4].map(band => (
                    <div key={band} className="flex items-center gap-2 mt-1">
                      <span className="w-4 text-xs text-muted-foreground">{band}</span>
                      <input value={d.band_descriptors[String(band)] || ''}
                        onChange={e => setDimensions(dimensions.map((x, j) => j === i ? {...x, band_descriptors: {...x.band_descriptors, [String(band)]: e.target.value}} : x))}
                        placeholder={`Band ${band} description`}
                        className="flex-1 bg-muted rounded px-2 py-1 text-xs" />
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* ── Step: Steps ── */}
        {step === 'steps' && (
          <div className="bg-card border border-border rounded-xl p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="font-semibold text-lg">4. Framework Steps</h2>
              <button onClick={() => setSteps([...steps, defaultStep()])}
                className="flex items-center gap-1.5 text-sm text-primary hover:underline">
                <Plus className="h-4 w-4" /> Add step
              </button>
            </div>
            {steps.map((s, i) => (
              <div key={i} className="border border-border rounded-lg p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-primary">Step {i + 1}</span>
                  {steps.length > 1 && (
                    <button onClick={() => setSteps(steps.filter((_, j) => j !== i))}
                      className="text-muted-foreground hover:text-destructive"><Trash2 className="h-4 w-4" /></button>
                  )}
                </div>
                <div>
                  <label className="text-xs text-muted-foreground">Label *</label>
                  <input value={s.label} onChange={e => setSteps(steps.map((x, j) => j === i ? {...x, label: e.target.value} : x))}
                    placeholder="e.g. Situation"
                    className="mt-1 w-full bg-muted rounded px-2 py-1.5 text-sm" />
                </div>
                <div>
                  <label className="text-xs text-muted-foreground">Description for learners</label>
                  <textarea value={s.description} onChange={e => setSteps(steps.map((x, j) => j === i ? {...x, description: e.target.value} : x))}
                    rows={2} placeholder="Explain what the learner should do in this step"
                    className="mt-1 w-full bg-muted rounded px-2 py-1.5 text-sm resize-none" />
                </div>
                <div>
                  <label className="text-xs text-muted-foreground">Scoring hints (for AI evaluator)</label>
                  <input value={s.scoring_hints} onChange={e => setSteps(steps.map((x, j) => j === i ? {...x, scoring_hints: e.target.value} : x))}
                    placeholder="e.g. Look for specific time and place"
                    className="mt-1 w-full bg-muted rounded px-2 py-1.5 text-sm" />
                </div>
              </div>
            ))}
          </div>
        )}

        {/* ── Step: Personas ── */}
        {step === 'personas' && (
          <div className="bg-card border border-border rounded-xl p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="font-semibold text-lg">5. Roleplay Personas</h2>
              <button onClick={() => setPersonas([...personas, {...defaultPersona(), is_default: false}])}
                className="flex items-center gap-1.5 text-sm text-primary hover:underline">
                <Plus className="h-4 w-4" /> Add persona
              </button>
            </div>
            <p className="text-sm text-muted-foreground">Optional — personas enable roleplay sessions for this module.</p>
            {personas.map((p, i) => (
              <div key={i} className="border border-border rounded-lg p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium text-muted-foreground">Persona {i + 1}</span>
                  {personas.length > 1 && (
                    <button onClick={() => setPersonas(personas.filter((_, j) => j !== i))}
                      className="text-muted-foreground hover:text-destructive"><Trash2 className="h-4 w-4" /></button>
                  )}
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs text-muted-foreground">Persona Name *</label>
                    <input value={p.persona_name} onChange={e => setPersonas(personas.map((x, j) => j === i ? {...x, persona_name: e.target.value} : x))}
                      placeholder="e.g. Direct Manager"
                      className="mt-1 w-full bg-muted rounded px-2 py-1.5 text-sm" />
                  </div>
                  <div>
                    <label className="text-xs text-muted-foreground">Traits (comma-separated)</label>
                    <input value={p.traits.join(', ')} onChange={e => setPersonas(personas.map((x, j) => j === i ? {...x, traits: e.target.value.split(',').map(t => t.trim())} : x))}
                      placeholder="direct, impatient"
                      className="mt-1 w-full bg-muted rounded px-2 py-1.5 text-sm" />
                  </div>
                </div>
                <div>
                  <label className="text-xs text-muted-foreground">System prompt (AI personality)</label>
                  <textarea value={p.system_prompt} onChange={e => setPersonas(personas.map((x, j) => j === i ? {...x, system_prompt: e.target.value} : x))}
                    rows={3} className="mt-1 w-full bg-muted rounded px-2 py-1.5 text-sm resize-none" />
                </div>
                <label className="flex items-center gap-2 text-sm cursor-pointer">
                  <input type="radio" checked={p.is_default} onChange={() => setPersonas(personas.map((x, j) => ({...x, is_default: j === i})))} />
                  Default persona
                </label>
              </div>
            ))}

            {/* Coaching prompt template */}
            <div className="pt-2">
              <div className="flex items-center justify-between mb-2">
                <label className="text-sm font-medium">Coaching Prompt Template</label>
                <span className="text-xs text-muted-foreground">Use {'{{intake}}'}, {'{{rubric}}'}, {'{{knowledge}}'}</span>
              </div>
              <textarea value={coachingTemplate} onChange={e => setCoachingTemplate(e.target.value)}
                rows={8} className="w-full bg-muted rounded px-3 py-2 text-xs font-mono resize-none focus:outline-none focus:ring-2 focus:ring-primary" />
            </div>
          </div>
        )}

        {/* ── Step: Preview ── */}
        {step === 'preview' && (
          <div className="bg-card border border-border rounded-xl p-6 space-y-4">
            <h2 className="font-semibold text-lg">6. Review & Publish</h2>
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div className="bg-muted/50 rounded-lg p-4">
                <div className="text-xs text-muted-foreground mb-1">Module</div>
                <div className="font-semibold">{name}</div>
                <div className="text-muted-foreground font-mono text-xs">{key}</div>
              </div>
              <div className="bg-muted/50 rounded-lg p-4">
                <div className="text-xs text-muted-foreground mb-1">Framework</div>
                <div className="font-semibold">{frameworkName}</div>
              </div>
              <div className="bg-muted/50 rounded-lg p-4">
                <div className="text-xs text-muted-foreground mb-1">Intake Fields</div>
                <div className="font-semibold">{fields.length} fields</div>
                <div className="text-xs text-muted-foreground">{fields.map(f => f.label).join(', ')}</div>
              </div>
              <div className="bg-muted/50 rounded-lg p-4">
                <div className="text-xs text-muted-foreground mb-1">Rubric</div>
                <div className="font-semibold">{dimensions.length} dimensions</div>
                <div className={`text-xs ${weightValid ? 'text-green-600' : 'text-red-500'}`}>
                  Weight sum: {totalWeight.toFixed(2)} {weightValid ? '✓' : '✗'}
                </div>
              </div>
              <div className="bg-muted/50 rounded-lg p-4">
                <div className="text-xs text-muted-foreground mb-1">Framework Steps</div>
                <div className="font-semibold">{steps.length} steps</div>
                <div className="text-xs text-muted-foreground">{steps.map(s => s.label).join(' → ')}</div>
              </div>
              <div className="bg-muted/50 rounded-lg p-4">
                <div className="text-xs text-muted-foreground mb-1">Personas</div>
                <div className="font-semibold">{personas.filter(p => p.persona_name).length} personas</div>
              </div>
            </div>
            {createModule.isError && (
              <div className="text-sm text-red-500 bg-red-500/10 rounded-lg p-3">
                {(createModule.error as Error)?.message || 'Failed to create module'}
              </div>
            )}
            <button
              onClick={() => createModule.mutate()}
              disabled={createModule.isPending || !weightValid}
              className="w-full flex items-center justify-center gap-2 py-3 bg-primary text-primary-foreground rounded-lg font-medium hover:bg-primary/90 disabled:opacity-50 transition-colors">
              {createModule.isPending ? <Loader2 className="h-5 w-5 animate-spin" /> : <Rocket className="h-5 w-5" />}
              {createModule.isPending ? 'Publishing...' : 'Publish Module'}
            </button>
          </div>
        )}

        {/* Navigation */}
        <div className="flex justify-between">
          <button
            onClick={() => setStep(STEPS[stepIdx - 1])}
            disabled={stepIdx === 0}
            className="px-5 py-2.5 bg-secondary text-secondary-foreground rounded-lg text-sm font-medium disabled:opacity-40 hover:bg-secondary/80">
            Back
          </button>
          {step !== 'preview' && (
            <button
              onClick={() => setStep(STEPS[stepIdx + 1])}
              disabled={!canAdvance()}
              className="px-5 py-2.5 bg-primary text-primary-foreground rounded-lg text-sm font-medium disabled:opacity-40 hover:bg-primary/90">
              Next →
            </button>
          )}
        </div>
      </div>
    </Layout>
  )
}
