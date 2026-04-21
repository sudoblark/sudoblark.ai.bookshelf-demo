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

export interface ToolExecution {
  name: string;
  inputs: string;
  result_summary: string;
  execution_time_ms: number;
}

export type StreamEvent =
  | { type: "text_delta"; delta: string }
  | { type: "metadata_update"; field: keyof BookMetadata; value: BookMetadata[keyof BookMetadata] }
  | { type: "upload_id"; upload_id: string }
  | { type: "tool_executions"; executions: ToolExecution[] }
  | { type: "complete" }
  | { type: "error"; message: string };

export interface Book extends BookMetadata {
  book_id: string;
  filename: string;
  s3_key: string;
}

export interface BookshelfOverview {
  total_books: number;
  most_common_author: string | null;
  most_common_author_count: number;
}

export interface CatalogueResponse {
  books: Book[];
  page: number;
  page_size: number;
  total_books: number;
  total_pages: number;
}

export interface SearchResponse {
  books: Book[];
  total_results: number;
  query: string;
  field: string;
}

export interface RelatedBook {
  file_id: string;
  title: string;
  author: string;
  similarity: number;
  s3_key: string;
}

export interface RelatedBooksResponse {
  file_id: string;
  related: RelatedBook[];
}

export interface GraphNode {
  id: string;
  title: string;
  author: string;
}

export interface GraphEdge {
  source: string;
  target: string;
  weight: number;
}

export interface SimilarityGraphResponse {
  nodes: GraphNode[];
  edges: GraphEdge[];
  threshold: number;
}

// Ops dashboard types

export interface StageEntry {
  startedAt: string;
  endedAt: string | null;
  sourceBucket: string | null;
  sourceKey: string | null;
  destinationBucket: string | null;
  destinationKey: string | null;
  error?: string;
}

export interface UploadFile {
  upload_id: string;
  user_id: string;
  stage: string;
  stages: Record<string, StageEntry>;
  created_at: string;
  updated_at: string;
}

export interface OpsListResponse {
  files: UploadFile[];
  count: number;
}

export interface OpsDetailResponse {
  file: UploadFile;
}
