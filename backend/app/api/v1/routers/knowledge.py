from __future__ import annotations
import logging
import os
import uuid
from uuid import UUID
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, UploadFile, File, status
from pydantic import BaseModel
from app.schemas.common import MessageResponse
from app.services.knowledge.knowledge_service import KnowledgeBaseService, KnowledgeSourceService
from app.api.v1.dependencies.auth import get_current_active_user, get_current_tenant_id
from app.models.user import User
from app.core.config import settings
from app.core.exceptions import BadRequestError

logger = logging.getLogger(__name__)

router = APIRouter()
_kb_svc = KnowledgeBaseService()
_src_svc = KnowledgeSourceService()

# ── File upload validation ────────────────────────────────────────────────────

ALLOWED_MIME_TYPES = {
    'application/pdf',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    'text/plain',
    'text/markdown',
    'text/csv',
}
MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50MB


async def validate_upload(file: UploadFile) -> None:
    """
    Validate uploaded file by magic bytes (not just extension or Content-Type header).
    Raises HTTP 413 if too large, 415 if MIME type is not allowed.
    """
    # Size check before reading full file
    if file.size and file.size > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large. Maximum size is 50MB.")

    # Magic byte check — read first 2KB only, then reset position
    header = await file.read(2048)
    await file.seek(0)

    try:
        import magic
        mime = magic.from_buffer(header, mime=True)
    except Exception:
        # python-magic not available — fall back to extension check
        ext = os.path.splitext(file.filename or "")[-1].lower()
        ext_to_mime = {
            ".pdf": "application/pdf",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            ".txt": "text/plain",
            ".md": "text/markdown",
            ".csv": "text/csv",
        }
        mime = ext_to_mime.get(ext, "application/octet-stream")

    if mime not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"File type '{mime}' is not supported. Allowed: PDF, DOCX, PPTX, TXT, MD, CSV."
        )


class KBCreateRequest(BaseModel):
    name: str
    description: str | None = None
    scope: str = "tenant"


class TextSourceRequest(BaseModel):
    title: str
    content: str


@router.get("/")
async def list_knowledge_bases(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    tenant_id: UUID | None = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_active_user),
):
    """List knowledge bases for the current tenant."""
    if tenant_id is None:
        return {"items": [], "total": 0}
    result = await _kb_svc.list_knowledge_bases(tenant_id=tenant_id, page=page, page_size=page_size)
    return {"items": [{"id": str(kb.id), "name": kb.name, "scope": kb.scope, "chunk_count": kb.chunk_count} for kb in result.items], "total": result.total}


@router.get("/{kb_id}")
async def get_knowledge_base(
    kb_id: UUID,
    current_user: User = Depends(get_current_active_user),
    tenant_id: UUID | None = Depends(get_current_tenant_id),
):
    """Get a knowledge base by ID."""
    kb = await _kb_svc.get_knowledge_base(kb_id, tenant_id=tenant_id)
    return {"id": str(kb.id), "name": kb.name, "scope": kb.scope, "description": kb.description, "chunk_count": kb.chunk_count}


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_knowledge_base(
    body: KBCreateRequest,
    current_user: User = Depends(get_current_active_user),
    tenant_id: UUID | None = Depends(get_current_tenant_id),
):
    """Create a new knowledge base."""
    if tenant_id is None:
        raise BadRequestError("Tenant context required")
    kb = await _kb_svc.create_knowledge_base(
        name=body.name, tenant_id=tenant_id, scope=body.scope,
        description=body.description, created_by=current_user.id,
    )
    # Audit log (non-blocking — use background task so it doesn't block response)
    import asyncio as _asyncio
    from app.services.audit_service import write_audit_log_background
    _asyncio.create_task(write_audit_log_background(
        action="kb_created",
        tenant_id=tenant_id,
        user_id=current_user.id,
        resource_type="knowledge_base",
        resource_id=str(kb.id),
        metadata={"name": kb.name, "scope": kb.scope},
    ))
    return {"id": str(kb.id), "name": kb.name, "scope": kb.scope}


@router.delete("/{kb_id}", response_model=MessageResponse)
async def delete_knowledge_base(
    kb_id: UUID,
    current_user: User = Depends(get_current_active_user),
    tenant_id: UUID | None = Depends(get_current_tenant_id),
):
    """Delete a knowledge base."""
    await _kb_svc.delete_knowledge_base(kb_id, tenant_id=tenant_id)
    import asyncio as _asyncio
    from app.services.audit_service import write_audit_log_background
    _asyncio.create_task(write_audit_log_background(
        action="kb_deleted", tenant_id=tenant_id, user_id=current_user.id,
        resource_type="knowledge_base", resource_id=str(kb_id),
    ))
    return MessageResponse(message="Knowledge base deleted")


@router.get("/{kb_id}/sources")
async def list_sources(
    kb_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
):
    """List sources in a knowledge base."""
    result = await _src_svc.list_sources(kb_id=kb_id, page=page, page_size=page_size)
    return {"items": [{"id": str(s.id), "title": s.title, "type": s.type, "status": s.status, "chunk_count": s.chunk_count} for s in result.items], "total": result.total}


@router.post("/{kb_id}/sources/text", status_code=status.HTTP_201_CREATED)
async def ingest_text(
    kb_id: UUID,
    body: TextSourceRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    tenant_id: UUID | None = Depends(get_current_tenant_id),
):
    """Ingest plain text into a knowledge base. Triggers ingestion + embedding in background."""
    if tenant_id is None:
        raise BadRequestError("Tenant context required")
    source = await _src_svc.create_source_from_text(
        kb_id=kb_id, title=body.title, content=body.content,
        tenant_id=tenant_id, created_by=current_user.id,
    )

    # Wire the ingestion pipeline via worker queue (retry + monitoring)
    from app.tasks.knowledge_ingestion import run_ingestion
    from app.tasks.worker import enqueue
    background_tasks.add_task(
        enqueue,
        run_ingestion,
        source_id=source.id,
        kb_id=kb_id,
        tenant_id=tenant_id,
        source_type="paste",
        title=body.title,
        content=body.content,
    )
    logger.info("[KB] Ingestion queued for text source %s (kb=%s)", source.id, kb_id)
    import asyncio as _asyncio
    from app.services.audit_service import write_audit_log_background
    _asyncio.create_task(write_audit_log_background(
        action="source_created", tenant_id=tenant_id, user_id=current_user.id,
        resource_type="knowledge_source", resource_id=str(source.id),
        metadata={"title": body.title, "type": "paste", "kb_id": str(kb_id)},
    ))
    return {"id": str(source.id), "title": source.title, "type": source.type, "status": source.status}


@router.post("/{kb_id}/sources/upload", status_code=status.HTTP_201_CREATED)
async def upload_source(
    kb_id: UUID,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
    tenant_id: UUID | None = Depends(get_current_tenant_id),
):
    """Upload a file to a knowledge base. Triggers ingestion + embedding in background."""
    if tenant_id is None:
        raise BadRequestError("Tenant context required")

    ext = os.path.splitext(file.filename or "")[-1].lower()
    if ext not in settings.ALLOWED_UPLOAD_EXTENSIONS:
        raise BadRequestError(f"File type {ext} not allowed")

    # Magic-byte validation
    await validate_upload(file)

    contents = await file.read()
    if len(contents) > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        raise BadRequestError(f"File exceeds {settings.MAX_UPLOAD_SIZE_MB}MB limit")

    upload_dir = settings.UPLOAD_DIR
    os.makedirs(upload_dir, exist_ok=True)
    file_name = f"{uuid.uuid4()}{ext}"
    file_path = os.path.join(upload_dir, file_name)
    with open(file_path, "wb") as f:
        f.write(contents)

    mime_type = file.content_type or "application/octet-stream"
    source = await _src_svc.create_source_from_file(
        kb_id=kb_id,
        title=file.filename or file_name,
        file_path=file_path,
        mime_type=mime_type,
        file_size=len(contents),
        tenant_id=tenant_id,
        created_by=current_user.id,
    )

    # Wire the ingestion pipeline via worker queue (retry + monitoring)
    from app.tasks.knowledge_ingestion import run_ingestion
    from app.tasks.worker import enqueue
    background_tasks.add_task(
        enqueue,
        run_ingestion,
        source_id=source.id,
        kb_id=kb_id,
        tenant_id=tenant_id,
        source_type="upload",
        title=source.title,
        file_path=file_path,
        mime_type=mime_type,
    )
    logger.info("[KB] Ingestion queued for upload source %s (kb=%s)", source.id, kb_id)
    return {"id": str(source.id), "title": source.title, "type": source.type, "status": source.status}


@router.delete("/{kb_id}/sources/{source_id}", response_model=MessageResponse)
async def delete_source(
    kb_id: UUID,
    source_id: UUID,
    current_user: User = Depends(get_current_active_user),
):
    """Delete a knowledge source."""
    await _src_svc.delete_source(source_id)
    return MessageResponse(message="Source deleted")


@router.get("/{kb_id}/sources/{source_id}/status")
async def get_source_status(
    kb_id: UUID,
    source_id: UUID,
    current_user: User = Depends(get_current_active_user),
):
    """Get ingestion status for a knowledge source."""
    source = await _src_svc.get_source(source_id)
    return {
        "id": str(source.id),
        "title": source.title,
        "type": source.type,
        "status": source.status,
        "chunk_count": source.chunk_count,
        "error_message": getattr(source, "error_message", None),
    }


class URLSourceRequest(BaseModel):
    title: str
    url: str


@router.post("/{kb_id}/sources/url", status_code=status.HTTP_201_CREATED)
async def ingest_url(
    kb_id: UUID,
    body: URLSourceRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    tenant_id: UUID | None = Depends(get_current_tenant_id),
):
    """Ingest a URL into a knowledge base. Triggers crawl + ingestion + embedding in background."""
    if tenant_id is None:
        raise BadRequestError("Tenant context required")
    source = await _src_svc.create_source_from_url(
        kb_id=kb_id, url=body.url, title=body.title,
        tenant_id=tenant_id, created_by=current_user.id,
    )

    from app.tasks.knowledge_ingestion import run_ingestion
    from app.tasks.worker import enqueue
    background_tasks.add_task(
        enqueue,
        run_ingestion,
        source_id=source.id,
        kb_id=kb_id,
        tenant_id=tenant_id,
        source_type="url",
        title=body.title,
        url=body.url,
    )
    logger.info("[KB] Ingestion queued for URL source %s (kb=%s)", source.id, kb_id)
    return {"id": str(source.id), "title": source.title, "type": source.type, "status": source.status}
