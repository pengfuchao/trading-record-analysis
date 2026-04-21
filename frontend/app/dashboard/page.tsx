"use client";

import { useState } from "react";
import useSWR, { mutate as globalMutate } from "swr";
import {
  AreaChart, Area, LineChart, Line, ComposedChart, Bar, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine,
} from "recharts";
import { api, Account, FtmoStatus, MT5SyncStatus, PlanAdherenceGroup, PlanAdherenceResponse, RRComparisonResponse, RRTrendBucket, RRTrendReportResponse, SegmentRow, SegmentAnalyticsResponse } from "@/lib/api";
import { useAccount } from "@/components/AccountProvider";
import AccountSelector from "@/components/AccountSelector";
import StatCard from "@/components/StatCard";
import { fmt, fmtPnl, fmtPct, fmtAgo } from "@/lib/utils";

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

// ── Edit account modal ────────────────────────────────────────────────────────

function EditAccountModal({
  account,
  onClose,
  onSaved,
}: {
  account: Account;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [broker, setBroker] = useState(account.broker);
  const [currency, setCurrency] = useState(account.account_currency);
  const [platform, setPlatform] = useState(account.platform);
  const [startingBalance, setStartingBalance] = useState(
    account.starting_balance != null ? String(account.starting_balance) : ""
  );
  const [propFirm, setPropFirm] = useState(account.prop_firm ?? "");
  const [challengePhase, setChallengePhase] = useState(account.challenge_phase ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSave() {
    setSaving(true);
    setError(null);
    try {
      const body: Record<string, unknown> = {};
      if (broker.trim()) body.broker = broker.trim();
      if (currency.trim()) body.account_currency = currency.trim().toUpperCase();
      if (platform) body.platform = platform;
      const bal = parseFloat(startingBalance);
      if (startingBalance.trim() !== "" && !isNaN(bal)) body.starting_balance = bal;
      // prop_firm: send always so empty string clears it
      body.prop_firm = propFirm.trim() || null;
      if (challengePhase) body.challenge_phase = challengePhase;

      await api.updateAccount(account.account_id, body as Partial<Account>);
      onSaved();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  const inputCls = "w-full bg-gray-800 border border-gray-700 rounded px-2 py-1.5 text-sm text-gray-100 focus:outline-none focus:border-blue-500";
  const labelCls = "block text-xs text-gray-500 uppercase tracking-wider mb-0.5";

  return (
    /* Backdrop */
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="bg-gray-950 border border-gray-700 rounded-xl shadow-2xl w-full max-w-md mx-4 p-6 space-y-5">
        {/* Header */}
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-gray-100">Edit Account</h2>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-300 text-lg leading-none">✕</button>
        </div>

        <p className="text-xs text-gray-500 -mt-2">
          Account ID: <span className="font-mono text-gray-400">{account.account_id}</span>
        </p>

        {/* Fields */}
        <div className="space-y-3">
          <div>
            <label className={labelCls}>Starting Balance</label>
            <input
              type="number"
              step="0.01"
              value={startingBalance}
              onChange={(e) => setStartingBalance(e.target.value)}
              placeholder="e.g. 10000"
              className={inputCls}
            />
            <p className="text-xs text-gray-600 mt-0.5">Required for FTMO panel and Total Return %</p>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className={labelCls}>Broker</label>
              <input value={broker} onChange={(e) => setBroker(e.target.value)} className={inputCls} />
            </div>
            <div>
              <label className={labelCls}>Currency</label>
              <input value={currency} onChange={(e) => setCurrency(e.target.value)} placeholder="USD" className={inputCls} />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className={labelCls}>Platform</label>
              <select value={platform} onChange={(e) => setPlatform(e.target.value)} className={inputCls}>
                <option value="MT4">MT4</option>
                <option value="MT5">MT5</option>
              </select>
            </div>
            <div>
              <label className={labelCls}>Challenge Phase</label>
              <select value={challengePhase} onChange={(e) => setChallengePhase(e.target.value)} className={inputCls}>
                <option value="">— unset —</option>
                <option value="Phase1">Phase 1</option>
                <option value="Phase2">Phase 2</option>
                <option value="Funded">Funded</option>
                <option value="Live">Live</option>
              </select>
            </div>
          </div>

          <div>
            <label className={labelCls}>Prop Firm</label>
            <input value={propFirm} onChange={(e) => setPropFirm(e.target.value)} placeholder="e.g. FTMO" className={inputCls} />
          </div>
        </div>

        {error && (
          <div className="bg-red-900/40 border border-red-700 text-red-300 text-xs px-3 py-2 rounded">
            {error}
          </div>
        )}

        <div className="flex gap-3 pt-1">
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-4 py-2 text-sm bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded transition-colors"
          >
            {saving ? "Saving…" : "Save Changes"}
          </button>
          <button
            onClick={onClose}
            disabled={saving}
            className="px-4 py-2 text-sm bg-gray-700 hover:bg-gray-600 text-gray-200 rounded transition-colors"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}

// ── FTMO status helpers ────────────────────────────────────────────────────────

const STATUS_STYLES = {
  SAFE:    { text: "text-green-400",  bar: "bg-green-500",  badge: "bg-green-900/40 border border-green-700 text-green-300" },
  AT_RISK: { text: "text-yellow-400", bar: "bg-yellow-500", badge: "bg-yellow-900/40 border border-yellow-700 text-yellow-300" },
  BREACHED:{ text: "text-red-400",    bar: "bg-red-500",    badge: "bg-red-900/40 border border-red-700 text-red-300" },
  UNKNOWN: { text: "text-gray-400",   bar: "bg-gray-500",   badge: "bg-gray-700/40 border border-gray-600 text-gray-400" },
} as const;
type StatusKey = keyof typeof STATUS_STYLES;

function statusStyle(s: string) {
  return STATUS_STYLES[(s as StatusKey) in STATUS_STYLES ? (s as StatusKey) : "UNKNOWN"];
}

function clamp01(v: number) { return Math.min(1, Math.max(0, v)); }

function FtmoBar({ fraction, status }: { fraction: number; status: string }) {
  const pct = clamp01(fraction) * 100;
  const style = statusStyle(status);
  return (
    <div className="w-full bg-gray-700 rounded-full h-1.5 mt-1.5">
      <div className={`h-1.5 rounded-full transition-all ${style.bar}`} style={{ width: `${pct.toFixed(1)}%` }} />
    </div>
  );
}

function FtmoPanel({
  ftmo,
  dailyLimitPct,
  maxLimitPct,
  onDailyLimit,
  onMaxLimit,
}: {
  ftmo: FtmoStatus;
  dailyLimitPct: string;
  maxLimitPct: string;
  onDailyLimit: (v: string) => void;
  onMaxLimit: (v: string) => void;
}) {
  const accountStyle = statusStyle(ftmo.account_status);

  // Daily loss progress: how much of the limit has been consumed
  const dailyUsedPct = Math.max(0, ftmo.daily_loss_used_pct ?? 0);
  const dailyFraction = ftmo.daily_loss_limit_pct > 0
    ? dailyUsedPct / ftmo.daily_loss_limit_pct
    : 0;

  // Overall drawdown progress
  const overallUsedPct = Math.abs(ftmo.current_max_drawdown_pct ?? 0);
  const overallFraction = ftmo.max_loss_limit_pct > 0
    ? overallUsedPct / ftmo.max_loss_limit_pct
    : 0;

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 space-y-4">
      {/* Header row */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className={`text-sm font-medium ${accountStyle.text}`}>
            Account: {ftmo.account_status}
          </span>
          {ftmo.daily_status !== ftmo.account_status && (
            <span className="text-xs text-gray-500">Daily: {ftmo.daily_status}</span>
          )}
          {ftmo.overall_status !== ftmo.account_status && (
            <span className="text-xs text-gray-500">Overall: {ftmo.overall_status}</span>
          )}
        </div>
        {/* Limit settings */}
        <div className="flex items-center gap-2 text-xs text-gray-500">
          <label>Daily</label>
          <input
            type="number"
            min="0.1" max="20" step="0.5"
            value={dailyLimitPct}
            onChange={(e) => onDailyLimit(e.target.value)}
            className="w-14 bg-gray-800 border border-gray-700 rounded px-1.5 py-0.5 text-gray-100 focus:outline-none focus:border-blue-500 text-xs"
          />
          <span>%</span>
          <label className="ml-2">Max</label>
          <input
            type="number"
            min="0.1" max="30" step="0.5"
            value={maxLimitPct}
            onChange={(e) => onMaxLimit(e.target.value)}
            className="w-14 bg-gray-800 border border-gray-700 rounded px-1.5 py-0.5 text-gray-100 focus:outline-none focus:border-blue-500 text-xs"
          />
          <span>%</span>
        </div>
      </div>

      {/* Two-column metrics */}
      <div className="grid grid-cols-2 gap-4">
        {/* Daily loss */}
        <div>
          <p className="text-xs text-gray-500 uppercase tracking-wider mb-2">Daily Loss</p>
          <div className="space-y-1">
            <div className="flex items-baseline justify-between">
              <span className="text-xs text-gray-400">Today</span>
              <span className={`text-sm font-mono ${ftmo.today_pnl < 0 ? "text-red-400" : "text-green-400"}`}>
                {fmtPnl(ftmo.today_pnl)}
              </span>
            </div>
            <div className="flex items-baseline justify-between">
              <span className="text-xs text-gray-500">Limit</span>
              <span className="text-xs text-gray-400">
                {ftmo.daily_loss_limit_pct}%
                {ftmo.daily_loss_limit_abs != null && ` (${fmtPnl(ftmo.daily_loss_limit_abs)})`}
              </span>
            </div>
            <FtmoBar fraction={dailyFraction} status={ftmo.daily_status} />
            <div className="flex items-baseline justify-between">
              <span className={`text-xs ${statusStyle(ftmo.daily_status).text}`}>
                {(dailyUsedPct).toFixed(2)}% used
              </span>
              {ftmo.daily_loss_remaining != null && (
                <span className="text-xs text-gray-500">
                  {fmtPnl(ftmo.daily_loss_remaining)} left
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Overall drawdown */}
        <div>
          <p className="text-xs text-gray-500 uppercase tracking-wider mb-2">Max Drawdown</p>
          <div className="space-y-1">
            <div className="flex items-baseline justify-between">
              <span className="text-xs text-gray-400">Current DD</span>
              <span className={`text-sm font-mono ${(ftmo.current_max_drawdown ?? 0) < 0 ? "text-red-400" : "text-gray-400"}`}>
                {ftmo.current_max_drawdown != null ? fmtPnl(ftmo.current_max_drawdown) : "—"}
              </span>
            </div>
            <div className="flex items-baseline justify-between">
              <span className="text-xs text-gray-500">Limit</span>
              <span className="text-xs text-gray-400">
                {ftmo.max_loss_limit_pct}%
                {ftmo.max_loss_limit_abs != null && ` (${fmtPnl(ftmo.max_loss_limit_abs)})`}
              </span>
            </div>
            <FtmoBar fraction={overallFraction} status={ftmo.overall_status} />
            <div className="flex items-baseline justify-between">
              <span className={`text-xs ${statusStyle(ftmo.overall_status).text}`}>
                {overallUsedPct.toFixed(2)}% used
              </span>
              {ftmo.max_loss_remaining != null && (
                <span className="text-xs text-gray-500">
                  {fmtPnl(ftmo.max_loss_remaining)} left
                </span>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Plan adherence panel ──────────────────────────────────────────────────────

function GroupStats({ g, label, color }: { g: PlanAdherenceGroup; label: string; color: "blue" | "orange" | "green" | "red" }) {
  const colorMap = {
    blue:   "text-blue-400",
    orange: "text-orange-400",
    green:  "text-green-400",
    red:    "text-red-400",
  };
  const labelColor = colorMap[color];
  const pnlColor = (g.avg_pnl ?? 0) >= 0 ? "text-green-400" : "text-red-400";
  const wr = g.win_rate != null ? `${(g.win_rate * 100).toFixed(1)}%` : "—";
  const avgPnl = g.avg_pnl != null ? fmtPnl(g.avg_pnl) : "—";
  const totalPnl = fmtPnl(g.total_pnl);
  const pf = g.profit_factor != null ? g.profit_factor.toFixed(2) : "—";

  return (
    <div className="space-y-1.5">
      <p className={`text-xs font-medium uppercase tracking-wider ${labelColor}`}>{label} ({g.count})</p>
      <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
        <span className="text-gray-500">Win rate</span>
        <span className="text-gray-100 font-mono">{wr}</span>
        <span className="text-gray-500">Avg PnL</span>
        <span className={`font-mono ${pnlColor}`}>{avgPnl}</span>
        <span className="text-gray-500">Total PnL</span>
        <span className={`font-mono ${(g.total_pnl ?? 0) >= 0 ? "text-green-400" : "text-red-400"}`}>{totalPnl}</span>
        <span className="text-gray-500">Prof. factor</span>
        <span className="text-gray-100 font-mono">{pf}</span>
      </div>
    </div>
  );
}

// ── Planned R:R vs Realized R panel ──────────────────────────────────────────

function RRComparisonPanel({ rr }: { rr: RRComparisonResponse }) {
  const shortfallColor =
    rr.avg_r_shortfall == null ? "text-gray-400"
    : rr.avg_r_shortfall >= 0   ? "text-green-400"
    : rr.avg_r_shortfall >= -0.5 ? "text-yellow-400"
    : "text-red-400";

  const realizationColor =
    rr.realization_pct == null ? "text-gray-400"
    : rr.realization_pct >= 90  ? "text-green-400"
    : rr.realization_pct >= 60  ? "text-yellow-400"
    : "text-red-400";

  const fmt2 = (v: number | undefined, sign = false) =>
    v == null ? "—" : sign ? `${v >= 0 ? "+" : ""}${v.toFixed(2)}R` : `${v.toFixed(2)}R`;

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-xs text-gray-500 uppercase tracking-wider">
          Planned R:R vs Realized R
        </p>
        <span className="text-xs text-gray-600">{rr.sample_count} qualifying trade{rr.sample_count !== 1 ? "s" : ""}</span>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-center">
        <div>
          <p className="text-xs text-gray-500 mb-1">Avg Planned R:R</p>
          <p className="text-lg font-mono font-semibold text-blue-400">{fmt2(rr.avg_planned_rr)}</p>
        </div>
        <div>
          <p className="text-xs text-gray-500 mb-1">Avg Realized R</p>
          <p className={`text-lg font-mono font-semibold ${rr.avg_actual_r != null && rr.avg_actual_r >= 0 ? "text-green-400" : "text-red-400"}`}>
            {fmt2(rr.avg_actual_r, true)}
          </p>
        </div>
        <div>
          <p className="text-xs text-gray-500 mb-1">Avg Shortfall</p>
          <p className={`text-lg font-mono font-semibold ${shortfallColor}`}>
            {fmt2(rr.avg_r_shortfall, true)}
          </p>
        </div>
        <div>
          <p className="text-xs text-gray-500 mb-1">R:R Realization</p>
          <p className={`text-lg font-mono font-semibold ${realizationColor}`}>
            {rr.realization_pct != null ? `${rr.realization_pct.toFixed(0)}%` : "—"}
          </p>
        </div>
      </div>

      {/* Target hit rate */}
      <div className="border-t border-gray-800 pt-3">
        <div className="flex items-center justify-between text-xs text-gray-500 mb-1">
          <span>Met planned target ({rr.met_target_count} of {rr.sample_count})</span>
          <span>{rr.pct_met_target != null ? `${rr.pct_met_target.toFixed(0)}%` : "—"}</span>
        </div>
        {rr.pct_met_target != null && (
          <div className="h-1.5 bg-gray-800 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all ${rr.pct_met_target >= 60 ? "bg-green-500" : rr.pct_met_target >= 40 ? "bg-yellow-500" : "bg-red-500"}`}
              style={{ width: `${Math.min(100, rr.pct_met_target)}%` }}
            />
          </div>
        )}
      </div>

      {/* Coaching signals */}
      {rr.coaching_signals.length > 0 && (
        <div className="space-y-1 pt-1">
          {rr.coaching_signals.map((s, i) => (
            <p key={i} className="text-xs text-gray-300 leading-relaxed">
              <span className="text-purple-400 mr-1.5">›</span>{s}
            </p>
          ))}
        </div>
      )}

      {rr.sample_count < 3 && (
        <p className="text-xs text-gray-600 italic">
          Need at least 3 trades with a linked plan + planned_rr + actual R for reliable comparison.
        </p>
      )}
    </div>
  );
}

function PlanAdherencePanel({ data }: { data: PlanAdherenceResponse }) {
  const showPlanLinkage  = data.planned_count >= 2 || data.unplanned_count >= 2;
  const showFollowedPlan = data.followed_count >= 2 || data.deviated_count >= 2;

  if (!showPlanLinkage && !showFollowedPlan && data.coaching_signals.length === 0) {
    return (
      <p className="text-xs text-gray-500">
        No plan adherence data yet. Link trade plans to trades and mark followed_plan to unlock these insights.
      </p>
    );
  }

  return (
    <div className="space-y-4">
      {/* Comparison grids */}
      <div className={`grid gap-4 ${showPlanLinkage && showFollowedPlan ? "sm:grid-cols-2" : "grid-cols-1"}`}>
        {/* Dimension 1: planned vs unplanned */}
        {showPlanLinkage && (
          <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 space-y-4">
            <p className="text-xs text-gray-500 uppercase tracking-wider">
              Plan linkage ({data.planned_pct != null ? `${data.planned_pct.toFixed(0)}% planned` : "—"})
            </p>
            <div className="grid grid-cols-2 gap-4 divide-x divide-gray-800">
              <GroupStats g={data.planned}   label="Planned"   color="blue" />
              <div className="pl-4">
                <GroupStats g={data.unplanned} label="Unplanned" color="orange" />
              </div>
            </div>
            {(data.planned_count < 3 || data.unplanned_count < 3) && (
              <p className="text-xs text-gray-600 italic pt-1">
                Not enough data for a reliable comparison yet.
              </p>
            )}
          </div>
        )}

        {/* Dimension 2: followed vs deviated */}
        {showFollowedPlan && (
          <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 space-y-4">
            <p className="text-xs text-gray-500 uppercase tracking-wider">
              Plan adherence (self-reported)
            </p>
            <div className="grid grid-cols-2 gap-4 divide-x divide-gray-800">
              <GroupStats g={data.followed} label="Followed"  color="green" />
              <div className="pl-4">
                <GroupStats g={data.deviated} label="Deviated" color="red" />
              </div>
            </div>
            {(data.followed_count < 3 || data.deviated_count < 3) && (
              <p className="text-xs text-gray-600 italic pt-1">
                Not enough data for a reliable comparison yet.
              </p>
            )}
          </div>
        )}
      </div>

      {/* Coaching signals */}
      {data.coaching_signals.length > 0 && (
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 space-y-2">
          <p className="text-xs text-gray-500 uppercase tracking-wider mb-2">Key signals</p>
          {data.coaching_signals.map((s, i) => (
            <p key={i} className="text-xs text-gray-300 leading-relaxed">
              <span className="text-blue-500 mr-1.5">›</span>{s}
            </p>
          ))}
          {data.linked_but_deviated_count > 0 && (
            <p className="text-xs text-amber-400 mt-1">
              ⚠ {data.linked_but_deviated_count} linked plan(s) deviated from — review execution discipline.
            </p>
          )}
        </div>
      )}
    </div>
  );
}

// ── R:R Realization Trend chart ───────────────────────────────────────────────

const TREND_COLORS = {
  improving: "text-green-400",
  worsening: "text-red-400",
  stable:    "text-yellow-400",
} as const;

function rrTrendBarColor(pct: number | null): string {
  if (pct == null) return "#6b7280";
  if (pct >= 90) return "#34d399";
  if (pct >= 60) return "#fbbf24";
  return "#f87171";
}

function fmtWeek(bucket: string): string {
  // "2026-W15" → "W15" or "Apr W15" — keep it short
  const m = bucket.match(/^(\d{4})-W(\d+)$/);
  if (!m) return bucket;
  return `W${m[2]}`;
}

function RRTrendChart({ report }: { report: RRTrendReportResponse }) {
  if (report.buckets.length === 0) return null;

  const MIN_SIGNAL_N = 3;
  const data = report.buckets.map((b) => ({
    label: fmtWeek(b.bucket),
    pct: b.realization_pct,
    planned: b.avg_planned_rr,
    actual: b.avg_actual_r,
    shortfall: b.avg_shortfall,
    n: b.n,
    lowSample: b.n < MIN_SIGNAL_N,
  }));

  const trendSignal = report.trend_signal;
  const trendColor = trendSignal ? (TREND_COLORS[trendSignal as keyof typeof TREND_COLORS] ?? "text-gray-400") : null;

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-xs text-gray-500 uppercase tracking-wider">R:R Realization Trend (weekly)</p>
        <div className="flex items-center gap-3 text-xs">
          {trendSignal && trendColor && (
            <span className={`font-medium ${trendColor}`}>
              {trendSignal === "improving" ? "↑ Improving" : trendSignal === "worsening" ? "↓ Worsening" : "→ Stable"}
            </span>
          )}
          <span className="text-gray-600">{report.total_qualifying} qualifying trade{report.total_qualifying !== 1 ? "s" : ""}</span>
        </div>
      </div>

      <ResponsiveContainer width="100%" height={150}>
        <ComposedChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
          <XAxis dataKey="label" tick={{ fontSize: 10, fill: "#6b7280" }} />
          <YAxis
            tick={{ fontSize: 10, fill: "#6b7280" }}
            domain={[0, 120]}
            tickFormatter={(v: number) => `${v}%`}
            width={36}
          />
          <ReferenceLine y={100} stroke="#6b7280" strokeDasharray="4 2" label={{ value: "100%", position: "right", fontSize: 9, fill: "#6b7280" }} />
          <Tooltip
            contentStyle={{ background: "#111827", border: "1px solid #374151", fontSize: 11 }}
            formatter={(value: number, name: string) => {
              if (name === "pct") return [`${value?.toFixed(0)}%`, "Realization"];
              return [value, name];
            }}
            labelFormatter={(label: string, payload) => {
              if (payload && payload[0]) {
                const d = payload[0].payload;
                return `${label}  (n=${d.n}${d.lowSample ? "*" : ""})\nPlanned: ${d.planned?.toFixed(2)}R → Realized: ${d.actual > 0 ? "+" : ""}${d.actual?.toFixed(2)}R`;
              }
              return label;
            }}
          />
          <Bar dataKey="pct" name="pct" radius={[2, 2, 0, 0]}>
            {data.map((d, i) => (
              <Cell key={i} fill={rrTrendBarColor(d.pct)} fillOpacity={d.lowSample ? 0.45 : 0.85} />
            ))}
          </Bar>
        </ComposedChart>
      </ResponsiveContainer>

      <div className="flex items-center gap-4 text-xs text-gray-600">
        <span><span className="inline-block w-2 h-2 rounded-sm bg-green-400 mr-1" />≥ 90%</span>
        <span><span className="inline-block w-2 h-2 rounded-sm bg-yellow-400 mr-1" />60–89%</span>
        <span><span className="inline-block w-2 h-2 rounded-sm bg-red-400 mr-1" />&lt; 60%</span>
        {data.some((d) => d.lowSample) && <span className="ml-1 italic">faded bars = &lt; 3 trades</span>}
      </div>
    </div>
  );
}

// ── MT5 data freshness pill (dashboard compact version) ───────────────────────

type FreshnessState = "fresh" | "stale" | "delayed" | "error" | "no_sync";

function computeFreshnessState(status: MT5SyncStatus): {
  state: FreshnessState;
  label: string;
  detail: string;
  cls: string;
} {
  const now = Date.now();
  const lastRun = status.last_runs[0];
  const intervalMs = (status.polling_interval_minutes ?? 60) * 60_000;
  const staleMs = Math.max(intervalMs * 1.5, 90 * 60_000);
  const lastSyncMs = status.last_sync_at ? new Date(status.last_sync_at).getTime() : null;
  const nextPollMs = status.next_poll_at ? new Date(status.next_poll_at).getTime() : null;

  if (!status.sync_configured || !lastRun) {
    return { state: "no_sync", label: "No sync", detail: "MT5 not configured", cls: "text-gray-500" };
  }

  const lastRunIsError = lastRun.status === "error";
  const errorNewerThanSuccess = !lastSyncMs || new Date(lastRun.started_at).getTime() > lastSyncMs;
  if (lastRunIsError && errorNewerThanSuccess) {
    const err = (lastRun.error_message ?? "sync error").slice(0, 60);
    return { state: "error", label: "Sync error", detail: err, cls: "text-red-400" };
  }

  if (!lastSyncMs) {
    return { state: "no_sync", label: "No sync", detail: "no successful sync yet", cls: "text-gray-500" };
  }

  const ageMs = now - lastSyncMs;
  const ago = fmtAgo(status.last_sync_at);
  const src = status.last_runs.find((r) => r.status === "success")?.triggered_by ?? "";
  const srcLabel = src ? ` · ${src}` : "";

  if (status.enabled && nextPollMs !== null && nextPollMs < now - 2 * 60_000) {
    return { state: "delayed", label: "Delayed", detail: `next poll overdue · last sync ${ago}`, cls: "text-orange-400" };
  }

  if (ageMs > staleMs) {
    return { state: "stale", label: "Stale", detail: `last sync ${ago}${srcLabel}`, cls: "text-yellow-400" };
  }

  return { state: "fresh", label: "Fresh", detail: `updated ${ago}${srcLabel}`, cls: "text-green-400" };
}

function Mt5FreshnessPill({ mt5Status }: { mt5Status: MT5SyncStatus }) {
  if (!mt5Status.sync_configured) return null;
  const { label, detail, cls } = computeFreshnessState(mt5Status);
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-gray-500">
      <span className="text-gray-600">MT5 data:</span>
      <span className={`font-medium ${cls}`}>{label}</span>
      <span className="text-gray-600">·</span>
      <span className="text-gray-500">{detail}</span>
    </span>
  );
}

// ── Segment analytics table ────────────────────────────────────────────────────

function SegmentTable({ rows, label }: { rows: SegmentRow[]; label: string }) {
  if (rows.length === 0) return null;
  const hasR = rows.some((r) => r.avg_r !== null);
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="text-gray-500 border-b border-gray-800">
            <th className="text-left py-1.5 pr-3 font-medium">{label}</th>
            <th className="text-right py-1.5 px-2 font-medium">Trades</th>
            <th className="text-right py-1.5 px-2 font-medium">Win %</th>
            <th className="text-right py-1.5 px-2 font-medium">Avg PnL</th>
            <th className="text-right py-1.5 px-2 font-medium">Total PnL</th>
            <th className="text-right py-1.5 px-2 font-medium">PF</th>
            {hasR && <th className="text-right py-1.5 px-2 font-medium">Avg R</th>}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr
              key={r.name}
              className={`border-b border-gray-800/50 ${r.low_sample ? "opacity-50" : ""}`}
            >
              <td className="py-1.5 pr-3 text-gray-100">
                {r.name}
                {r.low_sample && <span className="ml-1 text-gray-600 text-[10px]">({r.count})</span>}
              </td>
              <td className="text-right px-2 text-gray-400">{r.count}</td>
              <td className="text-right px-2 text-gray-300">
                {r.win_rate != null ? `${(r.win_rate * 100).toFixed(0)}%` : "—"}
              </td>
              <td className={`text-right px-2 ${r.avg_pnl != null && r.avg_pnl >= 0 ? "text-green-400" : "text-red-400"}`}>
                {r.avg_pnl != null ? fmtPnl(r.avg_pnl) : "—"}
              </td>
              <td className={`text-right px-2 font-medium ${r.total_pnl >= 0 ? "text-green-400" : "text-red-400"}`}>
                {fmtPnl(r.total_pnl)}
              </td>
              <td className="text-right px-2 text-gray-300">
                {r.profit_factor != null ? r.profit_factor.toFixed(2) : "—"}
              </td>
              {hasR && (
                <td className="text-right px-2 text-gray-400">
                  {r.avg_r != null ? r.avg_r.toFixed(2) : "—"}
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
      {rows.some((r) => r.low_sample) && (
        <p className="text-[10px] text-gray-600 mt-1">Faded rows have fewer than 3 trades — treat callouts with caution.</p>
      )}
    </div>
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
  const { accountId, accounts } = useAccount();
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [dailyLimitPct, setDailyLimitPct] = useState("5");
  const [maxLimitPct, setMaxLimitPct] = useState("10");
  const [showEditAccount, setShowEditAccount] = useState(false);

  const currentAccount = accounts.find((a) => a.account_id === accountId) ?? null;

  function handleAccountSaved() {
    setShowEditAccount(false);
    // Refresh account list (selector + any account-dependent display)
    globalMutate("accounts");
    // Refresh analytics — starting_balance change affects total return %, current balance
    globalMutate((k: unknown) => typeof k === "string" && k.startsWith(`analytics-${accountId}`));
    // Refresh FTMO — starting_balance change affects all limit calculations
    globalMutate((k: unknown) => typeof k === "string" && k.startsWith(`ftmo-${accountId}`));
  }

  const { data: analytics, isLoading } = useSWR(
    accountId ? `analytics-${accountId}-${fromDate}-${toDate}` : null,
    () => api.getAnalytics(accountId, {
      from_date: fromDate || undefined,
      to_date: toDate || undefined,
    })
  );
  const { data: ftmo } = useSWR(
    accountId ? `ftmo-${accountId}-${dailyLimitPct}-${maxLimitPct}` : null,
    () => api.getFtmoStatus(accountId, {
      daily_loss_limit_pct: parseFloat(dailyLimitPct) || 5,
      max_loss_limit_pct: parseFloat(maxLimitPct) || 10,
    }),
    { refreshInterval: 60_000 }   // re-check FTMO limits every minute
  );

  const { data: mistakes } = useSWR(
    accountId ? `mistakes-${accountId}-${fromDate}-${toDate}` : null,
    () => api.getMistakes(accountId, {
      from_date: fromDate || undefined,
      to_date: toDate || undefined,
    })
  );

  const { data: planAdherence } = useSWR(
    accountId ? `plan-adherence-${accountId}-${fromDate}-${toDate}` : null,
    () => api.getPlanAdherence(accountId, {
      from_date: fromDate || undefined,
      to_date: toDate || undefined,
    })
  );

  const { data: rrTrend } = useSWR(
    accountId ? `rr-trend-${accountId}-${fromDate}-${toDate}` : null,
    () => api.getRRTrend(accountId, {
      from_date: fromDate || undefined,
      to_date: toDate || undefined,
    })
  );

  const { data: segmentData } = useSWR(
    accountId ? `segment-analytics-${accountId}-${fromDate}-${toDate}` : null,
    () => api.getSegmentAnalytics(accountId, {
      from_date: fromDate || undefined,
      to_date: toDate || undefined,
    })
  );

  // MT5 freshness — only for accounts that have MT5 configured; 404 = no config
  const { data: mt5Status } = useSWR<MT5SyncStatus | null>(
    accountId ? `mt5-status-${accountId}` : null,
    async () => {
      try { return await api.getMt5Status(accountId, 3); }
      catch (e: any) { if (e?.message?.startsWith("404")) return null; throw e; }
    },
    { refreshInterval: 60_000 }
  );

  const hasEquity = analytics?.equity_curve && analytics.equity_curve.length > 1;

  return (
    <div className="space-y-6">
      {/* Edit account modal */}
      {showEditAccount && currentAccount && (
        <EditAccountModal
          account={currentAccount}
          onClose={() => setShowEditAccount(false)}
          onSaved={handleAccountSaved}
        />
      )}

      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Account Dashboard</h1>
        <div className="flex items-center gap-2">
          <AccountSelector />
          {accountId && (
            <button
              onClick={() => setShowEditAccount(true)}
              title="Edit account settings"
              className="text-gray-500 hover:text-gray-300 bg-gray-800 border border-gray-700 rounded px-2 py-1.5 text-xs transition-colors"
            >
              ⚙
            </button>
          )}
        </div>
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
        {mt5Status && <Mt5FreshnessPill mt5Status={mt5Status} />}
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

          {/* ── FTMO status ───────────────────────────────────────────────────── */}
          {analytics.starting_balance != null && ftmo && (
            <section>
              <h2 className="text-xs uppercase tracking-wider text-gray-500 mb-3">FTMO Challenge Status</h2>
              <FtmoPanel
                ftmo={ftmo}
                dailyLimitPct={dailyLimitPct}
                maxLimitPct={maxLimitPct}
                onDailyLimit={setDailyLimitPct}
                onMaxLimit={setMaxLimitPct}
              />
            </section>
          )}

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

      {/* ── Plan adherence ────────────────────────────────────────────────────── */}
      {planAdherence && planAdherence.total_trades > 0 && (
        <section>
          <h2 className="text-xs uppercase tracking-wider text-gray-500 mb-3">Plan vs Execution</h2>
          <div className="space-y-4">
            <PlanAdherencePanel data={planAdherence} />
            {planAdherence.rr_comparison && planAdherence.rr_comparison.sample_count > 0 && (
              <RRComparisonPanel rr={planAdherence.rr_comparison} />
            )}
          </div>
        </section>
      )}

      {/* ── R:R Realization Trend ─────────────────────────────────────────────── */}
      {rrTrend && rrTrend.buckets.length > 0 && (
        <section>
          <h2 className="text-xs uppercase tracking-wider text-gray-500 mb-3">Execution Trend</h2>
          <RRTrendChart report={rrTrend} />
        </section>
      )}
      {rrTrend && rrTrend.buckets.length === 0 && (
        <p className="text-xs text-gray-600 px-1">
          R:R Realization Trend appears when trades have a linked plan with{" "}
          <span className="font-mono">planned_rr &gt; 0</span> and{" "}
          <span className="font-mono">actual_r_multiple</span> set.
        </p>
      )}

      {/* ── Symbol & Session Analytics ──────────────────────────────────────── */}
      {segmentData && (segmentData.by_symbol.length > 0 || segmentData.by_session.length > 0) && (
        <section>
          <h2 className="text-xs uppercase tracking-wider text-gray-500 mb-3">Symbol & Session Analytics</h2>

          {/* Callout badges */}
          {(segmentData.best_symbol || segmentData.worst_symbol || segmentData.best_session || segmentData.worst_session) && (
            <div className="flex flex-wrap gap-2 mb-4">
              {segmentData.best_symbol && (
                <span className="text-xs bg-green-900/40 border border-green-700/50 text-green-300 rounded px-2 py-1">
                  Best symbol: <strong>{segmentData.best_symbol}</strong>
                </span>
              )}
              {segmentData.worst_symbol && (
                <span className="text-xs bg-red-900/40 border border-red-700/50 text-red-300 rounded px-2 py-1">
                  Worst symbol: <strong>{segmentData.worst_symbol}</strong>
                </span>
              )}
              {segmentData.best_session && (
                <span className="text-xs bg-blue-900/40 border border-blue-700/50 text-blue-300 rounded px-2 py-1">
                  Best session: <strong>{segmentData.best_session}</strong>
                </span>
              )}
              {segmentData.worst_session && (
                <span className="text-xs bg-orange-900/40 border border-orange-700/50 text-orange-300 rounded px-2 py-1">
                  Worst session: <strong>{segmentData.worst_session}</strong>
                </span>
              )}
            </div>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {segmentData.by_symbol.length > 0 && (
              <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
                <h3 className="text-xs uppercase tracking-wider text-gray-500 mb-3">By Symbol</h3>
                <SegmentTable rows={segmentData.by_symbol} label="Symbol" />
              </div>
            )}
            {segmentData.by_session.length > 0 && (
              <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
                <h3 className="text-xs uppercase tracking-wider text-gray-500 mb-3">By Session</h3>
                <SegmentTable rows={segmentData.by_session} label="Session" />
              </div>
            )}
          </div>
        </section>
      )}
    </div>
  );
}
