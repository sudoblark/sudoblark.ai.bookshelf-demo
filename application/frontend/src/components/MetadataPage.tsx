import { useEffect, useRef, useState } from "react";
import { acceptMetadata, streamInitialMetadata, streamRefinedMetadata } from "../api";
import { BookMetadata } from "../types";
import styles from "./MetadataPage.module.css";

interface Message {
  role: "user" | "assistant";
  content: string;
}

interface Props {
  sessionId: string;
  bucket: string;
  s3Key: string;
  filename: string;
  onReset: () => void;
}

const EMPTY_METADATA: BookMetadata = {
  title: "",
  author: "",
  isbn: "",
  publisher: "",
  published_year: null,
  description: "",
  confidence: null,
};

export function MetadataPage({ sessionId, bucket, s3Key, filename, onReset }: Props) {
  const [metadata, setMetadata] = useState<BookMetadata>(EMPTY_METADATA);
  const [messages, setMessages] = useState<Message[]>([]);
  const [extracting, setExtracting] = useState(true);
  const [refining, setRefining] = useState(false);
  const [saved, setSaved] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [userInput, setUserInput] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Run initial extraction on mount
  useEffect(() => {
    let cancelled = false;

    async function extract() {
      try {
        for await (const event of streamInitialMetadata(bucket, s3Key, filename)) {
          if (cancelled) break;
          if (event.type === "text_delta") {
            setMessages((prev) => {
              const last = prev[prev.length - 1];
              if (last?.role === "assistant") {
                return [...prev.slice(0, -1), { ...last, content: last.content + event.delta }];
              }
              return [...prev, { role: "assistant", content: event.delta }];
            });
          } else if (event.type === "metadata_update") {
            setMetadata((prev) => ({ ...prev, [event.field]: event.value }));
          } else if (event.type === "complete") {
            setExtracting(false);
          } else if (event.type === "error") {
            setError(event.message);
            setExtracting(false);
          }
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Extraction failed");
          setExtracting(false);
        }
      }
    }

    extract();
    return () => { cancelled = true; };
  }, [bucket, s3Key, filename]);

  async function handleSend() {
    const msg = userInput.trim();
    if (!msg || refining || extracting) return;

    setUserInput("");
    setRefining(true);
    setMessages((prev) => [...prev, { role: "user", content: msg }]);

    try {
      for await (const event of streamRefinedMetadata(sessionId, msg, metadata)) {
        if (event.type === "text_delta") {
          setMessages((prev) => {
            const last = prev[prev.length - 1];
            if (last?.role === "assistant") {
              return [...prev.slice(0, -1), { ...last, content: last.content + event.delta }];
            }
            return [...prev, { role: "assistant", content: event.delta }];
          });
        } else if (event.type === "metadata_update") {
          setMetadata((prev) => ({ ...prev, [event.field]: event.value }));
        } else if (event.type === "error") {
          setError(event.message);
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Refinement failed");
    } finally {
      setRefining(false);
    }
  }

  async function handleSave() {
    try {
      const result = await acceptMetadata(metadata, filename);
      setSaved(result.saved_key);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  if (saved) {
    return (
      <div className={styles.savedPage}>
        <p className={styles.savedIcon}>✅</p>
        <h2>Book saved!</h2>
        <p className={styles.savedMeta}>
          {metadata.title || filename}
          {metadata.author ? ` · ${metadata.author}` : ""}
        </p>
        <code className={styles.savedKey}>{saved}</code>
        <button className={styles.newBookBtn} onClick={onReset}>
          Add another book
        </button>
      </div>
    );
  }

  const busy = extracting || refining;

  return (
    <div className={styles.page}>
      {/* ── Book card (top center) ───────────────────────── */}
      <div className={styles.bookCardContainer}>
        <div className={styles.bookCard}>
          <div className={styles.bookSpine} />
          <div className={styles.bookCover}>
            <div className={styles.coverContent}>
              <div className={styles.coverTitle}>{metadata.title || "Untitled"}</div>
              <div className={styles.coverAuthor}>{metadata.author || "Unknown Author"}</div>
            </div>
          </div>
        </div>
      </div>

      {/* ── Metadata fields (top center) ─────────────────── */}
      <div className={styles.fieldsSection}>
        <div className={styles.cardFields}>
          <CardField
            label="Title"
            value={metadata.title}
            onChange={(v) => setMetadata((p) => ({ ...p, title: v }))}
          />
          <CardField
            label="Author"
            value={metadata.author}
            onChange={(v) => setMetadata((p) => ({ ...p, author: v }))}
          />
          <CardField
            label="Year"
            value={metadata.published_year?.toString() ?? ""}
            onChange={(v) => setMetadata((p) => ({ ...p, published_year: v ? parseInt(v, 10) : null }))}
            type="number"
          />
          <ISBNField
            value={metadata.isbn}
            onChange={(v) => setMetadata((p) => ({ ...p, isbn: v }))}
          />
          <CardField
            label="Publisher"
            value={metadata.publisher}
            onChange={(v) => setMetadata((p) => ({ ...p, publisher: v }))}
          />
        </div>

        {metadata.confidence !== null && (
          <div className={styles.confidence}>
            <span className={styles.confidenceLabel}>Confidence</span>
            <span className={styles.confidenceValue}>
              {Math.round((metadata.confidence ?? 0) * 100)}%
            </span>
          </div>
        )}

        <button
          className={styles.saveBtn}
          onClick={handleSave}
          disabled={busy}
        >
          Save book
        </button>
      </div>

      {/* ── Chat section (bottom) ──────────────────────── */}
      <section className={styles.chatSection}>
        <header className={styles.chatHeader}>
          <span className={styles.chatTitle}>Refine</span>
          {extracting && <span className={styles.analysing}>Analysing cover…</span>}
        </header>

        <div className={styles.messages}>
          {messages.length === 0 && extracting && (
            <p className={styles.placeholder}>Extracting metadata from your cover…</p>
          )}
          {messages.map((m, i) => (
            <div key={i} className={`${styles.message} ${styles[m.role]}`}>
              {m.content}
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>

        {error && <p className={styles.chatError}>{error}</p>}

        <div className={styles.inputRow}>
          <input
            className={styles.chatInput}
            type="text"
            placeholder={busy ? "Waiting…" : "Ask to correct or refine…"}
            value={userInput}
            onChange={(e) => setUserInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={busy}
          />
          <button
            className={styles.sendBtn}
            onClick={handleSend}
            disabled={busy || !userInput.trim()}
          >
            Send
          </button>
        </div>
      </section>
    </div>
  );
}

interface CardFieldProps {
  label: string;
  value: string;
  onChange: (v: string) => void;
  type?: string;
}

function CardField({ label, value, onChange, type = "text" }: CardFieldProps) {
  return (
    <div className={styles.cardField}>
      <label className={styles.fieldLabel}>{label}</label>
      <input
        className={styles.fieldInput}
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="—"
      />
    </div>
  );
}

interface ISBNFieldProps {
  value: string;
  onChange: (v: string) => void;
}

function ISBNField({ value, onChange }: ISBNFieldProps) {
  const displayValue = typeof value === "string" ? value.trim() : "";
  const isbnValid = displayValue && displayValue.length > 0 && !displayValue.includes("[");
  const isbnMissing = !displayValue || !isbnValid;

  return (
    <div className={styles.cardField}>
      <label className={styles.fieldLabel}>ISBN</label>
      {isbnMissing ? (
        <div className={styles.isbnMissing}>
          <span className={styles.isbnIcon}>🔍</span>
          <span className={styles.isbnText}>Not visible</span>
        </div>
      ) : (
        <input
          className={styles.fieldInput}
          type="text"
          value={displayValue}
          onChange={(e) => onChange(e.target.value)}
          placeholder="—"
        />
      )}
    </div>
  );
}
