"""
Real end-to-end workflow test.
Backend must be running on port 8000.
Tests actual feature workflows, not just HTTP 200.
"""
import asyncio, httpx, uuid, json, time

BASE = "http://localhost:8000/api/v1"
PASS = []
FAIL = []

def ok(name, detail=""):
    PASS.append(name)
    print(f"  PASS  {name}" + (f"  [{detail}]" if detail else ""))

def fail(name, detail=""):
    FAIL.append(name)
    print(f"  FAIL  {name}  -- {detail}")

async def main():
    print("\n=== AI COACH E2E WORKFLOW TESTS ===\n")
    async with httpx.AsyncClient(timeout=300) as c:

        # ── AUTH ──────────────────────────────────────────────────────────
        print("[AUTH]")
        email = f"e2e-{uuid.uuid4().hex[:6]}@test.com"
        pw = "E2eTest@123!"

        r = await c.post(f"{BASE}/auth/register", json={"email": email, "password": pw, "full_name": "E2E Tester"})
        if r.status_code == 201 and r.json().get("id"):
            ok("Register", f"user_id={r.json()['id'][:8]}")
        else:
            fail("Register", f"{r.status_code}: {r.text[:100]}")
            return

        r = await c.post(f"{BASE}/auth/login", json={"email": email, "password": pw})
        if r.status_code == 200 and "access_token" in r.json():
            token = r.json()["access_token"]
            ok("Login", "token received")
        else:
            fail("Login", f"{r.status_code}: {r.text[:100]}")
            return

        h = {"Authorization": f"Bearer {token}"}

        r = await c.get(f"{BASE}/auth/me", headers=h)
        if r.status_code == 200 and r.json().get("email") == email:
            ok("/auth/me", r.json()["email"])
        else:
            fail("/auth/me", f"{r.status_code}")

        # ── MODULES ───────────────────────────────────────────────────────
        print("\n[MODULES]")
        r = await c.get(f"{BASE}/modules/?status=published", headers=h)
        if r.status_code != 200 or r.json()["total"] == 0:
            fail("List published modules", f"total={r.json().get('total',0)}")
            return
        modules = r.json()["items"]
        module_id = modules[0]["id"]
        module_name = modules[0]["name"]
        ok("List published modules", f"total={r.json()['total']} first={module_name}")

        r = await c.get(f"{BASE}/modules/{module_id}", headers=h)
        d = r.json()
        intake = d.get("intake_schema", [])
        if r.status_code == 200 and len(intake) > 0:
            ok("Module detail with intake_schema", f"framework={d.get('framework_name')} fields={len(intake)}")
        else:
            fail("Module detail with intake_schema", f"intake_schema empty")

        # ── COACHING FLOW ─────────────────────────────────────────────────
        print("\n[COACHING FLOW]")
        r = await c.post(f"{BASE}/sessions/coaching", json={"module_id": module_id}, headers=h)
        if r.status_code == 201:
            session_id = r.json()["id"]
            ok("Create coaching session", f"id={session_id[:8]}")
        else:
            fail("Create coaching session", f"{r.status_code}: {r.text[:200]}")
            session_id = None

        if session_id:
            r = await c.get(f"{BASE}/sessions/coaching/{session_id}", headers=h)
            if r.status_code == 200:
                ok("Get coaching session + intake_schema", f"fields={len(r.json().get('intake_schema',[]))}")
            else:
                fail("Get coaching session", f"{r.status_code}")

            # Submit with real intake data matching the schema
            intake_data = {}
            for f in intake:
                intake_data[f["field_key"]] = f"Test value for {f['label']} - this is a specific example for E2E testing."

            print("  Submitting coaching session (AI feedback may take 60s)...")
            r = await c.post(f"{BASE}/sessions/coaching/{session_id}/complete",
                json={"intake_data": intake_data}, headers=h)
            if r.status_code == 200:
                d = r.json()
                report_id = d.get("feedback_report_id")
                score = d.get("final_score")
                ok("Complete coaching session", f"score={score} report_id={str(report_id)[:8] if report_id else 'None'}")

                if report_id:
                    r2 = await c.get(f"{BASE}/feedback/{report_id}", headers=h)
                    if r2.status_code == 200:
                        rd = r2.json()
                        ok("Fetch feedback report", f"score={rd.get('overall_score')} text_len={len(rd.get('feedback_text',''))}")
                    else:
                        fail("Fetch feedback report", f"{r2.status_code}: {r2.text[:100]}")
                else:
                    fail("Feedback report ID in response", "feedback_report_id is None")
            else:
                fail("Complete coaching session", f"{r.status_code}: {r.text[:200]}")

        # ── ROLEPLAY FLOW ─────────────────────────────────────────────────
        print("\n[ROLEPLAY FLOW]")
        r = await c.post(f"{BASE}/sessions/roleplay",
            json={"module_id": module_id, "scenario_prompt": "You are giving feedback to a direct report"}, headers=h)
        if r.status_code == 201:
            rp_id = r.json()["id"]
            ok("Create roleplay session", f"id={rp_id[:8]}")

            r = await c.post(f"{BASE}/sessions/roleplay/{rp_id}/turn",
                json={"content": "Hello, I wanted to discuss the presentation you gave last week."}, headers=h)
            if r.status_code == 200:
                resp_content = r.json().get("persona_content", "")
                ok("Submit roleplay turn + get AI response", f"response_len={len(resp_content)} turn={r.json().get('turn_number')}")
            else:
                fail("Submit roleplay turn", f"{r.status_code}: {r.text[:200]}")

            r = await c.post(f"{BASE}/sessions/roleplay/{rp_id}/complete", headers=h)
            if r.status_code == 200:
                rp_report_id = r.json().get("feedback_report_id")
                ok("Complete roleplay session", f"feedback_report_id={str(rp_report_id)[:8] if rp_report_id else 'None'}")
            else:
                fail("Complete roleplay session", f"{r.status_code}: {r.text[:200]}")
        else:
            fail("Create roleplay session", f"{r.status_code}: {r.text[:200]}")

        # ── KNOWLEDGE BASE FLOW ───────────────────────────────────────────
        print("\n[KNOWLEDGE BASE FLOW]")
        r = await c.post(f"{BASE}/knowledge/",
            json={"name": "E2E Test KB", "description": "End-to-end test"}, headers=h)
        if r.status_code == 201:
            kb_id = r.json()["id"]
            ok("Create knowledge base", f"id={kb_id[:8]}")

            r = await c.post(f"{BASE}/knowledge/{kb_id}/sources/text",
                json={"title": "SBI Guide", "content": "The SBI model is Situation, Behaviour, Impact. Always be specific about the situation."}, headers=h)
            if r.status_code == 201:
                src_id = r.json()["id"]
                ok("Ingest text source", f"id={src_id[:8]} status={r.json().get('status')}")

                # Wait for ingestion (background task)
                print("  Waiting for ingestion (5s)...")
                await asyncio.sleep(5)

                r = await c.get(f"{BASE}/knowledge/{kb_id}/sources/{src_id}/status", headers=h)
                if r.status_code == 200:
                    st = r.json()
                    ok("Check ingestion status", f"status={st.get('status')} chunks={st.get('chunk_count')}")
                else:
                    fail("Check ingestion status", f"{r.status_code}")
            else:
                fail("Ingest text source", f"{r.status_code}: {r.text[:200]}")
        else:
            fail("Create knowledge base", f"{r.status_code}: {r.text[:200]}")

        # ── ANALYTICS ─────────────────────────────────────────────────────
        print("\n[ANALYTICS]")
        r = await c.get(f"{BASE}/analytics/dashboard", headers=h)
        if r.status_code == 200:
            d = r.json()
            ok("Analytics dashboard", f"started={d.get('sessions_started')} avg_score={d.get('avg_score')} active_users={d.get('active_users')}")
        else:
            fail("Analytics dashboard", f"{r.status_code}")

        # ── ACHIEVEMENTS ──────────────────────────────────────────────────
        print("\n[ACHIEVEMENTS]")
        r = await c.get(f"{BASE}/progress/achievements", headers=h)
        if r.status_code == 200 and len(r.json()) > 0:
            ok("List achievements", f"count={len(r.json())}")
        else:
            fail("List achievements", f"{r.status_code} count={len(r.json()) if r.status_code==200 else 0}")

        r = await c.get(f"{BASE}/progress/achievements/mine", headers=h)
        if r.status_code == 200:
            ok("My achievements", f"earned={len(r.json())}")
        else:
            fail("My achievements", f"{r.status_code}")

        # ── BILLING ───────────────────────────────────────────────────────
        print("\n[BILLING]")
        r = await c.get(f"{BASE}/billing/plans")
        if r.status_code == 200:
            plans = r.json().get("plans", [])
            ok("Billing plans", f"count={len(plans)} names={[p['name'] for p in plans]}")
        else:
            fail("Billing plans", f"{r.status_code}")

        r = await c.get(f"{BASE}/billing/subscription", headers=h)
        if r.status_code == 200:
            ok("Billing subscription status", r.json().get("plan", "?"))
        else:
            fail("Billing subscription", f"{r.status_code}")

        # ── MODULE BUILDER ────────────────────────────────────────────────
        print("\n[MODULE BUILDER]")
        r = await c.post(f"{BASE}/modules/", headers=h,
            json={"key": f"e2e_{uuid.uuid4().hex[:6]}", "name": "E2E Module", "blurb": "Test"})
        if r.status_code == 201:
            new_mod_id = r.json()["id"]
            ok("Module Builder - create module", f"id={new_mod_id[:8]}")

            r = await c.post(f"{BASE}/modules/{new_mod_id}/versions", headers=h, json={
                "framework_name": "TEST",
                "intake_schema": [{"field_key": "situation", "label": "Situation", "type": "longtext", "required": True, "placeholder": "Describe..."}],
                "scoring_rubric": {"dimensions": [{"name": "Clarity", "weight": 1.0, "band_descriptors": {"1": "Poor", "2": "OK", "3": "Good", "4": "Excellent"}}]},
                "framework_steps": [{"label": "Situation", "description": "Describe it", "scoring_hints": "Be specific"}],
                "prompt_templates": [{"template_type": "coaching", "template_body": "Review {{intake}} and give feedback.", "variables": ["intake"]}],
                "personas": [],
            })
            if r.status_code == 201:
                ver_id = r.json()["id"]
                ok("Module Builder - create version", f"id={ver_id[:8]}")

                r = await c.post(f"{BASE}/modules/{new_mod_id}/versions/{ver_id}/publish", headers=h)
                if r.status_code == 200:
                    ok("Module Builder - publish", "published")
                else:
                    fail("Module Builder - publish", f"{r.status_code}: {r.text[:200]}")
            else:
                fail("Module Builder - create version", f"{r.status_code}: {r.text[:200]}")
        else:
            fail("Module Builder - create module", f"{r.status_code}: {r.text[:200]}")

    # ── SUMMARY ───────────────────────────────────────────────────────────
    print(f"\n{'='*50}")
    print(f"  PASSED: {len(PASS)}")
    print(f"  FAILED: {len(FAIL)}")
    print(f"{'='*50}")
    if FAIL:
        print("\nFAILED TESTS:")
        for f in FAIL:
            print(f"  X {f}")
    else:
        print("\nALL WORKFLOWS VERIFIED")

asyncio.run(main())
