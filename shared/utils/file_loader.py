import logging
import os

try:
    import yaml
except ImportError:
    yaml = None

def load_file_content(file_path: str, fallback: str = None) -> str:
    """
    Generic utility to load the content of a text file.

    This function reads the specified file and returns its content as a string.
    If the file is not found and a fallback is provided, it returns the fallback.

    Args:
        file_path (str): The path to the file to be read.
        fallback (str, optional): Default content if file is missing.

    Returns:
        str: The contents of the file or fallback.
    """
    try:
        with open(file_path, encoding='utf-8') as f:
            return f.read().strip()
    except (OSError, FileNotFoundError) as e:
        if fallback is not None:
            logging.warning(f"File not found or unreadable: {file_path}. Using fallback.")
            return fallback
        logging.error(f"Error reading file {file_path}: {e}")
        raise

def _build_instruction_from_yaml(data: dict) -> str:
    """
    Build a single instruction string from a YAML instruction document.
    Supports keys: role, objective, workflow, output_requirements, guidelines, constraint_checklist.
    """
    parts = []
    if data.get("role"):
        parts.append("Role:\n" + data["role"].strip())
    if data.get("objective"):
        parts.append("\nObjective:\n" + data["objective"].strip())
    if data.get("workflow"):
        parts.append("\nWorkflow:")
        for item in data["workflow"]:
            if isinstance(item, dict):
                step = item.get("step", "")
                name = item.get("name", "")
                desc = item.get("description", "")
                parts.append(f"\n  Step {step}: {name}\n{desc.strip()}")
            else:
                parts.append(f"  - {item}")
    if data.get("output_requirements"):
        oreq = data["output_requirements"]
        parts.append("\nOutput Requirements:")
        if isinstance(oreq, str):
            parts.append(oreq.strip())
        else:
            if oreq.get("format"):
                parts.append(f"  Format: {oreq['format']}")
            if oreq.get("threat_modeler_routing"):
                parts.append("\n  " + oreq["threat_modeler_routing"].strip().replace("\n", "\n  "))
            if oreq.get("sections"):
                for sec in oreq["sections"]:
                    if isinstance(sec, dict):
                        parts.append(f"\n  {sec.get('title', 'Section')}:\n  " + (sec.get("content") or "").strip().replace("\n", "\n  "))
                    else:
                        parts.append(f"  - {sec}")
            if oreq.get("constraint_checklist"):
                parts.append("\n  Constraint checklist:")
                for c in oreq["constraint_checklist"]:
                    parts.append(f"    - {c}")
    if data.get("guidelines"):
        parts.append("\nGuidelines:")
        for g in data["guidelines"]:
            parts.append(f"  - {g}")
    if data.get("constraint_checklist"):
        parts.append("\nConstraint checklist:")
        for c in data["constraint_checklist"]:
            parts.append(f"  - {c}")
    return "\n".join(parts).strip()


def load_instructions_file(file_path: str, fallback: str = "Perform your tasks as an expert agent.") -> str:
    """
    Loads agent instructions from a specified file with a default fallback.
    Supports .txt (raw text) and .yaml (structured role/objective/workflow/output_requirements).
    """
    if not os.path.isfile(file_path):
        if fallback is not None:
            logging.warning(f"Instructions file not found: {file_path}. Using fallback.")
            return fallback
        raise FileNotFoundError(f"Instructions file not found: {file_path}")
    if file_path.lower().endswith((".yaml", ".yml")):
        if yaml is None:
            logging.warning("PyYAML not available; reading YAML file as plain text.")
            return load_file_content(file_path, fallback=fallback)
        try:
            with open(file_path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
            if not data:
                return fallback or ""
            return _build_instruction_from_yaml(data)
        except Exception as e:
            logging.warning(f"Failed to parse YAML instructions from {file_path}: {e}. Using fallback.")
            return fallback or load_file_content(file_path, fallback=fallback)
    return load_file_content(file_path, fallback=fallback)


