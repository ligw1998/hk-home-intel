"use client";

export type CompareSelection = {
  id: string;
  name: string;
};

const STORAGE_KEY = "hhi.compare.selections";
const EVENT_NAME = "hhi:compare-updated";

function isBrowser(): boolean {
  return typeof window !== "undefined";
}

function dedupe(items: CompareSelection[]): CompareSelection[] {
  const seen = new Set<string>();
  const result: CompareSelection[] = [];
  for (const item of items) {
    if (!item.id || seen.has(item.id)) {
      continue;
    }
    seen.add(item.id);
    result.push(item);
  }
  return result.slice(0, 6);
}

export function getCompareSelections(): CompareSelection[] {
  if (!isBrowser()) {
    return [];
  }
  const raw = window.localStorage.getItem(STORAGE_KEY);
  if (!raw) {
    return [];
  }
  try {
    const parsed = JSON.parse(raw) as CompareSelection[];
    return Array.isArray(parsed) ? dedupe(parsed) : [];
  } catch {
    return [];
  }
}

export function setCompareSelections(items: CompareSelection[]): CompareSelection[] {
  const next = dedupe(items);
  if (isBrowser()) {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    window.dispatchEvent(new CustomEvent(EVENT_NAME, { detail: next }));
  }
  return next;
}

export function addCompareSelection(item: CompareSelection): CompareSelection[] {
  return setCompareSelections([...getCompareSelections(), item]);
}

export function removeCompareSelection(id: string): CompareSelection[] {
  return setCompareSelections(getCompareSelections().filter((item) => item.id !== id));
}

export function clearCompareSelections(): CompareSelection[] {
  return setCompareSelections([]);
}

export function subscribeCompareSelections(callback: (items: CompareSelection[]) => void): () => void {
  if (!isBrowser()) {
    return () => {};
  }
  const handler = () => callback(getCompareSelections());
  const customHandler = () => callback(getCompareSelections());
  window.addEventListener("storage", handler);
  window.addEventListener(EVENT_NAME, customHandler);
  return () => {
    window.removeEventListener("storage", handler);
    window.removeEventListener(EVENT_NAME, customHandler);
  };
}
