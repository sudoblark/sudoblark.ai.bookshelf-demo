import { BookMetadata, PresignedUrlResponse, StreamEvent } from "./types";

export async function getPresignedUrl(filename: string): Promise<PresignedUrlResponse> {
  const res = await fetch(`/api/upload/presigned?filename=${encodeURIComponent(filename)}`);
  if (!res.ok) throw new Error(`Failed to get presigned URL: ${res.statusText}`);
  return res.json();
}

export async function uploadToS3(url: string, file: File): Promise<void> {
  const res = await fetch(url, {
    method: "PUT",
    body: file,
    headers: { "Content-Type": file.type || "application/octet-stream" },
  });
  if (!res.ok) throw new Error(`S3 upload failed: ${res.statusText}`);
}

async function* parseSse(response: Response): AsyncGenerator<StreamEvent> {
  if (!response.body) throw new Error("No response body");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split("\n\n");
      buffer = parts.pop() ?? "";
      for (const part of parts) {
        if (part.startsWith("data: ")) {
          try {
            yield JSON.parse(part.slice(6)) as StreamEvent;
          } catch {
            // malformed event — skip
          }
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}

export async function* streamInitialMetadata(
  bucket: string,
  key: string,
  filename: string
): AsyncGenerator<StreamEvent> {
  const res = await fetch("/api/metadata/initial", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ bucket, key, filename }),
  });
  if (!res.ok) throw new Error(`Initial metadata request failed: ${res.statusText}`);
  yield* parseSse(res);
}

export async function* streamRefinedMetadata(
  sessionId: string,
  message: string,
  currentMetadata: BookMetadata
): AsyncGenerator<StreamEvent> {
  const res = await fetch("/api/metadata/refine", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: sessionId,
      message,
      current_metadata: currentMetadata,
    }),
  });
  if (!res.ok) throw new Error(`Refinement request failed: ${res.statusText}`);
  yield* parseSse(res);
}

export async function acceptMetadata(
  metadata: BookMetadata,
  filename: string
): Promise<{ status: string; saved_key: string; upload_id: string }> {
  const res = await fetch("/api/metadata/accept", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ metadata, filename }),
  });
  if (!res.ok) throw new Error(`Accept request failed: ${res.statusText}`);
  return res.json();
}
