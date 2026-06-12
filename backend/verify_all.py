"""
Full application verification — runs all flows and outputs PASS/FAIL.
Backend must be running on port 8000 before running this script.
"""
import asyncio
import httpx
import sys
import uuid

BASE = "http://localhost:8000/api/v1"
results = {}


def ok(area, msg=""):
    results[area] = ("PASS", msg)
    print(f"  PASS  {area}" + (f" — {msg}" if msg else ""))


def fail(area, msg):
    results[area] = ("FAIL", msg)
    print(f"  FAIL  {area} — {msg}")


async def main():
    print("\n========================================")
    print("  AI COACH PLATFORM — FULL VERIFICATION")
    print("========================================\n")

    async with httpx.AsyncClient(timeout=60) as c:

        # ── STEP 1: Backend health ─────────────────────────────────────────
        print("[1] BACKEND")
        try:
            r = await c.get("http://localhost:8000/health")
            if r.status_code == 200:
                ok("Backend /health", r.json().get("status"))
            else:
                fail("Backend /health", f"status={r.status_code}")
        except Exception as e:
            fail("Backend /health", f"NOT REACHABLE: {e}")

        try:
            r = await c.get("http://localhost:8000/health/detailed")
            d = r.json()
            ok("Backend /health/detailed",
               f"db={d['components']['database']} pgvector={d['components']['pgvector']} ollama={d['components'].get('ollama','?')[:15]}")
        except Exception as e:
            fail("Backend /health/detailed", str(e))

        try:
            r = await c.get("http://localhost:8000/docs")
            if r.status_code == 200:
                ok("Backend /docs")
            else:
                fail("Backend /docs", f"status={r.status_code}")
        except Exception as e:
            fail("Backend /docs", str(e))

        # ── STEP 3: AUTH FLOW ─────────────────────────────────────────────
        print("\n[3] AUTH FLOW")
        email = f"verify-{uuid.uuid4().hex[:8]}@example.com"
        password = "VerifyPass123!"
        token = None
        refresh = None

        try:
            r = await c.post(f"{BASE}/auth/register",
                json={"email": email, "password": password, "full_name": "Verify User"})
            if r.status_code == 201:
                ok("Auth Register", f"user_id={r.json()['id'][:8]}")
            else:
                fail("Auth Register", f"{r.status_code}: {r.text[:100]}")
        except Exception as e:
            fail("Auth Register", str(e))

        try:
            r = await c.post(f"{BASE}/auth/login",
                json={"email": email, "password": password})
            if r.status_code == 200:
                token = r.json()["access_token"]
                refresh = r.json()["refresh_token"]
                ok("Auth Login", "tokens received")
            else:
                fail("Auth Login", f"{r.status_code}: {r.text[:100]}")
        except Exception as e:
            fail("Auth Login", str(e))

        headers = {"Authorization": f"Bearer {token}"} if token else {}

        try:
            r = await c.get(f"{BASE}/auth/me", headers=headers)
            if r.status_code == 200:
                ok("Auth /me", r.json().get("email", "?"))
            else:
                fail("Auth /me", f"{r.status_code}: {r.text[:100]}")
        except Exception as e:
            fail("Auth /me", str(e))

        try:
            r = await c.post(f"{BASE}/auth/refresh",
                json={"refresh_token": refresh})
            if r.status_code == 200:
                token = r.json()["access_token"]
                ok("Auth Token Refresh")
            else:
                fail("Auth Token Refresh", f"{r.status_code}: {r.text[:100]}")
        except Exception as e:
            fail("Auth Token Refresh", str(e))

        if not token:
            fail("Auth (all subsequent flows)", "No token — skipping")
            return

        headers = {"Authorization": f"Bearer {token}"}

        # ── STEP 4: MODULES ───────────────────────────────────────────────
        print("\n[4] MODULES")
        module_id = None
        try:
            r = await c.get(f"{BASE}/modules/?status=published", headers=headers)
            mods = r.json()
            if r.status_code == 200 and mods.get("total", 0) > 0:
                module_id = mods["items"][0]["id"]
                ok("Modules List", f"total={mods['total']} first={mods['items'][0]['name']}")
            else:
                fail("Modules List", f"status={r.status_code} total={mods.get('total',0)}")
        except Exception as e:
            fail("Modules List", str(e))

        # ── STEP 4: COACHING FLOW ─────────────────────────────────────────
        print("\n[4] COACHING FLOW")
        session_id = None
        if module_id:
            try:
                r = await c.post(f"{BASE}/sessions/coaching",
                    json={"module_id": module_id}, headers=headers)
                if r.status_code == 201:
                    session_id = r.json()["id"]
                    ok("Coaching Create", f"session_id={session_id[:8]}")
                else:
                    fail("Coaching Create", f"{r.status_code}: {r.text[:200]}")
            except Exception as e:
                fail("Coaching Create", str(e))

            if session_id:
                try:
                    r = await c.get(f"{BASE}/sessions/coaching/{session_id}", headers=headers)
                    if r.status_code == 200:
                        schema = r.json().get("intake_schema", [])
                        ok("Coaching Get+intake_schema", f"{len(schema)} fields")
                    else:
                        fail("Coaching Get", f"{r.status_code}: {r.text[:100]}")
                except Exception as e:
                    fail("Coaching Get", str(e))
        else:
            fail("Coaching Flow", "No published module found — seed DB first")

        # ── STEP 5: ROLEPLAY FLOW ─────────────────────────────────────────
        print("\n[5] ROLEPLAY FLOW")
        rp_session_id = None
        if module_id:
            try:
                r = await c.post(f"{BASE}/sessions/roleplay",
                    json={"module_id": module_id}, headers=headers)
                if r.status_code == 201:
                    rp_session_id = r.json()["id"]
                    ok("Roleplay Create", f"session_id={rp_session_id[:8]}")
                else:
                    fail("Roleplay Create", f"{r.status_code}: {r.text[:200]}")
            except Exception as e:
                fail("Roleplay Create", str(e))
        else:
            fail("Roleplay Flow", "No module — skipped")

        # ── STEP 6: KNOWLEDGE BASE FLOW ───────────────────────────────────
        print("\n[6] KNOWLEDGE BASE FLOW")
        kb_id = None
        try:
            # Get tenant from existing KBs or create one
            r = await c.get(f"{BASE}/knowledge/", headers=headers)
            if r.status_code == 200:
                items = r.json().get("items", [])
                if items:
                    kb_id = items[0]["id"]
                    ok("Knowledge Base List", f"total={r.json()['total']}")
                else:
                    # Try to create one
                    r2 = await c.post(f"{BASE}/knowledge/",
                        json={"name": "Verify KB", "description": "Verification test KB"}, headers=headers)
                    if r2.status_code == 201:
                        kb_id = r2.json()["id"]
                        ok("Knowledge Base Create", f"kb_id={kb_id[:8]}")
                    else:
                        fail("Knowledge Base Create", f"{r2.status_code}: {r2.text[:200]}")
            else:
                fail("Knowledge Base List", f"{r.status_code}: {r.text[:100]}")
        except Exception as e:
            fail("Knowledge Base List", str(e))

        if kb_id:
            try:
                r = await c.post(f"{BASE}/knowledge/{kb_id}/sources/text",
                    json={"title": "Verify Test", "content": "This is a test of the ingestion pipeline. SBI feedback framework."},
                    headers=headers)
                if r.status_code == 201:
                    ok("Knowledge Base Ingest Text", f"source status={r.json().get('status')}")
                else:
                    fail("Knowledge Base Ingest Text", f"{r.status_code}: {r.text[:200]}")
            except Exception as e:
                fail("Knowledge Base Ingest Text", str(e))

        # ── STEP 7: ANALYTICS ─────────────────────────────────────────────
        print("\n[7] ANALYTICS")
        try:
            r = await c.get(f"{BASE}/analytics/dashboard", headers=headers)
            if r.status_code == 200:
                d = r.json()
                ok("Analytics Dashboard",
                   f"started={d.get('sessions_started')} completed={d.get('sessions_completed')} avg={d.get('avg_score')}")
            else:
                fail("Analytics Dashboard", f"{r.status_code}: {r.text[:100]}")
        except Exception as e:
            fail("Analytics Dashboard", str(e))

        try:
            r = await c.get(f"{BASE}/analytics/module-performance", headers=headers)
            if r.status_code == 200:
                ok("Analytics Module Performance", f"items={len(r.json().get('items',[]))}")
            else:
                fail("Analytics Module Performance", f"{r.status_code}: {r.text[:100]}")
        except Exception as e:
            fail("Analytics Module Performance", str(e))

        # ── STEP 8: ADMIN / MONITORING ────────────────────────────────────
        print("\n[8] ADMIN/MONITORING")
        try:
            r = await c.get(f"{BASE}/monitoring/stats", headers=headers)
            if r.status_code == 200:
                counts = r.json().get("table_counts", {})
                ok("Monitoring Stats",
                   f"users={counts.get('users')} sessions={counts.get('coaching_sessions')} reports={counts.get('feedback_reports')}")
            else:
                fail("Monitoring Stats", f"{r.status_code}: {r.text[:100]}")
        except Exception as e:
            fail("Monitoring Stats", str(e))

        try:
            r = await c.get(f"{BASE}/monitoring/health", headers=headers)
            if r.status_code == 200:
                ok("Monitoring Health", str(r.json().get("components", {}).get("database", "?")))
            else:
                fail("Monitoring Health", f"{r.status_code}: {r.text[:100]}")
        except Exception as e:
            fail("Monitoring Health", str(e))

        # ── STEP 9: BILLING ───────────────────────────────────────────────
        print("\n[9] BILLING")
        try:
            r = await c.get(f"{BASE}/billing/plans")
            if r.status_code == 200:
                plans = r.json().get("plans", [])
                ok("Billing Plans", f"{len(plans)} plans available")
            else:
                fail("Billing Plans", f"{r.status_code}: {r.text[:100]}")
        except Exception as e:
            fail("Billing Plans", str(e))

        try:
            r = await c.get(f"{BASE}/billing/subscription", headers=headers)
            if r.status_code == 200:
                ok("Billing Subscription", r.json().get("plan", "?"))
            else:
                fail("Billing Subscription", f"{r.status_code}: {r.text[:100]}")
        except Exception as e:
            fail("Billing Subscription", str(e))

        # ── STEP 10: MODULE BUILDER ───────────────────────────────────────
        print("\n[10] MODULE BUILDER")
        try:
            r = await c.post(f"{BASE}/modules/", headers=headers,
                json={"key": f"verify_{uuid.uuid4().hex[:6]}", "name": "Verify Module", "blurb": "Test"})
            if r.status_code == 201:
                new_mod_id = r.json()["id"]
                ok("Module Builder Create Module", f"id={new_mod_id[:8]}")

                # Create version
                r2 = await c.post(f"{BASE}/modules/{new_mod_id}/versions", headers=headers, json={
                    "framework_name": "VERIFY",
                    "intake_schema": [{"field_key": "situation", "label": "Situation", "type": "longtext", "required": True, "placeholder": "Describe..."}],
                    "scoring_rubric": {"dimensions": [{"name": "Clarity", "weight": 1.0, "band_descriptors": {"1": "Poor", "2": "OK", "3": "Good", "4": "Excellent"}}]},
                    "framework_steps": [{"label": "Situation", "description": "Describe the situation", "scoring_hints": "Look for specifics"}],
                    "prompt_templates": [{"template_type": "coaching", "template_body": "Review {{intake}} and give feedback.", "variables": ["intake"]}],
                    "personas": [{"persona_name": "Manager", "description": "Direct manager", "system_prompt": "You are a manager.", "traits": ["direct"], "is_default": True}],
                })
                if r2.status_code == 201:
                    ver_id = r2.json()["id"]
                    ok("Module Builder Create Version", f"version_id={ver_id[:8]}")

                    # Publish
                    r3 = await c.post(f"{BASE}/modules/{new_mod_id}/versions/{ver_id}/publish", headers=headers)
                    if r3.status_code == 200:
                        ok("Module Builder Publish", "published successfully")

                        # Verify appears in list
                        r4 = await c.get(f"{BASE}/modules/?status=published", headers=headers)
                        ids = [m["id"] for m in r4.json().get("items", [])]
                        if new_mod_id in ids:
                            ok("Module Builder Appears in List", "confirmed")
                        else:
                            fail("Module Builder Appears in List", "not found in published modules")
                    else:
                        fail("Module Builder Publish", f"{r3.status_code}: {r3.text[:200]}")
                else:
                    fail("Module Builder Create Version", f"{r2.status_code}: {r2.text[:200]}")
            else:
                fail("Module Builder Create Module", f"{r.status_code}: {r.text[:200]}")
        except Exception as e:
            import traceback
            fail("Module Builder", f"{e}\n{traceback.format_exc()[-300:]}")

        # ── PROGRESS & ACHIEVEMENTS ───────────────────────────────────────
        print("\n[BONUS] ACHIEVEMENTS")
        try:
            r = await c.get(f"{BASE}/progress/achievements", headers=headers)
            if r.status_code == 200:
                ok("Achievements List", f"{len(r.json())} available")
            else:
                fail("Achievements List", f"{r.status_code}: {r.text[:100]}")
        except Exception as e:
            fail("Achievements List", str(e))

    # ── FINAL SUMMARY ─────────────────────────────────────────────────────
    print("\n" + "="*50)
    print("  FINAL VERIFICATION RESULTS")
    print("="*50)
    passed = sum(1 for v in results.values() if v[0] == "PASS")
    failed = sum(1 for v in results.values() if v[0] == "FAIL")
    for area, (status, msg) in results.items():
        icon = "✅" if status == "PASS" else "❌"
        print(f"  {icon} {area:<35} {msg[:60]}")
    print(f"\n  {passed} PASSED  |  {failed} FAILED")
    print("="*50)
    return failed


asyncio.run(main())
