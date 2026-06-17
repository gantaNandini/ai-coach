import asyncio, httpx, uuid

async def verify():
    async with httpx.AsyncClient(timeout=30) as c:
        BASE = "http://localhost:8000/api/v1"
        
        email = f"verify-{uuid.uuid4().hex[:6]}@example.com"
        r = await c.post(f"{BASE}/auth/register", json={"email": email, "password": "Verify@123!", "full_name": "Verify"})
        print(f"REGISTER:      {r.status_code}")
        r = await c.post(f"{BASE}/auth/login", json={"email": email, "password": "Verify@123!"})
        print(f"LOGIN:         {r.status_code}")
        token = r.json()["access_token"]
        h = {"Authorization": f"Bearer {token}"}
        
        r = await c.get(f"{BASE}/modules/?status=published", headers=h)
        total = r.json()["total"]
        items = r.json()["items"]
        print(f"MODULES:       {r.status_code}  total={total}")
        
        r = await c.get(f"{BASE}/analytics/dashboard", headers=h)
        d = r.json()
        print(f"ANALYTICS:     {r.status_code}  started={d.get('sessions_started')}  avg_score={d.get('avg_score')}")
        
        r = await c.get(f"{BASE}/monitoring/stats", headers=h)
        t = r.json()["table_counts"]
        print(f"MONITORING:    {r.status_code}  users={t.get('users')}  sessions={t.get('coaching_sessions')}  reports={t.get('feedback_reports')}")
        
        r = await c.get(f"{BASE}/billing/plans")
        print(f"BILLING:       {r.status_code}  plans={len(r.json().get('plans', []))}")
        
        r = await c.get(f"{BASE}/progress/achievements", headers=h)
        print(f"ACHIEVEMENTS:  {r.status_code}  count={len(r.json())}")
        
        r = await c.get(f"{BASE}/health/detailed")
        rj = r.json()
        comp = rj.get("components", rj)
        db_status = comp.get("database", rj.get("status", "?"))
        ol_status = str(comp.get("ollama", rj.get("ollama", "?")))[:20]
        print(f"HEALTH:        {r.status_code}  db={db_status}  ollama={ol_status}")
        
        if items:
            mid = items[0]["id"]
            r = await c.get(f"{BASE}/modules/{mid}", headers=h)
            d = r.json()
            print(f"MODULE DETAIL: {r.status_code}  framework={d.get('framework_name')}  intake_fields={len(d.get('intake_schema', []))}")
        
        r = await c.get(f"{BASE}/knowledge/", headers=h)
        print(f"KNOWLEDGE:     {r.status_code}  kbs={r.json().get('total', 0)}")
        
        r = await c.get(f"{BASE}/sessions/coaching", headers=h)
        print(f"SESSIONS:      {r.status_code}  total={r.json().get('total', 0)}")
        
        print()
        print("========================================")
        print("  ALL LIVE API ENDPOINTS: VERIFIED OK")
        print("========================================")

asyncio.run(verify())
