"""
app/services/module_validator.py — API-layer validation for module definitions.

Returns human-readable errors before the DB CHECK fires.
Called from module create/update endpoints.

Usage:
    from app.services.module_validator import validate_module_schema
    errors = validate_module_schema(body)
    if errors:
        raise HTTPException(422, {"errors": errors})
"""
from __future__ import annotations

from typing import Any

REQUIRED_TEMPLATE_VARS = ["{{intake_summary}}", "{{rubric}}"]
WEIGHT_TOLERANCE = 0.001


def validate_module_schema(data: dict[str, Any]) -> list[str]:
    """
    Validate a module version definition.
    Returns a list of human-readable error strings. Empty = valid.
    """
    errors: list[str] = []

    # ── 1. Framework steps ────────────────────────────────────────────────────
    steps = data.get("framework_steps") or []
    if not steps:
        errors.append("At least one framework step is required.")
    else:
        for i, step in enumerate(steps):
            label = step.get("label", "").strip()
            if not label:
                errors.append(f"Framework step {i + 1} must have a non-empty label.")

    # ── 2. Intake schema fields ───────────────────────────────────────────────
    intake = data.get("intake_schema") or []
    for i, field in enumerate(intake):
        label = field.get("label", "").strip()
        if not label:
            errors.append(f"Intake field {i + 1} must have a non-empty label.")

    # ── 3. Rubric dimensions + weight sum ─────────────────────────────────────
    rubric = data.get("scoring_rubric") or {}
    dimensions = rubric.get("dimensions") or []
    if not dimensions:
        errors.append("Scoring rubric must have at least one dimension.")
    else:
        total_weight = 0.0
        for i, dim in enumerate(dimensions):
            name = dim.get("name", "").strip()
            if not name:
                errors.append(f"Rubric dimension {i + 1} must have a non-empty name.")
            weight = dim.get("weight")
            if weight is None:
                errors.append(f"Rubric dimension '{name or i + 1}' is missing a weight.")
            else:
                try:
                    total_weight += float(weight)
                except (TypeError, ValueError):
                    errors.append(f"Rubric dimension '{name or i + 1}' has an invalid weight: {weight!r}")

        if dimensions and abs(total_weight - 1.0) > WEIGHT_TOLERANCE:
            errors.append(
                f"Rubric dimension weights must sum to 1.0 "
                f"(currently {total_weight:.4f}). Adjust weights before saving."
            )

    # ── 4. Prompt templates ───────────────────────────────────────────────────
    templates = data.get("prompt_templates") or []
    for tmpl in templates:
        body = tmpl.get("template_body", "") or ""
        ttype = tmpl.get("template_type", "")
        if ttype in ("coaching", "scoring"):
            missing = [v for v in REQUIRED_TEMPLATE_VARS if v not in body]
            if missing:
                errors.append(
                    f"Prompt template '{ttype}' is missing required variable(s): "
                    f"{', '.join(missing)}. Add them to ensure the AI has context."
                )

    return errors
