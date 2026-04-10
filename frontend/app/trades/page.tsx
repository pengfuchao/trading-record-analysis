"use client";

import { useState } from "react";
import Link from "next/link";
import useSWR from "swr";
import { api } from "@/lib/api";
import { useAccount } from "@/components/AccountProvider";
import AccountSelector from "@/components/AccountSelector";
import Badge from "@/components/Badge";
import { fmtDateTime, fmtPnl, fmt, pnlColor } from "@/lib/utils";

export default function TradesPage() {
  const { accountId } = useAccount();
  const [symbol, setSymbol] = useState("");
  const [result, setResult] = useState("");

  const { data: trades = [], isLoading } = useSWR(
    accountId ? `trades-${accountId}-${symbol}-${result}` : null,
    () => api.listTrades(accountId, { symbol: symbol || undefined, result: result || undefined })
  );

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Trade Log</h1>
        <AccountSelector />
      </div>

      {/* Filters */}
      <div className="flex gap-3">
        <input
          placeholder="Symbol (e.g. XAUUSD)"
          value={symbol}
          onChange={(e) => setSymbol(e.target.value.toUpperCase())}
          className="bg-gray-800 border border-gray-700 rounded-md px-3 py-1.5 text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:ring-1 focus:ring-blue-500 w-44"
        />
        <select
          value={result}
          onChange={(e) => setResult(e.target.value)}
          className="bg-gray-800 border border-gray-700 rounded-md px-3 py-1.5 text-sm text-gray-100 focus:outline-none focus:ring-1 focus:ring-blue-500"
        >
          <option value="">All results</option>
          <option value="win">Win</option>
          <option value="loss">Loss</option>
          <option value="breakeven">Breakeven</option>
        </select>
      </div>

      {isLoading && <p className="text-gray-500 text-sm">Loading…</p>}

      {!isLoading && trades.length === 0 && (
        <p className="text-gray-500 text-sm">No trades found.</p>
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
    </div>
  );
}
