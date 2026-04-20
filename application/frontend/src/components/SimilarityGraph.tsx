import { useEffect, useState } from "react";
import { getSimilarityGraph } from "../api";
import { GraphEdge, GraphNode } from "../types";
import styles from "./SimilarityGraph.module.css";

const SVG_SIZE = 500;
const CENTER = SVG_SIZE / 2;
const RADIUS = 180;
const NODE_R = 20;
const MAX_LABEL = 18;

function truncate(s: string, max: number): string {
  return s.length > max ? s.slice(0, max - 1) + "…" : s;
}

function nodePositions(nodes: GraphNode[]): { x: number; y: number }[] {
  if (nodes.length === 0) return [];
  return nodes.map((_, i) => {
    const angle = (2 * Math.PI * i) / nodes.length - Math.PI / 2;
    return {
      x: CENTER + RADIUS * Math.cos(angle),
      y: CENTER + RADIUS * Math.sin(angle),
    };
  });
}

export function SimilarityGraph() {
  const [nodes, setNodes] = useState<GraphNode[]>([]);
  const [edges, setEdges] = useState<GraphEdge[]>([]);
  const [threshold, setThreshold] = useState(0.5);
  const [pending, setPending] = useState(0.5);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    getSimilarityGraph(threshold)
      .then((data) => {
        setNodes(data.nodes);
        setEdges(data.edges);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load graph"))
      .finally(() => setLoading(false));
  }, [threshold]);

  const positions = nodePositions(nodes);
  const posById = Object.fromEntries(nodes.map((n, i) => [n.id, positions[i]]));

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <h1 className={styles.title}>Similarity Graph</h1>
        <p className={styles.subtitle}>
          {nodes.length} books · {edges.length} connections
        </p>
      </div>

      <div className={styles.controls}>
        <label className={styles.sliderLabel}>
          Similarity threshold: <strong>{pending.toFixed(2)}</strong>
        </label>
        <input
          type="range"
          min="0"
          max="1"
          step="0.05"
          value={pending}
          className={styles.slider}
          onChange={(e) => setPending(parseFloat(e.target.value))}
          onMouseUp={() => setThreshold(pending)}
          onTouchEnd={() => setThreshold(pending)}
        />
      </div>

      <div className={styles.graphArea}>
        {loading && <div className={styles.status}>Loading…</div>}
        {!loading && error && <div className={styles.statusError}>{error}</div>}
        {!loading && !error && nodes.length === 0 && (
          <div className={styles.status}>No books with embeddings yet.</div>
        )}
        {!loading && !error && nodes.length > 0 && (
          <svg
            viewBox={`0 0 ${SVG_SIZE} ${SVG_SIZE}`}
            className={styles.svg}
            aria-label="Book similarity graph"
          >
            {edges.map((e) => {
              const a = posById[e.source];
              const b = posById[e.target];
              if (!a || !b) return null;
              return (
                <line
                  key={`${e.source}-${e.target}`}
                  x1={a.x}
                  y1={a.y}
                  x2={b.x}
                  y2={b.y}
                  stroke="var(--color-copper)"
                  strokeWidth={e.weight * 3}
                  strokeOpacity={e.weight * 0.8}
                />
              );
            })}

            {nodes.map((n, i) => {
              const pos = positions[i];
              return (
                <g key={n.id}>
                  <circle
                    cx={pos.x}
                    cy={pos.y}
                    r={NODE_R}
                    fill="var(--color-copper)"
                    fillOpacity={0.85}
                    stroke="var(--bg-primary)"
                    strokeWidth={2}
                  />
                  <text
                    x={pos.x}
                    y={pos.y + NODE_R + 14}
                    textAnchor="middle"
                    className={styles.nodeLabel}
                  >
                    {truncate(n.title, MAX_LABEL)}
                  </text>
                  <text
                    x={pos.x}
                    y={pos.y + NODE_R + 26}
                    textAnchor="middle"
                    className={styles.nodeAuthor}
                  >
                    {truncate(n.author, MAX_LABEL)}
                  </text>
                </g>
              );
            })}
          </svg>
        )}
      </div>
    </div>
  );
}
