import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from '@/stores/auth'
import { useThemeStore } from '@/stores/theme'
import { useEffect, lazy, Suspense } from 'react'
import { Loader2 } from 'lucide-react'

// Lazy-loaded pages — each splits into its own chunk
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

function PageLoader() {
  return (
    <div className="flex items-center justify-center min-h-screen">
      <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
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
  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark')
  }, [theme])

  return (
    <BrowserRouter>
      <Suspense fallback={<PageLoader />}>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/dashboard" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
          <Route path="/modules" element={<ProtectedRoute><Modules /></ProtectedRoute>} />
          <Route path="/sessions/coaching/:sessionId" element={<ProtectedRoute><CoachingSession /></ProtectedRoute>} />
          <Route path="/sessions/roleplay/:sessionId" element={<ProtectedRoute><RoleplaySession /></ProtectedRoute>} />
          <Route path="/feedback/:reportId" element={<ProtectedRoute><FeedbackReport /></ProtectedRoute>} />
          <Route path="/knowledge" element={<ProtectedRoute><KnowledgeBase /></ProtectedRoute>} />
          <Route path="/analytics" element={<ProtectedRoute><Analytics /></ProtectedRoute>} />
          <Route path="/profile" element={<ProtectedRoute><Profile /></ProtectedRoute>} />
          <Route path="/admin" element={<ProtectedRoute><Admin /></ProtectedRoute>} />
          <Route path="/billing" element={<ProtectedRoute><Billing /></ProtectedRoute>} />
          <Route path="/modules/new" element={<ProtectedRoute><ModuleBuilder /></ProtectedRoute>} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Suspense>
    </BrowserRouter>
  )
}
