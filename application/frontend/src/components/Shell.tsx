import type { ReactNode } from "react";
import styles from "./Shell.module.css";

type NavItem = "new-book";

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
              className={`${styles.navItem} ${active === "new-book" ? styles.active : ""}`}
              onClick={() => onNav("new-book")}
            >
              <span className={styles.navIcon}>＋</span>
              New book
            </button>
          </li>
        </ul>
      </nav>

      <main className={styles.content}>{children}</main>
    </div>
  );
}
