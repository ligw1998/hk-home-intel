export function formatListingSegment(segment: string | null | undefined): string {
  switch (segment) {
    case "new":
      return "New";
    case "first_hand_remaining":
      return "First-hand remaining";
    case "second_hand":
      return "Second-hand";
    case "mixed":
      return "Mixed";
    case null:
    case undefined:
    case "":
      return "Unknown";
    default:
      return segment.replaceAll("_", " ");
  }
}

export const SEGMENT_OPTIONS = [
  { value: "all", label: "All segments" },
  { value: "new", label: "New" },
  { value: "first_hand_remaining", label: "First-hand remaining" },
  { value: "second_hand", label: "Second-hand" },
  { value: "mixed", label: "Mixed" },
] as const;
