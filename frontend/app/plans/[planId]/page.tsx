"use client";

import { useState } from "react";
import Link from "next/link";
import useSWR, { useSWRConfig } from "swr";
import { api, TradePlan, Trade } from "@/lib/api";
import { useAccount } from "@/components/AccountProvider";
import { fmtDateTime, fmt } from "@/lib/utils";

// ── Simple read-only field ────────────────────────────────────────────────────

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs text-gray-500 uppercase tracking-wider mb-0.5">{label}</dt>
      <dd className="text-sm text-gray-100 whitespace-pre-wrap">{value ?? "—"}</dd>
    </div>
  );
}

// ── Edit field helpers ────────────────────────────────────────────────────────

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
        {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </div>
  );
}

// ── Edit state ────────────────────────────────────────────────────────────────

type EditState = {
  status: string;
  symbol: string;
  intended_direction: string;
  setup_type: string;
  strategy: string;
  bias: string;
  thesis: string;
  entry_logic: string;
  stop_loss_logic: string;
  take_profit_logic: string;
  invalidation_logic: string;
  planned_entry_zone: string;
  planned_stop_loss: string;
  planned_take_profit: string;
  planned_rr: string;
  is_a_plus_setup: boolean;
  notes: string;
};

function initEdit(plan: TradePlan): EditState {
  return {
    status: plan.status ?? "planned",
    symbol: plan.symbol ?? "",
    intended_direction: plan.intended_direction ?? "",
    setup_type: plan.setup_type ?? "",
    strategy: plan.strategy ?? "",
    bias: plan.bias ?? "",
    thesis: plan.thesis ?? "",
    entry_logic: plan.entry_logic ?? "",
    stop_loss_logic: plan.stop_loss_logic ?? "",
    take_profit_logic: plan.take_profit_logic ?? "",
    invalidation_logic: plan.invalidation_logic ?? "",
    planned_entry_zone: plan.planned_entry_zone ?? "",
    planned_stop_loss: plan.planned_stop_loss != null ? String(plan.planned_stop_loss) : "",
    planned_take_profit: plan.planned_take_profit != null ? String(plan.planned_take_profit) : "",
    planned_rr: plan.planned_rr != null ? String(plan.planned_rr) : "",
    is_a_plus_setup: plan.is_a_plus_setup ?? false,
    notes: plan.notes ?? "",
  };
}

function editToPatch(state: EditState): Partial<TradePlan> {
  const patch: Record<string, unknown> = { status: state.status };

  // String fields: always send so empty string clears the stored value
  patch.symbol = state.symbol ? state.symbol.toUpperCase() : "";
  patch.intended_direction = state.intended_direction;
  patch.setup_type = state.setup_type;
  patch.strategy = state.strategy;
  patch.bias = state.bias;
  patch.thesis = state.thesis;
  patch.entry_logic = state.entry_logic;
  patch.stop_loss_logic = state.stop_loss_logic;
  patch.take_profit_logic = state.take_profit_logic;
  patch.invalidation_logic = state.invalidation_logic;
  patch.planned_entry_zone = state.planned_entry_zone;
  patch.notes = state.notes;

  // Numeric: only send if parseable
  if (state.planned_stop_loss !== "") {
    const v = parseFloat(state.planned_stop_loss);
    if (!isNaN(v)) patch.planned_stop_loss = v;
  }
  if (state.planned_take_profit !== "") {
    const v = parseFloat(state.planned_take_profit);
    if (!isNaN(v)) patch.planned_take_profit = v;
  }
  if (state.planned_rr !== "") {
    const v = parseFloat(state.planned_rr);
    if (!isNaN(v)) patch.planned_rr = v;
  }

  // Boolean: always send
  patch.is_a_plus_setup = state.is_a_plus_setup;

  return patch as Partial<TradePlan>;
}

// ── Status badge ──────────────────────────────────────────────────────────────

const STATUS_COLORS: Record<string, string> = {
  planned:   "bg-blue-900/40 text-blue-300 border-blue-700",
  linked:    "bg-green-900/40 text-green-300 border-green-700",
  cancelled: "bg-gray-700/40 text-gray-400 border-gray-600",
};

// ── Main page ─────────────────────────────────────────────────────────────────

export default function PlanDetailPage({ params }: { params: { planId: string } }) {
  const { planId } = params;
  const { accountId } = useAccount();
  const { mutate } = useSWRConfig();

  const swrKey = accountId && planId ? `trade-plan-${planId}` : null;
  const { data: plan, isLoading } = useSWR(
    swrKey,
    () => api.getTradePlan(accountId, planId)
  );

  // Trades for linking
  const { data: trades = [] } = useSWR(
    accountId ? `trades-${accountId}--` : null,
    () => api.listTrades(accountId)
  );

  const [editing, setEditing] = useState(false);
  const [editState, setEditState] = useState<EditState | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState(false);

  // Link trade state
  const [selectedTradeId, setSelectedTradeId] = useState("");
  const [linking, setLinking] = useState(false);
  const [linkError, setLinkError] = useState<string | null>(null);

  if (isLoading) return <p className="text-gray-500 text-sm">Loading…</p>;
  if (!plan) return <p className="text-gray-500 text-sm">Plan not found.</p>;

  const statusCls = STATUS_COLORS[plan.status] ?? STATUS_COLORS.planned;

  // Trades that are currently linked to this plan
  const linkedTrades = trades.filter((t: Trade) => t.trade_plan_id === planId);
  // Unlinked trades (no plan attached)
  const unlinkableTrades = trades.filter((t: Trade) => !t.trade_plan_id);

  function openEdit() {
    setEditState(initEdit(plan));
    setSaveError(null);
    setSaveSuccess(false);
    setEditing(true);
  }

  function closeEdit() {
    setEditing(false);
    setEditState(null);
  }

  async function handleSave() {
    if (!editState) return;
    setSaving(true);
    setSaveError(null);
    try {
      await api.updateTradePlan(accountId, planId, editToPatch(editState));
      await mutate(swrKey);
      await mutate(`trade-plans-${accountId}`);
      setSaveSuccess(true);
      setEditing(false);
      setEditState(null);
    } catch (err: unknown) {
      setSaveError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  async function handleLink() {
    if (!selectedTradeId) return;
    setLinking(true);
    setLinkError(null);
    try {
      await api.linkPlanToTrade(accountId, planId, selectedTradeId);
      await mutate(swrKey);
      await mutate(`trade-plans-${accountId}`);
      await mutate((key) => typeof key === "string" && key.startsWith(`trades-${accountId}`));
      setSelectedTradeId("");
    } catch (err: unknown) {
      setLinkError(err instanceof Error ? err.message : "Link failed");
    } finally {
      setLinking(false);
    }
  }

  async function handleUnlink(tradeId: string) {
    try {
      await api.unlinkPlanFromTrade(accountId, planId, tradeId);
      await mutate(swrKey);
      await mutate(`trade-plans-${accountId}`);
      await mutate((key) => typeof key === "string" && key.startsWith(`trades-${accountId}`));
    } catch (err: unknown) {
      setLinkError(err instanceof Error ? err.message : "Unlink failed");
    }
  }

  function set<K extends keyof EditState>(key: K, val: EditState[K]) {
    setEditState((prev) => prev ? { ...prev, [key]: val } : prev);
  }

  return (
    <div className="space-y-6 max-w-4xl">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link href="/plans" className="text-gray-500 hover:text-gray-300 text-sm">← Trade Plans</Link>
        <h1 className="text-xl font-semibold">
          {plan.symbol ?? "Plan"} {plan.intended_direction ? `(${plan.intended_direction})` : ""}
        </h1>
        <span className={`text-xs px-2 py-0.5 rounded border ${statusCls}`}>{plan.status}</span>
        {plan.is_a_plus_setup && (
          <span className="text-xs bg-yellow-900/40 text-yellow-300 px-2 py-0.5 rounded">A+</span>
        )}
        <div className="ml-auto">
          {!editing && (
            <button
              onClick={openEdit}
              className="px-3 py-1.5 text-xs bg-blue-600 hover:bg-blue-500 text-white rounded"
            >
              Edit Plan
            </button>
          )}
        </div>
      </div>

      {saveSuccess && !editing && (
        <div className="bg-green-900/40 border border-green-700 text-green-300 text-sm px-4 py-2 rounded">
          Saved successfully.
        </div>
      )}

      {/* Edit form */}
      {editing && editState && (
        <section className="bg-gray-900 border border-blue-700 rounded-lg p-5 space-y-5">
          <div className="flex items-center justify-between">
            <h2 className="text-xs uppercase tracking-wider text-blue-400">Edit Plan</h2>
            <button onClick={closeEdit} className="text-xs text-gray-500 hover:text-gray-300">✕ Cancel</button>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            <SelectInput
              label="Status"
              value={editState.status}
              onChange={(v) => set("status", v)}
              options={[
                { value: "planned", label: "Planned" },
                { value: "linked", label: "Linked" },
                { value: "cancelled", label: "Cancelled" },
              ]}
            />
            <TextInput label="Symbol" value={editState.symbol} onChange={(v) => set("symbol", v)} />
            <SelectInput
              label="Direction"
              value={editState.intended_direction}
              onChange={(v) => set("intended_direction", v)}
              options={[{ value: "long", label: "Long" }, { value: "short", label: "Short" }]}
            />
            <TextInput label="Setup Type" value={editState.setup_type} onChange={(v) => set("setup_type", v)} />
            <TextInput label="Strategy" value={editState.strategy} onChange={(v) => set("strategy", v)} />
            <TextInput label="Bias" value={editState.bias} onChange={(v) => set("bias", v)} />
          </div>

          <div className="space-y-3">
            <TextArea label="Trade Thesis" value={editState.thesis} onChange={(v) => set("thesis", v)} />
            <TextArea label="Entry Logic" value={editState.entry_logic} onChange={(v) => set("entry_logic", v)} />
            <TextArea label="Stop Loss Logic" value={editState.stop_loss_logic} onChange={(v) => set("stop_loss_logic", v)} />
            <TextArea label="Take Profit Logic" value={editState.take_profit_logic} onChange={(v) => set("take_profit_logic", v)} />
            <TextArea label="Invalidation" value={editState.invalidation_logic} onChange={(v) => set("invalidation_logic", v)} />
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <TextInput label="Entry Zone" value={editState.planned_entry_zone} onChange={(v) => set("planned_entry_zone", v)} />
            <TextInput label="Planned SL" value={editState.planned_stop_loss} onChange={(v) => set("planned_stop_loss", v)} />
            <TextInput label="Planned TP" value={editState.planned_take_profit} onChange={(v) => set("planned_take_profit", v)} />
            <TextInput label="Planned R:R" value={editState.planned_rr} onChange={(v) => set("planned_rr", v)} />
          </div>

          <label className="flex items-center gap-2 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={editState.is_a_plus_setup}
              onChange={(e) => set("is_a_plus_setup", e.target.checked)}
              className="w-3.5 h-3.5 accent-yellow-500"
            />
            <span className="text-xs text-gray-400">A+ Setup</span>
          </label>

          <TextArea label="Notes" value={editState.notes} onChange={(v) => set("notes", v)} />

          {saveError && (
            <div className="bg-red-900/40 border border-red-700 text-red-300 text-xs px-3 py-2 rounded">
              {saveError}
            </div>
          )}
          <div className="flex gap-3">
            <button onClick={handleSave} disabled={saving}
              className="px-4 py-2 text-sm bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded">
              {saving ? "Saving…" : "Save Changes"}
            </button>
            <button onClick={closeEdit} disabled={saving}
              className="px-4 py-2 text-sm bg-gray-700 hover:bg-gray-600 text-gray-200 rounded">
              Cancel
            </button>
          </div>
        </section>
      )}

      {/* Read-only plan view */}
      {!editing && (
        <>
          <section className="bg-gray-900 border border-gray-800 rounded-lg p-5">
            <h2 className="text-xs uppercase tracking-wider text-gray-500 mb-4">Plan Overview</h2>
            <dl className="grid grid-cols-2 sm:grid-cols-3 gap-4">
              <Field label="Symbol"    value={plan.symbol} />
              <Field label="Direction" value={plan.intended_direction} />
              <Field label="Setup"     value={plan.setup_type} />
              <Field label="Strategy"  value={plan.strategy} />
              <Field label="Bias"      value={plan.bias} />
              <Field label="R:R"       value={fmt(plan.planned_rr)} />
              <Field label="Entry Zone"  value={plan.planned_entry_zone} />
              <Field label="Planned SL"  value={fmt(plan.planned_stop_loss, 5)} />
              <Field label="Planned TP"  value={fmt(plan.planned_take_profit, 5)} />
            </dl>
            <p className="text-xs text-gray-600 mt-4">
              Created {plan.created_at ? fmtDateTime(plan.created_at) : "—"}
            </p>
          </section>

          <section className="bg-gray-900 border border-gray-800 rounded-lg p-5">
            <h2 className="text-xs uppercase tracking-wider text-gray-500 mb-4">Thesis & Logic</h2>
            <dl className="space-y-4">
              {plan.thesis && <Field label="Trade Thesis" value={plan.thesis} />}
              {plan.entry_logic && <Field label="Entry Logic" value={plan.entry_logic} />}
              {plan.stop_loss_logic && <Field label="Stop Loss Logic" value={plan.stop_loss_logic} />}
              {plan.take_profit_logic && <Field label="Take Profit Logic" value={plan.take_profit_logic} />}
              {plan.invalidation_logic && <Field label="Invalidation" value={plan.invalidation_logic} />}
              {plan.notes && <Field label="Notes" value={plan.notes} />}
            </dl>
          </section>

          {/* Linked trades */}
          <section className="bg-gray-900 border border-gray-800 rounded-lg p-5">
            <h2 className="text-xs uppercase tracking-wider text-gray-500 mb-4">Linked Trades</h2>

            {linkedTrades.length === 0 && (
              <p className="text-xs text-gray-500">No trades linked to this plan yet.</p>
            )}

            {linkedTrades.length > 0 && (
              <div className="space-y-2 mb-4">
                {linkedTrades.map((t: Trade) => (
                  <div key={t.trade_id} className="flex items-center justify-between bg-gray-800/50 rounded px-3 py-2">
                    <div>
                      <Link href={`/trades/${t.trade_id}`} className="text-sm text-blue-400 hover:text-blue-300">
                        {t.symbol} {t.direction} — {fmtDateTime(t.entry_datetime)}
                      </Link>
                      <span className={`ml-2 text-xs ${t.result === "win" ? "text-green-400" : t.result === "loss" ? "text-red-400" : "text-gray-400"}`}>
                        {t.result ?? "—"}
                      </span>
                    </div>
                    <button
                      onClick={() => handleUnlink(t.trade_id)}
                      className="text-xs text-gray-500 hover:text-red-400 transition-colors"
                    >
                      Unlink
                    </button>
                  </div>
                ))}
              </div>
            )}

            {/* Link a trade */}
            {plan.status !== "cancelled" && (
              <div className="flex items-center gap-3 mt-3">
                <select
                  value={selectedTradeId}
                  onChange={(e) => setSelectedTradeId(e.target.value)}
                  className="bg-gray-800 border border-gray-700 rounded px-2 py-1 text-sm text-gray-100 focus:outline-none focus:border-blue-500 flex-1"
                >
                  <option value="">Select a trade to link…</option>
                  {unlinkableTrades.map((t: Trade) => (
                    <option key={t.trade_id} value={t.trade_id}>
                      {t.symbol} {t.direction} — {t.entry_datetime ? new Date(t.entry_datetime).toLocaleDateString() : "?"} ({t.result ?? "?"})
                    </option>
                  ))}
                </select>
                <button
                  onClick={handleLink}
                  disabled={!selectedTradeId || linking}
                  className="px-3 py-1.5 text-xs bg-green-700 hover:bg-green-600 disabled:opacity-50 text-white rounded"
                >
                  {linking ? "Linking…" : "Link Trade"}
                </button>
              </div>
            )}

            {linkError && (
              <p className="text-xs text-red-400 mt-2">{linkError}</p>
            )}
          </section>
        </>
      )}
    </div>
  );
}
