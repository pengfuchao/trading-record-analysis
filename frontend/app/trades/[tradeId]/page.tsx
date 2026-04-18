"use client";

import { useState } from "react";
import Link from "next/link";
import useSWR, { useSWRConfig } from "swr";
import { api, Trade, TradePlan } from "@/lib/api";
import { useAccount } from "@/components/AccountProvider";
import Badge from "@/components/Badge";
import { fmtDateTime, fmtPnl, fmt, pnlColor } from "@/lib/utils";

// ── Read-only field display ────────────────────────────────────────────────────

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs text-gray-500 uppercase tracking-wider mb-0.5">{label}</dt>
      <dd className="text-sm text-gray-100">{value ?? "—"}</dd>
    </div>
  );
}

// ── Edit form helpers ──────────────────────────────────────────────────────────

function TextInput({ label, value, onChange, placeholder }: {
  label: string; value: string; onChange: (v: string) => void; placeholder?: string;
}) {
  return (
    <div>
      <label className="block text-xs text-gray-500 uppercase tracking-wider mb-0.5">{label}</label>
      <input
        className="w-full bg-gray-800 border border-gray-700 rounded px-2 py-1 text-sm text-gray-100 focus:outline-none focus:border-blue-500"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
      />
    </div>
  );
}

function TextArea({ label, value, onChange, placeholder }: {
  label: string; value: string; onChange: (v: string) => void; placeholder?: string;
}) {
  return (
    <div>
      <label className="block text-xs text-gray-500 uppercase tracking-wider mb-0.5">{label}</label>
      <textarea
        rows={3}
        className="w-full bg-gray-800 border border-gray-700 rounded px-2 py-1 text-sm text-gray-100 focus:outline-none focus:border-blue-500 resize-y"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
      />
    </div>
  );
}

function SetupTypeInput({ value, onChange, setupNames }: {
  value: string; onChange: (v: string) => void; setupNames: string[];
}) {
  return (
    <div>
      <label className="block text-xs text-gray-500 uppercase tracking-wider mb-0.5">Setup Type</label>
      <input
        list="setup-type-options"
        className="w-full bg-gray-800 border border-gray-700 rounded px-2 py-1 text-sm text-gray-100 focus:outline-none focus:border-blue-500"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="e.g. OB Retest"
      />
      <datalist id="setup-type-options">
        {setupNames.map((name) => (
          <option key={name} value={name} />
        ))}
      </datalist>
    </div>
  );
}

function SelectInput({ label, value, onChange, options }: {
  label: string; value: string; onChange: (v: string) => void;
  options: { value: string; label: string }[];
}) {
  return (
    <div>
      <label className="block text-xs text-gray-500 uppercase tracking-wider mb-0.5">{label}</label>
      <select
        className="w-full bg-gray-800 border border-gray-700 rounded px-2 py-1 text-sm text-gray-100 focus:outline-none focus:border-blue-500"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      >
        <option value="">— unset —</option>
        {options.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
    </div>
  );
}

function CheckFlag({ label, checked, onChange }: {
  label: string; checked: boolean; onChange: (v: boolean) => void;
}) {
  return (
    <label className="flex items-center gap-2 cursor-pointer select-none">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="w-3.5 h-3.5 accent-red-500"
      />
      <span className={`text-xs ${checked ? "text-red-300" : "text-gray-500"}`}>{label}</span>
    </label>
  );
}

// ── Edit state initializer ─────────────────────────────────────────────────────

type EditState = {
  stop_loss: string;
  setup_type: string;
  strategy: string;
  session: string;
  higher_tf_bias: string;
  entry_timeframe: string;
  market_condition: string;
  followed_plan: boolean | null;
  is_a_plus_setup: boolean | null;
  early_entry: boolean;
  chasing: boolean;
  fomo: boolean;
  emotional_trade: boolean;
  revenge_trade: boolean;
  overtrading: boolean;
  hesitation: boolean;
  moved_stop: boolean;
  premature_exit: boolean;
  held_loser_too_long: boolean;
  trade_quality: string;
  problem_source: string;
  lesson_learned: string;
  notes: string;
  repeat_next_time: string;
  avoid_next_time: string;
};

function initEdit(trade: Trade): EditState {
  return {
    stop_loss: trade.stop_loss != null ? String(trade.stop_loss) : "",
    setup_type: trade.setup_type ?? "",
    strategy: trade.strategy ?? "",
    session: trade.session ?? "",
    higher_tf_bias: trade.higher_tf_bias ?? "",
    entry_timeframe: trade.entry_timeframe ?? "",
    market_condition: trade.market_condition ?? "",
    followed_plan: trade.followed_plan ?? null,
    is_a_plus_setup: trade.is_a_plus_setup ?? null,
    early_entry: trade.early_entry ?? false,
    chasing: trade.chasing ?? false,
    fomo: trade.fomo ?? false,
    emotional_trade: trade.emotional_trade ?? false,
    revenge_trade: trade.revenge_trade ?? false,
    overtrading: trade.overtrading ?? false,
    hesitation: trade.hesitation ?? false,
    moved_stop: trade.moved_stop ?? false,
    premature_exit: trade.premature_exit ?? false,
    held_loser_too_long: trade.held_loser_too_long ?? false,
    trade_quality: trade.trade_quality ?? "",
    problem_source: trade.problem_source ?? "",
    lesson_learned: trade.lesson_learned ?? "",
    notes: trade.notes ?? "",
    repeat_next_time: trade.repeat_next_time ?? "",
    avoid_next_time: trade.avoid_next_time ?? "",
  };
}

function editToPatch(state: EditState): Partial<Trade> {
  const patch: Record<string, unknown> = {};

  // Numeric: only send if user entered a parseable value
  if (state.stop_loss !== "") {
    const val = parseFloat(state.stop_loss);
    if (!isNaN(val)) patch.stop_loss = val;
  }

  // String fields: always send so empty string clears the stored value
  patch.setup_type = state.setup_type.trim();
  patch.strategy = state.strategy;
  patch.session = state.session;
  patch.higher_tf_bias = state.higher_tf_bias;
  patch.entry_timeframe = state.entry_timeframe;
  patch.market_condition = state.market_condition;
  patch.trade_quality = state.trade_quality;
  patch.problem_source = state.problem_source;
  patch.lesson_learned = state.lesson_learned;
  patch.notes = state.notes;
  patch.repeat_next_time = state.repeat_next_time;
  patch.avoid_next_time = state.avoid_next_time;

  // Booleans: always send
  if (state.followed_plan !== null) patch.followed_plan = state.followed_plan;
  if (state.is_a_plus_setup !== null) patch.is_a_plus_setup = state.is_a_plus_setup;
  patch.early_entry = state.early_entry;
  patch.chasing = state.chasing;
  patch.fomo = state.fomo;
  patch.emotional_trade = state.emotional_trade;
  patch.revenge_trade = state.revenge_trade;
  patch.overtrading = state.overtrading;
  patch.hesitation = state.hesitation;
  patch.moved_stop = state.moved_stop;
  patch.premature_exit = state.premature_exit;
  patch.held_loser_too_long = state.held_loser_too_long;

  return patch as Partial<Trade>;
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function TradeDetailPage({ params }: { params: { tradeId: string } }) {
  const { tradeId } = params;
  const { accountId } = useAccount();
  const { mutate } = useSWRConfig();

  const swrKey = accountId && tradeId ? `trade-${tradeId}` : null;
  const { data: trade, isLoading } = useSWR(
    swrKey,
    () => api.getTrade(accountId, tradeId)
  );

  // Setup names for autocomplete — fetched once, cached globally
  const { data: setups = [] } = useSWR("setups", () => api.listSetups());
  const setupNames = setups.map((s) => s.name);

  // Load linked plan if trade has one
  const { data: linkedPlan } = useSWR(
    trade?.trade_plan_id && accountId ? `trade-plan-${trade.trade_plan_id}` : null,
    () => api.getTradePlan(accountId, trade!.trade_plan_id!)
  );

  const [editing, setEditing] = useState(false);
  const [editState, setEditState] = useState<EditState | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState(false);

  if (isLoading) return <p className="text-gray-500 text-sm">Loading…</p>;
  if (!trade) return <p className="text-gray-500 text-sm">Trade not found.</p>;

  const flags = [
    { label: "Early Entry",         value: trade.early_entry },
    { label: "Chasing",             value: trade.chasing },
    { label: "FOMO",                value: trade.fomo },
    { label: "Emotional",           value: trade.emotional_trade },
    { label: "Revenge Trade",       value: trade.revenge_trade },
    { label: "Overtrading",         value: trade.overtrading },
    { label: "Hesitation",          value: trade.hesitation },
    { label: "Moved Stop",          value: trade.moved_stop },
    { label: "Premature Exit",      value: trade.premature_exit },
    { label: "Held Loser Too Long", value: trade.held_loser_too_long },
  ];
  const activeFlags = flags.filter((f) => f.value === true);

  function openEdit() {
    setEditState(initEdit(trade));
    setSaveError(null);
    setSaveSuccess(false);
    setEditing(true);
  }

  function closeEdit() {
    setEditing(false);
    setEditState(null);
    setSaveError(null);
    setSaveSuccess(false);
  }

  async function handleSave() {
    if (!editState) return;
    setSaving(true);
    setSaveError(null);
    setSaveSuccess(false);
    try {
      await api.updateTrade(accountId, tradeId, editToPatch(editState));
      // Invalidate detail cache
      await mutate(swrKey);
      // Invalidate all trade-list keys for this account (they include filter suffixes)
      await mutate((key) => typeof key === "string" && key.startsWith(`trades-${accountId}`));
      // Invalidate analytics so dashboard reflects updated followed_plan / mistake flags
      await mutate((key) => typeof key === "string" && key.startsWith(`analytics-${accountId}`));
      setSaveSuccess(true);
      setEditing(false);
      setEditState(null);
    } catch (err: unknown) {
      setSaveError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  function set<K extends keyof EditState>(key: K, val: EditState[K]) {
    setEditState((prev) => prev ? { ...prev, [key]: val } : prev);
  }

  return (
    <div className="space-y-6 max-w-4xl">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link href="/trades" className="text-gray-500 hover:text-gray-300 text-sm">← Trade Log</Link>
        <h1 className="text-xl font-semibold">
          {trade.symbol ?? "Trade"} — {fmtDateTime(trade.entry_datetime)}
        </h1>
        {trade.result && (
          <Badge label={trade.result} variant={trade.result as "win" | "loss" | "breakeven"} />
        )}
        <div className="ml-auto">
          {!editing && (
            <button
              onClick={openEdit}
              className="px-3 py-1.5 text-xs bg-blue-600 hover:bg-blue-500 text-white rounded transition-colors"
            >
              Edit Journal
            </button>
          )}
        </div>
      </div>

      {/* Success banner */}
      {saveSuccess && !editing && (
        <div className="bg-green-900/40 border border-green-700 text-green-300 text-sm px-4 py-2 rounded">
          Saved successfully.
        </div>
      )}

      {/* Execution numbers — always read-only */}
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

      {/* ── EDIT FORM ──────────────────────────────────────────────────────────── */}
      {editing && editState && (
        <section className="bg-gray-900 border border-blue-700 rounded-lg p-5 space-y-5">
          <div className="flex items-center justify-between mb-1">
            <h2 className="text-xs uppercase tracking-wider text-blue-400">Edit Journal Entry</h2>
            <button onClick={closeEdit} className="text-xs text-gray-500 hover:text-gray-300">✕ Cancel</button>
          </div>

          {/* Stop loss (correctable) */}
          <div>
            <p className="text-xs text-gray-600 mb-2 italic">Stop loss can be corrected if not in CSV. R is recomputed on save.</p>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
              <TextInput
                label="Stop Loss (price)"
                value={editState.stop_loss}
                onChange={(v) => set("stop_loss", v)}
                placeholder="e.g. 1.0950"
              />
            </div>
          </div>

          {/* Strategy & Context */}
          <div>
            <p className="text-xs text-gray-500 uppercase tracking-wider mb-2">Strategy & Context</p>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
              <SetupTypeInput value={editState.setup_type} onChange={(v) => set("setup_type", v)} setupNames={setupNames} />
              <TextInput label="Strategy" value={editState.strategy} onChange={(v) => set("strategy", v)} placeholder="e.g. SMC" />
              <SelectInput
                label="Session"
                value={editState.session}
                onChange={(v) => set("session", v)}
                options={[
                  { value: "Asia", label: "Asia" },
                  { value: "London", label: "London" },
                  { value: "London/NY", label: "London/NY" },
                  { value: "New York", label: "New York" },
                  { value: "After Hours", label: "After Hours" },
                ]}
              />
              <TextInput label="HTF Bias" value={editState.higher_tf_bias} onChange={(v) => set("higher_tf_bias", v)} placeholder="e.g. Bullish" />
              <TextInput label="Entry Timeframe" value={editState.entry_timeframe} onChange={(v) => set("entry_timeframe", v)} placeholder="e.g. M15" />
              <TextInput label="Market Condition" value={editState.market_condition} onChange={(v) => set("market_condition", v)} placeholder="e.g. Trending" />
            </div>
          </div>

          {/* Execution quality */}
          <div>
            <p className="text-xs text-gray-500 uppercase tracking-wider mb-2">Execution Quality</p>
            <div className="flex flex-wrap gap-6 mb-3">
              <label className="flex items-center gap-2 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={editState.followed_plan === true}
                  onChange={(e) => set("followed_plan", e.target.checked ? true : false)}
                  className="w-3.5 h-3.5 accent-green-500"
                />
                <span className={`text-xs ${editState.followed_plan ? "text-green-300" : "text-gray-500"}`}>Followed Plan</span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={editState.is_a_plus_setup === true}
                  onChange={(e) => set("is_a_plus_setup", e.target.checked ? true : false)}
                  className="w-3.5 h-3.5 accent-yellow-500"
                />
                <span className={`text-xs ${editState.is_a_plus_setup ? "text-yellow-300" : "text-gray-500"}`}>A+ Setup</span>
              </label>
            </div>
          </div>

          {/* Mistake flags */}
          <div>
            <p className="text-xs text-gray-500 uppercase tracking-wider mb-2">Mistake Flags</p>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
              <CheckFlag label="Early Entry"         checked={editState.early_entry}         onChange={(v) => set("early_entry", v)} />
              <CheckFlag label="Chasing"             checked={editState.chasing}             onChange={(v) => set("chasing", v)} />
              <CheckFlag label="FOMO"                checked={editState.fomo}                onChange={(v) => set("fomo", v)} />
              <CheckFlag label="Emotional"           checked={editState.emotional_trade}     onChange={(v) => set("emotional_trade", v)} />
              <CheckFlag label="Revenge Trade"       checked={editState.revenge_trade}       onChange={(v) => set("revenge_trade", v)} />
              <CheckFlag label="Overtrading"         checked={editState.overtrading}         onChange={(v) => set("overtrading", v)} />
              <CheckFlag label="Hesitation"          checked={editState.hesitation}          onChange={(v) => set("hesitation", v)} />
              <CheckFlag label="Moved Stop"          checked={editState.moved_stop}          onChange={(v) => set("moved_stop", v)} />
              <CheckFlag label="Premature Exit"      checked={editState.premature_exit}      onChange={(v) => set("premature_exit", v)} />
              <CheckFlag label="Held Loser Too Long" checked={editState.held_loser_too_long} onChange={(v) => set("held_loser_too_long", v)} />
            </div>
          </div>

          {/* Review / reflection */}
          <div>
            <p className="text-xs text-gray-500 uppercase tracking-wider mb-2">Review & Reflection</p>
            <div className="grid grid-cols-2 sm:grid-cols-2 gap-3 mb-3">
              <SelectInput
                label="Trade Quality"
                value={editState.trade_quality}
                onChange={(v) => set("trade_quality", v)}
                options={[
                  { value: "good trade", label: "Good Trade" },
                  { value: "bad trade", label: "Bad Trade" },
                  { value: "learning trade", label: "Learning Trade" },
                ]}
              />
              <SelectInput
                label="Problem Source"
                value={editState.problem_source}
                onChange={(v) => set("problem_source", v)}
                options={[
                  { value: "analysis", label: "Analysis" },
                  { value: "execution", label: "Execution" },
                  { value: "psychology", label: "Psychology" },
                  { value: "risk", label: "Risk Management" },
                ]}
              />
            </div>
            <div className="space-y-3">
              <TextArea label="Lesson Learned" value={editState.lesson_learned} onChange={(v) => set("lesson_learned", v)} placeholder="What did you learn from this trade?" />
              <TextArea label="Notes" value={editState.notes} onChange={(v) => set("notes", v)} placeholder="Any additional context or observations" />
              <TextArea label="Repeat Next Time" value={editState.repeat_next_time} onChange={(v) => set("repeat_next_time", v)} placeholder="What to do again" />
              <TextArea label="Avoid Next Time" value={editState.avoid_next_time} onChange={(v) => set("avoid_next_time", v)} placeholder="What to avoid" />
            </div>
          </div>

          {/* Save / Cancel */}
          {saveError && (
            <div className="bg-red-900/40 border border-red-700 text-red-300 text-xs px-3 py-2 rounded">
              {saveError}
            </div>
          )}
          <div className="flex items-center gap-3 pt-1">
            <button
              onClick={handleSave}
              disabled={saving}
              className="px-4 py-2 text-sm bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded transition-colors"
            >
              {saving ? "Saving…" : "Save Changes"}
            </button>
            <button
              onClick={closeEdit}
              disabled={saving}
              className="px-4 py-2 text-sm bg-gray-700 hover:bg-gray-600 disabled:opacity-50 text-gray-200 rounded transition-colors"
            >
              Cancel
            </button>
          </div>
        </section>
      )}

      {/* ── READ-ONLY VIEW (shown when not editing) ────────────────────────────── */}
      {!editing && (
        <>
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
            {trade.key_levels && <div className="mt-3"><Field label="Key Levels" value={<p className="whitespace-pre-wrap">{trade.key_levels}</p>} /></div>}
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

          {/* Linked plan */}
          <section className="bg-gray-900 border border-gray-800 rounded-lg p-5">
            <h2 className="text-xs uppercase tracking-wider text-gray-500 mb-4">Linked Trade Plan</h2>
            {!trade.trade_plan_id && (
              <div className="text-xs text-gray-500">
                No plan linked. <Link href="/plans" className="text-blue-400 hover:text-blue-300">Go to Plans</Link> to create and link a plan.
              </div>
            )}
            {trade.trade_plan_id && linkedPlan && (
              <div className="space-y-3">
                <div className="flex items-center gap-2">
                  <Link href={`/plans/${linkedPlan.plan_id}`} className="text-sm text-blue-400 hover:text-blue-300 font-medium">
                    {linkedPlan.symbol ?? "Plan"} {linkedPlan.intended_direction ? `(${linkedPlan.intended_direction})` : ""} →
                  </Link>
                  <span className="text-xs bg-green-900/40 text-green-300 px-2 py-0.5 rounded">linked</span>
                </div>
                <dl className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                  {linkedPlan.setup_type && <Field label="Setup" value={linkedPlan.setup_type} />}
                  {linkedPlan.bias && <Field label="Bias" value={linkedPlan.bias} />}
                  {linkedPlan.planned_rr != null && <Field label="Planned R:R" value={String(linkedPlan.planned_rr)} />}
                  {linkedPlan.planned_entry_zone && <Field label="Entry Zone" value={linkedPlan.planned_entry_zone} />}
                </dl>
                {linkedPlan.thesis && (
                  <div>
                    <dt className="text-xs text-gray-500 uppercase tracking-wider mb-0.5">Thesis</dt>
                    <dd className="text-sm text-gray-300 whitespace-pre-wrap">{linkedPlan.thesis}</dd>
                  </div>
                )}
                {linkedPlan.invalidation_logic && (
                  <div>
                    <dt className="text-xs text-gray-500 uppercase tracking-wider mb-0.5">Invalidation</dt>
                    <dd className="text-sm text-gray-300 whitespace-pre-wrap">{linkedPlan.invalidation_logic}</dd>
                  </div>
                )}
              </div>
            )}
            {trade.trade_plan_id && !linkedPlan && (
              <p className="text-xs text-gray-500">Loading plan…</p>
            )}
          </section>
        </>
      )}
    </div>
  );
}
