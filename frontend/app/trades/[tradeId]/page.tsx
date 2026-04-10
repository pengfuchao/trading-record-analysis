"use client";

import { use } from "react";
import Link from "next/link";
import useSWR from "swr";
import { api } from "@/lib/api";
import { useAccount } from "@/components/AccountProvider";
import Badge from "@/components/Badge";
import { fmtDateTime, fmtPnl, fmt, pnlColor } from "@/lib/utils";

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs text-gray-500 uppercase tracking-wider mb-0.5">{label}</dt>
      <dd className="text-sm text-gray-100">{value ?? "—"}</dd>
    </div>
  );
}

function BoolField({ label, value }: { label: string; value: boolean | undefined | null }) {
  if (value == null) return null;
  return (
    <div className="flex items-center gap-2">
      <span className={`w-2 h-2 rounded-full ${value ? "bg-red-400" : "bg-gray-700"}`} />
      <span className={`text-xs ${value ? "text-red-300" : "text-gray-600"}`}>{label}</span>
    </div>
  );
}

export default function TradeDetailPage({ params }: { params: Promise<{ tradeId: string }> }) {
  const { tradeId } = use(params);
  const { accountId } = useAccount();

  const { data: trade, isLoading } = useSWR(
    accountId && tradeId ? `trade-${tradeId}` : null,
    () => api.getTrade(accountId, tradeId)
  );

  if (isLoading) return <p className="text-gray-500 text-sm">Loading…</p>;
  if (!trade) return <p className="text-gray-500 text-sm">Trade not found.</p>;

  const flags = [
    { label: "Early Entry",          value: trade.early_entry },
    { label: "Chasing",              value: trade.chasing },
    { label: "FOMO",                 value: trade.fomo },
    { label: "Emotional",            value: trade.emotional_trade },
    { label: "Revenge Trade",        value: trade.revenge_trade },
    { label: "Overtrading",          value: trade.overtrading },
    { label: "Hesitation",           value: trade.hesitation },
    { label: "Moved Stop",           value: trade.moved_stop },
    { label: "Premature Exit",       value: trade.premature_exit },
    { label: "Held Loser Too Long",  value: trade.held_loser_too_long },
  ];

  const activeFlags = flags.filter((f) => f.value === true);

  return (
    <div className="space-y-6 max-w-4xl">
      <div className="flex items-center gap-4">
        <Link href="/trades" className="text-gray-500 hover:text-gray-300 text-sm">← Trade Log</Link>
        <h1 className="text-xl font-semibold">
          {trade.symbol ?? "Trade"} — {fmtDateTime(trade.entry_datetime)}
        </h1>
        {trade.result && (
          <Badge label={trade.result} variant={trade.result as "win" | "loss" | "breakeven"} />
        )}
      </div>

      {/* Execution numbers */}
      <section className="bg-gray-900 border border-gray-800 rounded-lg p-5">
        <h2 className="text-xs uppercase tracking-wider text-gray-500 mb-4">Execution</h2>
        <dl className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <Field label="Direction"    value={trade.direction} />
          <Field label="Lot Size"     value={fmt(trade.lot_size)} />
          <Field label="Entry"        value={fmt(trade.entry_price, 5)} />
          <Field label="Exit"         value={fmt(trade.exit_price, 5)} />
          <Field label="Stop Loss"    value={fmt(trade.stop_loss, 5)} />
          <Field label="Take Profit"  value={fmt(trade.take_profit, 5)} />
          <Field label="Net PnL"      value={<span className={pnlColor(trade.net_pnl)}>{fmtPnl(trade.net_pnl)}</span>} />
          <Field label="R Multiple"   value={<span className={pnlColor(trade.actual_r_multiple)}>{fmt(trade.actual_r_multiple)}</span>} />
          <Field label="Commission"   value={fmt(trade.commission)} />
          <Field label="Swap"         value={fmt(trade.swap)} />
          <Field label="Entry Time"   value={fmtDateTime(trade.entry_datetime)} />
          <Field label="Exit Time"    value={fmtDateTime(trade.exit_datetime)} />
        </dl>
      </section>

      {/* Strategy / context */}
      <section className="bg-gray-900 border border-gray-800 rounded-lg p-5">
        <h2 className="text-xs uppercase tracking-wider text-gray-500 mb-4">Strategy & Context</h2>
        <dl className="grid grid-cols-2 sm:grid-cols-3 gap-4">
          <Field label="Setup"            value={trade.setup_type} />
          <Field label="Strategy"         value={trade.strategy} />
          <Field label="Session"          value={trade.session} />
          <Field label="HTF Bias"         value={trade.higher_tf_bias} />
          <Field label="Entry TF"         value={trade.entry_timeframe} />
          <Field label="Market Condition" value={trade.market_condition} />
        </dl>
        {trade.key_levels && <Field label="Key Levels" value={<p className="whitespace-pre-wrap">{trade.key_levels}</p>} />}
        {trade.news_context && <div className="mt-3"><Field label="News Context" value={trade.news_context} /></div>}
        {trade.pre_trade_bias && <div className="mt-3"><Field label="Pre-Trade Bias" value={trade.pre_trade_bias} /></div>}
      </section>

      {/* Rationale */}
      <section className="bg-gray-900 border border-gray-800 rounded-lg p-5">
        <h2 className="text-xs uppercase tracking-wider text-gray-500 mb-4">Rationale</h2>
        <dl className="space-y-3">
          {trade.entry_reason && <Field label="Entry Reason" value={trade.entry_reason} />}
          {trade.trigger_confirmation && <Field label="Trigger / Confirmation" value={trade.trigger_confirmation} />}
          {trade.stop_loss_logic && <Field label="Stop Loss Logic" value={trade.stop_loss_logic} />}
          {trade.take_profit_logic && <Field label="Take Profit Logic" value={trade.take_profit_logic} />}
          {trade.exit_reason && <Field label="Exit Reason" value={trade.exit_reason} />}
        </dl>
      </section>

      {/* Execution flags */}
      <section className="bg-gray-900 border border-gray-800 rounded-lg p-5">
        <h2 className="text-xs uppercase tracking-wider text-gray-500 mb-4">Execution Quality</h2>
        <div className="flex flex-wrap gap-3 mb-4">
          <div className="flex items-center gap-2">
            <span className={`w-2 h-2 rounded-full ${trade.followed_plan ? "bg-green-400" : "bg-red-400"}`} />
            <span className="text-xs text-gray-400">Followed Plan</span>
          </div>
          <div className="flex items-center gap-2">
            <span className={`w-2 h-2 rounded-full ${trade.is_a_plus_setup ? "bg-green-400" : "bg-gray-700"}`} />
            <span className="text-xs text-gray-400">A+ Setup</span>
          </div>
        </div>
        {activeFlags.length > 0 && (
          <div>
            <p className="text-xs text-gray-500 mb-2">Execution mistakes flagged:</p>
            <div className="flex flex-wrap gap-2">
              {activeFlags.map((f) => (
                <span key={f.label} className="text-xs bg-red-900/50 text-red-300 px-2 py-0.5 rounded">
                  {f.label}
                </span>
              ))}
            </div>
          </div>
        )}
        {trade.mistake_tags && trade.mistake_tags.length > 0 && (
          <div className="mt-3">
            <p className="text-xs text-gray-500 mb-2">Mistake tags:</p>
            <div className="flex flex-wrap gap-2">
              {trade.mistake_tags.map((tag) => (
                <span key={tag} className="text-xs bg-yellow-900/40 text-yellow-300 px-2 py-0.5 rounded">{tag}</span>
              ))}
            </div>
          </div>
        )}
      </section>

      {/* Review / reflection */}
      <section className="bg-gray-900 border border-gray-800 rounded-lg p-5">
        <h2 className="text-xs uppercase tracking-wider text-gray-500 mb-4">Review & Reflection</h2>
        <dl className="space-y-3">
          <Field label="Trade Quality" value={trade.trade_quality} />
          <Field label="Problem Source" value={trade.problem_source} />
          {trade.lesson_learned && <Field label="Lesson Learned" value={trade.lesson_learned} />}
          {trade.repeat_next_time && <Field label="Repeat Next Time" value={trade.repeat_next_time} />}
          {trade.avoid_next_time && <Field label="Avoid Next Time" value={trade.avoid_next_time} />}
          {trade.notes && <Field label="Notes" value={<p className="whitespace-pre-wrap">{trade.notes}</p>} />}
        </dl>
      </section>
    </div>
  );
}
