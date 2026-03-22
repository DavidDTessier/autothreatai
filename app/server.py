#!/usr/bin/env python3
"""
FastAPI server to serve the frontend and proxy requests to the orchestrator agent.
"""

import asyncio
import base64
import datetime
import hashlib
import io
import json
import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from PIL import Image
from pydantic import BaseModel

# Add project root to path
project_root = Path(__file__).parent.parent.absolute()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _user_friendly_error(raw_message: str, status_code: int | None = None) -> str:
    """Map internal/technical errors to short, user-friendly messages. No stack traces or URLs."""
    msg = (raw_message or "").strip().lower()
    if "404" in msg or "not_found" in msg or "not found" in msg:
        if "model" in msg or "models/" in msg:
            return "The selected model is not available. Please choose a different model from the dropdown."
        return "The requested resource was not found. Please try again."
    if status_code == 404:
        return "The requested resource was not found. Please try again."
    if "403" in msg or "permission" in msg or "forbidden" in msg:
        return "Access was denied. Please check your API key or Vertex AI permissions."
    if "401" in msg or "unauthorized" in msg or "invalid api key" in msg or "invalid_api_key" in msg:
        return "Invalid or missing API key. Please check your credentials."
    if "429" in msg or "quota" in msg or "rate limit" in msg:
        return "Request limit reached. Please wait a moment and try again."
    if "500" in msg or "503" in msg or "502" in msg:
        return "The analysis service is temporarily unavailable. Please try again later."
    if "connect" in msg or "connection" in msg or "refused" in msg or "timeout" in msg or "unreachable" in msg:
        return "Unable to reach the analysis service. Please check that all services are running and try again."
    if "model" in msg and ("not" in msg or "unsupported" in msg or "not found" in msg):
        return "The selected model is not available. Please choose a different model from the dropdown."
    # Generic fallback: never expose stack traces or internal details
    return "Analysis failed. Please try again or choose a different model."


def _cleanup_old_files(dir_path: Path, max_age_seconds: float) -> int:
    """Delete files in dir_path older than max_age_seconds. Returns count deleted."""
    if not dir_path.exists() or not dir_path.is_dir():
        return 0
    now = datetime.datetime.now().timestamp()
    deleted = 0
    for f in dir_path.iterdir():
        if f.is_file():
            try:
                age = now - f.stat().st_mtime
                if age > max_age_seconds:
                    f.unlink()
                    deleted += 1
                    logger.debug("Deleted old file: %s", f.name)
            except OSError as e:
                logger.warning("Could not delete %s: %s", f, e)
    return deleted


def _run_cleanup() -> None:
    """Run cleanup of uploads and reports directories (called from background task)."""
    uploads_max_sec = UPLOADS_MAX_AGE_HOURS * 3600
    reports_max_sec = REPORTS_MAX_AGE_DAYS * 86400
    logs_max_sec = LOGS_MAX_AGE_DAYS * 86400
    n_uploads = _cleanup_old_files(UPLOAD_DIR, uploads_max_sec)
    n_reports = _cleanup_old_files(REPORTS_DIR, reports_max_sec)
    n_logs = _cleanup_old_files(LOGS_DIR, logs_max_sec)
    if n_uploads or n_reports or n_logs:
        logger.info(
            "Cleanup: deleted %s file(s) from uploads, %s from reports, %s from logs",
            n_uploads,
            n_reports,
            n_logs,
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start background cleanup task; cancel it on shutdown."""
    cleanup_task: asyncio.Task | None = None

    async def cleanup_loop() -> None:
        while True:
            try:
                await asyncio.get_event_loop().run_in_executor(None, _run_cleanup)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning("Cleanup task error: %s", e)
            try:
                await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)
            except asyncio.CancelledError:
                break

    cleanup_task = asyncio.create_task(cleanup_loop())
    logger.info(
        "Periodic cleanup started: uploads older than %sh, reports older than %sd, every %ss",
        UPLOADS_MAX_AGE_HOURS,
        REPORTS_MAX_AGE_DAYS,
        CLEANUP_INTERVAL_SECONDS,
    )
    yield
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="AutoThreat AI", lifespan=lifespan)

# Enable CORS
app.add_middleware(
    # ⚠️ Whitelist specific origins - don't use ["*"] for production
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "http://localhost:8000").split(","), # Whitelist specific origins
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
    expose_headers=["*"],
    max_age=3600,
)

# File upload validation
ALLOWED_MIME_TYPES = ['image/png', 'image/jpeg', 'image/jpg', 'image/gif', 'image/webp']
ALLOWED_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.webp'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

# Temporary upload directory
UPLOAD_DIR = project_root / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

# Reports directory
REPORTS_DIR = project_root / "reports"
REPORTS_DIR.mkdir(exist_ok=True)

# Logs
LOGS_DIR = project_root / "logs"
LOGS_DIR.mkdir(exist_ok=True)

# Periodic cleanup: delete files older than these (env overridable)
UPLOADS_MAX_AGE_HOURS = int(os.getenv("UPLOADS_MAX_AGE_HOURS", "24"))
REPORTS_MAX_AGE_DAYS = int(os.getenv("REPORTS_MAX_AGE_DAYS", "7"))
LOGS_MAX_AGE_DAYS = int(os.getenv("LOGS_MAX_AGE_DAYS", "30"))
CLEANUP_INTERVAL_SECONDS = int(os.getenv("CLEANUP_INTERVAL_SECONDS", "3600"))  # 1 hour

# Orchestrator URL
ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://localhost:8005")
# Try different possible agent names (try directory name first as it's more reliable)
AGENT_NAME = "threat_model_orchestrator"  # From agent name in agent.py (single 'l')
AGENT_NAME_ALT = "orchestrator"  # From directory name

# Store working agent name
WORKING_AGENT_NAME = AGENT_NAME

# Frontend: Svelte build (app/frontend-svelte/dist)
frontend_svelte_dist = project_root / "app" / "frontend-svelte" / "dist"
svelte_available = frontend_svelte_dist.exists() and (frontend_svelte_dist / "index.html").exists()
if svelte_available:
    logger.info("Serving Svelte frontend from %s", frontend_svelte_dist)
else:
    logger.warning("Svelte frontend not built. Run: cd app/frontend-svelte && yarn install && yarn build")


@app.get("/")
async def serve_index():
    """Serve the Svelte frontend index."""
    index_path = frontend_svelte_dist / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path), media_type="text/html")
    raise HTTPException(status_code=404, detail="Frontend not found. Build with: cd app/frontend-svelte && yarn build")


@app.get("/favicon.svg")
async def serve_favicon():
    """Serve the Svelte favicon."""
    favicon_path = frontend_svelte_dist / "favicon.svg"
    if favicon_path.exists():
        return FileResponse(str(favicon_path), media_type="image/svg+xml")
    raise HTTPException(status_code=404)


@app.get("/assets/{filename:path}")
async def serve_asset(filename: str):
    """Serve Svelte build assets (CSS, JS) with correct media types."""
    if ".." in filename or filename.startswith("/"):
        raise HTTPException(status_code=400, detail="Invalid path")
    assets_dir = frontend_svelte_dist / "assets"
    file_path = (assets_dir / filename).resolve()
    if not file_path.is_file() or not str(file_path).startswith(str(assets_dir.resolve())):
        raise HTTPException(status_code=404, detail="Not found")
    media_type = "text/css" if filename.endswith(".css") else "application/javascript" if filename.endswith(".js") else None
    headers = {"Cache-Control": "public, max-age=0"} if media_type else None
    return FileResponse(str(file_path), media_type=media_type, headers=headers)


@app.post("/api/sessions")
async def create_session():
    """Create a new session with the orchestrator."""
    global WORKING_AGENT_NAME
    user_id = "web_user"

    # First, try to get list of available apps to find the correct orchestrator name
    try:
        async with httpx.AsyncClient() as client:
            list_url = f"{ORCHESTRATOR_URL}/list-apps"
            logger.info("Checking available apps at: %s", list_url)
            list_response = await client.get(list_url, timeout=5.0)
            if list_response.status_code == 200:
                available_apps = list_response.json()
                logger.info("Available apps: %s", available_apps)

                # Try to find orchestrator app name (check common variations)
                orchestrator_candidates = [
                    "threat_model_orchestrator",
                    "threat_modeller_orchestrator",
                    "orchestrator",
                    "threat_model_orchestrator_agent"
                ]

                for candidate in orchestrator_candidates:
                    if candidate in available_apps:
                        logger.info("Found orchestrator app: %s", candidate)
                        WORKING_AGENT_NAME = candidate
                        # Now create session with correct name
                        url = f"{ORCHESTRATOR_URL}/apps/{candidate}/users/{user_id}/sessions"
                        logger.info("Creating session at: %s", url)
                        session_response = await client.post(url, timeout=10.0)
                        if session_response.status_code in [200, 201]:
                            result = session_response.json()
                            logger.info("Session created successfully with agent: %s", candidate)
                            return result
                        else:
                            error_text = session_response.text[:500] if session_response.text else str(session_response.status_code)
                            logger.warning("Failed to create session with %s: %s - %s", candidate, session_response.status_code, error_text)
    except Exception as e:
        logger.warning("Could not list apps, trying direct connection: %s", e)

    # Fallback: Try both possible agent names directly
    for agent_name in [AGENT_NAME, AGENT_NAME_ALT]:
        url = f"{ORCHESTRATOR_URL}/apps/{agent_name}/users/{user_id}/sessions"
        logger.info("Trying to create session at: %s", url)

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, timeout=10.0)
                if response.status_code == 200 or response.status_code == 201:
                    result = response.json()
                    logger.info("Session created successfully with agent: %s", agent_name)
                    WORKING_AGENT_NAME = agent_name
                    return result
                else:
                    error_text = response.text[:500] if response.text else str(response.status_code)
                    logger.warning("Failed with agent name %s: %s - %s", agent_name, response.status_code, error_text)
        except httpx.HTTPError as e:
            logger.warning("Failed with agent name %s: %s", agent_name, e)
            continue

    # If we get here, both attempts failed
    raise HTTPException(
        status_code=503,
        detail=f"Cannot connect to orchestrator. Tried both {AGENT_NAME} and {AGENT_NAME_ALT}. Check that the orchestrator is running on {ORCHESTRATOR_URL} and accessible."
    )


class QueryRequest(BaseModel):
    """Request model for query endpoint."""
    user_id: str = "web_user"
    session_id: str
    message: str | None = ""  # Optional text message (for backward compatibility)
    message_parts: list[dict[str, Any]] | None = []  # Optional list of message parts (text or inlineData)
    # Google Gemini: API key and/or Vertex AI (required)
    api_key: str | None = None
    use_vertex: bool | None = False
    vertex_project: str | None = None
    vertex_location: str | None = None
    model_id: str | None = None  # Gemini model (e.g. gemini-3-flash-preview)


@app.post("/api/query")
async def stream_query(request: QueryRequest):
    """Stream query to the orchestrator agent."""
    global WORKING_AGENT_NAME
    url = f"{ORCHESTRATOR_URL}/run_sse"

    logger.info("Streaming query to: %s", url)
    logger.info("Using agent name: %s", WORKING_AGENT_NAME)
    logger.info("Session ID: %s", request.session_id)
    logger.info("User ID: %s", request.user_id)
    logger.info("Model ID: %s", request.model_id)
    logger.info("API Key: %s", request.api_key)
    logger.info("Use Vertex: %s", request.use_vertex)
    logger.info("Vertex Project: %s", request.vertex_project)
    logger.info("Vertex Location: %s", request.vertex_location)

    # Build message parts from request
    message_parts = []
    if request.message_parts:
        # Use provided message_parts (can include text and inlineData)
        message_parts = request.message_parts
        logger.info("Using message_parts: %d parts", len(message_parts))
        for i, part in enumerate(message_parts):
            if "text" in part:
                logger.info("Part %d: text (%d chars)", i, len(part.get("text", "")))
            elif "inlineData" in part:
                mime_type = part.get("inlineData", {}).get("mimeType", "unknown")
                logger.info("Part %d: inlineData (%s)", i, mime_type)
    elif request.message:
        # Fallback to text-only message
        message_parts = [{"text": request.message}]
        logger.info("Using text message: %d chars", len(request.message))

    if not message_parts:
        raise HTTPException(status_code=400, detail="Either 'message' or 'message_parts' must be provided")

    # Require either Google API key or Vertex AI
    has_api_key = bool(request.api_key and request.api_key.strip())
    has_vertex = bool(
        request.use_vertex
        and request.vertex_project
        and request.vertex_project.strip()
        and request.vertex_location
        and request.vertex_location.strip()
    )
    if not has_api_key and not has_vertex:
        raise HTTPException(
            status_code=400,
            detail="Credentials required: provide either a Google API key or Vertex AI (check 'Use Vertex AI' and fill Project ID and Location).",
        )

    request_payload_creds: dict[str, Any] = {}
    if request.api_key:
        request_payload_creds["api_key"] = request.api_key
    if request.use_vertex:
        request_payload_creds["use_vertex"] = True
        if request.vertex_project:
            request_payload_creds["vertex_project"] = request.vertex_project
        if request.vertex_location:
            request_payload_creds["vertex_location"] = request.vertex_location
    if request.model_id and request.model_id.strip():
        request_payload_creds["model_id"] = request.model_id.strip()

    # Set API key / Vertex / model on orchestrator and all agent processes (ADK reads from env)
    if request_payload_creds:
        base = ORCHESTRATOR_URL.rstrip("/").rsplit(":", 1)[0] if ":" in ORCHESTRATOR_URL else "http://localhost"
        set_key_urls = [f"{base}:{port}/set-api-key" for port in (8001, 8002, 8003, 8004, 8005)]
        orch_url = f"{ORCHESTRATOR_URL.rstrip('/')}/set-api-key"
        try:
            async with httpx.AsyncClient(timeout=10.0) as set_client:
                for set_key_url in set_key_urls:
                    try:
                        r = await set_client.post(set_key_url, json=request_payload_creds)
                        if r.status_code == 200:
                            logger.info("set-api-key succeeded: %s", set_key_url)
                        else:
                            if set_key_url == orch_url:
                                logger.error("set-api-key orchestrator failed: %s %s", r.status_code, r.text[:300])
                                raise HTTPException(
                                    status_code=503,
                                    detail=(
                                        "Orchestrator could not accept API key. "
                                        "If using Docker, rebuild the orchestrator: docker compose build orchestrator"
                                    ),
                                )
                            logger.warning("set-api-key %s returned %s", set_key_url, r.status_code)
                    except HTTPException:
                        raise
                    except Exception as e:
                        if set_key_url == orch_url:
                            raise HTTPException(
                                status_code=503,
                                detail=(
                                    f"Cannot set API key on orchestrator: {e!s}. "
                                    "If using Docker, ensure orchestrator is running and rebuilt."
                                ),
                            ) from e
                        logger.debug("set-api-key %s failed: %s", set_key_url, e)
        except HTTPException:
            raise
        except Exception as e:
            logger.error("set-api-key request failed: %s", e)
            raise HTTPException(
                status_code=503,
                detail=f"Cannot set API key on orchestrator: {e!s}. If using Docker, ensure orchestrator is running and rebuilt."
            ) from e

    client = httpx.AsyncClient(timeout=300.0)
    try:
        # Stream the response - keep connection alive
        async def generate():
            try:
                request_payload = {
                    "app_name": WORKING_AGENT_NAME,
                    "user_id": request.user_id,
                    "session_id": request.session_id,
                    "new_message": {"parts": message_parts},
                    "streaming": True,
                }
                request_payload.update(request_payload_creds)

                # Create preview for logging
                preview_parts = []
                for part in message_parts:
                    if "text" in part:
                        text = part["text"]
                        preview_parts.append(f"text: {text[:30]}..." if len(text) > 30 else f"text: {text}")
                    elif "inlineData" in part:
                        mime_type = part["inlineData"].get("mimeType", "unknown")  # pyright: ignore[reportAttributeAccessIssue]
                        preview_parts.append(f"image: {mime_type}")

                logger.info("Sending request to orchestrator with payload: %s", {
                    "app_name": request_payload["app_name"],
                    "user_id": request_payload["user_id"],
                    "session_id": request_payload["session_id"],
                    "message_parts": preview_parts,
                })

                async with client.stream(
                    "POST",
                    url,
                    json=request_payload,
                    headers={"Content-Type": "application/json"},
                ) as response:
                    logger.info("Response status: %s", response.status_code)
                    logger.info("Response headers: %s", dict(response.headers))

                    if response.status_code != 200:
                        # Read error response
                        error_text = f"HTTP {response.status_code}"
                        try:
                            # Read error body from stream
                            error_chunks = []
                            async for chunk in response.aiter_bytes():
                                error_chunks.append(chunk)
                            if error_chunks:
                                error_body = b"".join(error_chunks)
                                error_text = error_body.decode('utf-8', errors='replace')
                        except Exception as e:
                            logger.warning("Could not read error body: %s", e)

                        logger.error("Query failed with status %s: %s", response.status_code, error_text[:200])
                        logger.error("Request URL was: %s", url)
                        friendly = _user_friendly_error(error_text, response.status_code)
                        yield f"data: {json.dumps({'error': friendly})}\n\n"
                        return

                    # Stream the response chunks - small chunk_size so browser gets updates as each SSE event is sent
                    try:
                        async for chunk in response.aiter_bytes(chunk_size=256):
                            if chunk:
                                # Decode and yield immediately - no buffering
                                try:
                                    decoded = chunk.decode('utf-8', errors='replace')
                                    yield decoded
                                except UnicodeDecodeError:
                                    # Skip invalid UTF-8 sequences
                                    pass
                    except Exception as e:
                        logger.error("Error reading stream: %s", e, exc_info=True)
                        friendly = _user_friendly_error(str(e))
                        yield f"data: {json.dumps({'error': friendly})}\n\n"
            except Exception as e:
                logger.error("Error in stream generation: %s", e, exc_info=True)
                friendly = _user_friendly_error(str(e))
                yield f"data: {json.dumps({'error': friendly})}\n\n"
            finally:
                await client.aclose()

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
                "X-Content-Type-Options": "nosniff",
            }
        )
    except HTTPException:
        raise
    except httpx.HTTPStatusError as e:
        logger.error("HTTP error from orchestrator: %s", e, exc_info=True)
        status_code = e.response.status_code if e.response else 503
        error_detail = (e.response.text[:500] if e.response and e.response.text else str(e)) or ""
        friendly = _user_friendly_error(error_detail, status_code)
        raise HTTPException(status_code=status_code, detail=friendly) from e
    except httpx.HTTPError as e:
        logger.error("Failed to connect to orchestrator: %s", e, exc_info=True)
        friendly = _user_friendly_error(str(e))
        raise HTTPException(status_code=503, detail=friendly) from e
    except Exception as e:
        logger.error("Unexpected error in stream_query: %s", e, exc_info=True)
        friendly = _user_friendly_error(str(e))
        raise HTTPException(status_code=500, detail=friendly) from e


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    """
    Securely upload and validate image files.

    Validates file size, MIME type, and image integrity before accepting uploads.
    Returns base64-encoded data for use in message_parts.
    """
    try:
        # Read file contents
        contents = await file.read()

        # Check file size
        if len(contents) > MAX_FILE_SIZE:
            raise HTTPException(status_code=413, detail=f"File too large. Maximum size is {MAX_FILE_SIZE / (1024*1024):.0f}MB")

        # Validate file extension
        file_ext = Path(file.filename).suffix.lower() if file.filename else ""
        if file_ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"
            )

        # Validate MIME type from file content using Pillow
        try:
            img = Image.open(io.BytesIO(contents))
            img.verify()  # Verify image is not corrupted

            # Get actual format from Pillow
            img_format = img.format.lower() if img.format else ""
            valid_formats = {'png', 'jpeg', 'jpg', 'gif', 'webp'}

            if img_format not in valid_formats:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid image format detected: {img_format}. Allowed formats: {', '.join(valid_formats)}"
                )

            # Reopen image after verify() (verify() closes the image)
            img = Image.open(io.BytesIO(contents))

            # Additional validation: check image dimensions (prevent decompression bombs)
            width, height = img.size
            max_dimension = 10000  # 10k pixels max
            if width > max_dimension or height > max_dimension:
                raise HTTPException(
                    status_code=400,
                    detail=f"Image dimensions too large. Maximum: {max_dimension}x{max_dimension} pixels"
                )

            # Validate MIME type matches file extension
            mime_type_map = {
                'png': 'image/png',
                'jpeg': 'image/jpeg',
                'jpg': 'image/jpeg',
                'gif': 'image/gif',
                'webp': 'image/webp'
            }

            detected_mime = mime_type_map.get(img_format, '')
            if detected_mime not in ALLOWED_MIME_TYPES:
                raise HTTPException(status_code=400, detail="MIME type validation failed")

            # Validate client-provided MIME type matches detected type
            if file.content_type and file.content_type not in ALLOWED_MIME_TYPES:
                logger.warning("Client MIME type mismatch: %s vs detected %s", file.content_type, detected_mime)
                # Use detected MIME type instead of client-provided

        except Image.UnidentifiedImageError as exc:
            raise HTTPException(status_code=400, detail="Invalid or corrupted image file") from exc
        except Exception as e:
            logger.error("Image validation error: %s", e)
            raise HTTPException(status_code=400, detail="Image validation failed") from e

        # Generate secure filename with hash to prevent collisions
        file_hash = hashlib.sha256(contents).hexdigest()[:16]
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_filename = f"upload_{timestamp}_{file_hash}{file_ext}"
        file_path = UPLOAD_DIR / safe_filename

        # Save file with secure permissions (optional, for audit trail)
        # In production, you might want to store these temporarily and clean up
        try:
            with open(file_path, 'wb') as f:
                f.write(contents)
            # Set restrictive permissions (owner read/write only)
            os.chmod(file_path, 0o600)
        except Exception as e:
            logger.error("Error saving uploaded file: %s", e)
            # Continue even if save fails - we still have contents in memory

        # Convert to base64 for use in message_parts
        base64_data = base64.b64encode(contents).decode('utf-8')

        logger.info("File uploaded successfully: %s (%d bytes, %s)", file.filename, len(contents), detected_mime)

        return JSONResponse({
            "status": "success",
            "mimeType": detected_mime,
            "data": base64_data,
            "filename": file.filename,  # Original filename
            "serverFilename": safe_filename,  # Server-side filename for cleanup
            "size": len(contents),
            "dimensions": {"width": width, "height": height}
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Unexpected error in file upload: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="File upload failed") from e


@app.delete("/api/upload/{filename}")
async def delete_uploaded_file(filename: str):
    """
    Delete an uploaded file from the server.

    This endpoint allows cleanup of uploaded files that are no longer needed.
    Only files in the uploads directory can be deleted.
    """
    try:
        # Validate filename to prevent path traversal
        if not filename.startswith('upload_') or '..' in filename or '/' in filename or '\\' in filename:
            raise HTTPException(status_code=400, detail="Invalid filename")

        # Normalize path and ensure it's within uploads directory
        file_path = (UPLOAD_DIR / filename).resolve()
        uploads_dir = UPLOAD_DIR.resolve()

        # Prevent path traversal
        if not str(file_path).startswith(str(uploads_dir)):
            raise HTTPException(status_code=403, detail="Access denied")

        # Check if file exists
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File not found")

        # Delete the file
        try:
            file_path.unlink()
            logger.info("Deleted uploaded file: %s", filename)
            return JSONResponse({
                "status": "success",
                "message": f"File {filename} deleted successfully"
            })
        except OSError as e:
            logger.error("Error deleting file %s: %s", filename, e)
            raise HTTPException(status_code=500, detail="Failed to delete file") from e

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Unexpected error deleting file: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="File deletion failed") from e


@app.get("/api/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "orchestrator_url": ORCHESTRATOR_URL}


# Vertex AI config only when not running in a container (e.g. docker)
RUNNING_IN_CONTAINER = os.environ.get("RUNNING_IN_CONTAINER", "").strip().lower() in ("1", "true", "yes")


@app.get("/api/config")
async def get_config():
    """Frontend config: vertex available (local only), supported Gemini models."""
    return {
        "vertex_available": not RUNNING_IN_CONTAINER,
        "supported_models": [
            {"id": "gemini-3-flash-preview", "label": "Gemini 3 Flash Preview (Default)"},
            {"id": "gemini-3-pro-preview", "label": "Gemini 3 Pro Preview"},
            {"id": "gemini-2.5-pro", "label": "Gemini 2.5 Pro"},
            {"id": "gemini-flash-latest", "label": "Gemini 2.5 Flash Latest (09 2025)"},
            {"id": "gemini-flash-lite-latest", "label": "Gemini 2.5 Flash Lite Latest (09 2025)"},
            {"id": "gemini-2.5-flash", "label": "Gemini 2.5 Flash"},
            {"id": "gemini-2.5-flash-lite", "label": "Gemini 2.5 Flash Lite"},
            {"id": "gemini-2.0-flash", "label": "Gemini 2.0 Flash"},
            {"id": "gemini-2.0-flash-lite", "label": "Gemini 2.0 Flash Lite"},
        ],
        "default_model_id": "gemini-3-flash-preview",
    }


@app.get("/api/reports/latest-pdf")
async def get_latest_pdf():
    """Get the latest PDF report file."""
    reports_dir = project_root / "reports"
    if not reports_dir.exists():
        raise HTTPException(status_code=404, detail="Reports directory not found")

    # Find all PDF files
    pdf_files = list(reports_dir.glob("report_*.pdf"))
    if not pdf_files:
        raise HTTPException(status_code=404, detail="No PDF reports found")

    # Get the most recent PDF
    latest_pdf = max(pdf_files, key=lambda p: p.stat().st_mtime)

    return {
        "file_path": str(latest_pdf.relative_to(project_root)),
        "filename": latest_pdf.name,
        "created": latest_pdf.stat().st_mtime
    }


@app.get("/api/reports/download/{filename}")
async def download_report(filename: str):
    """Download a report file."""
    # Security: Only allow PDF files from reports directory
    if not filename.endswith('.pdf') or not filename.startswith('report_'):
        raise HTTPException(status_code=400, detail="Invalid filename")

     # Normalize path and ensure it's within reports directory
    file_path = (project_root / "reports" / filename).resolve()
    reports_dir = (project_root / "reports").resolve()

     # Prevent path traversal
    if not str(file_path).startswith(str(reports_dir)):
        raise HTTPException(status_code=403, detail="Access denied")

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type="application/pdf"
    )

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
