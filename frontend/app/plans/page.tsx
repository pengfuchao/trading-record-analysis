"use client";

import { useState } from "react";
import Link from "next/link";
import useSWR, { useSWRConfig } from "swr";
import { api, TradePlan } from "@/lib/api";
import { useAccount } from "@/components/AccountProvider";
import AccountSelector from "@/components/AccountSelector";

const STATUS_COLORS: Record<string, string> = {
  planned:   "bg-blue-900/40 text-blue-300",
  linked:    "bg-green-900/40 text-green-300",
  cancelled: "bg-gray-700/40 text-gray-400",
};

function PlanStatusBadge({ status }: { status: string }) {
  const cls = STATUS_COLORS[status] ?? "bg-gray-700/40 text-gray-400";
  return (
    <span className={`text-xs px-2 py-0.5 rounded ${cls}`}>
      {status}
    </span>
  );
}

type CreateState = {
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

const EMPTY_CREATE: CreateState = {
  symbol: "", intended_direction: "", setup_type: "", strategy: "",
  bias: "", thesis: "", entry_logic: "", stop_loss_logic: "",
  take_profit_logic: "", invalidation_logic: "", planned_entry_zone: "",
  planned_stop_loss: "", planned_take_profit: "", planned_rr: "",
  is_a_plus_setup: false, notes: "",
};

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

export default function PlansPage() {
  const { accountId } = useAccount();
  const { mutate } = useSWRConfig();
  const swrKey = accountId ? `trade-plans-${accountId}` : null;

  const { data: plans = [], isLoading } = useSWR(
    swrKey,
    () => api.listTradePlans(accountId)
  );

  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState<CreateState>(EMPTY_CREATE);
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  function set<K extends keyof CreateState>(key: K, val: CreateState[K]) {
    setForm((prev) => ({ ...prev, [key]: val }));
  }

  async function handleCreate() {
    setCreating(true);
    setCreateError(null);
    try {
      const body: Partial<TradePlan> = {};
      if (form.symbol) body.symbol = form.symbol.toUpperCase();
      if (form.intended_direction) body.intended_direction = form.intended_direction;
      if (form.setup_type) body.setup_type = form.setup_type;
      if (form.strategy) body.strategy = form.strategy;
      if (form.bias) body.bias = form.bias;
      if (form.thesis) body.thesis = form.thesis;
      if (form.entry_logic) body.entry_logic = form.entry_logic;
      if (form.stop_loss_logic) body.stop_loss_logic = form.stop_loss_logic;
      if (form.take_profit_logic) body.take_profit_logic = form.take_profit_logic;
      if (form.invalidation_logic) body.invalidation_logic = form.invalidation_logic;
      if (form.planned_entry_zone) body.planned_entry_zone = form.planned_entry_zone;
      if (form.planned_stop_loss) body.planned_stop_loss = parseFloat(form.planned_stop_loss);
      if (form.planned_take_profit) body.planned_take_profit = parseFloat(form.planned_take_profit);
      if (form.planned_rr) body.planned_rr = parseFloat(form.planned_rr);
      if (form.is_a_plus_setup) body.is_a_plus_setup = form.is_a_plus_setup;
      if (form.notes) body.notes = form.notes;

      await api.createTradePlan(accountId, body);
      await mutate(swrKey);
      setForm(EMPTY_CREATE);
      setShowCreate(false);
    } catch (err: unknown) {
      setCreateError(err instanceof Error ? err.message : "Create failed");
    } finally {
      setCreating(false);
    }
  }

  return (
    <div className="space-y-6 max-w-4xl">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Trade Plans</h1>
        <div className="flex items-center gap-3">
          <AccountSelector />
          {accountId && !showCreate && (
            <button
              onClick={() => { setShowCreate(true); setCreateError(null); }}
              className="px-3 py-1.5 text-xs bg-blue-600 hover:bg-blue-500 text-white rounded transition-colors"
            >
              + New Plan
            </button>
          )}
        </div>
      </div>

      {!accountId && (
        <p className="text-gray-500 text-sm">Select an account to view and create trade plans.</p>
      )}

      {/* Create form */}
      {showCreate && accountId && (
        <section className="bg-gray-900 border border-blue-700 rounded-lg p-5 space-y-5">
          <div className="flex items-center justify-between">
            <h2 className="text-xs uppercase tracking-wider text-blue-400">New Trade Plan</h2>
            <button onClick={() => setShowCreate(false)} className="text-xs text-gray-500 hover:text-gray-300">✕ Cancel</button>
          </div>

          <div>
            <p className="text-xs text-gray-500 uppercase tracking-wider mb-2">Instrument</p>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
              <TextInput label="Symbol" value={form.symbol} onChange={(v) => set("symbol", v)} placeholder="e.g. XAUUSD" />
              <SelectInput
                label="Direction"
                value={form.intended_direction}
                onChange={(v) => set("intended_direction", v)}
                options={[{ value: "long", label: "Long" }, { value: "short", label: "Short" }]}
              />
              <TextInput label="Setup Type" value={form.setup_type} onChange={(v) => set("setup_type", v)} placeholder="e.g. OB Retest" />
              <TextInput label="Strategy" value={form.strategy} onChange={(v) => set("strategy", v)} placeholder="e.g. SMC" />
              <TextInput label="Bias" value={form.bias} onChange={(v) => set("bias", v)} placeholder="e.g. Bullish" />
            </div>
          </div>

          <div>
            <p className="text-xs text-gray-500 uppercase tracking-wider mb-2">Thesis & Logic</p>
            <div className="space-y-3">
              <TextArea label="Trade Thesis" value={form.thesis} onChange={(v) => set("thesis", v)} placeholder="Why does this trade make sense?" />
              <TextArea label="Entry Logic" value={form.entry_logic} onChange={(v) => set("entry_logic", v)} placeholder="What triggers the entry?" />
              <TextArea label="Stop Loss Logic" value={form.stop_loss_logic} onChange={(v) => set("stop_loss_logic", v)} placeholder="Where and why is the stop?" />
              <TextArea label="Take Profit Logic" value={form.take_profit_logic} onChange={(v) => set("take_profit_logic", v)} placeholder="What is the target?" />
              <TextArea label="Invalidation" value={form.invalidation_logic} onChange={(v) => set("invalidation_logic", v)} placeholder="What would invalidate this idea?" />
            </div>
          </div>

          <div>
            <p className="text-xs text-gray-500 uppercase tracking-wider mb-2">Planned Levels</p>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <TextInput label="Entry Zone" value={form.planned_entry_zone} onChange={(v) => set("planned_entry_zone", v)} placeholder="e.g. 1.0850–1.0870" />
              <TextInput label="Planned SL" value={form.planned_stop_loss} onChange={(v) => set("planned_stop_loss", v)} placeholder="Price" />
              <TextInput label="Planned TP" value={form.planned_take_profit} onChange={(v) => set("planned_take_profit", v)} placeholder="Price" />
              <TextInput label="Planned R:R" value={form.planned_rr} onChange={(v) => set("planned_rr", v)} placeholder="e.g. 2.5" />
            </div>
          </div>

          <div className="flex items-center gap-4">
            <label className="flex items-center gap-2 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={form.is_a_plus_setup}
                onChange={(e) => set("is_a_plus_setup", e.target.checked)}
                className="w-3.5 h-3.5 accent-yellow-500"
              />
              <span className="text-xs text-gray-400">A+ Setup</span>
            </label>
          </div>

          <TextArea label="Notes" value={form.notes} onChange={(v) => set("notes", v)} placeholder="Any other context" />

          {createError && (
            <div className="bg-red-900/40 border border-red-700 text-red-300 text-xs px-3 py-2 rounded">
              {createError}
            </div>
          )}
          <div className="flex items-center gap-3">
            <button
              onClick={handleCreate}
              disabled={creating}
              className="px-4 py-2 text-sm bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded"
            >
              {creating ? "Creating…" : "Create Plan"}
            </button>
            <button
              onClick={() => setShowCreate(false)}
              disabled={creating}
              className="px-4 py-2 text-sm bg-gray-700 hover:bg-gray-600 text-gray-200 rounded"
            >
              Cancel
            </button>
          </div>
        </section>
      )}

      {/* Plans list */}
      {accountId && isLoading && <p className="text-gray-500 text-sm">Loading…</p>}

      {accountId && !isLoading && plans.length === 0 && !showCreate && (
        <p className="text-gray-500 text-sm">No trade plans yet. Click "+ New Plan" to write your first pre-trade plan.</p>
      )}

      {plans.length > 0 && (
        <div className="bg-gray-900 border border-gray-800 rounded-lg divide-y divide-gray-800">
          {plans.map((plan) => (
            <div key={plan.plan_id} className="px-4 py-3 flex items-center justify-between hover:bg-gray-800/40">
              <div className="flex items-center gap-3 min-w-0">
                <PlanStatusBadge status={plan.status} />
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-gray-100">
                      {plan.symbol ?? "—"} {plan.intended_direction ? `(${plan.intended_direction})` : ""}
                    </span>
                    {plan.setup_type && (
                      <span className="text-xs text-gray-500">{plan.setup_type}</span>
                    )}
                    {plan.is_a_plus_setup && (
                      <span className="text-xs bg-yellow-900/40 text-yellow-300 px-1.5 py-0.5 rounded">A+</span>
                    )}
                  </div>
                  {plan.thesis && (
                    <p className="text-xs text-gray-500 truncate max-w-sm mt-0.5">{plan.thesis}</p>
                  )}
                  {plan.planned_rr != null && (
                    <p className="text-xs text-gray-600 mt-0.5">R:R {plan.planned_rr}</p>
                  )}
                </div>
              </div>
              <Link
                href={`/plans/${plan.plan_id}`}
                className="text-xs text-blue-400 hover:text-blue-300 ml-4 shrink-0"
              >
                View →
              </Link>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
