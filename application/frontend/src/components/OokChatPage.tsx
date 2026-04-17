import { useEffect, useRef, useState } from "react";
import { streamOokChat } from "../api";
import { ToolsModal, type ToolExecution } from "./ToolsModal";
import styles from "./OokChatPage.module.css";

interface Message {
  role: "user" | "assistant";
  content: string;
  tools?: string[];
  executions?: ToolExecution[];
}

interface StreamEvent {
  type: string;
  delta?: string;
  message?: string;
}

export function OokChatPage() {
  const [sessionId] = useState(() => crypto.randomUUID());
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedToolsIdx, setExpandedToolsIdx] = useState<number | null>(null);
  const [modalToolExecutions, setModalToolExecutions] = useState<ToolExecution[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Auto-resize textarea based on content
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 200) + "px";
    }
  }, [input]);

  async function handleSend() {
    if (!input.trim() || loading) return;

    const userMessage = input.trim();
    setInput("");
    setLoading(true);
    setError(null);

    // Add user message immediately
    setMessages((prev) => [...prev, { role: "user", content: userMessage }]);

    try {
      let assistantMessage = "";

      let currentTools: string[] = [];
      let currentExecutions: ToolExecution[] = [];

      for await (const event of streamOokChat(sessionId, userMessage)) {
        if (event.type === "text_delta") {
          assistantMessage += event.delta || "";
          // Update last assistant message or add new one
          setMessages((prev) => {
            const last = prev[prev.length - 1];
            if (last && last.role === "assistant") {
              return [
                ...prev.slice(0, -1),
                { role: "assistant", content: assistantMessage, tools: currentTools, executions: currentExecutions },
              ];
            }
            return [...prev, { role: "assistant", content: assistantMessage, tools: currentTools, executions: currentExecutions }];
          });
        } else if (event.type === "tools_used") {
          currentTools = event.tools || [];
          // Update message with new tools list
          setMessages((prev) => {
            const last = prev[prev.length - 1];
            if (last && last.role === "assistant") {
              return [
                ...prev.slice(0, -1),
                { role: "assistant", content: last.content, tools: currentTools, executions: last.executions || [] },
              ];
            }
            return prev;
          });
        } else if (event.type === "tool_executions") {
          currentExecutions = event.executions || [];
          // Update message with execution details
          setMessages((prev) => {
            const last = prev[prev.length - 1];
            if (last && last.role === "assistant") {
              return [
                ...prev.slice(0, -1),
                { role: "assistant", content: last.content, tools: last.tools || [], executions: currentExecutions },
              ];
            }
            return prev;
          });
        } else if (event.type === "error") {
          setError(event.message || "Chat error — please try again");
        }
      }
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to send message"
      );
    } finally {
      setLoading(false);
      // Reset textarea height and re-focus for continuous typing
      if (textareaRef.current) {
        textareaRef.current.style.height = "auto";
        textareaRef.current.focus();
      }
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  return (
    <div className={styles.container}>
      {/* Header */}
      <div className={styles.header}>
        <div className={styles.headerIcon}>🦧</div>
        <div className={styles.headerContent}>
          <h1 className={styles.headerTitle}>Ook Chat</h1>
          <p className={styles.headerSubtitle}>Ask about your book collection</p>
        </div>
      </div>

      {/* Messages Area */}
      <div className={styles.messages}>
        {/* Welcome Screen */}
        {messages.length === 0 && (
          <div className={styles.welcome}>
            <div className={styles.welcomeIcon}>🦧</div>
            <h2 className={styles.welcomeTitle}>
              Hi! I'm Ook, your bookshelf assistant.
            </h2>
            <p className={styles.welcomeDescription}>
              Ask me anything about your book collection and I'll search through your books to help.
            </p>
            <div className={styles.welcomeExamples}>
              <p className={styles.welcomeExamplesTitle}>Try asking:</p>
              <ul className={styles.welcomeExamplesList}>
                <li className={styles.welcomeExampleItem}>
                  <span className={styles.welcomeExampleBullet}>•</span>
                  <span>"What books do I have?"</span>
                </li>
                <li className={styles.welcomeExampleItem}>
                  <span className={styles.welcomeExampleBullet}>•</span>
                  <span>"Who's my most common author?"</span>
                </li>
                <li className={styles.welcomeExampleItem}>
                  <span className={styles.welcomeExampleBullet}>•</span>
                  <span>"Find books by Sanderson"</span>
                </li>
              </ul>
            </div>
          </div>
        )}

        {/* Chat Messages */}
        {messages.map((msg, idx) => (
          <div key={idx}>
            <div
              className={`${styles.messageRow} ${styles[msg.role]}`}
            >
              {msg.role === "assistant" && <div className={styles.avatar}>🦧</div>}
              <div className={`${styles.messageBubble} ${styles[msg.role]}`}>
                {msg.content}
              </div>
            </div>
            {/* Tools button for assistant messages */}
            {msg.role === "assistant" && msg.executions && msg.executions.length > 0 && (
              <button
                className={styles.toolsButton}
                onClick={() => {
                  setModalToolExecutions(msg.executions || []);
                  setExpandedToolsIdx(idx);
                }}
              >
                📚 {msg.executions.length} tool{msg.executions.length !== 1 ? "s" : ""} used
              </button>
            )}
          </div>
        ))}

        {/* Typing Indicator */}
        {loading && (
          <div className={`${styles.messageRow} ${styles.assistant}`}>
            <div className={styles.avatar}>🦧</div>
            <div className={styles.typing}>
              <div className={styles.typingDots}>
                <div className={styles.typingDot}></div>
                <div className={styles.typingDot}></div>
                <div className={styles.typingDot}></div>
              </div>
              <span className={styles.typingText}>The librarian is thinking...</span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className={styles.inputArea}>
        <div className={styles.inputRow}>
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={loading ? "The librarian is thinking..." : "Ask about your books... (Shift+Enter for new line)"}
            disabled={loading}
            className={styles.textarea}
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || loading}
            className={styles.sendButton}
          >
            Send
          </button>
        </div>

        {/* Error Display */}
        {error && (
          <div className={styles.error}>
            <p className={styles.errorTitle}>Error:</p>
            <p className={styles.errorMessage}>{error}</p>
          </div>
        )}
      </div>

      {/* Operations modal */}
      <ToolsModal
        isOpen={expandedToolsIdx !== null}
        onClose={() => setExpandedToolsIdx(null)}
        executions={modalToolExecutions}
      />
    </div>
  );
}
