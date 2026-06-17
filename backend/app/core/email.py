"""
app/core/email.py — Transactional email sending.

Supports Resend and Postmark. Set EMAIL_PROVIDER in .env.
Falls back gracefully to log-only when no provider is configured.

Usage:
    from app.core.email import send_email
    await send_email(
        to="user@example.com",
        template="welcome",
        data={"full_name": "Alice", "verify_url": "https://..."},
    )

Templates:
    welcome            — new user registration confirmation
    email_verify       — email verification link
    password_reset     — password reset link
    session_feedback   — feedback report ready notification
    payment_failed     — billing payment failure alert
    achievement_earned — achievement award notification
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("ai_coach.email")

# ── Template definitions ──────────────────────────────────────────────────────

TEMPLATES: dict[str, dict[str, str]] = {
    "welcome": {
        "subject": "Welcome to AI Coach",
        "html": """
<h2>Welcome, {full_name}!</h2>
<p>Your AI Coach account has been created. Start your first coaching session today.</p>
<p><a href="{frontend_url}/dashboard">Go to Dashboard</a></p>
""",
    },
    "email_verify": {
        "subject": "Verify your AI Coach email",
        "html": """
<h2>Verify your email, {full_name}</h2>
<p>Click the link below to verify your email address:</p>
<p><a href="{verify_url}">Verify Email</a></p>
<p>This link expires in 24 hours.</p>
""",
    },
    "password_reset": {
        "subject": "Reset your AI Coach password",
        "html": """
<h2>Password reset requested</h2>
<p>Click the link below to reset your password. This link expires in 1 hour.</p>
<p><a href="{reset_url}">Reset Password</a></p>
<p>If you did not request this, ignore this email.</p>
""",
    },
    "session_feedback": {
        "subject": "Your coaching feedback is ready",
        "html": """
<h2>Feedback ready, {full_name}!</h2>
<p>Your AI coaching feedback report for <strong>{module_name}</strong> is ready.</p>
<p>Overall score: <strong>{overall_score}/100</strong></p>
<p><a href="{feedback_url}">View Feedback</a></p>
""",
    },
    "payment_failed": {
        "subject": "Action required: payment failed",
        "html": """
<h2>Payment failed for your AI Coach subscription</h2>
<p>We were unable to process your payment. Please update your billing information.</p>
<p><a href="{billing_url}">Update Billing</a></p>
""",
    },
    "achievement_earned": {
        "subject": "You earned a new achievement!",
        "html": """
<h2>Achievement unlocked: {achievement_name}</h2>
<p>Congratulations, {full_name}! You earned <strong>{points} points</strong>.</p>
<p><a href="{achievements_url}">View achievements</a></p>
""",
    },
}


def _render_template(template: str, data: dict[str, Any]) -> tuple[str, str]:
    """Render subject + HTML body from a named template."""
    tpl = TEMPLATES.get(template)
    if not tpl:
        raise ValueError(f"Unknown email template: {template!r}")

    from app.core.config import settings
    base_data = {"frontend_url": settings.FRONTEND_URL, **data}

    subject = tpl["subject"]
    html = tpl["html"].format(**base_data)
    return subject, html


async def send_email(
    to: str,
    template: str,
    data: dict[str, Any],
    from_email: str | None = None,
) -> bool:
    """
    Send a transactional email using the configured provider.

    Returns True on success, False on failure.
    Never raises — email failures are logged but don't break the caller.
    """
    from app.core.config import settings

    try:
        subject, html = _render_template(template, data)
    except Exception as exc:
        logger.error("[EMAIL] Template render failed: %s", exc)
        return False

    sender = from_email or settings.EMAIL_FROM
    provider = settings.EMAIL_PROVIDER

    if provider == "none":
        logger.info(
            "[EMAIL] Provider=none — would send to=%s subject=%r (set EMAIL_PROVIDER to enable)",
            to, subject,
        )
        return True

    if provider == "resend":
        return await _send_resend(to=to, subject=subject, html=html, sender=sender)

    if provider == "postmark":
        return await _send_postmark(to=to, subject=subject, html=html, sender=sender)

    logger.warning("[EMAIL] Unknown EMAIL_PROVIDER=%r — not sending", provider)
    return False


async def _send_resend(to: str, subject: str, html: str, sender: str) -> bool:
    """Send via Resend API."""
    from app.core.config import settings
    api_key = settings.RESEND_API_KEY
    if not api_key:
        logger.error("[EMAIL] RESEND_API_KEY not configured")
        return False
    try:
        import resend
        resend.api_key = api_key
        resp = resend.Emails.send({
            "from": sender,
            "to": [to],
            "subject": subject,
            "html": html,
        })
        logger.info("[EMAIL] Resend sent id=%s to=%s", resp.get("id"), to)
        return True
    except Exception as exc:
        logger.error("[EMAIL] Resend failed for %s: %s", to, exc)
        return False


async def _send_postmark(to: str, subject: str, html: str, sender: str) -> bool:
    """Send via Postmark API."""
    from app.core.config import settings
    token = settings.POSTMARK_SERVER_TOKEN
    if not token:
        logger.error("[EMAIL] POSTMARK_SERVER_TOKEN not configured")
        return False
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                "https://api.postmarkapp.com/email",
                headers={
                    "X-Postmark-Server-Token": token,
                    "Content-Type": "application/json",
                },
                json={
                    "From": sender,
                    "To": to,
                    "Subject": subject,
                    "HtmlBody": html,
                },
            )
            resp.raise_for_status()
            logger.info("[EMAIL] Postmark sent to=%s status=%d", to, resp.status_code)
            return True
    except Exception as exc:
        logger.error("[EMAIL] Postmark failed for %s: %s", to, exc)
        return False
