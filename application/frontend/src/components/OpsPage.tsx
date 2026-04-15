import { useEffect, useState } from "react";
import { getOpsFiles } from "../api";
import { UploadFile } from "../types";
import styles from "./OpsPage.module.css";

interface Props {
  onNavigateToNewBook: () => void;
}

type StatusFilter = "ALL" | "IN_PROGRESS" | "SUCCESS" | "FAILED";

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

  function getStatusColor(status: string): string {
    switch (status) {
      case "SUCCESS":
        return styles.statusSuccess;
      case "FAILED":
        return styles.statusFailed;
      case "IN_PROGRESS":
        return styles.statusInProgress;
      case "QUEUED":
        return styles.statusQueued;
      default:
        return "";
    }
  }

  function getFilteredFiles(): UploadFile[] {
    if (statusFilter === "ALL") return files;
    return files.filter((file) => file.current_status === statusFilter);
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
              {(["ALL", "IN_PROGRESS", "SUCCESS", "FAILED"] as StatusFilter[]).map((filter) => (
                <button
                  key={filter}
                  className={`${styles.filterButton} ${statusFilter === filter ? styles.filterActive : ""}`}
                  onClick={() => setStatusFilter(filter)}
                >
                  {filter === "ALL" ? "All" : filter.replace("_", " ")}
                  <span className={styles.filterCount}>
                    {filter === "ALL"
                      ? files.length
                      : files.filter((f) => f.current_status === filter).length}
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
                <th className={styles.colStatus}>Status</th>
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
                    <span className={`${styles.badge} ${getStatusColor(file.current_status)}`}>
                      {file.current_status}
                    </span>
                  </td>
                  <td className={styles.colCreated}>{formatDate(file.created_at)}</td>
                  <td className={styles.colUpdated}>{formatDate(file.updated_at)}</td>
                </tr>,
                expandedId === file.upload_id && (
                  <tr key={`detail-${file.upload_id}`}>
                    <td colSpan={5} className={styles.detailCell}>
                      <div className={styles.detail}>
                        <h3>Pipeline Progress</h3>
                        <div className={styles.progressContainer}>
                          <div className={styles.progressBar}>
                            {["user_upload", "routing", "av_scan", "enrichment"].map((stageName, idx) => {
                              const stageData = file.stage_progress.find(s => s.stage_name === stageName);
                              const isComplete = stageData?.status === "success";
                              const isFailed = stageData?.status === "failed";
                              const isActive = stageData?.status === "in_progress";

                              return (
                                <div key={stageName} className={styles.stageNode}>
                                  <div
                                    className={`${styles.stageCircle} ${
                                      isComplete ? styles.stageSuccess : ""
                                    } ${isActive ? styles.stageActive : ""} ${
                                      isFailed ? styles.stageFailed : ""
                                    }`}
                                  >
                                    {isComplete && "✓"}
                                    {isFailed && "✕"}
                                    {isActive && "⟳"}
                                    {!stageData && "○"}
                                  </div>
                                  <div className={styles.stageLabelSmall}>
                                    {stageName.replace("_", "\n")}
                                  </div>
                                  {stageData?.processing_time && (
                                    <div className={styles.stageTimeSmall}>
                                      {stageData.processing_time}s
                                    </div>
                                  )}
                                </div>
                              );
                            })}
                          </div>
                        </div>
                        <div className={styles.stageDetails}>
                          {file.stage_progress.map((stage, idx) => (
                            <div
                              key={idx}
                              className={`${styles.stageDetailItem} ${
                                stage.status === "success" ? styles.detailSuccess : ""
                              } ${stage.status === "failed" ? styles.detailFailed : ""} ${
                                stage.status === "in_progress" ? styles.detailInProgress : ""
                              }`}
                            >
                              <div className={styles.detailName}>{stage.stage_name}</div>
                              <div className={styles.detailStatus}>{stage.status}</div>
                              {stage.processing_time && (
                                <div className={styles.detailTime}>{stage.processing_time}s</div>
                              )}
                              {stage.error_message && (
                                <div className={styles.detailError}>{stage.error_message}</div>
                              )}
                            </div>
                          ))}
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
