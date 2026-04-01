export interface BookMetadata {
  title: string;
  author: string;
  isbn: string;
  publisher: string;
  published_year: number | null;
  description: string;
  confidence: number | null;
}

export interface PresignedUrlResponse {
  url: string;
  key: string;
  bucket: string;
  session_id: string;
}

export type StreamEvent =
  | { type: "text_delta"; delta: string }
  | { type: "metadata_update"; field: keyof BookMetadata; value: BookMetadata[keyof BookMetadata] }
  | { type: "complete" }
  | { type: "error"; message: string };
