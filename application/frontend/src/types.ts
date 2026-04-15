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
