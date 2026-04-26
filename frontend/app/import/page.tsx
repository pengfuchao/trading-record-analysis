"use client";

import { useCallback, useRef, useState } from "react";
import Link from "next/link";
import { mutate } from "swr";
import { api, EnrichSLTPResponse, ImportPreviewResponse, ImportResponse, RecomputeResponse } from "@/lib/api";
import { useAccount } from "@/components/AccountProvider";
import AccountSelector from "@/components/AccountSelector";
import { fmtDateTime, fmtPnl, fmt, pnlColor } from "@/lib/utils";

type Stage = "idle" | "previewing" | "preview_ready" | "importing" | "done";

export default function ImportPage() {
  const { accountId } = useAccount();
  const fileRef = useRef<HTMLInputElement>(null);

  const [stage, setStage] = useState<Stage>("idle");
  const [isImporting, setIsImporting] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<ImportPreviewResponse | null>(null);
  const [result, setResult] = useState<ImportResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [strategy, setStrategy] = useState<"skip" | "update_broker">("skip");
  const [dragging, setDragging] = useState(false);
  const [recomputeState, setRecomputeState] = useState<"idle" | "running" | "done" | "error">("idle");
  const [recomputeResult, setRecomputeResult] = useState<RecomputeResponse | null>(null);
  const enrichFileRef = useRef<HTMLInputElement>(null);
  const [enrichState, setEnrichState] = useState<"idle" | "running" | "done" | "error">("idle");
  const [enrichResult, setEnrichResult] = useState<EnrichSLTPResponse | null>(null);
  const [enrichError, setEnrichError] = useState<string | null>(null);

  const handleFile = useCallback(
    async (f: File) => {
      if (!accountId) {
        setError("Select an account first.");
        return;
      }
      setFile(f);
      setError(null);
      setPreview(null);
      setResult(null);
      setStage("previewing");
      try {
        const data = await api.previewImport(accountId, f);
        setPreview(data);
        setStage("preview_ready");
      } catch (e: any) {
        setError(e.message ?? "Preview failed");
        setStage("idle");
      }
    },
    [accountId]
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragging(false);
      const f = e.dataTransfer.files[0];
      if (f) handleFile(f);
    },
    [handleFile]
  );

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) handleFile(f);
  };

  const handleImport = async () => {
    if (!accountId || !file) return;
    setStage("importing");
    setIsImporting(true);
    setError(null);
    try {
      const data = await api.importCsv(accountId, file, strategy);
      setResult(data);
      setStage("done");
      setIsImporting(false);
      // Invalidate all account-scoped SWR caches (keys include filter suffixes)
      const pfx = (p: string) => (k: unknown) => typeof k === "string" && k.startsWith(p);
      mutate(pfx(`trades-${accountId}`));
      mutate(pfx(`analytics-${accountId}`));
      mutate(pfx(`mistakes-${accountId}`));
      mutate(pfx(`ftmo-${accountId}`));
    } catch (e: any) {
      setError(e.message ?? "Import failed");
      setStage("preview_ready");
      setIsImporting(false);
    }
  };

  const handleRecompute = async () => {
    if (!accountId) return;
    setRecomputeState("running");
    try {
      const data = await api.recomputeDerived(accountId);
      setRecomputeResult(data);
      setRecomputeState("done");
      // Refresh caches — R values and session affect analytics and trade list
      const pfx = (p: string) => (k: unknown) => typeof k === "string" && k.startsWith(p);
      mutate(pfx(`trades-${accountId}`));
      mutate(pfx(`analytics-${accountId}`));
      mutate(pfx(`mistakes-${accountId}`));
      mutate(pfx(`ftmo-${accountId}`));
    } catch (e: any) {
      setError(e.message ?? "Recompute failed");
      setRecomputeState("error");
    }
  };

  const handleEnrich = async (f: File) => {
    if (!accountId) return;
    setEnrichState("running");
    setEnrichError(null);
    setEnrichResult(null);
    try {
      const data = await api.enrichSlTp(accountId, f);
      setEnrichResult(data);
      setEnrichState("done");
      // Refresh trade list and analytics — SL/TP/R may have changed
      const pfx = (p: string) => (k: unknown) => typeof k === "string" && k.startsWith(p);
      mutate(pfx(`trades-${accountId}`));
      mutate(pfx(`analytics-${accountId}`));
    } catch (e: any) {
      setEnrichError(e.message ?? "Enrichment failed");
      setEnrichState("error");
    } finally {
      if (enrichFileRef.current) enrichFileRef.current.value = "";
    }
  };

  const reset = () => {
    setStage("idle");
    setIsImporting(false);
    setFile(null);
    setPreview(null);
    setResult(null);
    setError(null);
    setRecomputeState("idle");
    setRecomputeResult(null);
    setEnrichState("idle");
    setEnrichResult(null);
    setEnrichError(null);
    if (fileRef.current) fileRef.current.value = "";
    if (enrichFileRef.current) enrichFileRef.current.value = "";
  };

  return (
    <div className="space-y-6 max-w-4xl">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Import MT4 / MT5 Statement</h1>
        <AccountSelector />
      </div>

      {/* Error banner */}
      {error && (
        <div className="bg-red-900/40 border border-red-700 text-red-300 text-sm px-4 py-3 rounded-md">
          {error}
        </div>
      )}

      {/* Done state */}
      {stage === "done" && result && (
        <div className="space-y-4">
          <div className="bg-green-900/30 border border-green-700 rounded-lg p-5 space-y-2">
            <p className="text-green-300 font-semibold">Import complete</p>
            <div className="grid grid-cols-3 gap-4 mt-3">
              <div className="text-center">
                <p className="text-2xl font-semibold text-green-400">{result.trades_new}</p>
                <p className="text-xs text-gray-500 mt-1">New trades</p>
              </div>
              <div className="text-center">
                <p className="text-2xl font-semibold text-blue-400">{result.trades_updated}</p>
                <p className="text-xs text-gray-500 mt-1">Updated</p>
              </div>
              <div className="text-center">
                <p className="text-2xl font-semibold text-gray-400">{result.trades_skipped}</p>
                <p className="text-xs text-gray-500 mt-1">Skipped</p>
              </div>
            </div>
            {result.validation_error_count > 0 && (
              <p className="text-yellow-400 text-sm mt-2">
                {result.validation_error_count} rows had validation errors and were skipped.
              </p>
            )}
          </div>

          {/* Recompute derived fields */}
          <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 space-y-2">
            <p className="text-xs text-gray-500 uppercase tracking-wider">Derived fields</p>
            <p className="text-xs text-gray-400">
              Recalculate price-based R and session for all trades in this account using the latest formulas.
              Manual enrichment fields are never overwritten.
            </p>
            {recomputeState === "idle" && (
              <button
                onClick={handleRecompute}
                className="text-sm text-blue-400 hover:text-blue-300 transition-colors"
              >
                Recompute R & session →
              </button>
            )}
            {recomputeState === "running" && (
              <span className="flex items-center gap-2 text-sm text-gray-400">
                <span className="w-3 h-3 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
                Recomputing…
              </span>
            )}
            {recomputeState === "done" && recomputeResult && (
              <p className="text-xs text-green-400">
                Done — {recomputeResult.trades_updated_r} R values updated
                {recomputeResult.trades_updated_session > 0
                  ? `, ${recomputeResult.trades_updated_session} sessions updated`
                  : ""}
                {" "}({recomputeResult.trades_processed} trades processed)
              </p>
            )}
            {recomputeState === "error" && (
              <p className="text-xs text-red-400">Recompute failed — see error above.</p>
            )}
          </div>

          <div className="flex gap-3">
            <Link href="/trades" className="bg-blue-600 hover:bg-blue-700 text-white text-sm px-4 py-2 rounded-md transition-colors">
              View Trade Log
            </Link>
            <button onClick={reset} className="text-gray-400 hover:text-gray-100 text-sm px-4 py-2 rounded-md transition-colors">
              Import Another File
            </button>
          </div>
        </div>
      )}

      {/* Upload zone (idle or preview ready) */}
      {(stage === "idle" || stage === "preview_ready") && (
        <div
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={handleDrop}
          onClick={() => fileRef.current?.click()}
          className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
            dragging
              ? "border-blue-500 bg-blue-900/10"
              : "border-gray-700 hover:border-gray-500"
          }`}
        >
          <input
            ref={fileRef}
            type="file"
            accept=".csv"
            className="hidden"
            onChange={handleInputChange}
          />
          <p className="text-gray-400 text-sm">
            {file
              ? `Selected: ${file.name} — click or drop to replace`
              : "Drop your MT4/MT5 CSV export here, or click to browse"}
          </p>
          <p className="text-gray-600 text-xs mt-1">Supports MT4 account history and MT5 trading history exports</p>
        </div>
      )}

      {/* Previewing spinner */}
      {stage === "previewing" && (
        <div className="flex items-center gap-3 py-4">
          <div className="w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
          <span className="text-gray-400 text-sm">Analyzing file…</span>
        </div>
      )}

      {/* Preview panel */}
      {stage === "preview_ready" && preview && (
        <div className="space-y-4">
          {/* Header summary */}
          <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
            <div className="flex items-center gap-4 flex-wrap">
              <span className="bg-blue-900/50 text-blue-300 text-xs font-semibold px-2.5 py-1 rounded">
                {preview.detected_platform}
              </span>
              <span className="text-sm text-gray-300">
                <span className="text-green-400 font-semibold">{preview.new_trade_count}</span> new trades
              </span>
              {preview.existing_trade_count > 0 && (
                <span className="text-sm text-gray-300">
                  <span className="text-yellow-400 font-semibold">{preview.existing_trade_count}</span> already in DB
                </span>
              )}
              {preview.validation_error_count > 0 && (
                <span className="text-sm text-gray-300">
                  <span className="text-red-400 font-semibold">{preview.validation_error_count}</span> validation errors
                </span>
              )}
              <span className="text-xs text-gray-500 ml-auto">
                {preview.total_rows_in_file} rows in file → {preview.trade_rows_parsed} trade rows parsed
              </span>
            </div>
          </div>

          {/* Duplicate strategy (only shown if there are existing trades) */}
          {preview.existing_trade_count > 0 && (
            <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 space-y-2">
              <p className="text-xs text-gray-500 uppercase tracking-wider">For existing trades</p>
              <label className="flex items-start gap-3 cursor-pointer">
                <input
                  type="radio"
                  name="strategy"
                  value="skip"
                  checked={strategy === "skip"}
                  onChange={() => setStrategy("skip")}
                  className="mt-0.5"
                />
                <div>
                  <p className="text-sm text-gray-100">Skip (recommended)</p>
                  <p className="text-xs text-gray-500">Keep existing trades unchanged — all setup tags, lessons, and enrichment are preserved</p>
                </div>
              </label>
              <label className="flex items-start gap-3 cursor-pointer">
                <input
                  type="radio"
                  name="strategy"
                  value="update_broker"
                  checked={strategy === "update_broker"}
                  onChange={() => setStrategy("update_broker")}
                  className="mt-0.5"
                />
                <div>
                  <p className="text-sm text-gray-100">Update broker fields</p>
                  <p className="text-xs text-gray-500">Refresh price, PnL, and execution data from CSV — manual enrichment fields are still preserved</p>
                </div>
              </label>
            </div>
          )}

          {/* Preview table */}
          {preview.preview_rows.length > 0 && (
            <div className="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
              <p className="text-xs text-gray-500 px-4 py-2 border-b border-gray-800">
                Preview — first {preview.preview_rows.length} trades
              </p>
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-gray-500 text-xs uppercase tracking-wider border-b border-gray-800">
                    <th className="text-left px-4 py-2">Entry Date</th>
                    <th className="text-left px-4 py-2">Symbol</th>
                    <th className="text-left px-4 py-2">Dir</th>
                    <th className="text-right px-4 py-2">Lots</th>
                    <th className="text-right px-4 py-2">Net PnL</th>
                    <th className="text-left px-4 py-2">Result</th>
                    <th className="text-left px-4 py-2">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-800">
                  {preview.preview_rows.map((row) => (
                    <tr
                      key={row.trade_id}
                      className={row.is_existing ? "bg-yellow-900/10" : ""}
                    >
                      <td className="px-4 py-2 text-gray-400 whitespace-nowrap">
                        {fmtDateTime(row.entry_datetime)}
                      </td>
                      <td className="px-4 py-2 font-medium">{row.symbol ?? "—"}</td>
                      <td className="px-4 py-2 text-gray-400">{row.direction ?? "—"}</td>
                      <td className="px-4 py-2 text-right font-mono text-gray-300">
                        {fmt(row.lot_size)}
                      </td>
                      <td className={`px-4 py-2 text-right font-mono ${pnlColor(row.net_pnl)}`}>
                        {fmtPnl(row.net_pnl)}
                      </td>
                      <td className="px-4 py-2 text-gray-400 capitalize">{row.result ?? "—"}</td>
                      <td className="px-4 py-2">
                        {row.is_existing ? (
                          <span className="text-xs bg-yellow-900/40 text-yellow-300 px-2 py-0.5 rounded">Existing</span>
                        ) : (
                          <span className="text-xs bg-green-900/40 text-green-300 px-2 py-0.5 rounded">New</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Validation errors */}
          {preview.validation_errors.length > 0 && (
            <div className="bg-red-900/20 border border-red-800 rounded-lg p-4">
              <p className="text-xs text-red-400 uppercase tracking-wider mb-2">Validation errors (these rows will be skipped)</p>
              <ul className="space-y-1">
                {preview.validation_errors.slice(0, 10).map((e, i) => (
                  <li key={i} className="text-xs text-red-300">
                    {e.trade_id ? `Trade ${e.trade_id}` : "Row"}{e.field ? ` · ${e.field}` : ""}: {e.message}
                  </li>
                ))}
                {preview.validation_errors.length > 10 && (
                  <li className="text-xs text-red-500">…and {preview.validation_errors.length - 10} more</li>
                )}
              </ul>
            </div>
          )}

          {/* Import button */}
          <div className="flex items-center gap-4">
            <button
              onClick={handleImport}
              disabled={preview.new_trade_count === 0 && strategy === "skip" && preview.existing_trade_count > 0}
              className="bg-blue-600 hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm px-5 py-2.5 rounded-md transition-colors font-medium"
            >
              {isImporting ? (
                <span className="flex items-center gap-2">
                  <span className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  Importing…
                </span>
              ) : (
                `Import ${preview.new_trade_count + (strategy === "update_broker" ? preview.existing_trade_count : 0)} trades`
              )}
            </button>
            <button onClick={reset} className="text-gray-500 hover:text-gray-300 text-sm transition-colors">
              Cancel
            </button>
            {preview.new_trade_count === 0 && strategy === "skip" && preview.existing_trade_count > 0 && (
              <p className="text-yellow-400 text-xs">All trades already imported. Switch to "Update broker fields" to re-sync.</p>
            )}
          </div>
        </div>
      )}

      {/* ── Enrich SL/TP from CSV ─────────────────────────────────────────── */}
      {accountId && (
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-5 space-y-3">
          <div>
            <p className="text-sm font-medium text-gray-200">Enrich SL / TP from CSV</p>
            <p className="text-xs text-gray-500 mt-1 leading-relaxed">
              Upload an FTMO / MT5 / MT4 exported statement to fill missing stop_loss and
              take_profit for trades already in the log. R is recomputed automatically.
              Existing values are never overwritten. No duplicate trades are created.
            </p>
          </div>

          {enrichError && (
            <p className="text-xs text-red-400">{enrichError}</p>
          )}

          {enrichState === "idle" || enrichState === "error" ? (
            <label className="cursor-pointer inline-flex items-center gap-2 text-sm text-blue-400 hover:text-blue-300 transition-colors">
              <input
                ref={enrichFileRef}
                type="file"
                accept=".csv"
                className="sr-only"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) handleEnrich(f);
                }}
              />
              Upload CSV to enrich →
            </label>
          ) : enrichState === "running" ? (
            <span className="flex items-center gap-2 text-sm text-gray-400">
              <span className="w-3 h-3 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
              Enriching…
            </span>
          ) : enrichResult && (
            <div className="space-y-3">
              <div className="grid grid-cols-3 sm:grid-cols-4 gap-3">
                <div className="text-center">
                  <p className="text-xl font-semibold text-green-400">{enrichResult.sl_filled}</p>
                  <p className="text-xs text-gray-500 mt-0.5">SL filled</p>
                </div>
                <div className="text-center">
                  <p className="text-xl font-semibold text-green-400">{enrichResult.tp_filled}</p>
                  <p className="text-xs text-gray-500 mt-0.5">TP filled</p>
                </div>
                <div className="text-center">
                  <p className="text-xl font-semibold text-blue-400">{enrichResult.r_computed}</p>
                  <p className="text-xs text-gray-500 mt-0.5">R computed</p>
                </div>
                <div className="text-center">
                  <p className="text-xl font-semibold text-gray-400">{enrichResult.not_in_db}</p>
                  <p className="text-xs text-gray-500 mt-0.5">Not in DB</p>
                </div>
              </div>
              <p className="text-xs text-gray-500">
                {enrichResult.rows_in_csv} rows read ({enrichResult.detected_platform}) ·{" "}
                {enrichResult.matched} matched · {enrichResult.already_had_sl} already had SL
              </p>
              <button
                onClick={() => { setEnrichState("idle"); setEnrichResult(null); }}
                className="text-xs text-gray-500 hover:text-gray-300 transition-colors"
              >
                Enrich another file
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
