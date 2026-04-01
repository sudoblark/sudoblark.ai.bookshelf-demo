import { useRef, useState } from "react";
import { getPresignedUrl, uploadToS3 } from "../api";
import styles from "./UploadPage.module.css";

interface Props {
  onUploadComplete: (sessionId: string, bucket: string, key: string, filename: string) => void;
}

export function UploadPage({ onUploadComplete }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [status, setStatus] = useState<"idle" | "uploading" | "error">("idle");
  const [error, setError] = useState<string | null>(null);

  async function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;

    setStatus("uploading");
    setError(null);

    try {
      const presigned = await getPresignedUrl(file.name);
      await uploadToS3(presigned.url, file);
      onUploadComplete(presigned.session_id, presigned.bucket, presigned.key, file.name);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
      setStatus("error");
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  const uploading = status === "uploading";

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <h1 className={styles.title}>New book</h1>
        <p className={styles.subtitle}>
          Upload a cover image and the AI will extract the book's metadata for you.
        </p>
      </header>

      <label className={`${styles.dropzone} ${uploading ? styles.busy : ""}`}>
        <input
          ref={inputRef}
          type="file"
          accept="image/*"
          className={styles.fileInput}
          onChange={handleChange}
          disabled={uploading}
        />
        {uploading ? (
          <>
            <span className={styles.icon}>⏳</span>
            <span className={styles.label}>Uploading…</span>
          </>
        ) : (
          <>
            <span className={styles.icon}>⬆️</span>
            <span className={styles.label}>Click to select a cover image</span>
            <span className={styles.hint}>JPEG · PNG · WEBP</span>
          </>
        )}
      </label>

      {error && <p className={styles.error}>{error}</p>}
    </div>
  );
}
