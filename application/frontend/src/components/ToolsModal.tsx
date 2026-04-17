import styles from "./ToolsModal.module.css";

export interface ToolExecution {
  name: string;
  inputs: string;
  result_summary: string;
  execution_time_ms: number;
}

interface ToolsModalProps {
  isOpen: boolean;
  onClose: () => void;
  executions: ToolExecution[];
}

export function ToolsModal({ isOpen, onClose, executions }: ToolsModalProps) {
  if (!isOpen) return null;

  return (
    <div className={styles.modalOverlay} onClick={onClose}>
      <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
        <div className={styles.modalHeader}>
          <h3 className={styles.modalTitle}>🔧 Operations ({executions.length})</h3>
          <button
            className={styles.modalClose}
            onClick={onClose}
            aria-label="Close"
          >
            ✕
          </button>
        </div>
        <div className={styles.modalContent}>
          {executions.map((exec, i) => (
            <div key={i} className={styles.toolItem}>
              <div className={styles.toolName}>{exec.name}</div>
              <div className={styles.toolInputs}>{exec.inputs}</div>
              <div className={styles.toolResult}>{exec.result_summary}</div>
              <div className={styles.toolTime}>{exec.execution_time_ms.toFixed(1)}ms</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
