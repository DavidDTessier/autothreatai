import os
from typing import Literal

from google.adk.agents import Agent
from pydantic import BaseModel, Field

from shared.utils.file_loader import load_instructions_file

# Resolve paths relative to this file's directory
current_dir = os.path.dirname(os.path.abspath(__file__))
instructions_path = os.path.join(current_dir, "instructions.txt")

MODEL_NAME = "gemini-3-flash-preview"

# Define the Schema
class VerifierFeedback(BaseModel):
    """Structured feedback from the Verifier agent."""
    status: Literal["pass", "fail"] = Field(
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
    disallow_transfer_to_parent=True,
    disallow_transfer_to_peers=True,
)

root_agent = report_verifier_agentroot_agent = report_verifier_agent