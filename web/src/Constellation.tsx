import { useEffect, useMemo, useRef, useState } from "react";
import ForceGraph2D from "react-force-graph-2d";

// node.color (contracts.md §4.2: color ∈ {green, red, gray, orange}) → hex.
const COLOR_HEX: Record<string, string> = {
  green: "#22c55e",
  red: "#ef4444",
  gray: "#9ca3af",
  orange: "#f59e0b",
};
const LINK_HEX: Record<string, string> = {
  supported: "#22c55e",
  contradicted: "#ef4444",
  ungrounded: "#6b7280",
};

type Props = {
  verdict: any;
  selectedId: string | null;
  onSelect: (node: any) => void;
};

export default function Constellation({ verdict, selectedId, onSelect }: Props) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const [dims, setDims] = useState({ w: 800, h: 560 });

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const measure = () => setDims({ w: el.clientWidth, h: el.clientHeight });
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const data = useMemo(
    () => ({
      nodes: (verdict?.graph?.nodes ?? []).map((n: any) => ({ ...n })),
      links: (verdict?.graph?.edges ?? []).map((e: any) => ({
        source: e.src,
        target: e.dst,
        rel: e.rel,
        status: e.status,
      })),
    }),
    [verdict],
  );

  return (
    <div ref={wrapRef} className="constellation">
      <ForceGraph2D
        width={dims.w}
        height={dims.h}
        graphData={data}
        backgroundColor="#0b1020"
        cooldownTicks={120}
        nodeRelSize={6}
        linkColor={(l: any) => LINK_HEX[l.status] || "#4b5563"}
        linkWidth={(l: any) => (l.status === "contradicted" ? 3 : 1.3)}
        linkLineDash={(l: any) => (l.status === "ungrounded" ? [4, 3] : null)}
        linkDirectionalArrowLength={4}
        linkDirectionalArrowRelPos={1}
        onNodeClick={(n: any) => onSelect(n)}
        nodeCanvasObject={(node: any, ctx: any, scale: number) => {
          const isClaim = String(node.id).startsWith("claim:");
          const r = isClaim ? 5 : 6.5;
          const hex = COLOR_HEX[node.color] || "#9ca3af";
          ctx.beginPath();
          if (isClaim) {
            // draw claims as diamonds to distinguish them from entities
            ctx.moveTo(node.x, node.y - r);
            ctx.lineTo(node.x + r, node.y);
            ctx.lineTo(node.x, node.y + r);
            ctx.lineTo(node.x - r, node.y);
            ctx.closePath();
          } else {
            ctx.arc(node.x, node.y, r, 0, 2 * Math.PI);
          }
          ctx.fillStyle = hex;
          ctx.fill();
          if (node.id === selectedId) {
            ctx.lineWidth = 2.5 / scale;
            ctx.strokeStyle = "#ffffff";
            ctx.stroke();
          }
          const label = node.label ?? node.id;
          const fs = Math.max(3, 11 / scale);
          ctx.font = `${fs}px system-ui, -apple-system, sans-serif`;
          ctx.fillStyle = "#cbd5e1";
          ctx.textAlign = "center";
          ctx.textBaseline = "top";
          const short = label.length > 42 ? label.slice(0, 40) + "…" : label;
          ctx.fillText(short, node.x, node.y + r + 2);
        }}
        nodePointerAreaPaint={(node: any, color: string, ctx: any) => {
          ctx.fillStyle = color;
          ctx.beginPath();
          ctx.arc(node.x, node.y, 9, 0, 2 * Math.PI);
          ctx.fill();
        }}
      />
    </div>
  );
}
