"use client";

import { useState } from "react";
import Link from "next/link";
import useSWR from "swr";
import { api, TradeListResponse } from "@/lib/api";
import { useAccount } from "@/components/AccountProvider";
import AccountSelector from "@/components/AccountSelector";
import Badge from "@/components/Badge";
import { fmtDateTime, fmtPnl, fmt, pnlColor } from "@/lib/utils";

const PAGE_SIZE = 50;

export default function TradesPage() {
  const { accountId, accounts, isLoadingAccounts } = useAccount();
  const [symbol, setSymbol] = useState("");
  const [result, setResult] = useState("");
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [page, setPage] = useState(1);

  // Helpers that reset pagination when a filter changes
  function setSymbolReset(v: string) { setSymbol(v); setPage(1); }
  function setResultReset(v: string) { setResult(v); setPage(1); }
  function setFromDateReset(v: string) { setFromDate(v); setPage(1); }
  function setToDateReset(v: string) { setToDate(v); setPage(1); }

  const swrKey = accountId
    ? `trades-${accountId}-${symbol}-${result}-${fromDate}-${toDate}-p${page}`
    : null;

  const { data, isLoading } = useSWR<TradeListResponse>(
    swrKey,
    () => api.listTrades(accountId!, {
      symbol: symbol || undefined,
      result: result || undefined,
      from_date: fromDate || undefined,
      to_date: toDate || undefined,
      page,
      page_size: PAGE_SIZE,
    })
  );

  const trades = data?.items ?? [];
  const total = data?.total ?? 0;
  const totalPages = data?.total_pages ?? 1;
  const hasFilters = !!(symbol || result || fromDate || toDate);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Trade Log</h1>
        <div className="flex items-center gap-3">
          {accountId && (
            <a
              href={api.exportTradesCsvUrl(accountId, {
                symbol: symbol || undefined,
                result: result || undefined,
                from_date: fromDate || undefined,
                to_date: toDate || undefined,
              })}
              download
              className="text-xs text-gray-400 hover:text-gray-200 bg-gray-800 border border-gray-700 rounded px-3 py-1.5 transition-colors whitespace-nowrap"
            >
              ↓ Export CSV
            </a>
          )}
          <AccountSelector />
        </div>
      </div>

      {/* Empty-state: no accounts exist yet */}
      {!isLoadingAccounts && accounts.length === 0 && (
        <div className="rounded-lg border border-gray-800 bg-gray-900 px-5 py-10 text-center space-y-1">
          <p className="text-gray-300 text-sm font-medium">No accounts yet</p>
          <p className="text-gray-500 text-xs">Create your first account on the Dashboard to start recording trades.</p>
          <Link href="/" className="inline-block mt-3 text-xs text-blue-400 hover:text-blue-300 transition-colors">
            → Go to Dashboard
          </Link>
        </div>
      )}

      {/* Empty-state: accounts exist but none selected */}
      {!isLoadingAccounts && accounts.length > 0 && !accountId && (
        <p className="text-gray-500 text-sm">Select an account above to view your trades.</p>
      )}

      {/* Filters — only shown when an account is selected */}
      {accountId && (
        <div className="flex flex-wrap gap-2 items-center">
          <input
            placeholder="Symbol (e.g. XAUUSD)"
            value={symbol}
            onChange={(e) => setSymbolReset(e.target.value.toUpperCase())}
            className="bg-gray-800 border border-gray-700 rounded-md px-3 py-1.5 text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:ring-1 focus:ring-blue-500 w-44"
          />
          <select
            value={result}
            onChange={(e) => setResultReset(e.target.value)}
            className="bg-gray-800 border border-gray-700 rounded-md px-3 py-1.5 text-sm text-gray-100 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            <option value="">All results</option>
            <option value="Win">Win</option>
            <option value="Loss">Loss</option>
            <option value="Breakeven">Breakeven</option>
          </select>
          <span className="text-xs text-gray-500">from</span>
          <input
            type="date"
            value={fromDate}
            onChange={(e) => setFromDateReset(e.target.value)}
            className="bg-gray-800 border border-gray-700 rounded-md px-2 py-1.5 text-sm text-gray-100 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
          <span className="text-xs text-gray-500">to</span>
          <input
            type="date"
            value={toDate}
            onChange={(e) => setToDateReset(e.target.value)}
            className="bg-gray-800 border border-gray-700 rounded-md px-2 py-1.5 text-sm text-gray-100 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
          {(fromDate || toDate) && (
            <button
              onClick={() => { setFromDateReset(""); setToDateReset(""); }}
              className="text-xs text-gray-400 hover:text-gray-200 bg-gray-800 border border-gray-700 rounded px-2 py-1.5"
            >Clear dates</button>
          )}
        </div>
      )}

      {accountId && isLoading && <p className="text-gray-500 text-sm">Loading…</p>}

      {/* Empty-state: account selected, filters active, no results */}
      {accountId && !isLoading && trades.length === 0 && hasFilters && (
        <p className="text-gray-500 text-sm">No trades match the current filters.</p>
      )}

      {/* Empty-state: account selected, no filters, no trades yet */}
      {accountId && !isLoading && trades.length === 0 && !hasFilters && (
        <div className="rounded-lg border border-dashed border-gray-700 px-5 py-10 text-center space-y-1">
          <p className="text-gray-300 text-sm font-medium">No trades yet</p>
          <p className="text-gray-500 text-xs">Import a CSV file or set up MT5 sync to record your first trade.</p>
          <div className="flex justify-center gap-4 mt-3">
            <Link href="/import" className="text-xs text-blue-400 hover:text-blue-300 transition-colors">→ Import CSV</Link>
            <Link href="/mt5-sync" className="text-xs text-blue-400 hover:text-blue-300 transition-colors">→ MT5 Sync</Link>
          </div>
        </div>
      )}

      {trades.length > 0 && (
        <div className="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-800 text-gray-500 text-xs uppercase tracking-wider">
                <th className="text-left px-4 py-3">Date</th>
                <th className="text-left px-4 py-3">Symbol</th>
                <th className="text-left px-4 py-3">Dir</th>
                <th className="text-left px-4 py-3">Setup</th>
                <th className="text-left px-4 py-3">Result</th>
                <th className="text-right px-4 py-3">Net PnL</th>
                <th className="text-right px-4 py-3">R</th>
                <th className="text-right px-4 py-3">Lots</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800">
              {trades.map((t) => (
                <tr key={t.trade_id} className="hover:bg-gray-800/50 transition-colors">
                  <td className="px-4 py-3 text-gray-400 whitespace-nowrap">
                    <Link href={`/trades/${t.trade_id}`} className="hover:text-blue-400">
                      {fmtDateTime(t.entry_datetime)}
                    </Link>
                  </td>
                  <td className="px-4 py-3 font-medium">{t.symbol ?? "—"}</td>
                  <td className="px-4 py-3 text-gray-400">{t.direction ?? "—"}</td>
                  <td className="px-4 py-3 text-gray-400 max-w-[120px] truncate">{t.setup_type ?? "—"}</td>
                  <td className="px-4 py-3">
                    {t.result ? (
                      <Badge
                        label={t.result}
                        variant={t.result as "win" | "loss" | "breakeven"}
                      />
                    ) : "—"}
                  </td>
                  <td className={`px-4 py-3 text-right font-mono ${pnlColor(t.net_pnl)}`}>
                    {fmtPnl(t.net_pnl)}
                  </td>
                  <td className={`px-4 py-3 text-right font-mono ${pnlColor(t.actual_r_multiple)}`}>
                    {fmt(t.actual_r_multiple)}
                  </td>
                  <td className="px-4 py-3 text-right text-gray-400 font-mono">
                    {fmt(t.lot_size, 2)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Pagination controls */}
      {total > 0 && (
        <div className="flex items-center justify-between text-sm">
          <span className="text-gray-500 text-xs">
            {total} trade{total !== 1 ? "s" : ""} total
            {totalPages > 1 && ` · page ${page} of ${totalPages}`}
          </span>
          {totalPages > 1 && (
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
                className="px-3 py-1.5 text-xs bg-gray-800 border border-gray-700 rounded-md text-gray-300 hover:bg-gray-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                ← Prev
              </button>
              <span className="text-xs text-gray-500 tabular-nums">
                {page} / {totalPages}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages}
                className="px-3 py-1.5 text-xs bg-gray-800 border border-gray-700 rounded-md text-gray-300 hover:bg-gray-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                Next →
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
