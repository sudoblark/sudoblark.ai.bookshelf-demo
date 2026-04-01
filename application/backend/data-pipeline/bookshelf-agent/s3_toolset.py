"""S3 chunked-reader toolset for Vera and other pydantic-ai agents.

``build_s3_chunked_reader`` returns a ``FunctionToolset`` that lets an agent
read a single S3 object sequentially in fixed-size chunks.  Position state is
held inside the closure so the toolset is tightly scoped to one file per
agent run.

Typical usage inside a Lambda::

    from toolsets.s3_toolset import build_s3_chunked_reader

    toolset = build_s3_chunked_reader(s3_client, bucket, key)
    result = agent.run_sync(prompt, toolsets=[toolset])

Tools exposed
-------------
get_file_info
    HEAD the object and return its size, content-type, and chunk size.
read_next_chunk
    Read the next ``chunk_size_bytes`` bytes from the current position.
    Returns the decoded text, bytes consumed, current position, total size,
    and an ``end_of_file`` flag.
reset_position
    Rewind the internal read pointer back to byte 0.
"""

from typing import Any

from pydantic_ai import FunctionToolset


def build_s3_chunked_reader(
    s3_client: Any,
    bucket: str,
    key: str,
    chunk_size_bytes: int = 65_536,
    max_chunks: int | None = None,
) -> FunctionToolset:
    """Return a ``FunctionToolset`` for reading *key* in *bucket* chunk by chunk.

    Args:
        s3_client:        A ``boto3`` S3 client (or compatible test double).
        bucket:           The S3 bucket name.
        key:              The S3 object key.
        chunk_size_bytes: Maximum bytes per chunk (default 64 KB).
        max_chunks:       Maximum number of chunks the agent may read before
                          ``read_next_chunk`` returns ``end_of_file: True``.
                          ``None`` (default) means unlimited.

    Returns:
        A ``FunctionToolset`` exposing ``get_file_info``, ``read_next_chunk``,
        and ``reset_position``.
    """
    state: dict[str, Any] = {"position": 0, "total_size": None, "chunks_read": 0}

    toolset: FunctionToolset = FunctionToolset()

    @toolset.tool_plain
    def get_file_info() -> dict:
        """Return metadata about the S3 file: bucket, key, size_bytes, content_type,
        and chunk_size_bytes."""
        response = s3_client.head_object(Bucket=bucket, Key=key)
        total = response["ContentLength"]
        state["total_size"] = total
        return {
            "bucket": bucket,
            "key": key,
            "size_bytes": total,
            "content_type": response.get("ContentType", "application/octet-stream"),
            "chunk_size_bytes": chunk_size_bytes,
        }

    @toolset.tool_plain
    def read_next_chunk() -> dict:
        """Read the next chunk of the S3 file from the current position.

        Returns a dict with keys:
        - ``chunk``: decoded UTF-8 text (replacement chars for invalid bytes).
        - ``bytes_read``: number of bytes consumed in this call.
        - ``position``: byte offset *after* this read.
        - ``total_size``: total object size in bytes (fetched lazily if unknown).
        - ``end_of_file``: ``True`` when the position has reached the end.
        """
        if state["total_size"] is None:
            response = s3_client.head_object(Bucket=bucket, Key=key)
            state["total_size"] = response["ContentLength"]

        total: int = state["total_size"]
        start: int = state["position"]

        if start >= total:
            return {
                "chunk": "",
                "bytes_read": 0,
                "position": start,
                "total_size": total,
                "end_of_file": True,
            }

        if max_chunks is not None and state["chunks_read"] >= max_chunks:
            return {
                "chunk": "",
                "bytes_read": 0,
                "position": start,
                "total_size": total,
                "end_of_file": True,
            }

        end = min(start + chunk_size_bytes - 1, total - 1)
        response = s3_client.get_object(Bucket=bucket, Key=key, Range=f"bytes={start}-{end}")
        raw: bytes = response["Body"].read()
        chunk = raw.decode("utf-8", errors="replace")
        bytes_read = len(raw)
        state["position"] = start + bytes_read
        state["chunks_read"] += 1

        return {
            "chunk": chunk,
            "bytes_read": bytes_read,
            "position": state["position"],
            "total_size": total,
            "end_of_file": state["position"] >= total,
        }

    @toolset.tool_plain
    def reset_position() -> dict:
        """Reset the read position to the start of the file (byte 0)."""
        state["position"] = 0
        state["chunks_read"] = 0
        return {"position": 0, "message": "Read position reset to start of file."}

    return toolset
