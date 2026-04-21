import { useEffect, useRef, useState } from "react";
import { getSimilarityGraph } from "../api";
import { GraphEdge, GraphNode } from "../types";
import styles from "./SimilarityGraph.module.css";

const NODE_R = 10;
const MAX_LABEL = 22;

interface Props {
  focusBookId?: string | null;
  onClearFocus?: () => void;
}

function truncate(s: string, max: number): string {
  return s.length > max ? s.slice(0, max - 1) + "…" : s;
}

function circlePositions(
  nodes: GraphNode[],
  cx: number,
  cy: number,
  radius: number
): Map<string, { x: number; y: number }> {
  const map = new Map<string, { x: number; y: number }>();
  nodes.forEach((n, i) => {
    const angle = (2 * Math.PI * i) / nodes.length - Math.PI / 2;
    map.set(n.id, { x: cx + radius * Math.cos(angle), y: cy + radius * Math.sin(angle) });
  });
  return map;
}

// Layout for focus mode: centre node in middle, neighbours around it
function focusPositions(
  centre: GraphNode,
  neighbours: GraphNode[],
  cx: number,
  cy: number,
  radius: number
): Map<string, { x: number; y: number }> {
  const map = new Map<string, { x: number; y: number }>();
  map.set(centre.id, { x: cx, y: cy });
  neighbours.forEach((n, i) => {
    const angle = (2 * Math.PI * i) / neighbours.length - Math.PI / 2;
    map.set(n.id, { x: cx + radius * Math.cos(angle), y: cy + radius * Math.sin(angle) });
  });
  return map;
}

export function SimilarityGraph({ focusBookId, onClearFocus }: Props) {
  const [allNodes, setAllNodes] = useState<GraphNode[]>([]);
  const [allEdges, setAllEdges] = useState<GraphEdge[]>([]);
  const [threshold, setThreshold] = useState(0.1);
  const [pending, setPending] = useState(0.1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeFocusId, setActiveFocusId] = useState<string | null>(focusBookId ?? null);
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState(600);

  // Sync when the prop changes (e.g. clicking Graph on a different book card)
  useEffect(() => {
    setActiveFocusId(focusBookId ?? null);
  }, [focusBookId]);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const observer = new ResizeObserver((entries) => {
      setSize(Math.max(300, Math.min(entries[0].contentRect.width, 900)));
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    setLoading(true);
    setError(null);
    getSimilarityGraph(threshold)
      .then((data) => { setAllNodes(data.nodes); setAllEdges(data.edges); })
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load graph"))
      .finally(() => setLoading(false));
  }, [threshold]);

  const cx = size / 2;
  const cy = size / 2;

  // Derive the visible subgraph
  const isFocused = !!activeFocusId;
  const centreNode = isFocused ? allNodes.find((n) => n.id === activeFocusId) ?? null : null;
  const focusEdges = isFocused
    ? allEdges.filter((e) => e.source === activeFocusId || e.target === activeFocusId)
    : allEdges;
  const neighbourIds = isFocused
    ? new Set(focusEdges.flatMap((e) => [e.source, e.target]).filter((id) => id !== activeFocusId))
    : null;
  const visibleNodes = isFocused
    ? allNodes.filter((n) => n.id === activeFocusId || (neighbourIds?.has(n.id) ?? false))
    : allNodes;
  const visibleEdges = focusEdges;

  // Positions
  const radius = isFocused
    ? Math.min(cx - 80, 220)
    : Math.min(cx - 60, (2 * Math.PI * NODE_R * visibleNodes.length) / (2 * Math.PI * 1.4));

  const posById = isFocused && centreNode
    ? focusPositions(centreNode, visibleNodes.filter((n) => n.id !== activeFocusId), cx, cy, radius)
    : circlePositions(visibleNodes, cx, cy, radius);

  // Hover state
  const hoveredEdges = hoveredId
    ? visibleEdges.filter((e) => e.source === hoveredId || e.target === hoveredId)
    : visibleEdges;
  const connectedIds = hoveredId
    ? new Set(hoveredEdges.flatMap((e) => [e.source, e.target]))
    : null;

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div className={styles.titleRow}>
          <h1 className={styles.title}>
            {isFocused && centreNode ? `Neighbours of "${centreNode.title}"` : "Similarity Graph"}
          </h1>
          {isFocused && (
            <button className={styles.clearFocus} onClick={() => { setActiveFocusId(null); onClearFocus?.(); }}>
              ← Full graph
            </button>
          )}
        </div>
        <p className={styles.subtitle}>
          {isFocused
            ? "Books connected to the selected title by embedding similarity. Hover an edge to see the score."
            : "Each node is a book. Lines connect books with similar embeddings — the thicker the line, the more similar the content. Click a book card to focus on its neighbours, or hover a node here to highlight connections."}
        </p>
      </div>

      <div className={styles.controls}>
        <label className={styles.sliderLabel}>
          Min similarity: <strong>{pending.toFixed(2)}</strong>
        </label>
        <input
          type="range" min="0" max="1" step="0.05" value={pending}
          className={styles.slider}
          onChange={(e) => setPending(parseFloat(e.target.value))}
          onMouseUp={() => setThreshold(pending)}
          onTouchEnd={() => setThreshold(pending)}
        />
        <span className={styles.stats}>
          {visibleNodes.length} books · {visibleEdges.length} connections
        </span>
        <div className={styles.legend}>
          <span className={styles.legendItem}>
            <svg width="28" height="8">
              <line x1="0" y1="4" x2="28" y2="4" stroke="var(--color-copper)" strokeWidth="3" />
            </svg>
            Strong (&ge;70%)
          </span>
          <span className={styles.legendItem}>
            <svg width="28" height="8">
              <line x1="0" y1="4" x2="28" y2="4" stroke="var(--color-copper)" strokeWidth="2" strokeDasharray="6 4" />
            </svg>
            Moderate (40–70%)
          </span>
          <span className={styles.legendItem}>
            <svg width="28" height="8">
              <line x1="0" y1="4" x2="28" y2="4" stroke="var(--color-copper)" strokeWidth="1" strokeDasharray="2 5" />
            </svg>
            Weak (&lt;40%)
          </span>
        </div>
      </div>

      <div className={styles.graphArea} ref={containerRef}>
        {loading && <div className={styles.status}>Loading…</div>}
        {!loading && error && <div className={styles.statusError}>{error}</div>}
        {!loading && !error && visibleNodes.length === 0 && (
          <div className={styles.status}>
            {isFocused ? "No connections found for this book at the current threshold." : "No books with embeddings yet."}
          </div>
        )}
        {!loading && !error && visibleNodes.length > 0 && (
          <svg
            viewBox={`0 0 ${size} ${size}`}
            width={size}
            height={size}
            aria-label="Book similarity graph"
          >
            {hoveredEdges.map((e) => {
              const a = posById.get(e.source);
              const b = posById.get(e.target);
              if (!a || !b) return null;
              const mx = (a.x + b.x) / 2;
              const my = (a.y + b.y) / 2;
              const strokeDasharray =
                e.weight >= 0.7 ? undefined : e.weight >= 0.4 ? "6 4" : "2 5";
              return (
                <g key={`${e.source}-${e.target}`}>
                  <line
                    x1={a.x} y1={a.y} x2={b.x} y2={b.y}
                    stroke="var(--color-copper)"
                    strokeWidth={Math.max(e.weight * 4, 1)}
                    strokeOpacity={hoveredId ? 0.5 + e.weight * 0.4 : 0.2 + e.weight * 0.4}
                    strokeDasharray={strokeDasharray}
                  />
                  {(hoveredId || isFocused) && (
                    <text x={mx} y={my - 5} textAnchor="middle" className={styles.edgeLabel}>
                      {Math.round(e.weight * 100)}%
                    </text>
                  )}
                </g>
              );
            })}

            {visibleNodes.map((n) => {
              const pos = posById.get(n.id);
              if (!pos) return null;
              const isCentre = n.id === activeFocusId;
              const isHovered = n.id === hoveredId;
              const isConnected = connectedIds ? connectedIds.has(n.id) : false;
              const dimmed = hoveredId !== null && !isHovered && !isConnected;
              const showLabel = isCentre || isHovered || isConnected || isFocused || visibleNodes.length <= 20;
              const r = isCentre ? NODE_R * 1.8 : isHovered ? NODE_R * 1.4 : NODE_R;
              return (
                <g
                  key={n.id}
                  style={{ cursor: "pointer" }}
                  onMouseEnter={() => setHoveredId(n.id)}
                  onMouseLeave={() => setHoveredId(null)}
                  onClick={() => { setActiveFocusId(n.id); setHoveredId(null); }}
                >
                  <circle
                    cx={pos.x} cy={pos.y} r={r}
                    fill="var(--color-copper)"
                    fillOpacity={dimmed ? 0.2 : isCentre ? 1 : isHovered ? 0.95 : 0.75}
                    stroke={isCentre ? "var(--color-text-primary)" : "var(--bg-primary)"}
                    strokeWidth={isCentre ? 3 : 2}
                  />
                  {showLabel && (
                    <>
                      <text
                        x={pos.x} y={pos.y + r + 13}
                        textAnchor="middle"
                        className={isCentre || isHovered ? styles.nodeLabelActive : styles.nodeLabel}
                      >
                        {truncate(n.title, MAX_LABEL)}
                      </text>
                      <text
                        x={pos.x} y={pos.y + r + 25}
                        textAnchor="middle"
                        className={styles.nodeAuthor}
                      >
                        {truncate(n.author, MAX_LABEL)}
                      </text>
                    </>
                  )}
                </g>
              );
            })}
          </svg>
        )}
      </div>
    </div>
  );
}
