DO $$
DECLARE
  tid UUID;
  mid UUID;
  vid UUID;
  uid UUID;
BEGIN
  SELECT id INTO tid FROM tenants WHERE slug='test-org' LIMIT 1;
  SELECT id INTO uid FROM users WHERE email='testadmin@aicoach.io' LIMIT 1;

  IF tid IS NULL THEN RAISE NOTICE 'No tenant — run seed_test_tenant.sql first'; RETURN; END IF;

  -- Ensure module exists and is published
  SELECT id INTO mid FROM coaching_modules WHERE key='sbi_feedback' AND tenant_id=tid LIMIT 1;
  IF mid IS NULL THEN
    INSERT INTO coaching_modules (id,key,name,icon,blurb,tenant_id,status,created_by,gamification_overrides)
    VALUES (gen_random_uuid(),'sbi_feedback','SBI Feedback','BookOpen','SBI coaching framework',tid,'published',uid,'{}')
    RETURNING id INTO mid;
  ELSE
    UPDATE coaching_modules SET status='published' WHERE id=mid;
  END IF;
  RAISE NOTICE 'module id=%', mid;

  -- Ensure version exists with is_current=true
  SELECT id INTO vid FROM module_versions WHERE module_id=mid AND is_current=true LIMIT 1;
  IF vid IS NULL THEN
    INSERT INTO module_versions (
      id, module_id, version_number, framework_name, is_current,
      intake_schema, scoring_rubric, published_at, published_by
    ) VALUES (
      gen_random_uuid(), mid, 1, 'SBI', true,
      '[{"field_key":"situation","label":"Describe the Situation","type":"longtext","required":true,"placeholder":"What was the context?"},{"field_key":"behaviour","label":"Describe the Behaviour","type":"longtext","required":true,"placeholder":"What specifically happened?"},{"field_key":"impact","label":"Describe the Impact","type":"longtext","required":true,"placeholder":"What was the effect?"}]'::jsonb,
      '{"dimensions":[{"name":"Situation Clarity","weight":0.33,"band_descriptors":{"1":"Vague","2":"Partial","3":"Clear","4":"Precise"}},{"name":"Behaviour Specificity","weight":0.34,"band_descriptors":{"1":"Generic","2":"Somewhat specific","3":"Specific","4":"Very specific"}},{"name":"Impact Articulation","weight":0.33,"band_descriptors":{"1":"Unclear","2":"Implied","3":"Stated","4":"Quantified"}}]}'::jsonb,
      now(), uid
    )
    RETURNING id INTO vid;
    RAISE NOTICE 'created version id=%', vid;
  ELSE
    RAISE NOTICE 'existing version id=%', vid;
  END IF;

  -- Add coaching prompt template
  INSERT INTO module_prompt_templates (id, module_version_id, template_type, template_body, variables)
  VALUES (
    gen_random_uuid(), vid, 'coaching',
    'You are an expert SBI coach. Review this submission and respond with ONLY valid JSON.

KNOWLEDGE BASE CONTEXT:
{{knowledge}}

IMPORTANT: If knowledge says "No specific knowledge found", use general SBI principles only. Do NOT fabricate citations.

Situation: {{situation}}
Behaviour: {{behaviour}}
Impact: {{impact}}

Respond with ONLY this JSON:
{"feedback_text":"2-3 sentences of constructive SBI coaching feedback","strengths":["one strength"],"improvements":["one area to improve"],"recommendations":[{"priority":1,"area":"SBI structure","suggestion":"actionable tip"}],"next_steps":"one concrete next step"}',
    '["situation","behaviour","impact","knowledge"]'::jsonb
  )
  ON CONFLICT DO NOTHING;

  RAISE NOTICE 'Done: tenant=% module=% version=%', tid, mid, vid;
END $$;
