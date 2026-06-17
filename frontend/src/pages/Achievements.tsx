import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Trophy, Star, Lock, CheckCircle, Flame, Zap, TrendingUp, BookOpen, MessageCircle } from 'lucide-react'
import Layout from '@/components/Layout'
import { api } from '@/lib/api'

const ACHIEVEMENT_ICONS: Record<string, any> = {
  Award: Trophy,
  TrendingUp: TrendingUp,
  BookOpen: BookOpen,
  Star: Star,
  Zap: Zap,
  Flame: Flame,
  MessageCircle: MessageCircle,
}

const ACHIEVEMENT_EMOJIS: Record<string, string> = {
  first_session: '🎯',
  five_sessions: '🚀',
  ten_sessions: '📚',
  score_75_plus: '⭐',
  score_90_plus: '⚡',
  three_day_streak: '🔥',
  seven_day_streak: '🔥',
  first_roleplay: '💬',
}

const XP_PER_LEVEL = 100

export default function Achievements() {
  const [filter, setFilter] = useState<'all' | 'earned' | 'locked'>('all')

  const { data: allAchievements, isLoading: loadingAll } = useQuery({
    queryKey: ['achievements-all'],
    queryFn: () => api.get('/progress/achievements').then(r => r.data as any[]),
  })

  const { data: myAchievements, isLoading: loadingMine } = useQuery({
    queryKey: ['achievements-mine'],
    queryFn: () => api.get('/progress/achievements/mine').then(r => r.data as any[]),
  })

  const isLoading = loadingAll || loadingMine

  const earnedMap: Record<string, any> = {}
  myAchievements?.forEach((ua: any) => { earnedMap[ua.achievement_id] = ua })

  const totalXP = (allAchievements || [])
    .filter((a: any) => earnedMap[a.id])
    .reduce((s: number, a: any) => s + (a.points || 0), 0)

  const level = Math.floor(totalXP / XP_PER_LEVEL) + 1
  const xpInLevel = totalXP % XP_PER_LEVEL
  const xpProgress = (xpInLevel / XP_PER_LEVEL) * 100

  const filtered = (allAchievements || []).filter((a: any) => {
    if (filter === 'earned') return !!earnedMap[a.id]
    if (filter === 'locked') return !earnedMap[a.id]
    return true
  })

  return (
    <Layout>
      <div className="space-y-8">
        {/* Header */}
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Trophy className="h-6 w-6 text-yellow-500" /> Achievements
          </h1>
          <p className="text-muted-foreground mt-1">
            {myAchievements?.length || 0} of {allAchievements?.length || 0} earned · {totalXP} XP total
          </p>
        </div>

        {/* Level + XP */}
        <div className="bg-gradient-to-r from-yellow-500/10 to-orange-500/10 border border-yellow-500/20 rounded-2xl p-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <div className="text-sm text-muted-foreground">Current Level</div>
              <div className="text-4xl font-bold text-yellow-500">Level {level}</div>
            </div>
            <div className="text-right">
              <div className="text-sm text-muted-foreground">Total XP</div>
              <div className="text-2xl font-bold">{totalXP} <span className="text-sm font-normal text-muted-foreground">XP</span></div>
            </div>
          </div>
          <div className="space-y-1.5">
            <div className="flex justify-between text-xs text-muted-foreground">
              <span>Level {level}</span>
              <span>{xpInLevel} / {XP_PER_LEVEL} XP to Level {level + 1}</span>
            </div>
            <div className="h-3 bg-muted rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-yellow-500 to-orange-500 rounded-full transition-all"
                style={{ width: `${xpProgress}%` }}
              />
            </div>
          </div>
        </div>

        {/* Filter tabs */}
        <div className="flex gap-2">
          {(['all', 'earned', 'locked'] as const).map(f => (
            <button key={f} onClick={() => setFilter(f)}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors capitalize ${
                filter === f ? 'bg-primary text-primary-foreground' : 'bg-muted hover:bg-muted/80 text-muted-foreground'
              }`}>
              {f}
              {f === 'earned' && myAchievements && ` (${myAchievements.length})`}
              {f === 'locked' && allAchievements && ` (${allAchievements.length - (myAchievements?.length || 0)})`}
            </button>
          ))}
        </div>

        {/* Achievement grid */}
        {isLoading ? (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[...Array(8)].map((_, i) => (
              <div key={i} className="bg-muted rounded-xl h-36 animate-pulse" />
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
            {filtered.map((a: any) => {
              const earned = !!earnedMap[a.id]
              const ua = earnedMap[a.id]
              const emoji = ACHIEVEMENT_EMOJIS[a.key] || '🏅'
              return (
                <div key={a.id}
                  className={`relative rounded-xl p-4 flex flex-col items-center text-center border transition-all ${
                    earned
                      ? 'bg-yellow-500/5 border-yellow-500/30 shadow-sm'
                      : 'bg-muted/30 border-border opacity-60'
                  }`}>
                  {earned && (
                    <div className="absolute top-2 right-2">
                      <CheckCircle className="h-4 w-4 text-green-500" />
                    </div>
                  )}
                  {!earned && (
                    <div className="absolute top-2 right-2">
                      <Lock className="h-4 w-4 text-muted-foreground/50" />
                    </div>
                  )}
                  <div className={`text-4xl mb-2 ${!earned ? 'grayscale opacity-40' : ''}`}>{emoji}</div>
                  <div className="text-sm font-semibold leading-tight">{a.name}</div>
                  <div className="text-xs text-muted-foreground mt-1 leading-tight">{a.description}</div>
                  <div className={`mt-2 text-xs font-bold px-2 py-0.5 rounded-full ${
                    earned ? 'bg-yellow-500/20 text-yellow-600' : 'bg-muted text-muted-foreground'
                  }`}>
                    {a.points} XP
                  </div>
                  {earned && ua?.awarded_at && (
                    <div className="mt-1 text-[10px] text-muted-foreground">
                      {new Date(ua.awarded_at).toLocaleDateString('en', {month:'short', day:'numeric'})}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}

        {filtered.length === 0 && !isLoading && (
          <div className="text-center py-16 text-muted-foreground">
            <Trophy className="h-12 w-12 mx-auto mb-3 opacity-20" />
            <p>{filter === 'earned' ? 'No achievements earned yet. Complete coaching sessions to earn your first badge!' : 'No locked achievements.'}</p>
          </div>
        )}
      </div>
    </Layout>
  )
}
