import { useEffect, useState } from "react";
import {
  getBookshelfOverview,
  getBookshelfCatalogue,
  searchBookshelf,
} from "../api";
import { Book, BookshelfOverview, CatalogueResponse, SearchResponse } from "../types";
import styles from "./BookshelfPage.module.css";

interface Props {
  onNavigateToNewBook: () => void;
}

export function BookshelfPage({ onNavigateToNewBook }: Props) {
  const [overview, setOverview] = useState<BookshelfOverview | null>(null);
  const [books, setBooks] = useState<Book[]>([]);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [isSearching, setIsSearching] = useState(false);

  // Fetch overview on mount
  useEffect(() => {
    async function fetchOverview() {
      try {
        const data = await getBookshelfOverview();
        setOverview(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load overview");
      }
    }
    fetchOverview();
  }, []);

  // Fetch catalogue on mount and page change
  useEffect(() => {
    if (isSearching) return; // Don't fetch catalogue if searching

    async function fetchCatalogue() {
      setLoading(true);
      try {
        const data = await getBookshelfCatalogue(currentPage, 5);
        setBooks(data.books);
        setTotalPages(data.total_pages);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load books");
      } finally {
        setLoading(false);
      }
    }

    fetchCatalogue();
  }, [currentPage, isSearching]);

  async function handleSearch() {
    if (!searchQuery.trim()) return;
    setIsSearching(true);
    setLoading(true);
    try {
      // Search both title and author, deduplicate results
      const titleResults = await searchBookshelf(searchQuery, "title");
      const authorResults = await searchBookshelf(searchQuery, "author");

      // Merge and dedupe by book_id
      const allBooks = [...titleResults.books, ...authorResults.books];
      const uniqueBooks = Array.from(
        new Map(allBooks.map(book => [book.book_id, book])).values()
      );

      setBooks(uniqueBooks);
      setTotalPages(1); // Search doesn't paginate
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Search failed");
    } finally {
      setLoading(false);
    }
  }

  function handleClearSearch() {
    setSearchQuery("");
    setIsSearching(false);
    setCurrentPage(1); // Reset to page 1 when clearing search
  }

  function handlePrevPage() {
    if (currentPage > 1) setCurrentPage(currentPage - 1);
  }

  function handleNextPage() {
    if (currentPage < totalPages) setCurrentPage(currentPage + 1);
  }

  // Empty state
  if (!loading && overview?.total_books === 0) {
    return (
      <div className={styles.page}>
        <div className={styles.emptyState}>
          <div className={styles.emptyIcon}>📚</div>
          <h1 className={styles.emptyTitle}>Your bookshelf is empty</h1>
          <p className={styles.emptyDescription}>
            Start by uploading your first book cover image to get metadata
            extracted automatically.
          </p>
          <div className={styles.emptyCard}>
            <p className={styles.emptyCardTitle}>Getting started</p>
            <p className={styles.emptyCardText}>
              Upload a photo of any book cover and our AI will extract the title, author,
              and publication details to build your digital bookshelf.
            </p>
            <button className={styles.ctaButton} onClick={onNavigateToNewBook}>
              Add your first book
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.page}>
      {/* Header with Title and Search */}
      <div className={styles.header}>
        <div className={styles.headerLeft}>
          <div className={styles.headerIcon}>📚</div>
          <div className={styles.headerContent}>
            <h1 className={styles.headerTitle}>Bookshelf</h1>
            <p className={styles.headerCount}>
              {overview?.total_books ?? 0} {overview?.total_books === 1 ? "book" : "books"}
            </p>
          </div>
        </div>

        <div className={styles.headerRight}>
          <div className={styles.searchBar}>
            <input
              type="text"
              className={styles.searchInput}
              placeholder="Search books..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            />
            <button className={styles.searchButton} onClick={handleSearch}>
              Search
            </button>
            {isSearching && (
              <button className={styles.clearButton} onClick={handleClearSearch}>
                Clear
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Content Area */}
      <div className={styles.content}>
        {/* Error State */}
        {error && <div className={styles.error}>{error}</div>}

        {/* Loading State */}
        {loading && <div className={styles.loading}>Loading books...</div>}

        {/* Book Grid */}
        {!loading && books.length > 0 && (
          <div className={styles.bookGrid}>
            {books.map((book) => (
              <div key={book.book_id} className={styles.bookCard}>
                <div className={styles.bookTitle}>{book.title}</div>
                <div className={styles.bookAuthor}>{book.author}</div>
                <div className={styles.bookYear}>
                  {book.published_year ?? "Unknown"}
                </div>
                {book.confidence !== null && (
                  <div className={styles.confidenceBadge}>
                    {Math.round(book.confidence * 100)}%
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {/* No Results */}
        {!loading && books.length === 0 && isSearching && (
          <div className={styles.noResults}>
            No books found for "{searchQuery}"
          </div>
        )}
      </div>

      {/* Pagination */}
      {!loading && !isSearching && totalPages > 1 && (
        <div className={styles.pagination}>
          <button
            className={styles.paginationButton}
            onClick={handlePrevPage}
            disabled={currentPage === 1}
          >
            Previous
          </button>
          <span className={styles.pageInfo}>
            Page {currentPage} of {totalPages}
          </span>
          <button
            className={styles.paginationButton}
            onClick={handleNextPage}
            disabled={currentPage === totalPages}
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
