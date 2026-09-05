import type { DragEvent, ReactNode } from "react";
import { Table } from "@mantine/core";

// Fixed so a second sticky row (a per-column filter row) can compute its
// own sticky `top` as exactly this many pixels, stacking cleanly under
// the header row instead of guessing/measuring at render time.
export const HEADER_ROW_HEIGHT = 42;

interface ResizableThProps {
  width: number;
  top?: number;
  onResizeStart: (startX: number) => void;
  onClick?: () => void;
  draggable?: boolean;
  isDragging?: boolean;
  onDragStart?: () => void;
  onDragOver?: (event: DragEvent) => void;
  onDrop?: () => void;
  children: ReactNode;
}

/**
 * A Table.Th with a drag-to-resize handle on its right edge, sticky
 * positioning (so the header/filter rows stay visible while the table
 * body scrolls), and optional drag-to-reorder.
 *
 * position: sticky is set per-cell rather than on <thead> -- <thead> has
 * display: table-header-group, and sticky positioning on that display
 * type isn't reliably supported across browsers, unlike on table cells.
 */
export function ResizableTh({
  width,
  top = 0,
  onResizeStart,
  onClick,
  draggable,
  isDragging,
  onDragStart,
  onDragOver,
  onDrop,
  children,
}: ResizableThProps) {
  return (
    <Table.Th
      draggable={draggable}
      onDragStart={onDragStart}
      onDragOver={onDragOver}
      onDrop={onDrop}
      onClick={onClick}
      style={{
        width,
        height: HEADER_ROW_HEIGHT,
        position: "sticky",
        top,
        zIndex: 2,
        backgroundColor: "var(--mantine-color-body)",
        cursor: draggable ? "grab" : onClick ? "pointer" : undefined,
        userSelect: "none",
        overflow: "hidden",
        textOverflow: "ellipsis",
        whiteSpace: "nowrap",
        opacity: isDragging ? 0.4 : 1,
      }}
    >
      {children}
      <div
        onMouseDown={(event) => {
          event.preventDefault();
          event.stopPropagation();
          onResizeStart(event.clientX);
        }}
        style={{
          position: "absolute",
          top: 0,
          right: 0,
          bottom: 0,
          width: 6,
          cursor: "col-resize",
        }}
      />
    </Table.Th>
  );
}
