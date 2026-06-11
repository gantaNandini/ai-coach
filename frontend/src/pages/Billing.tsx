import { useQuery, useMutation } from '@tanstack/react-query'
import { CreditCard, CheckCircle, Zap, Building2, AlertCircle } from 'lucide-react'
import Layout from '@/components/Layout'
import { api } from '@/lib/api'

const PLAN_ICONS: Record<string, string> = { starter: '🚀', growth: '📈', enterprise: '🏢' }

export default function Billing() {
  const { data: plans } = useQuery({
    queryKey: ['billing-plans'],
    queryFn: () => api.get('/billing/plans').then(r => r.data),
  })

  const { data: subscription } = useQuery({
    queryKey: ['billing-subscription'],
    queryFn: () => api.get('/billing/subscription').then(r => r.data),
  })

  const checkout = useMutation({
    mutationFn: (plan: string) => api.post(`/billing/checkout?plan_key=${plan}`).then(r => r.data),
    onSuccess: (data) => { if (data.checkout_url) window.location.href = data.checkout_url },
  })

  const portal = useMutation({
    mutationFn: () => api.post('/billing/portal').then(r => r.data),
    onSuccess: (data) => { if (data.portal_url) window.location.href = data.portal_url },
  })

  return (
    <Layout>
      <div className="max-w-4xl mx-auto space-y-8">
        <div>
          <h1 className="text-2xl font-bold">Billing & Plans</h1>
          <p className="text-muted-foreground mt-1">Manage your subscription</p>
        </div>

        {/* Current subscription */}
        {subscription && (
          <div className="bg-card border border-border rounded-xl p-6">
            <div className="flex items-center justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <CreditCard className="h-5 w-5 text-primary" />
                  <h2 className="font-semibold">Current Plan</h2>
                </div>
                <p className="text-2xl font-bold mt-2 capitalize">{subscription.plan}</p>
                <p className={`text-sm mt-1 flex items-center gap-1.5 ${subscription.status === 'active' ? 'text-green-600' : 'text-yellow-600'}`}>
                  {subscription.status === 'active' ? <CheckCircle className="h-4 w-4" /> : <AlertCircle className="h-4 w-4" />}
                  {subscription.status}
                </p>
              </div>
              {subscription.billing_configured ? (
                <button onClick={() => portal.mutate()}
                  className="px-4 py-2 bg-secondary text-secondary-foreground rounded-lg text-sm hover:bg-secondary/80">
                  Manage Billing
                </button>
              ) : (
                <div className="text-xs text-muted-foreground bg-muted px-3 py-2 rounded-lg max-w-xs text-right">
                  {subscription.message}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Plans */}
        <div className="grid md:grid-cols-3 gap-6">
          {plans?.plans?.map((plan: any) => (
            <div key={plan.name} className={`bg-card border rounded-xl p-6 flex flex-col ${plan.name === 'Growth' ? 'border-primary' : 'border-border'}`}>
              {plan.name === 'Growth' && (
                <div className="text-xs font-bold text-primary bg-primary/10 px-2 py-0.5 rounded-full w-fit mb-3">Most Popular</div>
              )}
              <div className="text-3xl mb-2">{PLAN_ICONS[plan.name.toLowerCase()] || '📦'}</div>
              <h3 className="text-xl font-bold">{plan.name}</h3>
              <div className="mt-2 mb-4">
                {plan.price_usd ? (
                  <span className="text-3xl font-bold">${plan.price_usd}<span className="text-sm font-normal text-muted-foreground">/mo</span></span>
                ) : (
                  <span className="text-xl font-semibold text-muted-foreground">Custom pricing</span>
                )}
              </div>
              <ul className="space-y-2 flex-1 mb-6">
                {plan.sessions_per_month && (
                  <li className="flex items-center gap-2 text-sm"><CheckCircle className="h-4 w-4 text-green-500 flex-shrink-0" />{plan.sessions_per_month} sessions/month</li>
                )}
                {plan.knowledge_bases && (
                  <li className="flex items-center gap-2 text-sm"><CheckCircle className="h-4 w-4 text-green-500 flex-shrink-0" />{plan.knowledge_bases} knowledge bases</li>
                )}
                {plan.max_users && (
                  <li className="flex items-center gap-2 text-sm"><CheckCircle className="h-4 w-4 text-green-500 flex-shrink-0" />Up to {plan.max_users} users</li>
                )}
                {plan.note && (
                  <li className="flex items-center gap-2 text-sm text-muted-foreground"><Building2 className="h-4 w-4 flex-shrink-0" />{plan.note}</li>
                )}
              </ul>
              <button
                onClick={() => plan.name === 'Enterprise'
                  ? window.open('mailto:enterprise@aicoach.io?subject=Enterprise Plan')
                  : checkout.mutate(plan.name.toLowerCase())}
                className={`w-full py-2.5 rounded-lg text-sm font-medium transition-colors ${plan.name === 'Growth' ? 'bg-primary text-primary-foreground hover:bg-primary/90' : 'bg-secondary text-secondary-foreground hover:bg-secondary/80'}`}>
                {plan.name === 'Enterprise' ? 'Contact Sales' : `Get ${plan.name}`}
              </button>
            </div>
          ))}
        </div>
      </div>
    </Layout>
  )
}
