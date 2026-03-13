"""
Threat Modeler Orchestrator Agent

Uses ADK's SequentialAgent and LoopAgent to orchestrate the threat modeling workflow.
- Architecture Parser → Threat Modeler Router → (MEASTRO or standard) Threat Modeler → Report Builder → [Loop: Verifier → Escalation Checker] → Summary
- The loop continues until verifier gives a "pass" status (escalation condition met)
- When the architecture parser detects AI/Agentic flows, the router sends output to the MEASTRO threat modeler; otherwise to the standard threat modeler.
"""

import re
from typing import Any, AsyncGenerator

from google.adk.agents import Agent, LoopAgent, SequentialAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions

from agents.architecture_parser.agent import root_agent as architecture_parser
from agents.meastro_threat_modeler.agent import root_agent as meastro_threat_modeler
from agents.report_builder.agent import root_agent as report_builder
from agents.report_verifier.agent import root_agent as report_verifier
from agents.threat_modeler.agent import root_agent as threat_modeler

# Pattern to parse "Threat Modeler Routing: meastro_threat_modeler_agent" or "threat_modeler_agent" from architecture summary
THREAT_MODELER_ROUTING_PATTERN = re.compile(
    r"Threat\s+Modeler\s+Routing\s*:\s*(\w+)",
    re.IGNORECASE,
)


class ThreatModelerRouter(Agent):
    """
    Routes to MEASTRO threat modeler when the architecture includes AI/Agentic flows,
    otherwise to the standard threat modeler. Reads the architecture_parser output
    and the required "Threat Modeler Routing:" line to choose the downstream agent.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._meastro = meastro_threat_modeler
        self._standard = threat_modeler

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        state = ctx.session.state or {}
        if state.get("report_verification_status") is None:
            state["report_verification_status"] = "draft"
        architecture_summary = state.get("architecture_summary") or ""

        match = THREAT_MODELER_ROUTING_PATTERN.search(architecture_summary)
        if match:
            routing = match.group(1).strip().lower()
            use_meastro = "meastro" in routing
        else:
            use_meastro = False

        chosen = self._meastro if use_meastro else self._standard
        print(f"[ThreatModelerRouter] Using {'MEASTRO' if use_meastro else 'standard'} threat modeler.")
        async for event in chosen.run_async(ctx):
            yield event


threat_modeler_router = ThreatModelerRouter(
    name="threat_modeler_router",
    description="Routes to MEASTRO or standard threat modeler based on architecture parser classification.",
)

# Define the remote agents

class EscalationChecker(Agent):
    """
    Checks the verifier's feedback status to determine if the report is acceptable.

    This agent examines the verification results from report_verifier and:
    - If status is "pass", keeps verification_feedback in session state so the
      report_builder_agent (run after the loop) can set the report Status to Approved,
      then returns escalation signal to break the loop.
    - If status is not "pass", returns continue signal to loop again.
    """

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        """Check verification status and escalate if approved."""
        state = ctx.session.state or {}
        feedback: Any = state.get("verification_feedback")
        status: str = (
            getattr(feedback, "status", None)
            or (feedback.get("status") if isinstance(feedback, dict) else None)
            or "fail"
        )
        is_passed = status == "pass"
        print(f"[EscalationChecker] Verification feedback: {status}")

        if ctx.session.state is not None:
            ctx.session.state["report_verification_status"] = status
        if is_passed:
            if feedback is not None and ctx.session.state is not None:
                ctx.session.state["verification_feedback"] = feedback
            yield Event(author=self.name, actions=EventActions(escalate=True))
        else:
            yield Event(author=self.name)

escalation_checker_agent = EscalationChecker(name="escalation_checker")


class FinalReportBuilderRunner(Agent):
    """
    Runs the report_builder agent one more time after the verification loop.
    Used so the same report_builder instance is not added as a sub-agent twice
    (ADK allows an agent only one parent). When the loop exited with pass,
    report_builder will set the report Status to Approved.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._report_builder = report_builder

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        state = ctx.session.state or {}
        if state.get("report_verification_status") is None and state.get("verification_feedback") is not None:
            feedback = state["verification_feedback"]
            status = (
                getattr(feedback, "status", None)
                or (feedback.get("status") if isinstance(feedback, dict) else None)
                or "fail"
            )
            ctx.session.state["report_verification_status"] = status
        async for event in self._report_builder.run_async(ctx):
            yield event


final_report_builder_runner = FinalReportBuilderRunner(
    name="final_report_builder_runner",
    description="Runs report builder after verification loop to set Status to Approved when pass.",
)

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
# Architecture Parser → Threat Modeler Router → (MEASTRO or standard) Threat Modeler → [Loop: Report Builder → Verifier → Escalation Checker] → Final Report Builder run (set Status to Approved when pass)
root_agent = SequentialAgent(
    name="threat_model_orchestrator",
    description="Orchestrates threat modeling analysis with iterative report verification and refinement",
    sub_agents=[
        architecture_parser,
        threat_modeler_router,
        verification_loop,
        final_report_builder_runner,
    ]
)