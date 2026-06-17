import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { Sun, Moon, Shield, Trash2, Download, Bell, CheckCircle, AlertCircle, Loader2 } from 'lucide-react'
import Layout from '@/components/Layout'
import { api } from '@/lib/api'
import { useAuthStore } from '@/stores/auth'
import { useThemeStore } from '@/stores/theme'

export default function Settings() {
  const { user, clearAuth } = useAuthStore()
  const { theme, toggleTheme } = useThemeStore()
  const [pwForm, setPwForm] = useState({ current: '', next: '', confirm: '' })
  const [pwMsg, setPwMsg] = useState<{type:'ok'|'err', text:string}|null>(null)
  const [deleteConfirm, setDeleteConfirm] = useState('')
  const [deleteOpen, setDeleteOpen] = useState(false)

  const changePassword = useMutation({
    mutationFn: () => api.post('/auth/change-password', {
      current_password: pwForm.current,
      new_password: pwForm.next,
    }),
    onSuccess: () => {
      setPwMsg({ type: 'ok', text: 'Password changed successfully.' })
      setPwForm({ current: '', next: '', confirm: '' })
    },
    onError: (e: any) => {
      setPwMsg({ type: 'err', text: e?.response?.data?.detail || 'Failed to change password.' })
    },
  })

  const exportData = async () => {
    const r = await api.get('/users/me')
    const blob = new Blob([JSON.stringify(r.data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url; a.download = 'my-data.json'; a.click()
    URL.revokeObjectURL(url)
  }

  const handlePwSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setPwMsg(null)
    if (pwForm.next !== pwForm.confirm) {
      setPwMsg({ type: 'err', text: 'Passwords do not match.' })
      return
    }
    if (pwForm.next.length < 8) {
      setPwMsg({ type: 'err', text: 'Password must be at least 8 characters.' })
      return
    }
    changePassword.mutate()
  }

  const Section = ({ title, icon: Icon, children }: any) => (
    <div className="bg-card border border-border rounded-xl overflow-hidden">
      <div className="px-5 py-4 border-b border-border flex items-center gap-2">
        <Icon className="h-4.5 w-4.5 text-muted-foreground" />
        <h2 className="font-semibold">{title}</h2>
      </div>
      <div className="p-5">{children}</div>
    </div>
  )

  return (
    <Layout>
      <div className="max-w-2xl mx-auto space-y-6">
        <div>
          <h1 className="text-2xl font-bold">Settings</h1>
          <p className="text-muted-foreground mt-1">Manage your account and preferences</p>
        </div>

        {/* Appearance */}
        <Section title="Appearance" icon={Sun}>
          <div className="flex gap-3">
            <button onClick={() => theme === 'dark' && toggleTheme()}
              className={`flex-1 flex flex-col items-center gap-2 p-4 rounded-xl border-2 transition-all ${theme === 'light' ? 'border-primary bg-primary/5' : 'border-border hover:border-muted-foreground/30'}`}>
              <div className="w-12 h-8 bg-white rounded border border-gray-200 shadow-sm" />
              <Sun className="h-4 w-4" />
              <span className="text-sm font-medium">Light</span>
            </button>
            <button onClick={() => theme === 'light' && toggleTheme()}
              className={`flex-1 flex flex-col items-center gap-2 p-4 rounded-xl border-2 transition-all ${theme === 'dark' ? 'border-primary bg-primary/5' : 'border-border hover:border-muted-foreground/30'}`}>
              <div className="w-12 h-8 bg-gray-900 rounded border border-gray-700 shadow-sm" />
              <Moon className="h-4 w-4" />
              <span className="text-sm font-medium">Dark</span>
            </button>
          </div>
        </Section>

        {/* Notifications */}
        <Section title="Notifications" icon={Bell}>
          <div className="space-y-3">
            {[
              { label: 'Achievement notifications', desc: 'Get notified when you earn a badge', key: 'achievements' },
              { label: 'Session reminders', desc: 'Daily reminder to practice', key: 'reminders' },
              { label: 'Feedback ready', desc: 'When your AI feedback is generated', key: 'feedback' },
            ].map(n => (
              <div key={n.key} className="flex items-center justify-between py-2">
                <div>
                  <div className="text-sm font-medium">{n.label}</div>
                  <div className="text-xs text-muted-foreground">{n.desc}</div>
                </div>
                <div className="w-10 h-6 bg-primary rounded-full cursor-pointer flex items-center justify-end px-0.5">
                  <div className="w-5 h-5 bg-white rounded-full shadow" />
                </div>
              </div>
            ))}
          </div>
        </Section>

        {/* Change password */}
        <Section title="Change Password" icon={Shield}>
          <form onSubmit={handlePwSubmit} className="space-y-3">
            {pwMsg && (
              <div className={`flex items-center gap-2 text-sm px-3 py-2.5 rounded-lg ${pwMsg.type === 'ok' ? 'bg-green-500/10 text-green-600' : 'bg-red-500/10 text-red-600'}`}>
                {pwMsg.type === 'ok' ? <CheckCircle className="h-4 w-4" /> : <AlertCircle className="h-4 w-4" />}
                {pwMsg.text}
              </div>
            )}
            {[
              { key: 'current', label: 'Current password', placeholder: '••••••••' },
              { key: 'next', label: 'New password', placeholder: 'Min 8 characters' },
              { key: 'confirm', label: 'Confirm new password', placeholder: '••••••••' },
            ].map(f => (
              <div key={f.key}>
                <label className="text-sm font-medium block mb-1">{f.label}</label>
                <input type="password" value={(pwForm as any)[f.key]}
                  onChange={e => setPwForm(p => ({...p, [f.key]: e.target.value}))}
                  placeholder={f.placeholder}
                  className="w-full bg-muted rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary" />
              </div>
            ))}
            <button type="submit" disabled={changePassword.isPending || !pwForm.current || !pwForm.next}
              className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium disabled:opacity-50 hover:bg-primary/90">
              {changePassword.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
              Update password
            </button>
          </form>
        </Section>

        {/* Account */}
        <Section title="Account Data" icon={Download}>
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-sm font-medium">Export my data</div>
                <div className="text-xs text-muted-foreground">Download your profile and session data as JSON</div>
              </div>
              <button onClick={exportData}
                className="flex items-center gap-2 px-3 py-2 bg-secondary text-secondary-foreground rounded-lg text-sm hover:bg-secondary/80">
                <Download className="h-4 w-4" /> Export
              </button>
            </div>
          </div>
        </Section>

        {/* Danger zone */}
        <div className="bg-red-500/5 border border-red-500/20 rounded-xl overflow-hidden">
          <div className="px-5 py-4 border-b border-red-500/20 flex items-center gap-2">
            <Trash2 className="h-4.5 w-4.5 text-red-500" />
            <h2 className="font-semibold text-red-600">Danger Zone</h2>
          </div>
          <div className="p-5">
            {!deleteOpen ? (
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-sm font-medium">Delete account</div>
                  <div className="text-xs text-muted-foreground">This action cannot be undone. All data will be permanently deleted.</div>
                </div>
                <button onClick={() => setDeleteOpen(true)}
                  className="px-3 py-2 bg-red-500/10 text-red-600 rounded-lg text-sm font-medium hover:bg-red-500/20">
                  Delete account
                </button>
              </div>
            ) : (
              <div className="space-y-3">
                <p className="text-sm text-red-600 font-medium">Type <strong>DELETE</strong> to confirm:</p>
                <input value={deleteConfirm} onChange={e => setDeleteConfirm(e.target.value)}
                  placeholder="Type DELETE"
                  className="w-full bg-muted rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-500" />
                <div className="flex gap-2">
                  <button onClick={() => setDeleteOpen(false)} className="px-3 py-2 bg-secondary text-secondary-foreground rounded-lg text-sm">
                    Cancel
                  </button>
                  <button disabled={deleteConfirm !== 'DELETE'}
                    className="px-3 py-2 bg-red-600 text-white rounded-lg text-sm font-medium disabled:opacity-50 hover:bg-red-700">
                    Permanently delete
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* About */}
        <div className="text-center text-xs text-muted-foreground space-y-1 pb-4">
          <div>AI Coach Platform v1.0.0</div>
          <div className="flex items-center justify-center gap-1.5">
            <div className="w-2 h-2 rounded-full bg-green-500" />
            All systems operational
          </div>
        </div>
      </div>
    </Layout>
  )
}
