# ADR-0004: Pragma No Cover Exclusions for Streaming Tool Functions

## Status

Accepted

## Context

This repository is a demonstration project used in a workshop/conference talk on AI-assisted engineering. The CI pipeline enforces 80% test coverage (`--cov-fail-under=80`) to illustrate realistic quality gates — the kind you would apply in a production codebase. The tests exist to demonstrate *how* to test AI agent systems, not to achieve exhaustive production coverage.

Several categories of code exist that are structurally impossible or impractical to unit test without major trade-offs:

1. **Inner tool functions registered via `@toolset.tool_plain`** in `bookshelf_toolset.py` and `metadata_toolset.py` — pydantic-ai's `FunctionToolset` registers these as callable tool descriptors for the agent. They cannot be invoked directly in Python tests; they are only dispatched by the pydantic-ai agent runtime during a live model conversation.

2. **`_stream_events` async generators** in `ook_handler.py` and `metadata_handler.py` — these yield SSE events as the agent streams structured output. Testing them requires a live Bedrock model connection or a sufficiently deep mock of pydantic-ai's streaming internals. The existing integration tests cover the HTTP boundary (`handle()`); the inner generator body would require mocking pydantic-ai internals that are not part of our public interface contract.

3. **`output_type=False` branch in `BookshelfStreamingAgent.__init__`** — a sentinel branch that disables structured output for free-text chat. Currently unused in production (all callers pass an explicit output type); kept for completeness but not exercised by any test.

## Decision

Mark the above code paths with `# pragma: no cover` rather than writing brittle tests that mock framework internals.

## Rationale

### FunctionToolset Inner Functions

pydantic-ai's `FunctionToolset` wraps inner functions as tool descriptors. The decorated functions are not accessible as callable attributes on the toolset object — they are dispatched only when the agent decides to call the tool during a model invocation. There is no supported public API to invoke them outside of an agent run.

Writing tests that call these functions would require either:

- **Patching pydantic-ai internals**: Fragile; breaks on any minor version bump of pydantic-ai.
- **Running a live agent**: Requires Bedrock credentials, real S3/Textract setup, and is non-deterministic. That is integration testing, not unit testing.

The *logic* inside each tool function is covered indirectly:
- OCR logic is tested via `metadata_initial_handler.py` tests which call `_extract_ocr_text()` directly
- ISBN regex logic is tested in `test_isbn_toolset.py`
- Bookshelf query logic is tested in `test_bookshelf_handler.py` via `BookshelfHandler._list_all_books()`
- Tracker recording is tested in `test_tool_tracker.py`

What is untested is the pydantic-ai dispatch layer itself — which is the framework's responsibility, not ours.

### Streaming Generator Bodies

`_stream_events` methods are async generators that interleave agent streaming with SSE formatting. Testing them would require mocking:
- `pydantic_ai.Agent.run_stream()` context manager
- `result.stream_output()` async iterator
- Partial structured output objects (`StreamingAgentResponse`)

The existing handler tests (`test_ook_handler.py`, `test_metadata_handlers.py`) cover the HTTP layer: valid/invalid request bodies, session validation, error responses. The streaming logic itself is validated end-to-end by running the demo application — the live demonstration context is the primary validation environment for this code path.

### Accepted Trade-offs

| Trade-off | Impact | Reasoning |
|-----------|--------|-----------|
| Tool function bodies uncovered | Low — underlying logic tested elsewhere | FunctionToolset dispatch is framework-owned |
| Streaming body uncovered | Medium — integration tested manually | Mocking pydantic-ai streaming would be fragile |
| Sentinel branch uncovered | Negligible — unused in production | Remove when/if the branch is deleted |

## What Is NOT Skipped

The following are tested and must remain covered:

- `ToolTracker.record()`, `_summarize_result()`, `clear()`, `get_executions()` — pure Python, fully testable
- `BookshelfHandler` endpoint methods — tested via `test_bookshelf_handler.py` with moto S3
- All handler `handle()` methods — tested for validation, routing, and error paths
- `bookshelf_streaming_agent.py` agent initialisation — tested with mocked pydantic-ai classes

## References

- [pytest-cov pragma exclusions](https://coverage.readthedocs.io/en/latest/excluding.html)
- [pydantic-ai FunctionToolset](https://ai.pydantic.dev/tools/#function-tools)

## Revision History

- **2026-04-17**: Accepted. Documented rationale for `# pragma: no cover` on tool inner functions and streaming generators.
