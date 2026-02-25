"""Threat Modeler Agent for AutoThreat AI"""

import os

from google.adk.agents import Agent
from google.adk.tools.google_search_tool import google_search

from shared.utils.file_loader import load_instructions_file

# Resolve paths relative to this file's directory
current_dir = os.path.dirname(os.path.abspath(__file__))
instructions_path = os.path.join(current_dir, "instructions.txt")

DEFAULT_MODEL = "gemini-3-flash-preview"
MODEL_NAME = os.environ.get("GOOGLE_GENAI_MODEL", DEFAULT_MODEL)

threat_modeler_agent = Agent(
    name="threat_modeler_agent",
    description="Identifies potential security threats and vulnerabilities based on system architecture and data flows.",
    instruction=load_instructions_file(instructions_path),
    output_key="raw_threat_model",
    model=MODEL_NAME,
    tools=[google_search]
)

root_agent = threat_modeler_agent