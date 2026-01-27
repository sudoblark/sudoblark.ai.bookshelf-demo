/// Represents a single book record from the processed Parquet files.
///
/// This model mirrors the backend ETL pipeline output schema and is used
/// throughout the app for displaying and managing book metadata.
class Book {
  /// Unique identifier for the book record
  final String id;

  /// Original filename of the uploaded image
  final String filename;

  /// Extracted book title
  final String title;

  /// Extracted book author
  final String author;

  /// Extracted ISBN (International Standard Book Number)
  final String? isbn;

  /// Timestamp when the book record was processed
  final DateTime processedAt;

  /// Creates a new Book instance with required fields.
  const Book({
    required this.id,
    required this.filename,
    required this.title,
    required this.author,
    this.isbn,
    required this.processedAt,
  });

  /// Creates a Book instance from JSON response data.
  ///
  /// Expects JSON structure matching backend output:
  /// ```
  /// {
  ///   "id": "uuid-string",
  ///   "filename": "cover.jpg",
  ///   "title": "Book Title",
  ///   "author": "Author Name",
  ///   "isbn": "978-0-123456-78-9" (optional),
  ///   "processed_at": "2026-01-27T10:30:00Z"
  /// }
  /// ```
  factory Book.fromJson(Map<String, dynamic> json) {
    return Book(
      id: json['id'] as String,
      filename: json['filename'] as String,
      title: json['title'] as String,
      author: json['author'] as String,
      isbn: json['isbn'] as String?,
      processedAt: DateTime.parse(json['processed_at'] as String),
    );
  }

  /// Converts this Book to a JSON map.
  ///
  /// Used when sending data to the backend or storing locally.
  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'filename': filename,
      'title': title,
      'author': author,
      'isbn': isbn,
      'processed_at': processedAt.toIso8601String(),
    };
  }

  /// Returns a human-readable string representation of this Book.
  @override
  String toString() => 'Book(id: $id, title: $title, author: $author)';
}