"""
Threat Modeler Orchestrator Agent

Uses ADK's SequentialAgent and LoopAgent to orchestrate the threat modeling workflow.
- Architecture Parser → Threat Modeler → Report Builder → [Loop: Verifier → Escalation Checker] → Summary
- The loop continues until verifier gives a "pass" status (escalation condition met)
"""

from typing import AsyncGenerator, Literal

from google.adk.agents import Agent, LoopAgent, SequentialAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions

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
        is_passed = Literal[False, True] = False

        if verification_feedback.status == "pass":
            print(f"[EscalationChecker] Verification feedback: {verification_feedback.status}")
            is_passed = True
        else:
            print(f"[EscalationChecker] Verification feedback: {verification_feedback.status}")
            is_passed = False

        if is_passed:
            yield Event(author=self.name, actions=EventActions(escalate=True))
        else:
            yield Event(author=self.name)

escalation_checker_agent = EscalationChecker(name="escalation_checker")


# Create the verification loop: report_builder → report_verifier → escalation_checker
# This loop continues until the escalation checker signals completion (when status == "pass")
verification_loop = LoopAgent(
    name="verification_loop",
   description="Loops between report builder, report verifier, and escalation checker until report is approved",
    sub_agents=[
        report_builder, 
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
        architecture_parser, # Parse the input architecture
        threat_modeler, # Build threat model
        verification_loop,  # Loop between report builder, report verifier, and escalation checker
    ]
)