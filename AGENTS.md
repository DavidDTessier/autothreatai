# AutoThreat AI - Agent Context & Guidelines

This document provides technical context, development guidelines, and security guardrails for AI coding agents working on the AutoThreat AI repository.

> **CRITICAL INSTRUCTION:** For anything else—including architecture overview, general setup, installation, running the project, UI features, and troubleshooting—you **MUST read the [README.md](README.md)**. Do not duplicate those instructions here.

## Agent Architecture Context

The AutoThreat AI ecosystem is built using the Google Agent Development Kit (ADK) and operates as a set of standalone services communicating via the Agent-to-Agent (A2A) protocol.

### Agent Modules
- **Architecture Parser (`agents/architecture_parser/`, Port 8001):** Transforms textual descriptions and uploaded visual diagrams into structured architecture data.
- **Threat Modeler (`agents/threat_modeler/`, Port 8002):** Applies STRIDE methodology to identify specific vulnerabilities.
- **Report Builder (`agents/report_builder/`, Port 8003):** Compiles findings into Markdown and PDF reports. Uses Node.js `mermaid-cli` via `npx` for Mermaid-to-PNG conversion to avoid Python dependency conflicts.
- **Report Verifier (`agents/report_verifier/`, Port 8004):** Audits the generated report against security standards and manages the iterative refinement loop.
- **Orchestrator (`agents/orchestrator/`, Port 8005):** Coordinates sequential execution of agents and streams Server-Sent Events (SSE) to the frontend.

## Development Guidelines

- **Dependency Management:** Use `uv` for all Python dependencies. Update `pyproject.toml` or `uv.lock` accordingly.
- **FastAPI Wrappers:** When running under Docker, `agents/entrypoint.sh` dynamically generates FastAPI wrappers (`app/_agent_wrapper_<AGENT_NAME>.py`). This allows the frontend to dynamically inject configuration (like API keys and Gemini model ID) at runtime.
- **Logging:** Individual agent outputs are captured in the `logs/` directory.

## Security Guardrails

When modifying, testing, or executing agents within this repository, adhere to the following security guardrails:

1. **API Key & Credential Handling:**
   - NEVER hardcode API keys, Vertex AI credentials, or other secrets into the source code.
   - Always rely on the dynamic credential injection provided by the FastAPI wrappers or use `.env` files for local development.

2. **Data Privacy & Isolation:**
   - Agents process sensitive system architecture details. Do not implement logging that outputs raw user descriptions, uploaded diagrams, or API keys to standard output or persistent logs unnecessarily.
   - Maintain strict isolation between sessions. Ensure no data leaks between different users' threat modeling requests.

3. **Execution Safety:**
   - The Report Builder uses `npx` to execute external tools. Validate all inputs to the `mermaid-cli` to prevent arbitrary command injection.
   - Do not introduce arbitrary code execution features within the agents unless strictly sandboxed.

4. **Dependency Security:**
   - Only use explicit versions for dependencies in `pyproject.toml`.
   - Do not introduce unvetted third-party packages for core functionality (e.g., using official Google Cloud SDKs over unverified community wrappers).

Remember, read the [README.md](README.md) for full project documentation.