"""
Tool to convert Mermaid diagram source to a PNG image file.

Uses Node.js @mermaid-js/mermaid-cli (mmdc) via subprocess—no Python mermaid
library to avoid dependency conflicts with google-adk. Requires Node.js and
npx (install with: npm install -g @mermaid-js/mermaid-cli or use npx).
Output is written to the project's reports/ directory.
"""

import datetime
import logging
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

# Resolve project root (parent of shared/) so reports/ is always the same place
_CURR_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _CURR_DIR.parent.parent
_REPORTS_DIR = _PROJECT_ROOT / "reports"

_MIN_PNG_BYTES = 500


def _extract_mermaid_block(content: str) -> str:
    """Extract the first ```mermaid ... ``` block from content, or return content with fences stripped."""
    s = (content or "").strip()
    if not s:
        return ""
    if s.startswith("```"):
        lines = s.split("\n")
        if lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        s = "\n".join(lines)
        return s.strip()
    low = s.lower()
    idx = low.find("```mermaid")
    if idx >= 0:
        start = idx + len("```mermaid")
        rest = s[start:]
        end_idx = rest.find("```")
        if end_idx >= 0:
            return rest[:end_idx].strip()
        return rest.strip()
    return s.strip()


def _mermaid_cli_available() -> bool:
    """True if npx is available (to run @mermaid-js/mermaid-cli)."""
    return shutil.which("npx") is not None


def mermaid_to_png(mermaid_diagram: str, output_filename: str | None = None) -> dict:
    """
    Converts Mermaid diagram source to a PNG file in the reports directory.

    Runs Node.js mermaid-cli via: npx -y @mermaid-js/mermaid-cli -i input.mmd -o output.png.
    No Python mermaid package is used (avoids click version conflict with google-adk).

    Args:
        mermaid_diagram: The Mermaid diagram source (e.g. "graph TD\\n  A --> B").
                        May optionally be wrapped in ```mermaid ... ``` code fences.
        output_filename: Optional base filename for the PNG (e.g. "threat_map").

    Returns:
        A dict with "status" ("success" or "error"), "file_path" on success, "error" on failure.
    """
    diagram = _extract_mermaid_block(mermaid_diagram or "")
    if not diagram:
        return {"status": "error", "error": "Mermaid diagram content is empty."}

    if not _mermaid_cli_available():
        return {
            "status": "error",
            "error": "Node.js npx is required for Mermaid PNG export. Install Node.js, then run: npm install -g @mermaid-js/mermaid-cli",
        }

    _REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    base = (output_filename or "diagram").strip()
    base = re.sub(r"[^\w\-]", "_", base).strip("_") or "diagram"
    base_png = f"{base}_{timestamp}.png"
    output_path = _REPORTS_DIR / base_png
    file_path_rel = f"reports/{base_png}"

    temp_mmd = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".mmd",
            prefix="mermaid_",
            dir=str(_REPORTS_DIR),
            delete=False,
            encoding="utf-8",
        ) as f:
            f.write(diagram)
            temp_mmd = Path(f.name)

        result = subprocess.run(
            [
                "npx",
                "-y",
                "@mermaid-js/mermaid-cli",
                "-i", str(temp_mmd),
                "-o", str(output_path),
            ],
            capture_output=True,
            text=True,
            timeout=90,
            cwd=str(_PROJECT_ROOT),
        )

        if temp_mmd and temp_mmd.exists():
            try:
                temp_mmd.unlink(missing_ok=True)
            except OSError:
                pass

        if result.returncode != 0:
            stderr = (result.stderr or result.stdout or "").strip()
            logging.error("mermaid-cli failed: %s", stderr)
            return {
                "status": "error",
                "error": f"Mermaid conversion failed. {stderr[:400]}",
            }

        if not output_path.exists() or output_path.stat().st_size < _MIN_PNG_BYTES:
            return {
                "status": "error",
                "error": "PNG was not created or is empty. Ensure @mermaid-js/mermaid-cli is installed (npm install -g @mermaid-js/mermaid-cli).",
            }

        logging.info("Mermaid diagram saved as PNG: %s", output_path)
        return {"status": "success", "file_path": file_path_rel}
    except subprocess.TimeoutExpired:
        if temp_mmd and temp_mmd.exists():
            try:
                temp_mmd.unlink(missing_ok=True)
            except OSError:
                pass
        return {"status": "error", "error": "Mermaid conversion timed out."}
    except Exception as e:
        logging.error("mermaid_to_png failed: %s", e)
        if temp_mmd and temp_mmd.exists():
            try:
                temp_mmd.unlink(missing_ok=True)
            except OSError:
                pass
        return {"status": "error", "error": str(e)}
