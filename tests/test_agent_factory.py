import os
from unittest.mock import MagicMock, patch

import pytest
from google.adk.agents import Agent

from shared.utils.agent_factory import DynamicLlm, LocalOpenAILlm, create_agent


def test_create_agent_uses_dynamic_llm():
    # Arrange
    model_name = "gemini-3-flash-preview"
    name = "test_agent"
    description = "test description"
    instruction = "test instruction"

    # Act
    agent = create_agent(
        name=name,
        description=description,
        instruction=instruction,
        model=model_name,
        tools=[],
    )

    # Assert
    assert isinstance(agent, Agent)
    assert isinstance(agent.model, DynamicLlm)
    assert agent.model.model == model_name


@pytest.mark.asyncio
async def test_dynamic_llm_routes_to_local_when_env_var_is_local():
    # Prepare mock Request
    class DummyPart:
        def __init__(self, text=""):
            self.text = text

    class DummyContent:
        def __init__(self, role="user", parts=None):
            self.role = role
            self.parts = parts or []

    class DummyConfig:
        def __init__(self, system_instruction=None, temperature=None):
            self.system_instruction = system_instruction
            self.temperature = temperature

    class DummyLlmRequest:
        def __init__(self, contents, config=None, model=None):
            self.contents = contents
            self.config = config
            self.model = model

    request = DummyLlmRequest(
        contents=[DummyContent(role="user", parts=[DummyPart(text="Hello")])],
        config=DummyConfig(system_instruction="You are a helpful assistant."),
    )

    dynamic_llm = DynamicLlm(model="gemini-3-flash-preview")

    mock_resp = type("LlmResponse", (), {"content": "Local reply"})

    async def mock_generate(*args, **kwargs):
        yield mock_resp

    with patch.dict(os.environ, {"GOOGLE_GENAI_MODEL": "local/llama3"}):
        with patch.object(LocalOpenAILlm, "generate_content_async", side_effect=mock_generate) as mock_local_generate:
            results = []
            async for resp in dynamic_llm.generate_content_async(request, stream=False):
                results.append(resp)

            assert len(results) == 1
            assert results[0] == mock_resp
            mock_local_generate.assert_called_once()
            assert request.model == "llama3"


@pytest.mark.asyncio
async def test_dynamic_llm_routes_to_gemini_when_env_var_is_google():
    class DummyPart:
        def __init__(self, text=""):
            self.text = text

    class DummyContent:
        def __init__(self, role="user", parts=None):
            self.role = role
            self.parts = parts or []

    class DummyConfig:
        def __init__(self, system_instruction=None, temperature=None):
            self.system_instruction = system_instruction
            self.temperature = temperature

    class DummyLlmRequest:
        def __init__(self, contents, config=None, model=None):
            self.contents = contents
            self.config = config
            self.model = model

    request = DummyLlmRequest(
        contents=[DummyContent(role="user", parts=[DummyPart(text="Hello")])],
        config=DummyConfig(system_instruction="You are a helpful assistant."),
    )

    dynamic_llm = DynamicLlm(model="gemini-3-flash-preview")

    mock_resp = type("LlmResponse", (), {"content": "Gemini reply"})
    mock_google_llm = MagicMock()

    async def mock_generate(*args, **kwargs):
        yield mock_resp

    mock_google_llm.generate_content_async = mock_generate

    with patch.dict(os.environ, {"GOOGLE_GENAI_MODEL": "gemini-2.5-pro"}):
        with patch("shared.utils.agent_factory.LLMRegistry.new_llm", return_value=mock_google_llm) as mock_new_llm:
            results = []
            async for resp in dynamic_llm.generate_content_async(request, stream=False):
                results.append(resp)

            assert len(results) == 1
            assert results[0] == mock_resp
            mock_new_llm.assert_called_once_with("gemini-2.5-pro")
            assert request.model == "gemini-2.5-pro"


@pytest.mark.asyncio
async def test_local_openai_llm_generate_content_async_returns_response():
    # Prepare a fake LlmRequest object with minimal required attributes
    class DummyPart:
        def __init__(self, text=""):
            self.text = text

    class DummyContent:
        def __init__(self, role="user", parts=None):
            self.role = role
            self.parts = parts or []

    class DummyConfig:
        def __init__(self, system_instruction=None, temperature=None):
            self.system_instruction = system_instruction
            self.temperature = temperature

    class DummyLlmRequest:
        def __init__(self, contents, config=None):
            self.contents = contents
            self.config = config

    request = DummyLlmRequest(
        contents=[DummyContent(role="user", parts=[DummyPart(text="Hello")])],
        config=DummyConfig(system_instruction="You are a helpful assistant."),
    )

    # Patch AsyncOpenAI to return a mock client that yields a canned response
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [type("Choice", (), {"message": type("Message", (), {"content": "Mock reply"})})]

    async def mock_create(*args, **kwargs):
        return mock_response

    mock_client.chat.completions.create = mock_create

    with patch("shared.utils.agent_factory.AsyncOpenAI", return_value=mock_client):
        llm = LocalOpenAILlm(model="llama3")
        results = []
        async for resp in llm.generate_content_async(request, stream=False):
            results.append(resp)
        assert len(results) == 1
        response = results[0]
        assert hasattr(response, "content")
        assert "Mock reply" in str(response.content)
