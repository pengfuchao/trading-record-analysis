"use client";

import { useState } from "react";
import useSWR from "swr";
import {
  AreaChart, Area, LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine,
} from "recharts";
import { api } from "@/lib/api";
import { useAccount } from "@/components/AccountProvider";
import AccountSelector from "@/components/AccountSelector";
import StatCard from "@/components/StatCard";
import { fmt, fmtPnl, fmtPct } from "@/lib/utils";

// ── Chart tooltip formatters ───────────────────────────────────────────────────

function fmtDate(iso: string) {
  try { return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" }); }
  catch { return iso; }
}

function EquityCurveChart({ equity, dates }: { equity: number[]; dates: string[] }) {
  if (!equity.length) return <p className="text-xs text-gray-500">No data</p>;
  const data = equity.map((v, i) => ({ date: dates[i] ? fmtDate(dates[i]) : `T${i}`, equity: v }));
  const min = Math.min(...equity);
  const max = Math.max(...equity);
  const padding = (max - min) * 0.08 || 10;
  const color = equity[equity.length - 1] >= equity[0] ? "#34d399" : "#f87171";

  return (
    <ResponsiveContainer width="100%" height={200}>
      <AreaChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id="equityGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%"  stopColor={color} stopOpacity={0.25} />
            <stop offset="95%" stopColor={color} stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
        <XAxis
          dataKey="date"
          tick={{ fontSize: 10, fill: "#6b7280" }}
          interval="preserveStartEnd"
        />
        <YAxis
          tick={{ fontSize: 10, fill: "#6b7280" }}
          domain={[min - padding, max + padding]}
          width={60}
          tickFormatter={(v: number) => fmtPnl(v).replace(/[\s$]/g, "")}
        />
        <Tooltip
          contentStyle={{ background: "#111827", border: "1px solid #374151", fontSize: 12 }}
          formatter={(v: number) => [fmtPnl(v), "Balance"]}
        />
        <Area
          type="monotone"
          dataKey="equity"
          stroke={color}
          strokeWidth={1.5}
          fill="url(#equityGrad)"
          dot={false}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}

function DrawdownChart({ drawdown, dates }: { drawdown: number[]; dates: string[] }) {
  if (!drawdown.length) return <p className="text-xs text-gray-500">No data</p>;
  const data = drawdown.map((v, i) => ({ date: dates[i] ? fmtDate(dates[i]) : `T${i}`, dd: v }));
  const minDD = Math.min(...drawdown);

  return (
    <ResponsiveContainer width="100%" height={140}>
      <AreaChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id="ddGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%"  stopColor="#f87171" stopOpacity={0.3} />
            <stop offset="95%" stopColor="#f87171" stopOpacity={0.03} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
        <XAxis dataKey="date" tick={{ fontSize: 10, fill: "#6b7280" }} interval="preserveStartEnd" />
        <YAxis
          tick={{ fontSize: 10, fill: "#6b7280" }}
          domain={[minDD * 1.1, 0]}
          width={60}
          tickFormatter={(v: number) => fmtPnl(v).replace(/[\s$]/g, "")}
        />
        <ReferenceLine y={0} stroke="#6b7280" strokeDasharray="3 3" />
        <Tooltip
          contentStyle={{ background: "#111827", border: "1px solid #374151", fontSize: 12 }}
          formatter={(v: number) => [fmtPnl(v), "Drawdown"]}
        />
        <Area
          type="monotone"
          dataKey="dd"
          stroke="#f87171"
          strokeWidth={1.5}
          fill="url(#ddGrad)"
          dot={false}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}

// ── Date helpers ───────────────────────────────────────────────────────────────

function todayISO() {
  return new Date().toISOString().slice(0, 10);
}

function nDaysAgoISO(n: number) {
  const d = new Date();
  d.setDate(d.getDate() - n);
  return d.toISOString().slice(0, 10);
}

// ── Main dashboard ─────────────────────────────────────────────────────────────

export default function DashboardPage() {
  const { accountId } = useAccount();
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");

  const { data: analytics, isLoading } = useSWR(
    accountId ? `analytics-${accountId}-${fromDate}-${toDate}` : null,
    () => api.getAnalytics(accountId, {
      from_date: fromDate || undefined,
      to_date: toDate || undefined,
    })
  );
  const { data: mistakes } = useSWR(
    accountId ? `mistakes-${accountId}-${fromDate}-${toDate}` : null,
    () => api.getMistakes(accountId, {
      from_date: fromDate || undefined,
      to_date: toDate || undefined,
    })
  );

  const hasEquity = analytics?.equity_curve && analytics.equity_curve.length > 1;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Account Dashboard</h1>
        <AccountSelector />
      </div>

      {/* Date range filter */}
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs text-gray-500 uppercase tracking-wider">Period:</span>
        <input
          type="date"
          value={fromDate}
          onChange={(e) => setFromDate(e.target.value)}
          className="bg-gray-800 border border-gray-700 rounded px-2 py-1 text-xs text-gray-100 focus:outline-none focus:border-blue-500"
        />
        <span className="text-xs text-gray-500">—</span>
        <input
          type="date"
          value={toDate}
          onChange={(e) => setToDate(e.target.value)}
          className="bg-gray-800 border border-gray-700 rounded px-2 py-1 text-xs text-gray-100 focus:outline-none focus:border-blue-500"
        />
        <button
          onClick={() => { setFromDate(nDaysAgoISO(6)); setToDate(todayISO()); }}
          className="text-xs text-gray-400 hover:text-gray-200 bg-gray-800 border border-gray-700 rounded px-2 py-1"
        >7d</button>
        <button
          onClick={() => { setFromDate(nDaysAgoISO(29)); setToDate(todayISO()); }}
          className="text-xs text-gray-400 hover:text-gray-200 bg-gray-800 border border-gray-700 rounded px-2 py-1"
        >30d</button>
        <button
          onClick={() => { setFromDate(""); setToDate(""); }}
          className="text-xs text-gray-400 hover:text-gray-200 bg-gray-800 border border-gray-700 rounded px-2 py-1"
        >All time</button>
        {(fromDate || toDate) && (
          <span className="text-xs text-blue-400">filtered</span>
        )}
      </div>

      {!accountId && (
        <p className="text-gray-500 text-sm">No account selected. Connect a broker or import trades first.</p>
      )}

      {accountId && isLoading && (
        <p className="text-gray-500 text-sm">Loading…</p>
      )}

      {analytics && (
        <>
          {/* ── Account summary ─────────────────────────────────────────────── */}
          <section>
            <h2 className="text-xs uppercase tracking-wider text-gray-500 mb-3">Account</h2>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <StatCard label="Starting Balance" value={fmtPnl(analytics.starting_balance)} />
              <StatCard
                label="Current Balance"
                value={fmtPnl(analytics.current_balance)}
                color={analytics.current_balance != null && analytics.starting_balance != null && analytics.current_balance >= analytics.starting_balance ? "green" : "red"}
              />
              <StatCard
                label="Total Return"
                value={fmtPct(analytics.total_return_pct != null ? analytics.total_return_pct / 100 : null)}
                color={analytics.total_return_pct != null && analytics.total_return_pct >= 0 ? "green" : "red"}
              />
              <StatCard
                label="Total PnL"
                value={fmtPnl(analytics.total_net_pnl)}
                color={analytics.total_net_pnl != null && analytics.total_net_pnl >= 0 ? "green" : "red"}
              />
            </div>
          </section>

          {/* ── Equity curve ──────────────────────────────────────────────────── */}
          {hasEquity && (
            <section>
              <h2 className="text-xs uppercase tracking-wider text-gray-500 mb-3">Equity Curve</h2>
              <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
                <EquityCurveChart
                  equity={analytics.equity_curve}
                  dates={analytics.trade_dates}
                />
              </div>
            </section>
          )}

          {/* ── Drawdown curve ────────────────────────────────────────────────── */}
          {hasEquity && analytics.drawdown_curve.some((d) => d < 0) && (
            <section>
              <h2 className="text-xs uppercase tracking-wider text-gray-500 mb-3">Drawdown</h2>
              <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
                <DrawdownChart
                  drawdown={analytics.drawdown_curve}
                  dates={analytics.trade_dates}
                />
                <div className="flex gap-4 mt-2">
                  <span className="text-xs text-gray-500">
                    Max DD: <span className="text-red-400">{fmtPct(analytics.max_drawdown_pct != null ? analytics.max_drawdown_pct / 100 : null)}</span>
                  </span>
                  <span className="text-xs text-gray-500">
                    Max DD (vs balance): <span className="text-red-400">{fmtPct(analytics.max_drawdown_pct_of_starting_balance != null ? analytics.max_drawdown_pct_of_starting_balance / 100 : null)}</span>
                  </span>
                  <span className="text-xs text-gray-500">
                    Worst Day: <span className="text-red-400">{fmtPnl(analytics.daily_drawdown)}</span>
                  </span>
                </div>
              </div>
            </section>
          )}

          {/* ── Performance ──────────────────────────────────────────────────── */}
          <section>
            <h2 className="text-xs uppercase tracking-wider text-gray-500 mb-3">Performance</h2>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <StatCard label="Total Trades"    value={analytics.total_trades} />
              <StatCard label="Win Rate"        value={fmtPct(analytics.win_rate)}       sub="incl. breakevens"    color="blue" />
              <StatCard label="Win Rate (ex BE)" value={fmtPct(analytics.win_rate_ex_be)} sub="wins ÷ (wins+losses)" color="blue" />
              <StatCard label="Profit Factor"   value={fmt(analytics.profit_factor)}     color="blue" />
              <StatCard label="Expectancy"      value={fmt(analytics.expectancy)}         sub="avg $ per trade" />
              <StatCard label="Avg Win"         value={fmtPnl(analytics.average_win)}    color="green" />
              <StatCard label="Avg Loss"        value={fmtPnl(analytics.average_loss)}   color="red" />
              <StatCard label="Avg R"           value={fmt(analytics.average_r_multiple)} sub="price-based R" />
            </div>
          </section>

          {/* ── Risk ─────────────────────────────────────────────────────────── */}
          <section>
            <h2 className="text-xs uppercase tracking-wider text-gray-500 mb-3">Risk</h2>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <StatCard label="Max Drawdown"       value={fmtPnl(analytics.max_drawdown)}               sub="peak-to-trough $"     color="red" />
              <StatCard label="Max DD % (balance)" value={fmtPct(analytics.max_drawdown_pct_of_starting_balance != null ? analytics.max_drawdown_pct_of_starting_balance / 100 : null)} sub="FTMO-style"  color="red" />
              <StatCard label="Worst Day PnL"      value={fmtPnl(analytics.daily_drawdown)}             sub="closed trades only"   color="red" />
              <StatCard label="Worst Week PnL"     value={fmtPnl(analytics.weekly_drawdown)}            sub="closed trades only"   color="red" />
              <StatCard label="Largest Win"        value={fmtPnl(analytics.largest_win)}                color="green" />
              <StatCard label="Largest Loss"       value={fmtPnl(analytics.largest_loss)}               color="red" />
              <StatCard label="Max Consec. Wins"   value={analytics.max_consecutive_wins ?? "—"}        color="green" />
              <StatCard label="Max Consec. Losses" value={analytics.max_consecutive_losses ?? "—"}      color="red" />
              <StatCard label="Payoff Ratio"       value={fmt(analytics.payoff_ratio)} />
              <StatCard label="Sharpe"             value={fmt(analytics.sharpe_ratio)} />
            </div>
          </section>
        </>
      )}

      {/* ── Top mistakes ──────────────────────────────────────────────────────── */}
      {mistakes && mistakes.ranked_by_cost.length > 0 && (
        <section>
          <h2 className="text-xs uppercase tracking-wider text-gray-500 mb-3">Top Mistakes by Cost</h2>
          <div className="bg-gray-900 border border-gray-800 rounded-lg divide-y divide-gray-800">
            {mistakes.ranked_by_cost.slice(0, 5).map((tag) => {
              const s = mistakes.by_mistake[tag];
              return (
                <div key={tag} className="flex items-center justify-between px-4 py-3">
                  <div>
                    <span className="text-sm text-gray-100">{tag.replace(/_/g, " ")}</span>
                    <span className="ml-2 text-xs text-gray-500">{s.occurrence_count}× occurrences</span>
                  </div>
                  <span className="text-sm font-medium text-red-400">{fmtPnl(s.total_cost)}</span>
                </div>
              );
            })}
          </div>
        </section>
      )}
    </div>
  );
}
