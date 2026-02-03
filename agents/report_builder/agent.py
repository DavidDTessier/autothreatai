import os

from google.adk.agents import Agent

from shared.tools.file_writer_tool import convert_markdown_to_pdf, write_file
from shared.utils.file_loader import load_instructions_file

# Resolve paths relative to this file's directory
current_dir = os.path.dirname(os.path.abspath(__file__))
instructions_path = os.path.join(current_dir, "instructions.txt")

MODEL_NAME = "gemini-3-flash-preview"

report_builder_agent = Agent(
    name="report_builder_agent",
    description="Compiles threat model findings into a comprehensive, professional security report.",
    instruction=load_instructions_file(instructions_path),
    output_key="threat_model_report_content",
    model=MODEL_NAME,
    tools=[write_file, convert_markdown_to_pdf]
)

root_agent = report_builder_agent
