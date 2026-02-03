"""
Threat Modeler Orchestrator Agent

Uses ADK's SequentialAgent and LoopAgent to orchestrate the threat modeling workflow.
- Architecture Parser → Threat Modeler → Report Builder → [Loop: Verifier → Escalation Checker] → Summary
- The loop continues until verifier gives a "pass" status (escalation condition met)
"""

from typing import AsyncGenerator

from google.adk.agents import Agent, LoopAgent, SequentialAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from google.genai import types

from agents.architecture_parser.agent import root_agent as architecture_parser
from agents.report_builder.agent import root_agent as report_builder
from agents.report_verifier.agent import root_agent as report_verifier
from agents.threat_modeler.agent import root_agent as threat_modeler

# Define the remote agents

class EscalationChecker(Agent):
    """
    Checks the verifier's feedback status to determine if the report is acceptable.
    
    This agent examines the verification results from report_verifier and:
    - If status is "pass", returns escalation signal to break the loop
    - If status is not "pass", returns continue signal to loop again
    """
    
    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        """Check verification status and escalate if approved."""
        # Get the verification feedback from session state
        state = ctx.session.state or {}

        verification_feedback = state.get("verification_feedback", "No feedback provided")

        print(f"[EscalationChecker] Verification feedback: {verification_feedback}")    

        # Determine if we should escalate (break the loop)
        is_passed = False
        
        if isinstance(verification_feedback, dict) and verification_feedback.get("status", "fail") == "pass":
            is_passed = True
        elif isinstance(verification_feedback, dict) and '"status": "pass"' in verification_feedback:
            is_passed = True
    

        if is_passed:
          # tells the loop to stop
           yield Event(
                author=self.name,
                actions=EventActions(escalate=True)
           )
        else:
          # tells the loop to continue
            yield Event(author=self.name)

escalation_checker_agent = EscalationChecker(name="escalation_checker")


# Create the verification loop: report_verifier → escalation_checker
# This loop continues until the escalation checker signals completion (when status == "pass")
# NOTE: report_builder is NOT in the loop - it runs once before verification
# The loop only runs verifier → escalation_checker to avoid rebuilding the report multiple times
verification_loop = LoopAgent(
    name="verification_loop",
    description="Loops between report verification and escalation checking until report is approved",
    sub_agents=[
        report_verifier,
        escalation_checker_agent
    ],
    # The loop continues until the verifier approves the report or hits max iterations
    max_iterations=3,
)

# Create orchestration pipeline with looping verification
# The workflow: Architecture Parser → Threat Modeler → Report Builder → [Loop: Verifier → Escalation Checker] → Summary
# Report builder runs ONCE before verification to avoid rebuilding the report multiple times
root_agent = SequentialAgent(
    name="threat_model_orchestrator",
    description="Orchestrates threat modeling analysis with iterative report verification and refinement",
    sub_agents=[
        architecture_parser,
        threat_modeler,
        report_builder,  # Build report once before verification
        verification_loop,  # Loop only verifier and escalation checker
    ]
)