import os

from google.adk.agents import Agent

from shared.utils.file_loader import load_instructions_file

# Resolve paths relative to this file's directory
current_dir = os.path.dirname(os.path.abspath(__file__))
instructions_path = os.path.join(current_dir, "instructions.txt")

MODEL_NAME = "gemini-3-flash-preview"

architecture_parser_agent = Agent(
    name="architecture_parser_agent",
    description="Analyzes system architecture diagrams and documentation to identify trust boundaries, data flows, and potential attack vectors.",
    instruction=load_instructions_file(instructions_path),
    output_key="architecture_summary",
    model=MODEL_NAME
)

root_agent = architecture_parser_agent
