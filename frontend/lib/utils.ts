export function fmt(value: number | undefined | null, decimals = 2): string {
  if (value == null) return "—";
  return value.toFixed(decimals);
}

export function fmtPnl(value: number | undefined | null): string {
  if (value == null) return "—";
  const sign = value >= 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}`;
}

export function fmtPct(value: number | undefined | null): string {
  if (value == null) return "—";
  return `${(value * 100).toFixed(1)}%`;
}

export function fmtDate(dt: string | undefined | null): string {
  if (!dt) return "—";
  return new Date(dt).toLocaleDateString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

export function fmtDateTime(dt: string | undefined | null): string {
  if (!dt) return "—";
  return new Date(dt).toLocaleString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function resultColor(result: string | undefined): string {
  if (result === "win") return "text-green-400";
  if (result === "loss") return "text-red-400";
  return "text-gray-400";
}

export function pnlColor(value: number | undefined | null): string {
  if (value == null) return "text-gray-400";
  if (value > 0) return "text-green-400";
  if (value < 0) return "text-red-400";
  return "text-gray-400";
}

/** Human-readable relative time: "just now", "5m ago", "2h ago", "3d ago". */
export function fmtAgo(isoStr: string | undefined | null): string {
  if (!isoStr) return "—";
  const ms = Date.now() - new Date(isoStr).getTime();
  if (ms < 60_000) return "just now";
  const min = Math.floor(ms / 60_000);
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h ${min % 60}m ago`;
  return `${Math.floor(hr / 24)}d ago`;
}
