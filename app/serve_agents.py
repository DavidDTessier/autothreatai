#!/usr/bin/env python3
"""Start all agents as FastAPI endpoints."""

import logging
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Optional

# Add project root to path
project_root = Path(__file__).parent.parent.absolute()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Agent configuration
AGENTS = [
    {"name": "Architecture Parser", "dir": "agents/architecture_parser", "port": 8001, "a2a": True},
    {"name": "Threat Modeler", "dir": "agents/threat_modeler", "port": 8002, "a2a": True},
    {"name": "Report Content Builder", "dir": "agents/report_content_builder", "port": 8003, "a2a": True},
    {"name": "Report Verifier", "dir": "agents/report_verifier", "port": 8004, "a2a": True},
    {"name": "Threat Modeler Orchestrator", "dir": "agents/threat_modeller_orchestrator", "port": 8005, "a2a": False},
]

processes: List[subprocess.Popen] = []


def kill_existing_processes():
    """Kill any existing processes on the agent ports."""
    for agent in AGENTS:
        port = agent["port"]
        try:
            result = subprocess.run(["lsof", "-ti", f":{port}"], capture_output=True, text=True, check=False)
            if result.stdout.strip():
                for pid in result.stdout.strip().split("\n"):
                    try:
                        os.kill(int(pid), signal.SIGTERM)
                        time.sleep(0.5)
                    except (ValueError, ProcessLookupError, PermissionError):
                        pass
        except Exception:
            pass


def start_agent(agent_config: dict) -> Optional[subprocess.Popen]:
    """Start a single agent as a FastAPI endpoint."""
    agent_dir = project_root / agent_config["dir"]
    if not agent_dir.exists():
        logger.error("Agent directory not found: %s", agent_dir)
        return None
    
    port = agent_config["port"]
    name = agent_config["name"]
    agent_name = agent_dir.name
    
    logger.info("Starting %s on port %s...", name, port)
    
    # Create wrapper module
    wrapper_content = f'''import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
from google.adk.cli import fast_api
agents_parent = Path(r"{agent_dir.parent}")
app = fast_api.get_fast_api_app(
    agents_dir=str(agents_parent),
    session_service_uri=None, artifact_service_uri=None,
    memory_service_uri=None, eval_storage_uri=None,
    allow_origins=[], web=False, trace_to_cloud=False,
    otel_to_cloud=False, a2a={str(agent_config["a2a"])},
    host="0.0.0.0", port={port}, url_prefix=None,
    reload_agents=False, extra_plugins=None,
)
try:
    from shared.tools.a2a_utils import a2a_card_middleware
    from starlette.middleware.base import BaseHTTPMiddleware
    app.add_middleware(BaseHTTPMiddleware, dispatch=a2a_card_middleware)
except ImportError:
    pass
'''
    
    wrapper_file = project_root / "app" / f"_agent_wrapper_{agent_name}.py"
    wrapper_file.write_text(wrapper_content)
    
    env = os.environ.copy()
    env["PYTHONPATH"] = str(project_root)
    env["ADK_SUPPRESS_EXPERIMENTAL_FEATURE_WARNINGS"] = "True"
    
    log_file = project_root / "logs" / f"{name.lower().replace(' ', '_')}.log"
    log_file.parent.mkdir(exist_ok=True)
    
    try:
        with open(log_file, "w", encoding="utf-8") as f:
            process = subprocess.Popen(
                ["uv", "run", "uvicorn", f"app._agent_wrapper_{agent_name}:app", "--host", "0.0.0.0", "--port", str(port)],
                cwd=str(project_root), stdout=f, stderr=subprocess.STDOUT, env=env
            )
        
        time.sleep(2)
        if process.poll() is not None:
            logger.error("Failed to start %s (exit code: %s)", name, process.returncode)
            return None
        
        logger.info("✓ %s started (PID: %s)", name, process.pid)
        return process
    except Exception as e:
        logger.error("Failed to start %s: %s", name, e)
        return None


def signal_handler(_sig, _frame):
    """Handle shutdown signals."""
    logger.info("\nShutting down all agents...")
    for process in processes:
        try:
            process.terminate()
        except (OSError, ProcessLookupError):
            pass
    time.sleep(1)
    for process in processes:
        try:
            process.kill()
        except (OSError, ProcessLookupError):
            pass
    sys.exit(0)


def main():
    """Main function to start all agents."""
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    kill_existing_processes()
    time.sleep(1)
    
    logger.info("Starting Agent FastAPI Servers...")
    
    for agent_config in AGENTS:
        process = start_agent(agent_config)
        if process:
            processes.append(process)
        time.sleep(1)
    
    time.sleep(3)
    
    logger.info("\nAll agents started:")
    for agent_config in AGENTS:
        logger.info("  %s: http://localhost:%s", agent_config["name"], agent_config["port"])
    logger.info("\nPress Ctrl+C to stop all agents.")
    
    try:
        while True:
            for i, process in enumerate(processes):
                if process.poll() is not None:
                    agent_name = AGENTS[i]["name"] if i < len(AGENTS) else "Unknown"
                    logger.error("%s exited with code %s", agent_name, process.returncode)
            time.sleep(5)
    except KeyboardInterrupt:
        signal_handler(None, None)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error("Fatal error: %s", e, exc_info=True)
        signal_handler(None, None)
