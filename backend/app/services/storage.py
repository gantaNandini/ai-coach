"""
app/services/storage.py — Storage service facade.

Re-exports from app.core.storage so callers can use either import path.
The canonical implementation is in app/core/storage.py.
"""
from app.core.storage import StorageBackend, LocalStorage, S3Storage, get_storage

# Alias so `from app.services.storage import StorageService` works
StorageService = get_storage
