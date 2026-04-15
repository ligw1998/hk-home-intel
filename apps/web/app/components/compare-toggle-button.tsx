"use client";

import { useEffect, useState } from "react";

import {
  addCompareSelection,
  getCompareSelections,
  removeCompareSelection,
  subscribeCompareSelections,
} from "../lib/compare-store";

export function CompareToggleButton({
  developmentId,
  developmentName,
}: {
  developmentId: string;
  developmentName: string;
}) {
  const [selected, setSelected] = useState(false);

  useEffect(() => {
    const sync = () => {
      setSelected(getCompareSelections().some((item) => item.id === developmentId));
    };
    sync();
    return subscribeCompareSelections(sync);
  }, [developmentId]);

  function toggle() {
    if (selected) {
      removeCompareSelection(developmentId);
      return;
    }
    addCompareSelection({ id: developmentId, name: developmentName });
  }

  return (
    <button type="button" className="action-button action-button-secondary" onClick={toggle}>
      {selected ? "Remove from compare" : "Add to compare"}
    </button>
  );
}
