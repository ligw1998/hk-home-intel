export function formatEventType(eventType: string): string {
  switch (eventType) {
    case "new_listing":
      return "New listing";
    case "price_drop":
      return "Price drop";
    case "price_raise":
      return "Price raise";
    case "relist":
      return "Relist";
    case "sold":
      return "Sold";
    case "withdrawn":
      return "Withdrawn";
    case "status_change":
      return "Status change";
    default:
      return eventType.replaceAll("_", " ");
  }
}

export function formatListingStatus(status: string | null | undefined): string {
  if (!status) {
    return "Unknown";
  }
  return status.replaceAll("_", " ");
}
