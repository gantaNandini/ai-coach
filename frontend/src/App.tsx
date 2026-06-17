import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from '@/stores/auth'
import { useThemeStore } from '@/stores/theme'
import { useEffect, lazy, Suspense } from 'react'
import { Loader2 } from 'lucide-react'
import RequireRole from '@/components/RequireRole'
import { authApi } from '@/lib/api'

const Landing = lazy(() => import('@/pages/Landing'))
const Login = lazy(() => import('@/pages/Login'))
const Register = lazy(() => import('@/pages/Register'))
const Dashboard = lazy(() => import('@/pages/Dashboard'))
const Modules = lazy(() => import('@/pages/Modules'))
const CoachingSession = lazy(() => import('@/pages/CoachingSession'))
const RoleplaySession = lazy(() => import('@/pages/RoleplaySession'))
const FeedbackReport = lazy(() => import('@/pages/FeedbackReport'))
const KnowledgeBase = lazy(() => import('@/pages/KnowledgeBase'))
const Analytics = lazy(() => import('@/pages/Analytics'))
const Profile = lazy(() => import('@/pages/Profile'))
const Admin = lazy(() => import('@/pages/Admin'))
const Billing = lazy(() => import('@/pages/Billing'))
const ModuleBuilder = lazy(() => import('@/pages/ModuleBuilder'))
const Achievements = lazy(() => import('@/pages/Achievements'))
const Settings = lazy(() => import('@/pages/Settings'))

function PageLoader() {
  return (
    <div className="flex items-center justify-center min-h-screen bg-background">
      <div className="flex flex-col items-center gap-3">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
        <p className="text-sm text-muted-foreground">Loading...</p>
      </div>
    </div>
  )
}

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const user = useAuthStore((s) => s.user)
  if (!user) return <Navigate to="/login" replace />
  return <>{children}</>
}

export default function App() {
  const theme = useThemeStore((s) => s.theme)
  const { user, accessToken, refreshToken, setAuth } = useAuthStore()

  // Apply theme on mount and change
  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark')
  }, [theme])

  // Refresh roles from /auth/me on mount so role changes take effect
  // without requiring a full logout/login cycle.
  useEffect(() => {
    if (!user || !accessToken) return
    authApi.me()
      .then(r => {
        if (accessToken && refreshToken) setAuth(r.data, accessToken, refreshToken)
      })
      .catch(() => {
        // Silent — stale roles are safer than crashing on startup
      })
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []) // Run once on mount only

  return (
    <BrowserRouter>
      <Suspense fallback={<PageLoader />}>
        <Routes>
          {/* Public */}
          <Route path="/" element={<Landing />} />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />

          {/* Protected — all authenticated users */}
          <Route path="/dashboard" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
          <Route path="/modules" element={<ProtectedRoute><Modules /></ProtectedRoute>} />
          <Route path="/sessions/coaching/:sessionId" element={<ProtectedRoute><CoachingSession /></ProtectedRoute>} />
          <Route path="/sessions/roleplay/:sessionId" element={<ProtectedRoute><RoleplaySession /></ProtectedRoute>} />
          <Route path="/feedback/:reportId" element={<ProtectedRoute><FeedbackReport /></ProtectedRoute>} />
          <Route path="/achievements" element={<ProtectedRoute><Achievements /></ProtectedRoute>} />
          <Route path="/profile" element={<ProtectedRoute><Profile /></ProtectedRoute>} />
          <Route path="/settings" element={<ProtectedRoute><Settings /></ProtectedRoute>} />
          <Route path="/billing" element={<ProtectedRoute><Billing /></ProtectedRoute>} />
          {/* Stripe redirects back to these after checkout */}
          <Route path="/billing/success" element={<ProtectedRoute><Billing /></ProtectedRoute>} />
          <Route path="/billing/cancel" element={<ProtectedRoute><Billing /></ProtectedRoute>} />

          {/* Protected — admin only */}
          <Route path="/knowledge" element={
            <ProtectedRoute><RequireRole role="admin"><KnowledgeBase /></RequireRole></ProtectedRoute>
          } />
          <Route path="/analytics" element={
            <ProtectedRoute><RequireRole role="admin"><Analytics /></RequireRole></ProtectedRoute>
          } />
          <Route path="/modules/new" element={
            <ProtectedRoute><RequireRole role="admin"><ModuleBuilder /></RequireRole></ProtectedRoute>
          } />
          <Route path="/admin" element={
            <ProtectedRoute><RequireRole role="admin"><Admin /></RequireRole></ProtectedRoute>
          } />

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Suspense>
    </BrowserRouter>
  )
}
