
import os
import sys
import logging

import google.auth

# Add the agent directory to the path
sys.path.insert(0, os.path.dirname(__file__))

# Add the project root to the path so that 'shared' module can be imported
# The project root is two levels up from this file (agents/report_verifier/__init__.py)
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# --- Configuration ---
os.environ["ADK_SUPPRESS_EXPERIMENTAL_FEATURE_WARNINGS"] = "True"

# Suppress OpenTelemetry attribute warnings for None values
# These occur when usage metrics are not available (e.g., input_tokens is None)
logging.getLogger("opentelemetry.attributes").setLevel(logging.ERROR)
# Use default project from credentials if not in .env
try:
    _, project_id = google.auth.default()
    os.environ.setdefault("GOOGLE_CLOUD_PROJECT", project_id) # type: ignore
except Exception:
    # If no credentials available, continue without setting project
    pass

if "GEMINI_API_KEY" in os.environ and "GOOGLE_API_KEY" not in os.environ:
    os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "global")
    os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "True")
    os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "True")
