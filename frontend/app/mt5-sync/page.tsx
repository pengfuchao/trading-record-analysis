"use client";

import { useEffect, useState } from "react";
import useSWR from "swr";
import { mutate } from "swr";
import {
  api,
  MT5Config,
  MT5ConfigCreate,
  MT5SyncResponse,
  MT5SyncStatus,
  OpenPositionsResponse,
} from "@/lib/api";
import { useAccount } from "@/components/AccountProvider";
import AccountSelector from "@/components/AccountSelector";
import { fmtDateTime, fmtDate, fmtAgo } from "@/lib/utils";

// ── Helpers ───────────────────────────────────────────────────────────────────

/** Compute the expected env var name for the MT5 password from an account id. */
function envVarName(accountId: string): string {
  return `MT5_${accountId.toUpperCase().replace(/[-\s]/g, "_")}_PASSWORD`;
}

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

function daysAgo(n: number): string {
  const d = new Date();
  d.setDate(d.getDate() - n);
  return d.toISOString().slice(0, 10);
}

// ── Freshness computation ─────────────────────────────────────────────────────

type FreshnessState = "fresh" | "stale" | "delayed" | "error" | "no_sync";

interface FreshnessInfo {
  state: FreshnessState;
  ageMinutes: number | null;
  lastError: string | null;
  source: string | null;
}

function computeFreshness(status: MT5SyncStatus): FreshnessInfo {
  if (!status.sync_configured || status.last_runs.length === 0) {
    return { state: "no_sync", ageMinutes: null, lastError: null, source: null };
  }

  const now = Date.now();
  const lastRun = status.last_runs[0];
  const intervalMs = (status.polling_interval_minutes ?? 60) * 60_000;
  // Stale threshold: 1.5× polling interval, minimum 90 min
  const staleMs = Math.max(intervalMs * 1.5, 90 * 60_000);

  const lastSyncMs = status.last_sync_at ? new Date(status.last_sync_at).getTime() : null;
  const nextPollMs = status.next_poll_at ? new Date(status.next_poll_at).getTime() : null;

  // Latest run errored AND that error is more recent than the last success
  const lastRunIsError = lastRun.status === "error";
  const errorNewerThanSuccess =
    lastSyncMs === null ||
    new Date(lastRun.started_at).getTime() > lastSyncMs;
  if (lastRunIsError && errorNewerThanSuccess) {
    return {
      state: "error",
      ageMinutes: lastSyncMs ? Math.floor((now - lastSyncMs) / 60_000) : null,
      lastError: lastRun.error_message ?? "Unknown error",
      source: lastRun.triggered_by,
    };
  }

  if (!lastSyncMs) {
    return { state: "no_sync", ageMinutes: null, lastError: null, source: null };
  }

  const ageMs = now - lastSyncMs;
  const ageMinutes = Math.floor(ageMs / 60_000);
  const source =
    status.last_runs.find((r) => r.status === "success")?.triggered_by ?? null;

  // Delayed: polling enabled, next poll overdue by >2 min
  if (status.enabled && nextPollMs !== null && nextPollMs < now - 2 * 60_000) {
    return { state: "delayed", ageMinutes, lastError: null, source };
  }

  if (ageMs > staleMs) {
    return { state: "stale", ageMinutes, lastError: null, source };
  }

  return { state: "fresh", ageMinutes, lastError: null, source };
}

function FreshnessBadge({ status }: { status: MT5SyncStatus }) {
  const { state, ageMinutes, lastError, source } = computeFreshness(status);

  const cfg: Record<FreshnessState, { cls: string; label: string }> = {
    fresh:   { cls: "bg-green-900/40 text-green-300 border-green-700/50",   label: "Fresh" },
    stale:   { cls: "bg-yellow-900/40 text-yellow-300 border-yellow-700/50", label: "Stale" },
    delayed: { cls: "bg-orange-900/40 text-orange-300 border-orange-700/50", label: "Delayed" },
    error:   { cls: "bg-red-900/40 text-red-300 border-red-700/50",          label: "Error" },
    no_sync: { cls: "bg-gray-800 text-gray-400 border-gray-700",             label: "No sync" },
  };

  const { cls, label } = cfg[state];

  let detail = "";
  if (state === "fresh" || state === "stale") {
    const ago = status.last_sync_at ? fmtAgo(status.last_sync_at) : "—";
    const src = source ? ` · ${source}` : "";
    detail = `updated ${ago}${src}`;
  } else if (state === "delayed") {
    const ago = status.last_sync_at ? fmtAgo(status.last_sync_at) : "—";
    detail = `next poll overdue · last success ${ago}`;
  } else if (state === "error") {
    const truncated = lastError ? lastError.slice(0, 80) + (lastError.length > 80 ? "…" : "") : "unknown error";
    detail = truncated;
  } else if (state === "no_sync") {
    detail = "no successful sync yet";
  }

  return (
    <div className="flex items-center gap-2 flex-wrap">
      <span className={`text-xs px-2 py-0.5 rounded font-medium border ${cls}`}>
        {label}
      </span>
      {detail && (
        <span className="text-xs text-gray-400">{detail}</span>
      )}
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const cls =
    status === "success"
      ? "bg-green-900/40 text-green-300 border border-green-700/50"
      : status === "error"
      ? "bg-red-900/40 text-red-300 border border-red-700/50"
      : "bg-yellow-900/40 text-yellow-300 border border-yellow-700/50";
  return (
    <span className={`text-xs px-2 py-0.5 rounded font-medium ${cls}`}>
      {status}
    </span>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function MT5SyncPage() {
  const { accountId } = useAccount();

  // ── Config SWR — 404 means "no config yet", not a real error ────────────────
  const {
    data: config,
    error: configError,
    mutate: refreshConfig,
  } = useSWR<MT5Config | null>(
    accountId ? `mt5-config-${accountId}` : null,
    async () => {
      try {
        return await api.getMt5Config(accountId!);
      } catch (e: any) {
        if (e?.message?.startsWith("404")) return null;
        throw e;
      }
    },
    { revalidateOnFocus: false }
  );

  // ── Status / run history SWR ─────────────────────────────────────────────────
  const { data: status, mutate: refreshStatus } = useSWR<MT5SyncStatus>(
    accountId ? `mt5-status-${accountId}` : null,
    () => api.getMt5Status(accountId!, 10),
    { revalidateOnFocus: false }
  );

  // ── Open positions SWR ───────────────────────────────────────────────────────
  const { data: openPositions, mutate: refreshOpenPositions } = useSWR<OpenPositionsResponse>(
    accountId ? `open-positions-${accountId}` : null,
    () => api.getOpenPositions(accountId!),
    { revalidateOnFocus: false }
  );

  // ── Config form state ────────────────────────────────────────────────────────
  const [login, setLogin] = useState("");
  const [server, setServer] = useState("");
  const [terminalPath, setTerminalPath] = useState("");
  const [utcOffset, setUtcOffset] = useState("2");
  const [pollingInterval, setPollingInterval] = useState("60");
  const [pollingEnabled, setPollingEnabled] = useState(true);
  const [configSaving, setConfigSaving] = useState(false);
  const [configSaved, setConfigSaved] = useState(false);
  const [configError2, setConfigError2] = useState<string | null>(null);

  // Populate form when config loads
  useEffect(() => {
    if (config) {
      setLogin(String(config.mt5_login));
      setServer(config.mt5_server);
      setTerminalPath(config.terminal_path ?? "");
      setUtcOffset(String(config.broker_utc_offset));
      setPollingInterval(String(config.polling_interval_minutes));
      setPollingEnabled(config.enabled);
    }
  }, [config]);

  const handleSaveConfig = async () => {
    if (!accountId) return;
    const loginNum = parseInt(login, 10);
    if (!loginNum || loginNum <= 0) {
      setConfigError2("MT5 login must be a positive number.");
      return;
    }
    if (!server.trim()) {
      setConfigError2("Broker server is required.");
      return;
    }
    setConfigSaving(true);
    setConfigError2(null);
    setConfigSaved(false);
    try {
      const body: MT5ConfigCreate = {
        mt5_login: loginNum,
        mt5_server: server.trim(),
        terminal_path: terminalPath.trim() || undefined,
        broker_utc_offset: parseInt(utcOffset, 10) || 2,
        polling_interval_minutes: Math.max(1, parseInt(pollingInterval, 10) || 60),
        enabled: pollingEnabled,
      };
      await api.saveMt5Config(accountId, body);
      await refreshConfig();
      await refreshStatus();
      setConfigSaved(true);
    } catch (e: any) {
      setConfigError2(e.message ?? "Save failed");
    } finally {
      setConfigSaving(false);
    }
  };

  // ── Sync trigger state ───────────────────────────────────────────────────────
  const [fromDate, setFromDate] = useState(daysAgo(30));
  const [toDate, setToDate] = useState(today());
  const [syncing, setSyncing] = useState(false);
  const [syncResult, setSyncResult] = useState<MT5SyncResponse | null>(null);
  const [syncError, setSyncError] = useState<string | null>(null);

  const handleSync = async () => {
    if (!accountId) return;
    setSyncing(true);
    setSyncResult(null);
    setSyncError(null);
    try {
      const result = await api.triggerMt5Sync(accountId, {
        from_date: fromDate ? `${fromDate}T00:00:00` : undefined,
        to_date: toDate ? `${toDate}T23:59:59` : undefined,
      });
      setSyncResult(result);

      // Refresh status, open positions, and invalidate account-scoped caches
      await refreshStatus();
      await refreshOpenPositions();
      const pfx = (p: string) => (k: unknown) =>
        typeof k === "string" && k.startsWith(p);
      mutate(pfx(`trades-${accountId}`));
      mutate(pfx(`analytics-${accountId}`));
      mutate(pfx(`mistakes-${accountId}`));
      mutate(pfx(`ftmo-${accountId}`));
    } catch (e: any) {
      setSyncError(e.message ?? "Sync failed");
    } finally {
      setSyncing(false);
    }
  };

  // ── No account selected ──────────────────────────────────────────────────────
  if (!accountId) {
    return (
      <div className="space-y-6 max-w-3xl">
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-semibold">MT5 Live Sync</h1>
          <AccountSelector />
        </div>
        <p className="text-gray-500 text-sm">Select an account to manage MT5 sync settings.</p>
      </div>
    );
  }

  const configLoading = config === undefined && !configError;

  return (
    <div className="space-y-6 max-w-3xl">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">MT5 Live Sync</h1>
          <p className="text-xs text-gray-500 mt-0.5">
            Sync closed trade history directly from your MetaTrader 5 terminal.
            Requires Windows with MetaTrader5 Python package installed.
          </p>
        </div>
        <AccountSelector />
      </div>

      {/* ── Section 1: Connection Config ─────────────────────────────────────── */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-5 space-y-4">
        <div className="flex items-center justify-between">
          <p className="text-xs text-gray-500 uppercase tracking-wider">Connection Config</p>
          {config && (
            <span className="text-xs text-gray-500">
              Last updated {fmtDateTime(config.updated_at)}
            </span>
          )}
        </div>

        {configLoading && (
          <div className="flex items-center gap-2 text-sm text-gray-400">
            <span className="w-3 h-3 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
            Loading…
          </div>
        )}

        {!configLoading && (
          <div className="grid grid-cols-2 gap-4">
            {/* Login */}
            <div className="space-y-1">
              <label className="text-xs text-gray-400">MT5 Account Login *</label>
              <input
                type="number"
                value={login}
                onChange={(e) => setLogin(e.target.value)}
                placeholder="e.g. 12345678"
                className="w-full bg-gray-800 border border-gray-700 text-gray-100 text-sm rounded-md px-3 py-2 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </div>

            {/* Broker server */}
            <div className="space-y-1">
              <label className="text-xs text-gray-400">Broker Server *</label>
              <input
                type="text"
                value={server}
                onChange={(e) => setServer(e.target.value)}
                placeholder="e.g. ICMarkets-Live"
                className="w-full bg-gray-800 border border-gray-700 text-gray-100 text-sm rounded-md px-3 py-2 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </div>

            {/* UTC offset */}
            <div className="space-y-1">
              <label className="text-xs text-gray-400">Broker UTC Offset</label>
              <input
                type="number"
                value={utcOffset}
                onChange={(e) => setUtcOffset(e.target.value)}
                min={-12}
                max={14}
                placeholder="2"
                className="w-full bg-gray-800 border border-gray-700 text-gray-100 text-sm rounded-md px-3 py-2 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
              <p className="text-xs text-gray-600">
                Default 2 = EET (most MT5 brokers). Affects session classification and FTMO daily loss.
              </p>
            </div>

            {/* Terminal path */}
            <div className="space-y-1">
              <label className="text-xs text-gray-400">Terminal Path (optional)</label>
              <input
                type="text"
                value={terminalPath}
                onChange={(e) => setTerminalPath(e.target.value)}
                placeholder="C:\Program Files\MetaTrader 5\terminal64.exe"
                className="w-full bg-gray-800 border border-gray-700 text-gray-100 text-sm rounded-md px-3 py-2 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
              <p className="text-xs text-gray-600">
                Leave blank to use the MT5 default install path.
              </p>
            </div>

            {/* Polling interval */}
            <div className="space-y-1">
              <label className="text-xs text-gray-400">Auto-Poll Interval (minutes)</label>
              <input
                type="number"
                value={pollingInterval}
                onChange={(e) => setPollingInterval(e.target.value)}
                min={1}
                placeholder="60"
                className="w-full bg-gray-800 border border-gray-700 text-gray-100 text-sm rounded-md px-3 py-2 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
              <p className="text-xs text-gray-600">
                How often the background scheduler runs a sync. Minimum 1 minute.
              </p>
            </div>

            {/* Polling enabled */}
            <div className="space-y-1 flex flex-col justify-center">
              <label className="text-xs text-gray-400">Background Polling</label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={pollingEnabled}
                  onChange={(e) => setPollingEnabled(e.target.checked)}
                  className="w-4 h-4 rounded bg-gray-800 border-gray-600 text-blue-500 focus:ring-blue-500"
                />
                <span className="text-sm text-gray-300">
                  {pollingEnabled ? "Enabled" : "Disabled"}
                </span>
              </label>
              <p className="text-xs text-gray-600">
                Uncheck to pause auto-polling without deleting the config.
              </p>
            </div>
          </div>
        )}

        {/* Password note */}
        {!configLoading && (
          <div className="bg-gray-800/50 border border-gray-700 rounded-md px-4 py-3 space-y-1">
            <p className="text-xs text-gray-400 font-medium">Password — set via environment variable, never stored in DB</p>
            <p className="text-xs text-gray-500">
              On the backend server, set:
            </p>
            <code className="block text-xs font-mono text-blue-300 bg-gray-900 px-3 py-1.5 rounded mt-1 break-all">
              {envVarName(accountId)}=your_password
            </code>
            <p className="text-xs text-gray-600 mt-1">
              Restart the backend after setting this variable. The sync will fail with a 422 error if the variable is missing.
            </p>
          </div>
        )}

        {/* Config error / success */}
        {configError2 && (
          <p className="text-sm text-red-400">{configError2}</p>
        )}
        {configSaved && !configError2 && (
          <p className="text-sm text-green-400">Config saved.</p>
        )}

        {!configLoading && (
          <button
            onClick={handleSaveConfig}
            disabled={configSaving}
            className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm px-4 py-2 rounded-md transition-colors"
          >
            {configSaving ? (
              <span className="flex items-center gap-2">
                <span className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />
                Saving…
              </span>
            ) : config ? "Update Config" : "Save Config"}
          </button>
        )}
      </div>

      {/* ── Section 1b: Background Polling Status ───────────────────────────── */}
      {status?.sync_configured && (
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-5 space-y-3">
          <div className="flex items-center justify-between">
            <p className="text-xs text-gray-500 uppercase tracking-wider">Data Freshness</p>
            <span
              className={`text-xs px-2 py-0.5 rounded font-medium border ${
                status.enabled
                  ? "bg-green-900/40 text-green-300 border-green-700/50"
                  : "bg-gray-800 text-gray-400 border-gray-700"
              }`}
            >
              Polling {status.enabled ? "On" : "Off"}
            </span>
          </div>

          <FreshnessBadge status={status} />

          <div className="grid grid-cols-2 gap-4 text-sm pt-1">
            <div>
              <p className="text-xs text-gray-500">Last successful sync</p>
              <p className="text-gray-200 mt-0.5 text-xs">
                {status.last_sync_at
                  ? `${fmtDateTime(status.last_sync_at)} (${fmtAgo(status.last_sync_at)})`
                  : "—"}
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-500">
                {status.enabled ? "Next scheduled run" : "Interval (paused)"}
              </p>
              <p className="text-gray-200 mt-0.5 text-xs">
                {status.enabled
                  ? status.next_poll_at
                    ? fmtDateTime(status.next_poll_at)
                    : "Calculating…"
                  : status.polling_interval_minutes != null
                  ? `Every ${status.polling_interval_minutes} min (disabled)`
                  : "—"}
              </p>
            </div>
          </div>

          {status.enabled && (
            <p className="text-xs text-gray-600">
              Background sync runs every {status.polling_interval_minutes ?? "?"} min. Manual syncs
              share the same audit log below.
              Fresh = within 1.5× interval (min 90 min). Stale = older. Delayed = next poll overdue.
            </p>
          )}
          {!status.enabled && status.last_sync_at && (
            <p className="text-xs text-gray-600">
              Polling is disabled. Data was last updated {fmtAgo(status.last_sync_at)}. Enable polling
              above or run a manual sync to refresh.
            </p>
          )}
        </div>
      )}

      {/* ── Section 2: Manual Sync Trigger ──────────────────────────────────── */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-5 space-y-4">
        <p className="text-xs text-gray-500 uppercase tracking-wider">Manual Sync</p>

        {status && !status.sync_configured && (
          <p className="text-sm text-yellow-400">
            Save an MT5 config above before triggering a sync.
          </p>
        )}

        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-1">
            <label className="text-xs text-gray-400">From date</label>
            <input
              type="date"
              value={fromDate}
              onChange={(e) => setFromDate(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 text-gray-100 text-sm rounded-md px-3 py-2 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs text-gray-400">To date</label>
            <input
              type="date"
              value={toDate}
              onChange={(e) => setToDate(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 text-gray-100 text-sm rounded-md px-3 py-2 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>
        </div>

        <p className="text-xs text-gray-600">
          Sync fetches closed deals from MT5 for the selected date range and upserts them into
          the trade log. Manual enrichment (notes, flags, setup type) is always preserved.
        </p>

        <div className="flex items-center gap-4">
          <button
            onClick={handleSync}
            disabled={syncing || (status != null && !status.sync_configured)}
            className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm px-5 py-2.5 rounded-md transition-colors font-medium"
          >
            {syncing ? (
              <span className="flex items-center gap-2">
                <span className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />
                Syncing…
              </span>
            ) : (
              "Sync Now"
            )}
          </button>
          {status?.last_sync_at && !syncing && (
            <span className="text-xs text-gray-500">
              Last synced: {fmtDateTime(status.last_sync_at)}
            </span>
          )}
        </div>

        {/* Sync error */}
        {syncError && (
          <div className="bg-red-900/30 border border-red-700 text-red-300 text-sm px-4 py-3 rounded-md">
            {syncError}
          </div>
        )}

        {/* Sync result */}
        {syncResult && !syncError && (
          <div
            className={`border rounded-lg p-4 space-y-3 ${
              syncResult.status === "success"
                ? "bg-green-900/20 border-green-700"
                : "bg-red-900/20 border-red-700"
            }`}
          >
            <div className="flex items-center gap-3">
              <StatusBadge status={syncResult.status} />
              <span className="text-sm text-gray-300">
                {syncResult.status === "success"
                  ? "Sync complete"
                  : "Sync completed with error"}
              </span>
            </div>

            {syncResult.status === "success" && (
              <div className="grid grid-cols-5 gap-4">
                <div className="text-center">
                  <p className="text-2xl font-semibold text-green-400">{syncResult.trades_new}</p>
                  <p className="text-xs text-gray-500 mt-1">New trades</p>
                </div>
                <div className="text-center">
                  <p className="text-2xl font-semibold text-blue-400">{syncResult.trades_updated}</p>
                  <p className="text-xs text-gray-500 mt-1">Updated</p>
                </div>
                <div className="text-center">
                  <p className="text-2xl font-semibold text-gray-400">{syncResult.trades_skipped}</p>
                  <p className="text-xs text-gray-500 mt-1">Skipped</p>
                </div>
                <div className="text-center">
                  <p className="text-2xl font-semibold text-gray-300">{syncResult.deals_fetched}</p>
                  <p className="text-xs text-gray-500 mt-1">Deals fetched</p>
                </div>
                <div className="text-center">
                  <p className="text-2xl font-semibold text-yellow-400">{syncResult.open_positions_count}</p>
                  <p className="text-xs text-gray-500 mt-1">Open now</p>
                </div>
              </div>
            )}

            {syncResult.error_message && (
              <p className="text-xs text-red-300 font-mono break-words">
                {syncResult.error_message}
              </p>
            )}
          </div>
        )}
      </div>

      {/* ── Section 3: Run History ───────────────────────────────────────────── */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
        <div className="px-5 py-3 border-b border-gray-800 flex items-center justify-between">
          <p className="text-xs text-gray-500 uppercase tracking-wider">Recent Sync Runs</p>
          {status?.last_sync_at && (
            <span className="text-xs text-gray-500">
              Last success: {fmtDateTime(status.last_sync_at)}
            </span>
          )}
        </div>

        {!status || status.last_runs.length === 0 ? (
          <p className="text-sm text-gray-500 px-5 py-4">
            No sync runs yet. Configure MT5 connection above and trigger your first sync.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-gray-500 text-xs uppercase tracking-wider border-b border-gray-800">
                  <th className="text-left px-4 py-2">Started</th>
                  <th className="text-left px-4 py-2">Status</th>
                  <th className="text-left px-4 py-2">Source</th>
                  <th className="text-left px-4 py-2">Range</th>
                  <th className="text-right px-4 py-2">New</th>
                  <th className="text-right px-4 py-2">Updated</th>
                  <th className="text-left px-4 py-2">Error</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800">
                {status.last_runs.map((run) => (
                  <tr key={run.run_id} className="hover:bg-gray-800/30 transition-colors">
                    <td className="px-4 py-2.5 text-gray-400 whitespace-nowrap text-xs">
                      {fmtDateTime(run.started_at)}
                    </td>
                    <td className="px-4 py-2.5">
                      <StatusBadge status={run.status} />
                    </td>
                    <td className="px-4 py-2.5">
                      <span className={`text-xs px-1.5 py-0.5 rounded ${
                        run.triggered_by === "scheduled"
                          ? "bg-purple-900/40 text-purple-300 border border-purple-700/50"
                          : "bg-gray-800 text-gray-400 border border-gray-700"
                      }`}>
                        {run.triggered_by}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 text-gray-400 text-xs whitespace-nowrap">
                      {run.from_date && run.to_date
                        ? `${fmtDate(run.from_date)} – ${fmtDate(run.to_date)}`
                        : "—"}
                    </td>
                    <td className="px-4 py-2.5 text-right font-mono text-green-400">
                      {run.trades_new ?? "—"}
                    </td>
                    <td className="px-4 py-2.5 text-right font-mono text-blue-400">
                      {run.trades_updated ?? "—"}
                    </td>
                    <td className="px-4 py-2.5 text-xs text-red-300 max-w-xs truncate">
                      {run.error_message ?? ""}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ── Section 4: Open Positions ───────────────────────────────────────── */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
        <div className="px-5 py-3 border-b border-gray-800 flex items-center justify-between">
          <p className="text-xs text-gray-500 uppercase tracking-wider">Open Positions</p>
          {openPositions && openPositions.count > 0 && (
            <span className="text-xs text-gray-500">
              {openPositions.count} position{openPositions.count !== 1 ? "s" : ""} — as of last sync
              {status?.last_sync_at ? ` (${fmtAgo(status.last_sync_at)})` : ""}
            </span>
          )}
        </div>

        {!openPositions || openPositions.count === 0 ? (
          <p className="text-sm text-gray-500 px-5 py-4">
            No open positions found. Run a sync to capture current open positions from MT5.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-gray-500 text-xs uppercase tracking-wider border-b border-gray-800">
                  <th className="text-left px-4 py-2">Symbol</th>
                  <th className="text-left px-4 py-2">Side</th>
                  <th className="text-right px-4 py-2">Lots</th>
                  <th className="text-right px-4 py-2">Entry</th>
                  <th className="text-right px-4 py-2">Current</th>
                  <th className="text-right px-4 py-2">SL</th>
                  <th className="text-right px-4 py-2">TP</th>
                  <th className="text-right px-4 py-2">Float PnL</th>
                  <th className="text-left px-4 py-2">Opened</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800">
                {openPositions.positions.map((pos) => {
                  const pnlCls = pos.floating_pnl == null
                    ? "text-gray-400"
                    : pos.floating_pnl >= 0
                    ? "text-green-400"
                    : "text-red-400";
                  const sideCls = pos.direction === "long"
                    ? "text-blue-400"
                    : "text-orange-400";
                  return (
                    <tr key={pos.ticket} className="hover:bg-gray-800/30 transition-colors">
                      <td className="px-4 py-2.5 font-medium text-gray-100">{pos.symbol}</td>
                      <td className={`px-4 py-2.5 font-medium ${sideCls}`}>
                        {pos.direction.toUpperCase()}
                      </td>
                      <td className="px-4 py-2.5 text-right font-mono text-gray-300">{pos.lot_size}</td>
                      <td className="px-4 py-2.5 text-right font-mono text-gray-300">{pos.entry_price}</td>
                      <td className="px-4 py-2.5 text-right font-mono text-gray-200">
                        {pos.current_price ?? "—"}
                      </td>
                      <td className="px-4 py-2.5 text-right font-mono text-gray-500">
                        {pos.stop_loss ?? "—"}
                      </td>
                      <td className="px-4 py-2.5 text-right font-mono text-gray-500">
                        {pos.take_profit ?? "—"}
                      </td>
                      <td className={`px-4 py-2.5 text-right font-mono font-medium ${pnlCls}`}>
                        {pos.floating_pnl != null
                          ? `${pos.floating_pnl >= 0 ? "+" : ""}${pos.floating_pnl.toFixed(2)}`
                          : "—"}
                      </td>
                      <td className="px-4 py-2.5 text-xs text-gray-400 whitespace-nowrap">
                        {pos.opened_at ? new Date(pos.opened_at).toLocaleString() : "—"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
              {openPositions.count > 1 && (
                <tfoot>
                  <tr className="border-t border-gray-700 bg-gray-800/30">
                    <td colSpan={7} className="px-4 py-2 text-xs text-gray-500 text-right">
                      Total floating PnL
                    </td>
                    <td className={`px-4 py-2 text-right font-mono font-semibold text-sm ${
                      openPositions.positions.reduce((s, p) => s + (p.floating_pnl ?? 0), 0) >= 0
                        ? "text-green-400"
                        : "text-red-400"
                    }`}>
                      {(() => {
                        const total = openPositions.positions.reduce((s, p) => s + (p.floating_pnl ?? 0), 0);
                        return `${total >= 0 ? "+" : ""}${total.toFixed(2)}`;
                      })()}
                    </td>
                    <td />
                  </tr>
                </tfoot>
              )}
            </table>
          </div>
        )}
      </div>

      {/* ── Platform note ───────────────────────────────────────────────────── */}
      <div className="text-xs text-gray-600 space-y-1 pb-2">
        <p>
          MT5 sync requires Windows with MetaTrader5 installed:{" "}
          <code className="font-mono">pip install MetaTrader5</code>
        </p>
        <p>
          On Linux/Mac the sync will return an error — this is expected. The error is recorded in the
          run history above.
        </p>
        <p>
          After a successful sync, visit the{" "}
          <a href="/trades" className="text-blue-400 hover:underline">Trade Log</a> or{" "}
          <a href="/dashboard" className="text-blue-400 hover:underline">Dashboard</a> to see
          updated data.
        </p>
      </div>
    </div>
  );
}
