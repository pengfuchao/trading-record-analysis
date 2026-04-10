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
