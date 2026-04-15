"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import {
  clearCompareSelections,
  CompareSelection,
  removeCompareSelection,
  subscribeCompareSelections,
  getCompareSelections,
} from "../lib/compare-store";

export function CompareTray() {
  const [items, setItems] = useState<CompareSelection[]>([]);

  useEffect(() => {
    setItems(getCompareSelections());
    return subscribeCompareSelections(setItems);
  }, []);

  const compareHref = useMemo(() => `/compare?ids=${items.map((item) => item.id).join(",")}`, [items]);

  if (items.length === 0) {
    return null;
  }

  return (
    <aside className="compare-tray">
      <div className="compare-tray-head">
        <strong>Compare tray</strong>
        <span>{items.length} selected</span>
      </div>
      <div className="compare-tray-items">
        {items.map((item) => (
          <button
            key={item.id}
            type="button"
            className="compare-tray-chip"
            onClick={() => removeCompareSelection(item.id)}
            title="Remove from compare"
          >
            <span>{item.name}</span>
            <span>×</span>
          </button>
        ))}
      </div>
      <div className="compare-tray-actions">
        <Link href={compareHref}>Open compare</Link>
        <button type="button" className="action-button action-button-secondary" onClick={() => clearCompareSelections()}>
          Clear
        </button>
      </div>
    </aside>
  );
}
