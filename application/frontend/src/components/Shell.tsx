import type { ReactNode } from "react";
import styles from "./Shell.module.css";

type NavItem = "bookshelf" | "new-book" | "ook-chat";

interface Props {
  active: NavItem;
  onNav: (item: NavItem) => void;
  children: ReactNode;
}

export function Shell({ active, onNav, children }: Props) {
  return (
    <div className={styles.shell}>
      <nav className={styles.sidebar}>
        <div className={styles.logo}>
          <span className={styles.logoIcon}>📚</span>
          <span className={styles.logoText}>Bookshelf</span>
        </div>

        <ul className={styles.nav}>
          <li>
            <button
              className={`${styles.navItem} ${active === "bookshelf" ? styles.active : ""}`}
              onClick={() => onNav("bookshelf")}
            >
              <span className={styles.navIcon}>📚</span>
              Bookshelf
            </button>
          </li>
          <li>
            <button
              className={`${styles.navItem} ${active === "new-book" ? styles.active : ""}`}
              onClick={() => onNav("new-book")}
            >
              <span className={styles.navIcon}>＋</span>
              New book
            </button>
          </li>
          <li>
            <button
              className={`${styles.navItem} ${active === "ook-chat" ? styles.active : ""}`}
              onClick={() => onNav("ook-chat")}
            >
              <span className={styles.navIcon}>💬</span>
              Ook chat
            </button>
          </li>
        </ul>
      </nav>

      <main className={styles.content}>{children}</main>
    </div>
  );
}
