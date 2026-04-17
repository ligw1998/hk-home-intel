import Link from "next/link";

const WORKFLOW_ITEMS = [
  { href: "/", label: "Dashboard", key: "dashboard" },
  { href: "/shortlist", label: "Shortlist", key: "shortlist" },
  { href: "/map", label: "Map", key: "map" },
  { href: "/compare", label: "Compare", key: "compare" },
];

export function DecisionWorkflowNav({ current }: { current: string }) {
  return (
    <nav className="workflow-nav" aria-label="Decision workflow">
      {WORKFLOW_ITEMS.map((item) => (
        <Link
          key={item.key}
          href={item.href}
          className={item.key === current ? "workflow-chip workflow-chip-active" : "workflow-chip"}
        >
          {item.label}
        </Link>
      ))}
    </nav>
  );
}
