import { useEffect, useState } from "react";
import { getOpsFiles } from "../api";
import { UploadFile } from "../types";
import styles from "./OpsPage.module.css";

interface Props {
  onNavigateToNewBook: () => void;
}

type StatusFilter = "ALL" | "ACTIVE" | "FAILED";

export function OpsPage({ onNavigateToNewBook }: Props) {
  const [files, setFiles] = useState<UploadFile[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("ALL");

  useEffect(() => {
    async function fetchFiles() {
      setLoading(true);
      try {
        const data = await getOpsFiles();
        setFiles(data.files);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load ops files");
      } finally {
        setLoading(false);
      }
    }
    fetchFiles();
  }, []);

  function formatDate(dateStr: string): string {
    try {
      return new Date(dateStr).toLocaleString();
    } catch {
      return dateStr;
    }
  }

  function getStageColor(stage: string): string {
    if (stage === "failed") return styles.statusFailed;
    if (stage === "queued") return styles.statusQueued;
    return styles.statusSuccess;
  }

  function getFilteredFiles(): UploadFile[] {
    let filtered: UploadFile[];
    if (statusFilter === "FAILED") {
      filtered = files.filter((f) => f.stage === "failed");
    } else if (statusFilter === "ACTIVE") {
      filtered = files.filter((f) => f.stage !== "failed");
    } else {
      filtered = files;
    }
    return filtered.sort(
      (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
    );
  }

  // Empty state
  if (!loading && files.length === 0) {
    return (
      <div className={styles.page}>
        <div className={styles.container}>
          <div className={styles.icon}>📊</div>
          <h1 className={styles.title}>No uploads yet</h1>
          <p className={styles.subtitle}>
            Uploads will appear here as you process book covers.
          </p>
          <button className={styles.ctaButton} onClick={onNavigateToNewBook}>
            Upload your first book
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.page}>
      <h1 className={styles.title}>Operations Dashboard</h1>

      {error && <div className={styles.error}>{error}</div>}

      {loading && <div className={styles.loading}>Loading files...</div>}

      {!loading && files.length > 0 && (
        <>
          <div className={styles.filterBar}>
            <span className={styles.filterLabel}>Filter by status:</span>
            <div className={styles.filterButtons}>
              {(["ALL", "ACTIVE", "FAILED"] as StatusFilter[]).map((filter) => (
                <button
                  key={filter}
                  className={`${styles.filterButton} ${statusFilter === filter ? styles.filterActive : ""}`}
                  onClick={() => setStatusFilter(filter)}
                >
                  {filter}
                  <span className={styles.filterCount}>
                    {filter === "ALL"
                      ? files.length
                      : filter === "FAILED"
                      ? files.filter((f) => f.stage === "failed").length
                      : files.filter((f) => f.stage !== "failed").length}
                  </span>
                </button>
              ))}
            </div>
          </div>
          <div className={styles.tableContainer}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th className={styles.colExpand}></th>
                <th className={styles.colId}>Upload ID</th>
                <th className={styles.colStatus}>Stage</th>
                <th className={styles.colCreated}>Created</th>
                <th className={styles.colUpdated}>Updated</th>
              </tr>
            </thead>
            <tbody>
              {getFilteredFiles().map((file) => [
                <tr
                  key={`row-${file.upload_id}`}
                  className={styles.row}
                  onClick={() =>
                    setExpandedId(expandedId === file.upload_id ? null : file.upload_id)
                  }
                >
                  <td className={styles.colExpand}>
                    <span className={expandedId === file.upload_id ? styles.expandOpen : ""}>
                      ▶
                    </span>
                  </td>
                  <td className={styles.colId}>
                    <code>{file.upload_id.slice(0, 8)}</code>
                  </td>
                  <td className={styles.colStatus}>
                    <span className={`${styles.badge} ${getStageColor(file.stage)}`}>
                      {file.stage}
                    </span>
                  </td>
                  <td className={styles.colCreated}>{formatDate(file.created_at)}</td>
                  <td className={styles.colUpdated}>{formatDate(file.updated_at)}</td>
                </tr>,
                expandedId === file.upload_id && (
                  <tr key={`detail-${file.upload_id}`}>
                    <td colSpan={5} className={styles.detailCell}>
                      <div className={styles.detail}>
                        <h3>Pipeline Stages</h3>
                        <div className={styles.stageDetails}>
                          {Object.entries(file.stages).map(([stageName, stageData]) => (
                            <div
                              key={stageName}
                              className={`${styles.stageDetailItem} ${
                                stageData.error ? styles.detailFailed : styles.detailSuccess
                              }`}
                            >
                              <div className={styles.detailName}>{stageName}</div>
                              <div className={styles.detailStatus}>
                                {stageData.error ? "failed" : "complete"}
                              </div>
                              {stageData.startedAt && stageData.endedAt && (
                                <div className={styles.detailTime}>
                                  {(
                                    (new Date(stageData.endedAt).getTime() -
                                      new Date(stageData.startedAt).getTime()) /
                                    1000
                                  ).toFixed(1)}s
                                </div>
                              )}
                              {stageData.error && (
                                <div className={styles.detailError}>{stageData.error}</div>
                              )}
                            </div>
                          ))}
                          {Object.keys(file.stages).length === 0 && (
                            <div className={styles.detailEmpty}>No stage data recorded yet.</div>
                          )}
                        </div>
                      </div>
                    </td>
                  </tr>
                ),
              ])}
            </tbody>
          </table>
        </div>
        </>
      )}
    </div>
  );
}
