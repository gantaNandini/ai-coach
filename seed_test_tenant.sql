DO $$
DECLARE
  tid UUID;
  uid UUID;
  rid UUID;
BEGIN
  uid := (SELECT id FROM users WHERE email='testadmin@aicoach.io' LIMIT 1);
  rid := (SELECT id FROM roles WHERE name='tenant_admin' LIMIT 1);

  -- Create tenant
  INSERT INTO tenants (id, name, slug, plan, is_active)
  VALUES (gen_random_uuid(), 'Test Org', 'test-org', 'starter', true)
  ON CONFLICT (slug) DO NOTHING;

  SELECT id INTO tid FROM tenants WHERE slug='test-org';

  -- Link user to tenant
  INSERT INTO user_tenants (id, user_id, tenant_id, is_primary)
  VALUES (gen_random_uuid(), uid, tid, true)
  ON CONFLICT DO NOTHING;

  -- Grant admin role
  IF rid IS NOT NULL THEN
    INSERT INTO user_roles (id, user_id, role_id, tenant_id)
    VALUES (gen_random_uuid(), uid, rid, tid)
    ON CONFLICT DO NOTHING;
  END IF;

  -- Set user tenant_id
  UPDATE users SET tenant_id=tid WHERE id=uid;

  RAISE NOTICE 'Done: tenant_id=%, user_id=%', tid, uid;
END $$;
