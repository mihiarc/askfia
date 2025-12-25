"""Data download endpoints."""

import os
import uuid
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ...auth import require_auth
from ...models.schemas import DownloadRequest, DownloadResponse
from ...config import settings

logger = logging.getLogger(__name__)

# All download endpoints require authentication
router = APIRouter(dependencies=[require_auth])

# In-memory download registry (use Redis in production)
_downloads: dict[str, dict] = {}


@router.post("/prepare", response_model=DownloadResponse)
async def prepare_download(request: DownloadRequest):
    """
    Prepare FIA data for download.
    
    This downloads the data using pyFIA and stages it for the user.
    """
    from pyfia import download
    
    download_id = str(uuid.uuid4())[:8]
    
    try:
        # Download data
        if len(request.states) == 1:
            db_path = download(request.states[0], dir=settings.data_dir)
        else:
            db_path = download(request.states, dir=settings.data_dir)
        
        # Get file size
        file_size_mb = os.path.getsize(db_path) / 1e6
        
        # Register download
        _downloads[download_id] = {
            "path": db_path,
            "states": request.states,
            "tables": request.tables,
            "format": request.format,
        }
        
        return DownloadResponse(
            download_id=download_id,
            states=request.states,
            tables=request.tables,
            format=request.format,
            estimated_size_mb=file_size_mb,
            download_url=f"/api/v1/downloads/{download_id}",
            expires_in_hours=24,
        )
        
    except Exception as e:
        logger.exception("Error preparing download")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{download_id}")
async def get_download(download_id: str):
    """Download prepared FIA data."""
    
    if download_id not in _downloads:
        raise HTTPException(status_code=404, detail="Download not found or expired")
    
    download_info = _downloads[download_id]
    file_path = download_info["path"]
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    # Determine filename
    states = download_info["states"]
    if len(states) == 1:
        filename = f"FIA_{states[0]}.duckdb"
    else:
        filename = f"FIA_{'_'.join(states)}.duckdb"
    
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="application/octet-stream",
    )


@router.get("/{download_id}/info")
async def get_download_info(download_id: str):
    """Get information about a prepared download."""
    
    if download_id not in _downloads:
        raise HTTPException(status_code=404, detail="Download not found or expired")
    
    download_info = _downloads[download_id]
    file_path = download_info["path"]
    
    return {
        "download_id": download_id,
        "states": download_info["states"],
        "tables": download_info["tables"],
        "format": download_info["format"],
        "file_size_mb": os.path.getsize(file_path) / 1e6 if os.path.exists(file_path) else 0,
        "available": os.path.exists(file_path),
    }
