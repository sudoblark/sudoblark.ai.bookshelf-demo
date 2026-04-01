import styles from "./BookshelfPage.module.css";

interface Props {
  onNavigateToNewBook: () => void;
}

export function BookshelfPage({ onNavigateToNewBook }: Props) {
  return (
    <div className={styles.page}>
      <div className={styles.container}>
        <div className={styles.icon}>📚</div>
        <h1 className={styles.title}>Your bookshelf is empty</h1>
        <p className={styles.subtitle}>
          Start by uploading your first book cover image to get metadata
          extracted automatically.
        </p>
        <button
          className={styles.ctaButton}
          onClick={onNavigateToNewBook}
        >
          Add your first book
        </button>
      </div>
    </div>
  );
}
