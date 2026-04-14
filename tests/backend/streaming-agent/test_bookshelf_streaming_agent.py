"""Tests for bookshelf_streaming_agent.py - pydantic-ai Agent wrapper."""

import importlib
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add streaming-agent to path for imports
sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), "../../../application/backend/streaming-agent"),
)
agent_mod = importlib.import_module("bookshelf_streaming_agent")
BookshelfStreamingAgent = agent_mod.BookshelfStreamingAgent
INITIAL_SYSTEM_PROMPT = agent_mod.INITIAL_SYSTEM_PROMPT
REFINEMENT_SYSTEM_PROMPT = agent_mod.REFINEMENT_SYSTEM_PROMPT


@pytest.fixture
def mock_bedrock_client():
    """Mock Bedrock client."""
    return MagicMock()


class TestBookshelfStreamingAgentInitialization:
    """Test BookshelfStreamingAgent initialization."""

    @patch("bookshelf_streaming_agent.BedrockProvider")
    @patch("bookshelf_streaming_agent.BedrockConverseModel")
    @patch("bookshelf_streaming_agent.Agent")
    def test_agent_initialization_default(
        self, mock_agent_class, mock_model_class, mock_provider_class, mock_bedrock_client
    ):
        """Test agent initialization with default (initial) mode."""
        mock_model_instance = MagicMock()
        mock_model_class.return_value = mock_model_instance
        mock_provider_instance = MagicMock()
        mock_provider_class.return_value = mock_provider_instance

        BookshelfStreamingAgent(
            model_id="claude-haiku",
            bedrock_client=mock_bedrock_client,
        )

        # Verify Provider was created with bedrock_client
        mock_provider_class.assert_called_once_with(bedrock_client=mock_bedrock_client)

        # Verify Model was created with correct ID
        mock_model_class.assert_called_once_with("claude-haiku", provider=mock_provider_instance)

        # Verify Agent was created with INITIAL_SYSTEM_PROMPT
        call_kwargs = mock_agent_class.call_args[1]
        assert call_kwargs["system_prompt"] == INITIAL_SYSTEM_PROMPT

    @patch("bookshelf_streaming_agent.BedrockProvider")
    @patch("bookshelf_streaming_agent.BedrockConverseModel")
    @patch("bookshelf_streaming_agent.Agent")
    def test_agent_initialization_refinement_mode(
        self, mock_agent_class, mock_model_class, mock_provider_class, mock_bedrock_client
    ):
        """Test agent initialization in refinement mode."""
        mock_model_instance = MagicMock()
        mock_model_class.return_value = mock_model_instance
        mock_provider_instance = MagicMock()
        mock_provider_class.return_value = mock_provider_instance

        BookshelfStreamingAgent(
            model_id="claude-haiku",
            bedrock_client=mock_bedrock_client,
            refinement=True,
        )

        # Verify Agent was created with REFINEMENT_SYSTEM_PROMPT
        call_kwargs = mock_agent_class.call_args[1]
        assert call_kwargs["system_prompt"] == REFINEMENT_SYSTEM_PROMPT

    @patch("bookshelf_streaming_agent.BedrockProvider")
    @patch("bookshelf_streaming_agent.BedrockConverseModel")
    @patch("bookshelf_streaming_agent.Agent")
    def test_agent_sets_output_type(
        self, mock_agent_class, mock_model_class, mock_provider_class, mock_bedrock_client
    ):
        """Test that agent output_type is set to StreamingBookMetadataResponse."""
        from streaming_models import StreamingBookMetadataResponse

        mock_model_instance = MagicMock()
        mock_model_class.return_value = mock_model_instance
        mock_provider_instance = MagicMock()
        mock_provider_class.return_value = mock_provider_instance

        BookshelfStreamingAgent(
            model_id="test-model",
            bedrock_client=mock_bedrock_client,
        )

        call_kwargs = mock_agent_class.call_args[1]
        assert call_kwargs["output_type"] == StreamingBookMetadataResponse

    @patch("bookshelf_streaming_agent.BedrockProvider")
    @patch("bookshelf_streaming_agent.BedrockConverseModel")
    @patch("bookshelf_streaming_agent.Agent")
    def test_agent_different_model_ids(
        self, mock_agent_class, mock_model_class, mock_provider_class, mock_bedrock_client
    ):
        """Test agent initialization with different model IDs."""
        mock_model_instance = MagicMock()
        mock_model_class.return_value = mock_model_instance
        mock_provider_instance = MagicMock()
        mock_provider_class.return_value = mock_provider_instance

        model_ids = ["claude-3-sonnet", "claude-haiku", "custom-model-id"]

        for model_id in model_ids:
            BookshelfStreamingAgent(
                model_id=model_id,
                bedrock_client=mock_bedrock_client,
            )

            # Most recent call should have correct model_id
            call_args = mock_model_class.call_args[0]
            assert call_args[0] == model_id


class TestBookshelfStreamingAgentRunStream:
    """Test BookshelfStreamingAgent.run_stream method."""

    @patch("bookshelf_streaming_agent.BedrockProvider")
    @patch("bookshelf_streaming_agent.BedrockConverseModel")
    @patch("bookshelf_streaming_agent.Agent")
    def test_run_stream_returns_context_manager(
        self, mock_agent_class, mock_model_class, mock_provider_class, mock_bedrock_client
    ):
        """Test that run_stream returns an async context manager."""
        mock_agent_instance = MagicMock()
        mock_agent_class.return_value = mock_agent_instance

        mock_context_manager = AsyncMock()
        mock_agent_instance.run_stream.return_value = mock_context_manager

        mock_model_instance = MagicMock()
        mock_model_class.return_value = mock_model_instance
        mock_provider_instance = MagicMock()
        mock_provider_class.return_value = mock_provider_instance

        agent = BookshelfStreamingAgent(
            model_id="test-model",
            bedrock_client=mock_bedrock_client,
        )

        result = agent.run_stream("Test prompt")

        # Should return the context manager from _agent.run_stream()
        assert result == mock_context_manager

    @patch("bookshelf_streaming_agent.BedrockProvider")
    @patch("bookshelf_streaming_agent.BedrockConverseModel")
    @patch("bookshelf_streaming_agent.Agent")
    def test_run_stream_passes_prompt(
        self, mock_agent_class, mock_model_class, mock_provider_class, mock_bedrock_client
    ):
        """Test that run_stream passes prompt to agent."""
        mock_agent_instance = MagicMock()
        mock_agent_class.return_value = mock_agent_instance
        mock_agent_instance.run_stream.return_value = AsyncMock()

        mock_model_instance = MagicMock()
        mock_model_class.return_value = mock_model_instance
        mock_provider_instance = MagicMock()
        mock_provider_class.return_value = mock_provider_instance

        agent = BookshelfStreamingAgent(
            model_id="test-model",
            bedrock_client=mock_bedrock_client,
        )

        prompt = "Extract metadata from this book cover"
        agent.run_stream(prompt)

        # Verify run_stream was called with prompt
        call_args = mock_agent_instance.run_stream.call_args[0]
        assert call_args[0] == prompt

    @patch("bookshelf_streaming_agent.BedrockProvider")
    @patch("bookshelf_streaming_agent.BedrockConverseModel")
    @patch("bookshelf_streaming_agent.Agent")
    def test_run_stream_passes_toolsets(
        self, mock_agent_class, mock_model_class, mock_provider_class, mock_bedrock_client
    ):
        """Test that run_stream passes toolsets to agent."""
        mock_agent_instance = MagicMock()
        mock_agent_class.return_value = mock_agent_instance
        mock_agent_instance.run_stream.return_value = AsyncMock()

        mock_model_instance = MagicMock()
        mock_model_class.return_value = mock_model_instance
        mock_provider_instance = MagicMock()
        mock_provider_class.return_value = mock_provider_instance

        agent = BookshelfStreamingAgent(
            model_id="test-model",
            bedrock_client=mock_bedrock_client,
        )

        toolsets = [MagicMock(), MagicMock()]
        agent.run_stream("Test prompt", toolsets=toolsets)

        # Verify toolsets were passed
        call_kwargs = mock_agent_instance.run_stream.call_args[1]
        assert call_kwargs["toolsets"] == toolsets

    @patch("bookshelf_streaming_agent.BedrockProvider")
    @patch("bookshelf_streaming_agent.BedrockConverseModel")
    @patch("bookshelf_streaming_agent.Agent")
    def test_run_stream_toolsets_defaults_to_empty_list(
        self, mock_agent_class, mock_model_class, mock_provider_class, mock_bedrock_client
    ):
        """Test that toolsets defaults to empty list if not provided."""
        mock_agent_instance = MagicMock()
        mock_agent_class.return_value = mock_agent_instance
        mock_agent_instance.run_stream.return_value = AsyncMock()

        mock_model_instance = MagicMock()
        mock_model_class.return_value = mock_model_instance
        mock_provider_instance = MagicMock()
        mock_provider_class.return_value = mock_provider_instance

        agent = BookshelfStreamingAgent(
            model_id="test-model",
            bedrock_client=mock_bedrock_client,
        )

        agent.run_stream("Test prompt")

        # Verify toolsets was empty list
        call_kwargs = mock_agent_instance.run_stream.call_args[1]
        assert call_kwargs["toolsets"] == []

    @patch("bookshelf_streaming_agent.BedrockProvider")
    @patch("bookshelf_streaming_agent.BedrockConverseModel")
    @patch("bookshelf_streaming_agent.Agent")
    def test_run_stream_passes_message_history(
        self, mock_agent_class, mock_model_class, mock_provider_class, mock_bedrock_client
    ):
        """Test that run_stream passes message_history to agent."""
        mock_agent_instance = MagicMock()
        mock_agent_class.return_value = mock_agent_instance
        mock_agent_instance.run_stream.return_value = AsyncMock()

        mock_model_instance = MagicMock()
        mock_model_class.return_value = mock_model_instance
        mock_provider_instance = MagicMock()
        mock_provider_class.return_value = mock_provider_instance

        agent = BookshelfStreamingAgent(
            model_id="test-model",
            bedrock_client=mock_bedrock_client,
        )

        history = [MagicMock(), MagicMock()]
        agent.run_stream("Test prompt", message_history=history)

        # Verify message_history was passed
        call_kwargs = mock_agent_instance.run_stream.call_args[1]
        assert call_kwargs["message_history"] == history

    @patch("bookshelf_streaming_agent.BedrockProvider")
    @patch("bookshelf_streaming_agent.BedrockConverseModel")
    @patch("bookshelf_streaming_agent.Agent")
    def test_run_stream_message_history_defaults_to_none(
        self, mock_agent_class, mock_model_class, mock_provider_class, mock_bedrock_client
    ):
        """Test that message_history defaults to None if not provided."""
        mock_agent_instance = MagicMock()
        mock_agent_class.return_value = mock_agent_instance
        mock_agent_instance.run_stream.return_value = AsyncMock()

        mock_model_instance = MagicMock()
        mock_model_class.return_value = mock_model_instance
        mock_provider_instance = MagicMock()
        mock_provider_class.return_value = mock_provider_instance

        agent = BookshelfStreamingAgent(
            model_id="test-model",
            bedrock_client=mock_bedrock_client,
        )

        agent.run_stream("Test prompt")

        # Verify message_history defaults to None
        call_kwargs = mock_agent_instance.run_stream.call_args[1]
        assert call_kwargs["message_history"] is None


class TestBookshelfStreamingAgentSystemPrompts:
    """Test system prompts."""

    def test_initial_system_prompt_exists(self):
        """Test that INITIAL_SYSTEM_PROMPT is defined."""
        assert INITIAL_SYSTEM_PROMPT is not None
        assert len(INITIAL_SYSTEM_PROMPT) > 0

    def test_initial_system_prompt_content(self):
        """Test that INITIAL_SYSTEM_PROMPT has expected content."""
        assert "book metadata extraction" in INITIAL_SYSTEM_PROMPT.lower()
        assert "isbn" in INITIAL_SYSTEM_PROMPT.lower()

    def test_refinement_system_prompt_exists(self):
        """Test that REFINEMENT_SYSTEM_PROMPT is defined."""
        assert REFINEMENT_SYSTEM_PROMPT is not None
        assert len(REFINEMENT_SYSTEM_PROMPT) > 0

    def test_refinement_system_prompt_content(self):
        """Test that REFINEMENT_SYSTEM_PROMPT has expected content."""
        assert (
            "refinement" in REFINEMENT_SYSTEM_PROMPT.lower()
            or "refine" in REFINEMENT_SYSTEM_PROMPT.lower()
        )
        assert "conversation" in REFINEMENT_SYSTEM_PROMPT.lower()

    def test_prompts_are_different(self):
        """Test that initial and refinement prompts are different."""
        assert INITIAL_SYSTEM_PROMPT != REFINEMENT_SYSTEM_PROMPT

    def test_prompts_have_critical_rules(self):
        """Test that both prompts have critical ISBN rules."""
        assert "CRITICAL" in INITIAL_SYSTEM_PROMPT or "NEVER" in INITIAL_SYSTEM_PROMPT
        assert "CRITICAL" in REFINEMENT_SYSTEM_PROMPT or "NEVER" in REFINEMENT_SYSTEM_PROMPT


class TestBookshelfStreamingAgentInstances:
    """Test creating multiple agent instances."""

    @patch("bookshelf_streaming_agent.BedrockProvider")
    @patch("bookshelf_streaming_agent.BedrockConverseModel")
    @patch("bookshelf_streaming_agent.Agent")
    def test_multiple_agent_instances_independent(
        self, mock_agent_class, mock_model_class, mock_provider_class, mock_bedrock_client
    ):
        """Test that multiple agent instances are independent."""
        mock_model_instance = MagicMock()
        mock_model_class.return_value = mock_model_instance
        mock_provider_instance = MagicMock()
        mock_provider_class.return_value = mock_provider_instance

        agent1 = BookshelfStreamingAgent(
            model_id="model-1",
            bedrock_client=mock_bedrock_client,
            refinement=False,
        )

        agent2 = BookshelfStreamingAgent(
            model_id="model-2",
            bedrock_client=mock_bedrock_client,
            refinement=True,
        )

        # Should be different instances
        assert agent1 is not agent2

    @patch("bookshelf_streaming_agent.BedrockProvider")
    @patch("bookshelf_streaming_agent.BedrockConverseModel")
    @patch("bookshelf_streaming_agent.Agent")
    def test_initial_and_refinement_agents(
        self, mock_agent_class, mock_model_class, mock_provider_class, mock_bedrock_client
    ):
        """Test creating both initial and refinement agents."""
        mock_model_instance = MagicMock()
        mock_model_class.return_value = mock_model_instance
        mock_provider_instance = MagicMock()
        mock_provider_class.return_value = mock_provider_instance

        initial_agent = BookshelfStreamingAgent(
            model_id="test-model",
            bedrock_client=mock_bedrock_client,
            refinement=False,
        )

        refinement_agent = BookshelfStreamingAgent(
            model_id="test-model",
            bedrock_client=mock_bedrock_client,
            refinement=True,
        )

        # Both should be created successfully
        assert initial_agent is not None
        assert refinement_agent is not None
        assert initial_agent is not refinement_agent
