import json
from google.adk.agents.callback_context import CallbackContext
from typing import Callable

def save_output_callback(key: str) -> Callable[[CallbackContext], None]:
    """Creates a callback function to save the agent's last output to session state under the specified key."""
    def callback(callback_ctx: CallbackContext, **kwargs):
        ctx = callback_ctx
        agent_output = None
        # Find the last event from this agent that has content
        for event in reversed(ctx.session.events):
            if event.author == ctx.agent_name and event.content and event.content.parts:
                agent_output = event.content.parts[0].text
                break
        if agent_output:
            # Try to parse as JSON if it looks like it, for judge_feedback or verifier
            if key == "verifier_feedback" and agent_output.strip().startswith("{"):
                try:
                    ctx.state[key] = json.loads(agent_output)
                except json.JSONDecodeError:
                    ctx.state[key] = agent_output
            else:
                ctx.state[key] = agent_output
            print(f"[{ctx.agent_name}] Saved output to state['{key}']")
    return callback