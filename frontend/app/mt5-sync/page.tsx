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
} from "@/lib/api";
import { useAccount } from "@/components/AccountProvider";
import AccountSelector from "@/components/AccountSelector";
import { fmtDateTime, fmtDate } from "@/lib/utils";

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

  // ── Config form state ────────────────────────────────────────────────────────
  const [login, setLogin] = useState("");
  const [server, setServer] = useState("");
  const [terminalPath, setTerminalPath] = useState("");
  const [utcOffset, setUtcOffset] = useState("2");
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

      // Refresh status and invalidate account-scoped caches
      await refreshStatus();
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
              <div className="grid grid-cols-4 gap-4">
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
