"use client";

import { useState } from "react";

function formatExactMoney(amount: number): string {
  return new Intl.NumberFormat("en-HK", {
    style: "currency",
    currency: "HKD",
    maximumFractionDigits: 0,
  }).format(amount);
}

function formatCompactMoney(amount: number): string {
  const absolute = Math.abs(amount);
  if (absolute >= 1_000_000) {
    const value = amount / 1_000_000;
    const digits = absolute >= 10_000_000 ? 1 : 2;
    return `HK$${value.toFixed(digits).replace(/\.0+$/, "").replace(/(\.\d*[1-9])0+$/, "$1")}M`;
  }
  if (absolute >= 1_000) {
    const value = amount / 1_000;
    const digits = absolute >= 100_000 ? 0 : 1;
    return `HK$${value.toFixed(digits).replace(/\.0+$/, "").replace(/(\.\d*[1-9])0+$/, "$1")}K`;
  }
  return formatExactMoney(amount);
}

export function MoneyValue({
  amount,
  className,
  interactive = true,
}: {
  amount: number | null;
  className?: string;
  interactive?: boolean;
}) {
  const [expanded, setExpanded] = useState(false);

  if (amount === null) {
    return <span className={className}>TBD</span>;
  }

  const compact = formatCompactMoney(amount);
  const exact = formatExactMoney(amount);
  if (compact === exact) {
    return <span className={className}>{exact}</span>;
  }
  if (!interactive) {
    return <span className={className}>{compact}</span>;
  }

  return (
    <button
      type="button"
      className={`money-toggle${className ? ` ${className}` : ""}`}
      onClick={() => setExpanded((current) => !current)}
      title={expanded ? "Show compact amount" : "Show exact amount"}
    >
      {expanded ? exact : compact}
    </button>
  );
}
