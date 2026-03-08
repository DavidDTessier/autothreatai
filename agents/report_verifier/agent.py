"""
Report Verifier Agent

Audits the threat model report against security best practices and project requirements.
"""

import os

from google.adk.agents import Agent
from pydantic import BaseModel, Field

from shared.utils.file_loader import load_instructions_file

# Resolve paths relative to this file's directory
current_dir = os.path.dirname(os.path.abspath(__file__))
instructions_path = os.path.join(current_dir, "instructions.yaml")

DEFAULT_MODEL = "gemini-3-flash-preview"
MODEL_NAME = os.environ.get("GOOGLE_GENAI_MODEL", DEFAULT_MODEL)

# Define the Schema
class VerifierFeedback(BaseModel):
    """Structured feedback from the Verifier agent."""
    status: str = Field(
        description="Whether the threat model report is sufficient ('pass') or needs more work ('fail')."
    )
    feedback: str = Field(
        description="Detailed feedback on what is missing. If 'pass', a brief confirmation."
    )

report_verifier_agent = Agent(
    name="report_verifier_agent",
    description="Audits the threat model report against security best practices and project requirements.",
    instruction=load_instructions_file(instructions_path),
    model=MODEL_NAME,
    output_schema=VerifierFeedback,
    output_key="verification_feedback",  # Stored in session state so escalation checker can read .status
    disallow_transfer_to_parent=True,
    disallow_transfer_to_peers=True,
)

root_agent = report_verifier_agent