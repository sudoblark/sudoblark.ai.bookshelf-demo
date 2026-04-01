import styles from "./OokChatPage.module.css";

export function OokChatPage() {
  return (
    <div className={styles.page}>
      <div className={styles.container}>
        <div className={styles.icon}>🦍</div>
        <h1 className={styles.title}>Ook Chat</h1>
        <p className={styles.subtitle}>
          AI-powered book discovery assistant
        </p>
        <p className={styles.status}>Coming soon…</p>
      </div>
    </div>
  );
}
