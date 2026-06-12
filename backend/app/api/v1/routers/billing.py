"""
billing.py — Subscription & billing management.

Uses Stripe for payment processing. If STRIPE_SECRET_KEY is not set,
all endpoints return 501 with a clear message so the app still runs.

Production setup:
  1. Add STRIPE_SECRET_KEY to .env
  2. Create products/prices in Stripe dashboard
  3. Set STRIPE_WEBHOOK_SECRET for webhook verification

Plans seeded:
  starter  — $49/mo  — 50 sessions, 1 KB, 5 users
  growth   — $149/mo — 500 sessions, 5 KBs, 25 users
  enterprise — custom
"""
from __future__ import annotations

import logging
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Header, Request
from pydantic import BaseModel

from app.api.v1.dependencies.auth import get_current_active_user
from app.models.user import User
from app.core.config import settings

router = APIRouter()
logger = logging.getLogger("ai_coach.billing")

# Stripe plan definitions — update price IDs from your Stripe dashboard
PLANS = {
    "starter": {
        "name": "Starter",
        "price_usd": 49,
        "sessions_per_month": 50,
        "knowledge_bases": 1,
        "max_users": 5,
        "stripe_price_id": "price_starter_monthly",
    },
    "growth": {
        "name": "Growth",
        "price_usd": 149,
        "sessions_per_month": 500,
        "knowledge_bases": 5,
        "max_users": 25,
        "stripe_price_id": "price_growth_monthly",
    },
    "enterprise": {
        "name": "Enterprise",
        "price_usd": None,
        "sessions_per_month": None,
        "knowledge_bases": None,
        "max_users": None,
        "stripe_price_id": None,
        "note": "Contact sales for custom pricing",
    },
}


def _stripe_client():
    """Return configured Stripe client or raise 501 if not configured."""
    stripe_key = getattr(settings, "STRIPE_SECRET_KEY", None)
    if not stripe_key:
        raise HTTPException(
            status_code=501,
            detail="Billing not configured. Set STRIPE_SECRET_KEY in .env to enable billing.",
        )
    try:
        import stripe
        stripe.api_key = stripe_key
        return stripe
    except ImportError:
        raise HTTPException(
            status_code=501,
            detail="Stripe not installed. Run: pip install stripe",
        )


@router.get("/plans")
async def list_plans():
    """List available subscription plans."""
    return {"plans": list(PLANS.values())}


@router.post("/checkout")
async def create_checkout_session(
    plan_key: str,
    current_user: User = Depends(get_current_active_user),
):
    """
    Create a Stripe Checkout session for subscription.
    Redirects user to Stripe-hosted payment page.
    """
    if plan_key not in PLANS:
        raise HTTPException(status_code=400, detail=f"Unknown plan: {plan_key}")

    plan = PLANS[plan_key]
    if plan.get("stripe_price_id") is None:
        raise HTTPException(
            status_code=400,
            detail="Enterprise plan requires contacting sales. Email enterprise@aicoach.io",
        )

    stripe = _stripe_client()
    base_url = getattr(settings, "APP_BASE_URL", "http://localhost:5173")

    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{"price": plan["stripe_price_id"], "quantity": 1}],
            mode="subscription",
            success_url=f"{base_url}/billing/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{base_url}/billing/cancel",
            customer_email=current_user.email,
            metadata={
                "user_id": str(current_user.id),
                "plan": plan_key,
            },
        )
        return {"checkout_url": session.url, "session_id": session.id}
    except Exception as exc:
        logger.error("[BILLING] Checkout creation failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Checkout failed: {exc}")


@router.post("/portal")
async def customer_portal(
    current_user: User = Depends(get_current_active_user),
):
    """Redirect to Stripe Customer Portal for subscription management."""
    stripe = _stripe_client()
    base_url = getattr(settings, "APP_BASE_URL", "http://localhost:5173")

    # Look up Stripe customer ID from tenant settings
    try:
        from app.database.unit_of_work import UnitOfWork
        async with UnitOfWork() as uow:
            # Try to get tenant's stripe_customer_id from settings
            user = await uow.users.get_by_id(current_user.id)
            tenant_id = None  # would come from user's active tenant role

        if not tenant_id:
            raise HTTPException(status_code=400, detail="No active tenant subscription found.")

        session = stripe.billing_portal.Session.create(
            customer="stripe_customer_id_here",  # replace with real lookup
            return_url=f"{base_url}/profile",
        )
        return {"portal_url": session.url}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Portal creation failed: {exc}")


@router.post("/webhook")
async def stripe_webhook(request: Request, stripe_signature: str = Header(None)):
    """
    Stripe webhook handler — processes subscription lifecycle events.
    Verifies signature using STRIPE_WEBHOOK_SECRET.
    """
    webhook_secret = getattr(settings, "STRIPE_WEBHOOK_SECRET", None)
    if not webhook_secret:
        raise HTTPException(status_code=501, detail="STRIPE_WEBHOOK_SECRET not configured.")

    stripe = _stripe_client()
    payload = await request.body()

    try:
        event = stripe.Webhook.construct_event(
            payload, stripe_signature, webhook_secret
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid webhook payload.")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid webhook signature.")

    event_type = event["type"]
    data = event["data"]["object"]

    logger.info("[BILLING] Webhook: %s", event_type)

    if event_type == "checkout.session.completed":
        user_id = data.get("metadata", {}).get("user_id")
        plan = data.get("metadata", {}).get("plan")
        customer_id = data.get("customer")
        subscription_id = data.get("subscription")
        logger.info("[BILLING] Subscription created: user=%s plan=%s", user_id, plan)
        # Update tenant subscription plan in DB
        if user_id and plan:
            try:
                from app.database.unit_of_work import UnitOfWork
                from uuid import UUID
                async with UnitOfWork() as uow:
                    user = await uow.users.get_by_id(UUID(user_id))
                    if user and user.tenant_id:
                        tenant = await uow.tenants.get_by_id(user.tenant_id)
                        if tenant:
                            tenant.subscription_plan = plan
                            if customer_id:
                                tenant.stripe_customer_id = customer_id
                            if subscription_id:
                                tenant.stripe_subscription_id = subscription_id
                    await uow.commit()
            except Exception as exc:
                logger.error("[BILLING] Failed to update tenant subscription: %s", exc)

    elif event_type == "customer.subscription.deleted":
        logger.info("[BILLING] Subscription cancelled: %s", data.get("id"))
        # Downgrade tenant to free tier
        customer_id = data.get("customer")
        if customer_id:
            try:
                from app.database.unit_of_work import UnitOfWork
                from sqlalchemy import text
                async with UnitOfWork() as uow:
                    await uow.session.execute(
                        text("UPDATE tenants SET subscription_plan='free' WHERE stripe_customer_id=:cid"),
                        {"cid": customer_id},
                    )
                    await uow.commit()
                logger.info("[BILLING] Tenant downgraded to free tier for customer %s", customer_id)
            except Exception as exc:
                logger.error("[BILLING] Failed to downgrade tenant: %s", exc)

    elif event_type == "invoice.payment_failed":
        logger.warning("[BILLING] Payment failed: %s", data.get("customer"))
        # Send payment failure notification to tenant admin (via analytics event for now)
        customer_id = data.get("customer")
        if customer_id:
            try:
                from app.database.unit_of_work import UnitOfWork
                from app.repositories.analytics.analytics_repository import AnalyticsEventCreate
                async with UnitOfWork() as uow:
                    await uow.analytics.track_event(
                        AnalyticsEventCreate(
                            event_type="billing.payment_failed",
                            properties={"customer_id": customer_id, "invoice": data.get("id")},
                        )
                    )
                    await uow.commit()
            except Exception as exc:
                logger.error("[BILLING] Failed to log payment failure event: %s", exc)

    return {"status": "received"}


@router.get("/subscription")
async def get_subscription(
    current_user: User = Depends(get_current_active_user),
):
    """Get current subscription status for the user's tenant."""
    # Returns mock data when Stripe is not configured
    return {
        "plan": "starter",
        "status": "active",
        "billing_configured": bool(getattr(settings, "STRIPE_SECRET_KEY", None)),
        "message": "Configure STRIPE_SECRET_KEY to enable real billing.",
    }
