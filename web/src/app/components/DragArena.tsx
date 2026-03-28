"use client";
/* eslint-disable @next/next/no-img-element */

import { useRef, useState, useCallback, useEffect, useMemo } from "react";

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

interface ArenaProps {
  stimuli: Stimulus[];
  onPositionsChange?: (positions: Record<string, Position>) => void;
  onAllInside?: (allInside: boolean) => void;
  onSubmit?: () => void;
  onMediaPlay?: (itemId: string, mediaUrl: string, mediaType: Stimulus["mediaType"]) => void;
  playedItems?: Set<string>;
  size?: number;
  trialIndex?: number;
  language?: "en" | "tr";
}

const ITEM_RADIUS = 55;
const ARENA_PADDING = 20;
const CIRCLE_THICKNESS = 3;

export default function DragArena({
  stimuli,
  onPositionsChange,
  onAllInside,
  onSubmit,
  onMediaPlay,
  playedItems = new Set(),
  size = 600,
  trialIndex = 0,
  language = "en",
}: ArenaProps) {
  const arenaRef = useRef<HTMLDivElement>(null);
  const [items, setItems] = useState<DraggableItem[]>([]);
  const [draggedId, setDraggedId] = useState<string | null>(null);
  const dragOffset = useRef<Position>({ x: 0, y: 0 });

  const arenaRadius = size / 2 - ARENA_PADDING;
  const center = size / 2;

  // Calculate initial seating positions (outside the circle)
  const getInitialPositions = useCallback(() => {
    return stimuli.map((s, i) => {
      const angle = (2 * Math.PI * i) / stimuli.length - Math.PI / 2;
      const seatRadius = arenaRadius + ITEM_RADIUS + 35;
      return {
        x: center + seatRadius * Math.cos(angle),
        y: center + seatRadius * Math.sin(angle),
      };
    });
  }, [stimuli, center, arenaRadius]);

  // Stable key representing which stimuli are shown (IDs only, not metadata like thumbnails)
  const stimuliKey = useMemo(
    () => stimuli.map((s) => s.id).join(","),
    [stimuli]
  );

  // Initialize/reset positions ONLY when the set of stimulus IDs or trialIndex changes
  useEffect(() => {
    if (stimuli.length === 0) return;

    const initialPositions = getInitialPositions();
    const newItems: DraggableItem[] = stimuli.map((s, i) => ({
      ...s,
      position: initialPositions[i],
      initialPosition: initialPositions[i],
      isDragging: false,
    }));
    setItems(newItems);
    setDraggedId(null);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stimuliKey, trialIndex]);

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
      return dist + ITEM_RADIUS * 0.6 <= arenaRadius;
    },
    [center, arenaRadius]
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
  const activePointerIdRef = useRef<number | null>(null);

  const handlePointerDown = (e: React.PointerEvent, id: string) => {
    if (e.pointerType === "mouse" && e.button !== 0) return;
    if (draggedIdRef.current !== null) return;

    const item = items.find((i) => i.id === id);
    if (!item) return;

    const rect = arenaRef.current?.getBoundingClientRect();
    if (!rect) return;

    e.preventDefault();
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);

    draggedIdRef.current = id;
    activePointerIdRef.current = e.pointerId;
    setDraggedId(id);

    dragOffset.current = {
      x: e.clientX - rect.left - item.position.x,
      y: e.clientY - rect.top - item.position.y,
    };

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
      if (!draggedIdRef.current || !arenaRef.current) return;
      if (activePointerIdRef.current !== null && e.pointerId !== activePointerIdRef.current) return;

      const rect = arenaRef.current.getBoundingClientRect();
      const newX = e.clientX - rect.left - dragOffset.current.x;
      const newY = e.clientY - rect.top - dragOffset.current.y;

      setItems((prev) =>
        prev.map((item) =>
          item.id === draggedIdRef.current
            ? { ...item, position: { x: newX, y: newY } }
            : item
        )
      );
    },
    []
  );

  const handlePointerUp = useCallback((e?: PointerEvent) => {
    if (activePointerIdRef.current !== null && e && e.pointerId !== activePointerIdRef.current) return;

    if (draggedIdRef.current) {
      const id = draggedIdRef.current;
      setItems((prev) =>
        prev.map((i) =>
          i.id === id ? { ...i, isDragging: false } : i
        )
      );
    }

    draggedIdRef.current = null;
    activePointerIdRef.current = null;
    setDraggedId(null);
  }, []);

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
  const canSubmit = allInside && allPlayed;

  const containerSize = size + ITEM_RADIUS * 2 + 70;

  return (
    <div style={{ position: "relative" }}>
      <div
        ref={arenaRef}
        style={{
          width: containerSize,
          height: containerSize,
          position: "relative",
          background: "#000",
          touchAction: "none",
          userSelect: "none",
          WebkitUserSelect: "none",
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

        {/* SVG for connection lines */}
        <svg width={containerSize} height={containerSize} style={{ position: "absolute", top: 0, left: 0, pointerEvents: "none" }}>
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
                left: item.position.x - ITEM_RADIUS + offset,
                top: item.position.y - ITEM_RADIUS + offset,
                width: ITEM_RADIUS * 2,
                height: ITEM_RADIUS * 2,
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
                    fontSize: 20,
                  }}
                >
                  {item.ordinal + 1}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Done button */}
      <button
        onClick={onSubmit}
        disabled={!canSubmit}
        style={{
          position: "absolute",
          bottom: 8,
          left: 8,
          padding: "10px 30px",
          borderRadius: 2,
          border: "none",
          background: canSubmit ? "#00ff00" : "#ff0000",
          color: "#000",
          fontSize: 14,
          fontWeight: 700,
          cursor: canSubmit ? "pointer" : "not-allowed",
        }}
      >
        {language === "tr" ? "Bitir" : "Done"}
      </button>
    </div>
  );
}
