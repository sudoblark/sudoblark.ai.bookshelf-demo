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
  const [searchField, setSearchField] = useState<"title" | "author">("title");
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
      const data = await searchBookshelf(searchQuery, searchField);
      setBooks(data.books);
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
        <div className={styles.container}>
          <div className={styles.icon}>📚</div>
          <h1 className={styles.title}>Your bookshelf is empty</h1>
          <p className={styles.subtitle}>
            Start by uploading your first book cover image to get metadata
            extracted automatically.
          </p>
          <button className={styles.ctaButton} onClick={onNavigateToNewBook}>
            Add your first book
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.page}>
      {/* Overview Stats */}
      <div className={styles.statsRow}>
        <div className={styles.statCard}>
          <div className={styles.statLabel}>Total Books</div>
          <div className={styles.statValue}>{overview?.total_books ?? "—"}</div>
        </div>
        <div className={styles.statCard}>
          <div className={styles.statLabel}>Most Common Author</div>
          <div className={styles.statValue}>
            {overview?.most_common_author ?? "—"}
          </div>
          <div className={styles.statSubtext}>
            {overview?.most_common_author_count ?? 0} books
          </div>
        </div>
      </div>

      {/* Search Bar */}
      <div className={styles.searchBar}>
        <input
          type="text"
          className={styles.searchInput}
          placeholder="Search books..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSearch()}
        />
        <select
          className={styles.searchField}
          value={searchField}
          onChange={(e) => setSearchField(e.target.value as "title" | "author")}
        >
          <option value="title">Title</option>
          <option value="author">Author</option>
        </select>
        <button className={styles.searchButton} onClick={handleSearch}>
          Search
        </button>
        {isSearching && (
          <button className={styles.clearButton} onClick={handleClearSearch}>
            Clear
          </button>
        )}
      </div>

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
