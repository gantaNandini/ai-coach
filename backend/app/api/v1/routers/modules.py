from __future__ import annotations
from uuid import UUID
from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field
from typing import Any
from app.schemas.common import MessageResponse
from app.services.module.module_service import CoachingModuleService
from app.api.v1.dependencies.auth import get_current_active_user, get_current_tenant_id
from app.models.user import User

router = APIRouter()
_svc = CoachingModuleService()


class ModuleCreateRequest(BaseModel):
    key: str
    name: str
    blurb: str | None = None
    icon: str | None = None


class ModuleUpdateRequest(BaseModel):
    name: str | None = None
    blurb: str | None = None
    icon: str | None = None


class ModuleVersionCreateRequest(BaseModel):
    """Full module definition for creating a version."""
    framework_name: str = Field(..., description="e.g. SBI, GROW, or custom name")
    intake_schema: list[dict[str, Any]] = Field(default_factory=list, description="List of intake field definitions")
    scoring_rubric: dict[str, Any] = Field(default_factory=dict, description="Rubric with dimensions and weights")
    framework_steps: list[dict[str, Any]] = Field(default_factory=list, description="Ordered framework steps")
    prompt_templates: list[dict[str, Any]] = Field(default_factory=list, description="Prompt templates by type")
    personas: list[dict[str, Any]] = Field(default_factory=list, description="Roleplay personas")


@router.get("/")
async def list_modules(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    module_status: str | None = Query(None, alias="status"),
    tenant_id: UUID | None = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_active_user),
):
    """List coaching modules."""
    result = await _svc.list_modules(
        tenant_id=tenant_id, status=module_status, page=page, page_size=page_size
    )
    return {
        "items": [
            {
                "id": str(m.id),
                "key": m.key,
                "name": m.name,
                "status": m.status,
                "blurb": m.blurb,
                "icon": m.icon,
            }
            for m in result.items
        ],
        "total": result.total,
    }


@router.get("/{module_id}")
async def get_module(
    module_id: UUID,
    current_user: User = Depends(get_current_active_user),
):
    """Get a coaching module by ID with full version details including intake_schema and framework steps."""
    from app.database.unit_of_work import UnitOfWork
    m = await _svc.get_module(module_id)
    result = {"id": str(m.id), "key": m.key, "name": m.name, "status": m.status, "blurb": m.blurb}
    # Enrich with current version details
    try:
        async with UnitOfWork() as uow:
            mv = await uow.module_versions.get_current_version_with_definition(module_id)
            if mv:
                result["framework_name"] = mv.framework_name or ""
                result["intake_schema"] = mv.intake_schema or []
                result["scoring_rubric"] = mv.scoring_rubric or {}
                result["version_id"] = str(mv.id)
                result["version_number"] = mv.version_number
                result["framework_steps"] = [
                    {"id": str(s.id), "step_key": s.step_key, "title": s.title,
                     "description": s.description, "step_order": s.step_order}
                    for s in (mv.framework_steps or [])
                ]
    except Exception:
        result["framework_name"] = ""
        result["intake_schema"] = []
        result["scoring_rubric"] = {}
    return result


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_module(
    body: ModuleCreateRequest,
    current_user: User = Depends(get_current_active_user),
    tenant_id: UUID | None = Depends(get_current_tenant_id),
):
    """Create a new coaching module."""
    m = await _svc.create_module(
        key=body.key, name=body.name, tenant_id=tenant_id,
        created_by=current_user.id, blurb=body.blurb, icon=body.icon,
    )
    return {"id": str(m.id), "key": m.key, "name": m.name, "status": m.status}


@router.patch("/{module_id}")
async def update_module(
    module_id: UUID,
    body: ModuleUpdateRequest,
    current_user: User = Depends(get_current_active_user),
):
    """Update a coaching module."""
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    m = await _svc.update_module(module_id, **updates)
    return {"id": str(m.id), "key": m.key, "name": m.name, "status": m.status}


@router.post("/{module_id}/publish")
async def publish_module(
    module_id: UUID,
    current_user: User = Depends(get_current_active_user),
):
    """Publish a module to make it available to learners."""
    m = await _svc.publish_module(module_id, published_by=current_user.id)
    return {"id": str(m.id), "key": m.key, "status": m.status}


@router.post("/{module_id}/archive")
async def archive_module(
    module_id: UUID,
    current_user: User = Depends(get_current_active_user),
):
    """Archive a module."""
    m = await _svc.archive_module(module_id)
    return {"id": str(m.id), "key": m.key, "status": m.status}


@router.delete("/{module_id}", response_model=MessageResponse)
async def delete_module(
    module_id: UUID,
    current_user: User = Depends(get_current_active_user),
):
    """Soft-delete a coaching module."""
    await _svc.delete_module(module_id)
    return MessageResponse(message="Module deleted")

# ── No-Code Module Builder Endpoints ──────────────────────────────────────────

@router.post("/{module_id}/versions", status_code=status.HTTP_201_CREATED)
async def create_module_version(
    module_id: UUID,
    body: ModuleVersionCreateRequest,
    current_user: User = Depends(get_current_active_user),
    tenant_id: UUID | None = Depends(get_current_tenant_id),
):
    """
    Create a complete module version with intake schema, rubric, steps,
    prompt templates, and personas. This is the no-code module builder endpoint.
    """
    from app.database.unit_of_work import UnitOfWork
    from app.models.module import (
        ModuleVersion, ModuleFrameworkStep, ModulePromptTemplate, ModulePersona
    )
    import uuid

    async with UnitOfWork() as uow:
        # Get next version number
        count = await uow.module_versions.count_versions(module_id)
        version_number = count + 1

        # Create version
        mv = ModuleVersion(
            id=uuid.uuid4(),
            module_id=module_id,
            version_number=version_number,
            framework_name=body.framework_name,
            intake_schema=body.intake_schema,
            scoring_rubric=body.scoring_rubric,
            is_current=False,
        )
        uow.session.add(mv)
        await uow.session.flush()

        # Add framework steps
        for i, step in enumerate(body.framework_steps):
            s = ModuleFrameworkStep(
                id=uuid.uuid4(),
                module_version_id=mv.id,
                step_order=i,
                label=step.get("label", step.get("title", f"Step {i+1}")),
                description=step.get("description", ""),
                scoring_hints=step.get("scoring_hints"),
            )
            uow.session.add(s)

        # Add prompt templates
        for tmpl in body.prompt_templates:
            t = ModulePromptTemplate(
                id=uuid.uuid4(),
                module_version_id=mv.id,
                template_type=tmpl.get("template_type", "coaching"),
                template_body=tmpl.get("template_body", ""),
                variables=tmpl.get("variables", []),
            )
            uow.session.add(t)

        # Add personas
        for p in body.personas:
            persona = ModulePersona(
                id=uuid.uuid4(),
                module_version_id=mv.id,
                persona_name=p.get("persona_name", "Default Persona"),
                description=p.get("description"),
                system_prompt=p.get("system_prompt", "You are a professional persona."),
                traits=p.get("traits", []),
                is_default=p.get("is_default", False),
            )
            uow.session.add(persona)

        await uow.commit()

        return {
            "id": str(mv.id),
            "module_id": str(module_id),
            "version_number": version_number,
            "framework_name": mv.framework_name,
            "intake_schema": mv.intake_schema,
            "scoring_rubric": mv.scoring_rubric,
            "steps_created": len(body.framework_steps),
            "templates_created": len(body.prompt_templates),
            "personas_created": len(body.personas),
            "status": "draft",
        }


@router.post("/{module_id}/versions/{version_id}/publish")
async def publish_version(
    module_id: UUID,
    version_id: UUID,
    current_user: User = Depends(get_current_active_user),
):
    """Publish a specific module version — makes it the active version for learners."""
    from app.database.unit_of_work import UnitOfWork
    from app.core.exceptions import NotFoundError
    async with UnitOfWork() as uow:
        mv = await uow.module_versions.get(version_id)
        if mv is None or mv.module_id != module_id:
            raise NotFoundError("ModuleVersion", version_id)

        result = await uow.module_versions.set_current_version(
            version_id=version_id,
            module_id=module_id,
            published_by=current_user.id,
            expected_version=mv.version,
        )
        await uow.commit()

    # Also publish the parent module
    await _svc.publish_module(module_id, published_by=current_user.id)

    return {
        "id": str(result.id),
        "module_id": str(module_id),
        "version_number": result.version_number,
        "is_current": result.is_current,
        "published_at": result.published_at.isoformat() if result.published_at else None,
    }


@router.get("/{module_id}/versions")
async def list_versions(
    module_id: UUID,
    current_user: User = Depends(get_current_active_user),
):
    """List all versions of a module."""
    from app.database.unit_of_work import UnitOfWork

    async with UnitOfWork() as uow:
        page = await uow.module_versions.version_history(module_id, page=1, page_size=50)

    return {
        "items": [
            {
                "id": str(v.id),
                "version_number": v.version_number,
                "framework_name": v.framework_name,
                "is_current": v.is_current,
                "published_at": v.published_at.isoformat() if v.published_at else None,
                "created_at": v.created_at.isoformat(),
            }
            for v in page.items
        ],
        "total": page.total,
    }


@router.get("/{module_id}/versions/{version_id}")
async def get_version_detail(
    module_id: UUID,
    version_id: UUID,
    current_user: User = Depends(get_current_active_user),
):
    """Get full module version definition — used by the module builder editor."""
    from app.database.unit_of_work import UnitOfWork
    from app.core.exceptions import NotFoundError

    async with UnitOfWork() as uow:
        mv = await uow.module_versions.get_version_with_definition(version_id)
        if mv is None or mv.module_id != module_id:
            raise NotFoundError("ModuleVersion", version_id)

    return {
        "id": str(mv.id),
        "module_id": str(mv.module_id),
        "version_number": mv.version_number,
        "framework_name": mv.framework_name,
        "is_current": mv.is_current,
        "intake_schema": mv.intake_schema or [],
        "scoring_rubric": mv.scoring_rubric or {},
        "published_at": mv.published_at.isoformat() if mv.published_at else None,
        "framework_steps": [
            {
                "id": str(s.id),
                "step_order": s.step_order,
                "label": s.label,
                "description": s.description,
                "scoring_hints": s.scoring_hints,
            }
            for s in sorted(mv.framework_steps or [], key=lambda x: x.step_order)
        ],
        "prompt_templates": [
            {
                "id": str(t.id),
                "template_type": t.template_type,
                "template_body": t.template_body,
                "variables": t.variables or [],
            }
            for t in (mv.prompt_templates or [])
        ],
        "personas": [
            {
                "id": str(p.id),
                "persona_name": p.persona_name,
                "description": p.description,
                "system_prompt": p.system_prompt,
                "traits": p.traits or [],
                "is_default": p.is_default,
            }
            for p in (mv.personas or [])
        ],
    }
