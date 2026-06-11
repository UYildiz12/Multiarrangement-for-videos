"use client";
/* eslint-disable @next/next/no-img-element */

import { useRef, useState, useCallback, useEffect, useMemo, type CSSProperties } from "react";

interface Position {
  x: number;
  y: number;
}

interface Stimulus {
  id: string;
  ordinal: number;
  label: string;
  mediaUrl?: string;
  thumbnail?: string;
  mediaType: "video" | "audio" | "image";
}

interface DraggableItem extends Stimulus {
  position: Position;
  initialPosition: Position;
  isDragging: boolean;
}

export interface TraceSample {
  ordinal: number;
  x: number;
  y: number;
  /** 0 = pickup, 1 = move, 2 = drop */
  phase: 0 | 1 | 2;
}

interface ArenaProps {
  stimuli: Stimulus[];
  onPositionsChange?: (positions: Record<string, Position>) => void;
  onAllInside?: (allInside: boolean) => void;
  onSubmit?: () => void;
  onMediaPlay?: (itemId: string, mediaUrl: string, mediaType: Stimulus["mediaType"]) => void;
  onTraceSample?: (sample: TraceSample) => void;
  playedItems?: Set<string>;
  size?: number;
  trialIndex?: number;
  language?: "en" | "tr";
  submitting?: boolean;
}

const MAX_ITEM_RADIUS = 55;
const MIN_ITEM_RADIUS = 16;
const COMFORTABLE_ITEM_RADIUS = 24;
const ARENA_PADDING = 20;
const CIRCLE_THICKNESS = 3;
const MIN_SEAT_GAP = 22;
const MAX_SEAT_RINGS = 3;
const RING_ARC_GAP = 8;
const MAX_CONTAINER_FACTOR = 1.7;
const TRACE_MIN_INTERVAL_MS = 50;
const TRACE_MIN_DISTANCE_PX = 2;
const MIN_ZOOM = 0.5;
const MAX_ZOOM = 2.5;

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

/** Pan is only meaningful when zoomed in; bound it so the arena stays in view. */
function clampPan(pan: Position, zoom: number, containerSize: number): Position {
  const limit = Math.max(0, (containerSize * (zoom - 1)) / 2);
  return {
    x: clamp(pan.x, -limit, limit),
    y: clamp(pan.y, -limit, limit),
  };
}

export interface SeatLayout {
  radius: number;
  seats: Position[];
  containerSize: number;
}

function ringCapacity(seatRadius: number, itemRadius: number): number {
  return Math.max(1, Math.floor((2 * Math.PI * seatRadius) / (2 * itemRadius + RING_ARC_GAP)));
}

/**
 * Seat tokens on up to three concentric rings outside the arena so large
 * adaptive batches keep usably large tokens instead of shrinking to dust.
 */
export function computeSeatLayout(count: number, arenaSize: number): SeatLayout {
  const maxRadius = arenaSize >= 560
    ? MAX_ITEM_RADIUS
    : clamp(Math.floor(arenaSize * 0.09), MIN_ITEM_RADIUS, MAX_ITEM_RADIUS);
  const arenaRadius = Math.max(0, arenaSize / 2 - ARENA_PADDING);
  const center = arenaSize / 2;

  const layoutFor = (radius: number, maxRings: number): number[] | null => {
    const gap = Math.max(MIN_SEAT_GAP, radius * 0.8);
    const ringCounts: number[] = [];
    let remaining = count;
    for (let ring = 0; ring < maxRings && remaining > 0; ring += 1) {
      const seatRadius = arenaRadius + radius + gap + ring * (2 * radius + gap);
      const capacity = ringCapacity(seatRadius, radius);
      const take = Math.min(capacity, remaining);
      ringCounts.push(take);
      remaining -= take;
    }
    return remaining <= 0 ? ringCounts : null;
  };

  const buildSeats = (radius: number, ringCounts: number[]): SeatLayout => {
    const gap = Math.max(MIN_SEAT_GAP, radius * 0.8);
    const seats: Position[] = [];
    let outermost = arenaRadius + radius + gap;
    ringCounts.forEach((ringCount, ring) => {
      const seatRadius = arenaRadius + radius + gap + ring * (2 * radius + gap);
      outermost = Math.max(outermost, seatRadius);
      const angleOffset = -Math.PI / 2 + (ring * Math.PI) / Math.max(1, ringCounts.length * 2);
      for (let i = 0; i < ringCount; i += 1) {
        const angle = angleOffset + (2 * Math.PI * i) / ringCount;
        seats.push({
          x: center + seatRadius * Math.cos(angle),
          y: center + seatRadius * Math.sin(angle),
        });
      }
    });
    const containerSize = Math.ceil(2 * (outermost + radius));
    return { radius, seats, containerSize };
  };

  if (count <= 0) {
    return { radius: maxRadius, seats: [], containerSize: arenaSize };
  }
  if (count <= 14) {
    const ringCounts = layoutFor(maxRadius, 1) ?? [count];
    return buildSeats(maxRadius, ringCounts);
  }

  // Prefer the largest radius (>= comfortable floor) whose container stays
  // reasonable; relax the floor only if even small tokens cannot be seated.
  for (let radius = maxRadius; radius >= COMFORTABLE_ITEM_RADIUS; radius -= 1) {
    const ringCounts = layoutFor(radius, MAX_SEAT_RINGS);
    if (!ringCounts) continue;
    const layout = buildSeats(radius, ringCounts);
    if (layout.containerSize <= arenaSize * MAX_CONTAINER_FACTOR) {
      return layout;
    }
  }
  for (let radius = COMFORTABLE_ITEM_RADIUS - 1; radius >= MIN_ITEM_RADIUS; radius -= 1) {
    const ringCounts = layoutFor(radius, MAX_SEAT_RINGS);
    if (ringCounts) {
      return buildSeats(radius, ringCounts);
    }
  }
  const fallback = layoutFor(MIN_ITEM_RADIUS, 12) ?? [count];
  return buildSeats(MIN_ITEM_RADIUS, fallback);
}

export function getTokenRadiusForStimulusCount(stimulusCount: number, arenaSize: number): number {
  return computeSeatLayout(stimulusCount, arenaSize).radius;
}

export default function DragArena({
  stimuli,
  onPositionsChange,
  onAllInside,
  onSubmit,
  onMediaPlay,
  onTraceSample,
  playedItems = new Set(),
  size = 600,
  trialIndex = 0,
  language = "en",
  submitting = false,
}: ArenaProps) {
  const arenaRef = useRef<HTMLDivElement>(null);
  const viewportRef = useRef<HTMLDivElement>(null);
  const [items, setItems] = useState<DraggableItem[]>([]);
  const [draggedId, setDraggedId] = useState<string | null>(null);
  const dragOffset = useRef<Position>({ x: 0, y: 0 });
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState<Position>({ x: 0, y: 0 });
  const zoomRef = useRef(1);
  zoomRef.current = zoom;
  const containerSizeRef = useRef(0);

  // Single entry point for zoom changes: clamps zoom and re-clamps pan so the
  // arena recenters as you zoom back out.
  const applyZoom = useCallback((next: number) => {
    const clamped = clamp(next, MIN_ZOOM, MAX_ZOOM);
    zoomRef.current = clamped;
    setZoom(clamped);
    setPan((prev) => clampPan(prev, clamped, containerSizeRef.current));
  }, []);

  const arenaRadius = size / 2 - ARENA_PADDING;
  const center = size / 2;
  const seatLayout = useMemo(
    () => computeSeatLayout(stimuli.length, size),
    [stimuli.length, size]
  );
  const itemRadius = seatLayout.radius;
  const containerSize = Math.max(seatLayout.containerSize, size + itemRadius * 2 + MIN_SEAT_GAP * 2);
  containerSizeRef.current = containerSize;

  // Stable key representing which stimuli are shown (IDs only, not metadata like thumbnails)
  const stimuliKey = useMemo(
    () => stimuli.map((s) => s.id).join(","),
    [stimuli]
  );

  // Initialize/reset positions ONLY when the set of stimulus IDs or trialIndex changes
  useEffect(() => {
    if (stimuli.length === 0) return;

    const seats = computeSeatLayout(stimuli.length, size).seats;
    const newItems: DraggableItem[] = stimuli.map((s, i) => ({
      ...s,
      position: seats[i] ?? { x: size / 2, y: size / 2 },
      initialPosition: seats[i] ?? { x: size / 2, y: size / 2 },
      isDragging: false,
    }));
    setItems(newItems);
    setDraggedId(null);
    setZoom(1);
    setPan({ x: 0, y: 0 });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stimuliKey, trialIndex, size]);

  // Sync metadata changes (thumbnail, mediaUrl, label) to existing items WITHOUT resetting positions
  useEffect(() => {
    if (stimuli.length === 0) return;
    setItems((prev) => {
      if (prev.length !== stimuli.length) return prev;
      let changed = false;
      const next = prev.map((item, i) => {
        const s = stimuli[i];
        if (!s || s.id !== item.id) return item;
        if (
          s.thumbnail === item.thumbnail &&
          s.mediaUrl === item.mediaUrl &&
          s.label === item.label
        )
          return item;
        changed = true;
        return { ...item, thumbnail: s.thumbnail, mediaUrl: s.mediaUrl, label: s.label };
      });
      return changed ? next : prev;
    });
  }, [stimuli]);

  // Check if item center is inside the arena circle
  const isInsideArena = useCallback(
    (pos: Position): boolean => {
      const dx = pos.x - center;
      const dy = pos.y - center;
      const dist = Math.sqrt(dx * dx + dy * dy);
      return dist + itemRadius * 0.6 <= arenaRadius;
    },
    [center, arenaRadius, itemRadius]
  );

  // Update parent when positions change
  useEffect(() => {
    const allInside = items.every((item) => isInsideArena(item.position));
    onAllInside?.(allInside);

    const positions: Record<string, Position> = {};
    items.forEach((item) => {
      positions[item.ordinal.toString()] = item.position;
    });
    onPositionsChange?.(positions);
  }, [items, isInsideArena, onAllInside, onPositionsChange]);

  const draggedIdRef = useRef<string | null>(null);
  const draggedOrdinalRef = useRef<number | null>(null);
  const draggedPositionRef = useRef<Position | null>(null);
  const activePointerIdRef = useRef<number | null>(null);
  const panPointerIdRef = useRef<number | null>(null);
  const panStartRef = useRef<{ pointer: Position; pan: Position } | null>(null);
  const pinchPointersRef = useRef<Map<number, Position>>(new Map());
  const pinchStartRef = useRef<{ distance: number; zoom: number } | null>(null);
  const lastTraceRef = useRef<{ time: number; x: number; y: number } | null>(null);

  const toLogical = useCallback((clientX: number, clientY: number): Position | null => {
    const rect = arenaRef.current?.getBoundingClientRect();
    if (!rect) return null;
    const scale = zoomRef.current || 1;
    return { x: (clientX - rect.left) / scale, y: (clientY - rect.top) / scale };
  }, []);

  const emitTrace = useCallback(
    (ordinal: number, position: Position, phase: TraceSample["phase"]) => {
      if (!onTraceSample) return;
      const now = typeof performance !== "undefined" ? performance.now() : Date.now();
      if (phase === 1) {
        const last = lastTraceRef.current;
        if (last) {
          const dx = position.x - last.x;
          const dy = position.y - last.y;
          if (
            now - last.time < TRACE_MIN_INTERVAL_MS ||
            Math.sqrt(dx * dx + dy * dy) < TRACE_MIN_DISTANCE_PX
          ) {
            return;
          }
        }
      }
      lastTraceRef.current = { time: now, x: position.x, y: position.y };
      onTraceSample({ ordinal, x: position.x, y: position.y, phase });
    },
    [onTraceSample]
  );

  const handlePointerDown = (e: React.PointerEvent, id: string) => {
    if (e.pointerType === "mouse" && e.button !== 0) return;
    if (draggedIdRef.current !== null) return;

    const item = items.find((i) => i.id === id);
    if (!item) return;

    const logical = toLogical(e.clientX, e.clientY);
    if (!logical) return;

    e.preventDefault();
    e.stopPropagation();
    (e.currentTarget as HTMLElement).setPointerCapture?.(e.pointerId);

    draggedIdRef.current = id;
    draggedOrdinalRef.current = item.ordinal;
    draggedPositionRef.current = item.position;
    activePointerIdRef.current = e.pointerId;
    setDraggedId(id);

    dragOffset.current = {
      x: logical.x - item.position.x,
      y: logical.y - item.position.y,
    };

    lastTraceRef.current = null;
    emitTrace(item.ordinal, item.position, 0);

    setItems((prev) =>
      prev.map((i) => ({ ...i, isDragging: i.id === id }))
    );
  };

  const handleDoubleClick = (item: DraggableItem) => {
    if (onMediaPlay && item.mediaUrl) {
      onMediaPlay(item.id, item.mediaUrl, item.mediaType);
    }
  };

  const handlePointerMove = useCallback(
    (e: PointerEvent) => {
      // Pinch zoom (two pointers on the stage background).
      if (pinchPointersRef.current.has(e.pointerId)) {
        pinchPointersRef.current.set(e.pointerId, { x: e.clientX, y: e.clientY });
        if (pinchPointersRef.current.size === 2 && pinchStartRef.current) {
          const [a, b] = Array.from(pinchPointersRef.current.values());
          const distance = Math.hypot(a.x - b.x, a.y - b.y);
          if (pinchStartRef.current.distance > 0) {
            applyZoom(pinchStartRef.current.zoom * (distance / pinchStartRef.current.distance));
          }
          return;
        }
      }

      if (panPointerIdRef.current === e.pointerId && panStartRef.current) {
        const start = panStartRef.current;
        setPan(
          clampPan(
            {
              x: start.pan.x + (e.clientX - start.pointer.x),
              y: start.pan.y + (e.clientY - start.pointer.y),
            },
            zoomRef.current,
            containerSizeRef.current
          )
        );
        return;
      }

      if (!draggedIdRef.current || !arenaRef.current) return;
      if (activePointerIdRef.current !== null && e.pointerId !== activePointerIdRef.current) return;

      const logical = toLogical(e.clientX, e.clientY);
      if (!logical) return;
      const newX = logical.x - dragOffset.current.x;
      const newY = logical.y - dragOffset.current.y;

      const id = draggedIdRef.current;
      draggedPositionRef.current = { x: newX, y: newY };
      setItems((prev) =>
        prev.map((item) =>
          item.id === id
            ? { ...item, position: { x: newX, y: newY } }
            : item
        )
      );
      if (draggedOrdinalRef.current !== null) {
        emitTrace(draggedOrdinalRef.current, { x: newX, y: newY }, 1);
      }
    },
    [applyZoom, emitTrace, toLogical]
  );

  const handlePointerUp = useCallback((e?: PointerEvent) => {
    if (e && pinchPointersRef.current.has(e.pointerId)) {
      pinchPointersRef.current.delete(e.pointerId);
      if (pinchPointersRef.current.size < 2) pinchStartRef.current = null;
    }
    if (e && panPointerIdRef.current === e.pointerId) {
      panPointerIdRef.current = null;
      panStartRef.current = null;
    }
    if (activePointerIdRef.current !== null && e && e.pointerId !== activePointerIdRef.current) return;

    if (draggedIdRef.current) {
      const id = draggedIdRef.current;
      if (draggedOrdinalRef.current !== null && draggedPositionRef.current !== null) {
        lastTraceRef.current = null;
        emitTrace(draggedOrdinalRef.current, draggedPositionRef.current, 2);
      }
      setItems((prev) =>
        prev.map((i) =>
          i.id === id ? { ...i, isDragging: false } : i
        )
      );
    }

    draggedIdRef.current = null;
    draggedOrdinalRef.current = null;
    draggedPositionRef.current = null;
    activePointerIdRef.current = null;
    setDraggedId(null);
  }, [emitTrace]);

  useEffect(() => {
    window.addEventListener("pointermove", handlePointerMove);
    window.addEventListener("pointerup", handlePointerUp);
    window.addEventListener("pointercancel", handlePointerUp);
    return () => {
      window.removeEventListener("pointermove", handlePointerMove);
      window.removeEventListener("pointerup", handlePointerUp);
      window.removeEventListener("pointercancel", handlePointerUp);
    };
  }, [handlePointerMove, handlePointerUp]);

  // Wheel zoom needs a non-passive listener to prevent page scroll.
  useEffect(() => {
    const node = viewportRef.current;
    if (!node) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      applyZoom(zoomRef.current * (e.deltaY < 0 ? 1.1 : 1 / 1.1));
    };
    node.addEventListener("wheel", onWheel, { passive: false });
    return () => node.removeEventListener("wheel", onWheel);
  }, [applyZoom]);

  const handleStagePointerDown = (e: React.PointerEvent) => {
    // Background pointer: start panning (single) or pinch zoom (second pointer).
    if (draggedIdRef.current !== null) return;
    if (e.pointerType === "mouse" && e.button !== 0) return;

    if (e.pointerType === "touch") {
      pinchPointersRef.current.set(e.pointerId, { x: e.clientX, y: e.clientY });
      if (pinchPointersRef.current.size === 2) {
        const [a, b] = Array.from(pinchPointersRef.current.values());
        pinchStartRef.current = { distance: Math.hypot(a.x - b.x, a.y - b.y), zoom: zoomRef.current };
        panPointerIdRef.current = null;
        panStartRef.current = null;
        return;
      }
    }
    // The arena itself must stay put at default zoom: panning is only for
    // navigating while zoomed in.
    if (zoomRef.current <= 1.001) return;
    panPointerIdRef.current = e.pointerId;
    panStartRef.current = { pointer: { x: e.clientX, y: e.clientY }, pan };
  };

  // Connection lines while dragging
  const draggedItem = items.find((i) => i.id === draggedId);
  const draggedInside = draggedItem ? isInsideArena(draggedItem.position) : false;
  const connectionLines: { x1: number; y1: number; x2: number; y2: number; thickness: number; opacity: number }[] = [];

  if (draggedItem && draggedInside) {
    const maxPossibleDistance = arenaRadius * 2;
    for (const item of items) {
      if (item.id === draggedId) continue;
      if (!isInsideArena(item.position)) continue;
      const dx = draggedItem.position.x - item.position.x;
      const dy = draggedItem.position.y - item.position.y;
      const distance = Math.sqrt(dx * dx + dy * dy);
      const proximityFactor = Math.max(0, 1 - distance / maxPossibleDistance);
      connectionLines.push({
        x1: draggedItem.position.x,
        y1: draggedItem.position.y,
        x2: item.position.x,
        y2: item.position.y,
        thickness: Math.max(1, Math.round(1 + proximityFactor * 7)),
        opacity: 0.3 + proximityFactor * 0.7,
      });
    }
  }

  const allInside = items.every((item) => isInsideArena(item.position));
  const allPlayed = items.every((item) =>
    item.mediaType === "image" || playedItems.has(item.id)
  );
  const canSubmit = allInside && allPlayed && !submitting;

  const zoomLabel = `${Math.round(zoom * 100)}%`;

  return (
    <div style={{ position: "relative", width: containerSize, height: containerSize }}>
      {/* Camera viewport: a fixed window that clips the world. The arena never
          moves on the page; pan/zoom move the camera behind this window. */}
      <div
        ref={viewportRef}
        data-testid="arena-viewport"
        onPointerDown={handleStagePointerDown}
        style={{
          position: "absolute",
          inset: 0,
          overflow: "hidden",
          background: "#000",
          touchAction: "none",
          cursor: panPointerIdRef.current !== null ? "grabbing" : zoom > 1.001 ? "grab" : undefined,
        }}
      >
      <div
        ref={arenaRef}
        data-testid="arena-stage"
        style={{
          width: containerSize,
          height: containerSize,
          position: "relative",
          touchAction: "none",
          userSelect: "none",
          WebkitUserSelect: "none",
          transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
          transformOrigin: "center center",
        }}
      >
        {/* White circle */}
        <div
          style={{
            position: "absolute",
            left: (containerSize - size) / 2,
            top: (containerSize - size) / 2,
            width: size,
            height: size,
            borderRadius: "50%",
            border: `${CIRCLE_THICKNESS}px solid #fff`,
          }}
        />

        {/* Draggable tokens with thumbnails */}
        {items.map((item) => {
          const inside = isInsideArena(item.position);
          const hasBeenPlayed = item.mediaType === "image" || playedItems.has(item.id);
          const isValid = inside && hasBeenPlayed;
          const outlineColor = isValid ? "#00ff00" : "#ff0000";
          const offset = (containerSize - size) / 2;

          return (
            <div
              key={item.id}
              onPointerDown={(e) => handlePointerDown(e, item.id)}
              onDoubleClick={() => handleDoubleClick(item)}
              style={{
                position: "absolute",
                left: item.position.x - itemRadius + offset,
                top: item.position.y - itemRadius + offset,
                width: itemRadius * 2,
                height: itemRadius * 2,
                borderRadius: "50%",
                overflow: "hidden",
                border: `4px solid ${outlineColor}`,
                boxShadow: item.isDragging ? "0 10px 30px rgba(0, 0, 0, 0.7)" : "0 4px 12px rgba(0, 0, 0, 0.5)",
                cursor: item.isDragging ? "grabbing" : "grab",
                touchAction: "none",
                transform: item.isDragging ? "scale(1.08)" : "scale(1)",
                transition: item.isDragging ? "none" : "transform 0.15s ease, box-shadow 0.15s ease",
                zIndex: item.isDragging ? 1000 : 1,
              }}
              role="button"
              tabIndex={0}
              title={item.label}
              aria-label={`${language === "tr" ? "Uyarani oynat" : "Play stimulus"} ${item.label}`}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  handleDoubleClick(item);
                }
              }}
            >
              {/* Thumbnail or placeholder */}
              {item.thumbnail ? (
                <img
                  src={item.thumbnail}
                  alt={item.label}
                  style={{ width: "100%", height: "100%", objectFit: "cover", pointerEvents: "none" }}
                  draggable={false}
                />
              ) : (
                <div
                  style={{
                    width: "100%",
                    height: "100%",
                    background: "radial-gradient(circle at 30% 30%, #666 0%, #333 50%, #111 100%)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    color: "#fff",
                    fontWeight: 700,
                    fontSize: Math.max(10, Math.min(20, itemRadius * 0.55)),
                  }}
                >
                  {item.ordinal + 1}
                </div>
              )}
            </div>
          );
        })}

        {/* SVG for connection lines — above tokens so distance cues stay visible */}
        <svg
          width={containerSize}
          height={containerSize}
          style={{ position: "absolute", top: 0, left: 0, pointerEvents: "none", zIndex: 2000 }}
        >
          {connectionLines.map((line, idx) => (
            <line
              key={idx}
              x1={line.x1 + (containerSize - size) / 2}
              y1={line.y1 + (containerSize - size) / 2}
              x2={line.x2 + (containerSize - size) / 2}
              y2={line.y2 + (containerSize - size) / 2}
              stroke="#ff0000"
              strokeWidth={line.thickness}
              strokeOpacity={line.opacity}
            />
          ))}
        </svg>
      </div>
      </div>

      {/* Zoom controls */}
      <div
        style={{
          position: "absolute",
          top: 8,
          right: 8,
          display: "flex",
          gap: 6,
          alignItems: "center",
          zIndex: 3000,
        }}
      >
        <button
          type="button"
          aria-label={language === "tr" ? "Uzaklas" : "Zoom out"}
          onClick={() => applyZoom(zoomRef.current / 1.2)}
          style={zoomButtonStyle}
        >
          −
        </button>
        <span style={{ color: "#888", fontSize: 11, minWidth: 38, textAlign: "center" }}>{zoomLabel}</span>
        <button
          type="button"
          aria-label={language === "tr" ? "Yakinlas" : "Zoom in"}
          onClick={() => applyZoom(zoomRef.current * 1.2)}
          style={zoomButtonStyle}
        >
          +
        </button>
        <button
          type="button"
          aria-label={language === "tr" ? "Gorunumu sifirla" : "Reset view"}
          onClick={() => {
            setZoom(1);
            setPan({ x: 0, y: 0 });
          }}
          style={{ ...zoomButtonStyle, width: "auto", padding: "0 8px" }}
        >
          ⟲
        </button>
      </div>

      {/* Done button */}
      <button
        onClick={onSubmit}
        disabled={!canSubmit}
        style={{
          position: "absolute",
          bottom: 8,
          left: -12,
          padding: "10px 30px",
          borderRadius: 2,
          border: "none",
          background: canSubmit ? "#00ff00" : "#ff0000",
          color: "#000",
          fontSize: 14,
          fontWeight: 700,
          cursor: canSubmit ? "pointer" : "not-allowed",
          zIndex: 3000,
        }}
      >
        {language === "tr" ? "Bitir" : "Done"}
      </button>
    </div>
  );
}

const zoomButtonStyle: CSSProperties = {
  width: 28,
  height: 28,
  borderRadius: 6,
  border: "1px solid #333",
  background: "#111",
  color: "#fff",
  fontSize: 15,
  fontWeight: 700,
  cursor: "pointer",
  lineHeight: 1,
};
