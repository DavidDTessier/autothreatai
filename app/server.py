#!/usr/bin/env python3
"""
FastAPI server to serve the frontend and proxy requests to the orchestrator agent.
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.absolute()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import logging
from typing import Any, Dict, List, Optional

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="AutoThreat AI")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Orchestrator URL
ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://localhost:8005")
# Try different possible agent names (try directory name first as it's more reliable)
AGENT_NAME = "threat_model_orchestrator"  # From agent name in agent.py (single 'l')
AGENT_NAME_ALT = "orchestrator"  # From directory name

# Mount static files
frontend_path = project_root / "app" / "frontend"
if frontend_path.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_path)), name="static")
    logger.info("Frontend static files mounted at /static")
    
    # Ensure images directory exists
    images_dir = frontend_path / "images"
    images_dir.mkdir(exist_ok=True)
    logger.info("Images directory ready: %s", images_dir)
else:
    logger.warning("Frontend directory not found: %s", frontend_path)


@app.get("/")
async def serve_index():
    """Serve the frontend index.html file."""
    index_path = frontend_path / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    raise HTTPException(status_code=404, detail="Frontend not found")


# Store working agent name
_working_agent_name = AGENT_NAME

@app.post("/api/sessions")
async def create_session():
    """Create a new session with the orchestrator."""
    global _working_agent_name
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
                        _working_agent_name = candidate
                        # Now create session with correct name
                        url = f"{ORCHESTRATOR_URL}/apps/{candidate}/users/{user_id}/sessions"
                        logger.info("Creating session at: %s", url)
                        session_response = await client.post(url, timeout=10.0)
                        if session_response.status_code in [200, 201]:
                            result = session_response.json()
                            logger.info("Session created successfully with agent: %s", candidate)
                            return result
                        else:
                            error_text = await session_response.text() if hasattr(session_response, 'text') else str(session_response.status_code)  # pyright: ignore[reportCallIssue]
                            logger.warning("Failed to create session with %s: %s - %s", candidate, session_response.status_code, error_text[:200])
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
                    _working_agent_name = agent_name
                    return result
                else:
                    error_text = await response.text() if hasattr(response, 'text') else str(response.status_code)
                    logger.warning("Failed with agent name %s: %s - %s", agent_name, response.status_code, error_text[:200])
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
    message: Optional[str] = ""  # Optional text message (for backward compatibility)
    message_parts: Optional[List[Dict[str, Any]]] = []  # Optional list of message parts (text or inlineData)


@app.post("/api/query")
async def stream_query(request: QueryRequest):
    """Stream query to the orchestrator agent."""
    global _working_agent_name
    url = f"{ORCHESTRATOR_URL}/run_sse"
    
    logger.info("Streaming query to: %s", url)
    logger.info("Using agent name: %s", _working_agent_name)
    logger.info("Session ID: %s", request.session_id)
    logger.info("User ID: %s", request.user_id)
    
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
    
    client = httpx.AsyncClient(timeout=300.0)
    try:
        # Stream the response - keep connection alive
        async def generate():
            try:
                request_payload = {
                    "app_name": _working_agent_name,
                    "user_id": request.user_id,
                    "session_id": request.session_id,
                    "new_message": {"parts": message_parts},
                    "streaming": True,
                }
                
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
                        yield f"data: {{\"error\": \"Orchestrator returned error ({response.status_code}): {error_text[:500]}\"}}\n\n"
                        return
                    
                    # Stream the response chunks - use bytes for lower latency
                    try:
                        # Use aiter_bytes for more immediate processing (no text decoding buffering)
                        async for chunk in response.aiter_bytes(chunk_size=1024):
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
                        yield f"data: {{\"error\": \"Stream error: {str(e)}\"}}\n\n"
            except Exception as e:
                logger.error("Error in stream generation: %s", e, exc_info=True)
                yield f"data: {{\"error\": \"Connection error: {str(e)}\"}}\n\n"
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
        # Re-raise HTTP exceptions (already handled above)
        raise
    except httpx.HTTPStatusError as e:
        logger.error("HTTP error from orchestrator: %s", e, exc_info=True)
        status_code = e.response.status_code if e.response else 503
        error_detail = str(e)
        raise HTTPException(status_code=status_code, detail=f"Orchestrator HTTP error: {error_detail}") from e
    except httpx.HTTPError as e:
        logger.error("Failed to connect to orchestrator: %s", e, exc_info=True)
        raise HTTPException(status_code=503, detail=f"Cannot connect to orchestrator: {str(e)}") from e
    except Exception as e:
        logger.error("Unexpected error in stream_query: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}") from e


@app.get("/api/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "orchestrator_url": ORCHESTRATOR_URL}


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
    
    file_path = project_root / "reports" / filename
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
