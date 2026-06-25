import logging
import os
from collections.abc import AsyncGenerator
from typing import Any

from google.adk.agents import Agent
from google.adk.models import LLMRegistry
from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


class LocalOpenAILlm(BaseLlm):
    """
    Custom BaseLlm adapter that sends generation requests to an OpenAI-compatible
    endpoint (e.g., Ollama, vLLM) using the openai Python SDK.
    """

    model: str
    base_url: str = os.getenv("LOCAL_MODEL_BASE_URL", "http://localhost:11434/v1")
    api_key: str = "ollama"

    def _convert_contents(self, llm_request: LlmRequest) -> list[dict]:
        messages = []

        # Add system instruction if present
        if llm_request.config and llm_request.config.system_instruction:
            system_text = ""
            if isinstance(llm_request.config.system_instruction, str):
                system_text = llm_request.config.system_instruction
            else:
                system_text = str(llm_request.config.system_instruction)
            messages.append({"role": "system", "content": system_text})

        # Convert contents
        for content in llm_request.contents:
            role = "assistant" if content.role == "model" else "user"
            text_parts = []
            for part in (content.parts or []):
                if part.text:
                    text_parts.append(part.text)

            if text_parts:
                messages.append({"role": role, "content": "".join(text_parts)})

        return messages

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:

        self._maybe_append_user_content(llm_request)
        messages = self._convert_contents(llm_request)

        client = AsyncOpenAI(base_url=self.base_url, api_key=self.api_key)

        try:
            # We currently do not support tool calling in this simple local adapter
            response = await client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=stream,
                temperature=llm_request.config.temperature if llm_request.config else None,
            )

            if stream:
                async for chunk in response:
                    content = chunk.choices[0].delta.content if chunk.choices else ""
                    if content:
                        yield LlmResponse(
                            partial=True,
                            content=types.Content(role="model", parts=[types.Part.from_text(text=content)]),
                        )
                # Yield final complete response block
                yield LlmResponse(
                    partial=False,
                    content=types.Content(
                        role="model",
                        parts=[types.Part.from_text(text="")],  # Simplified for streaming
                    ),
                )
            else:
                content = response.choices[0].message.content if response.choices else ""
                yield LlmResponse(
                    partial=False, content=types.Content(role="model", parts=[types.Part.from_text(text=content or "")])
                )
        except Exception as e:
            logger.error(f"Error calling local model {self.model}: {e}")
            yield LlmResponse(error_code="LOCAL_MODEL_ERROR", error_message=str(e), partial=False)


class DynamicLlm(BaseLlm):
    """
    Custom BaseLlm adapter that checks os.environ["GOOGLE_GENAI_MODEL"]
    at query time and delegates to the appropriate provider (Gemini or LocalOpenAILlm).
    """

    model: str = "gemini-3-flash-preview"

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        # Read the current model from the environment, falling back to the default
        current_model = os.environ.get("GOOGLE_GENAI_MODEL", self.model)

        # Override the request's model attribute so the delegate knows which model to request
        llm_request.model = current_model

        if current_model.startswith("local/"):
            actual_model = current_model.replace("local/", "")
            # Instantiate local OpenAI provider dynamically
            local_llm = LocalOpenAILlm(model=actual_model)
            # Update the request model in case local LLM needs it
            llm_request.model = actual_model
            async for chunk in local_llm.generate_content_async(llm_request, stream=stream):
                yield chunk
        else:
            # Instantiate standard Google/Gemini provider dynamically via LLMRegistry
            google_llm = LLMRegistry.new_llm(current_model)
            async for chunk in google_llm.generate_content_async(llm_request, stream=stream):
                yield chunk



def create_agent(
    name: str,
    description: str,
    instruction: str,
    model: str,
    output_key: str | None = None,
    tools: list[Any] | None = None,
    **kwargs,
) -> Agent:
    """
    Factory method to create an ADK Agent using the DynamicLlm adapter.
    This routes requests to either Gemini or a local model (Ollama)
    at run-time based on the GOOGLE_GENAI_MODEL environment variable.
    """
    tools = tools or []
    dynamic_llm = DynamicLlm(model=model)
    return Agent(
        name=name,
        description=description,
        instruction=instruction,
        output_key=output_key,
        model=dynamic_llm,
        tools=tools,
        **kwargs,
    )
