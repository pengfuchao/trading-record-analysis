"use client";

import { useState } from "react";
import useSWR, { useSWRConfig } from "swr";
import { api, SetupDefinition, SetupStatsResponse, SetupReportResponse } from "@/lib/api";
import { useAccount } from "@/components/AccountProvider";
import AccountSelector from "@/components/AccountSelector";
import { fmtPct, fmt, fmtPnl, pnlColor } from "@/lib/utils";

// ── Form state ────────────────────────────────────────────────────────────────

type SetupFormState = {
  setup_id: string;
  name: string;
  strategy_group: string;
  description: string;
  market_environment: string;
  preconditions: string;
  entry_criteria: string;
  confirmation_rules: string;
  stop_loss_rules: string;
  take_profit_rules: string;
  invalidation_conditions: string;
  common_mistakes: string;
  notes: string;
};

function emptyForm(): SetupFormState {
  return {
    setup_id: "", name: "", strategy_group: "", description: "",
    market_environment: "", preconditions: "", entry_criteria: "",
    confirmation_rules: "", stop_loss_rules: "", take_profit_rules: "",
    invalidation_conditions: "", common_mistakes: "", notes: "",
  };
}

function fromSetup(s: SetupDefinition): SetupFormState {
  return {
    setup_id: s.setup_id,
    name: s.name,
    strategy_group: s.strategy_group ?? "",
    description: s.description ?? "",
    market_environment: s.market_environment ?? "",
    preconditions: s.preconditions ?? "",
    entry_criteria: s.entry_criteria ?? "",
    confirmation_rules: s.confirmation_rules ?? "",
    stop_loss_rules: s.stop_loss_rules ?? "",
    take_profit_rules: s.take_profit_rules ?? "",
    invalidation_conditions: s.invalidation_conditions ?? "",
    common_mistakes: s.common_mistakes ?? "",
    notes: s.notes ?? "",
  };
}

function slugify(name: string): string {
  return name.toLowerCase().trim().replace(/\s+/g, "-").replace(/[^a-z0-9-]/g, "");
}

// For create: omit empty optional fields. For update: send all (empty string clears stored value).
function formToCreatePayload(state: SetupFormState): Record<string, unknown> {
  const payload: Record<string, unknown> = {
    setup_id: state.setup_id.trim(),
    name: state.name.trim(),
  };
  const optional: (keyof SetupFormState)[] = [
    "strategy_group", "description", "market_environment", "preconditions",
    "entry_criteria", "confirmation_rules", "stop_loss_rules", "take_profit_rules",
    "invalidation_conditions", "common_mistakes", "notes",
  ];
  for (const key of optional) {
    if (state[key]) payload[key] = state[key];
  }
  return payload;
}

function formToUpdatePatch(state: SetupFormState): Partial<SetupDefinition> {
  return {
    name: state.name.trim(),
    strategy_group: state.strategy_group || undefined,
    description: state.description || undefined,
    market_environment: state.market_environment || undefined,
    preconditions: state.preconditions || undefined,
    entry_criteria: state.entry_criteria || undefined,
    confirmation_rules: state.confirmation_rules || undefined,
    stop_loss_rules: state.stop_loss_rules || undefined,
    take_profit_rules: state.take_profit_rules || undefined,
    invalidation_conditions: state.invalidation_conditions || undefined,
    common_mistakes: state.common_mistakes || undefined,
    notes: state.notes || undefined,
  };
}

// ── Input helpers (consistent with plan detail page style) ────────────────────

function TextInput({ label, value, onChange, placeholder, readOnly }: {
  label: string; value: string; onChange?: (v: string) => void;
  placeholder?: string; readOnly?: boolean;
}) {
  return (
    <div>
      <label className="block text-xs text-gray-500 uppercase tracking-wider mb-0.5">{label}</label>
      <input
        readOnly={readOnly}
        className={`w-full bg-gray-800 border border-gray-700 rounded px-2 py-1 text-sm text-gray-100 focus:outline-none focus:border-blue-500 ${readOnly ? "opacity-60 cursor-default" : ""}`}
        value={value}
        onChange={readOnly ? undefined : (e) => onChange?.(e.target.value)}
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

// ── Shared create/edit form ───────────────────────────────────────────────────

function SetupForm({
  initial,
  isNew = false,
  onSave,
  onCancel,
}: {
  initial: SetupFormState;
  isNew?: boolean;
  onSave: (data: SetupFormState) => Promise<void>;
  onCancel: () => void;
}) {
  const [state, setState] = useState<SetupFormState>(initial);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [idTouched, setIdTouched] = useState(false);

  function set<K extends keyof SetupFormState>(key: K, val: string) {
    setState((prev) => {
      const next = { ...prev, [key]: val };
      if (key === "name" && isNew && !idTouched) {
        next.setup_id = slugify(val);
      }
      return next;
    });
  }

  async function handleSave() {
    if (!state.name.trim()) { setError("Name is required."); return; }
    if (!state.setup_id.trim()) { setError("Setup ID is required."); return; }
    setSaving(true);
    setError(null);
    try {
      await onSave(state);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Save failed");
      setSaving(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <TextInput
          label="Name *"
          value={state.name}
          onChange={(v) => set("name", v)}
          placeholder="e.g. ICT BOS Retest"
        />
        <TextInput
          label={isNew ? "Setup ID (slug) *" : "Setup ID"}
          value={state.setup_id}
          readOnly={!isNew}
          onChange={isNew ? (v) => { setIdTouched(true); set("setup_id", v); } : undefined}
          placeholder="e.g. ict-bos-retest"
        />
        <TextInput
          label="Strategy Group"
          value={state.strategy_group}
          onChange={(v) => set("strategy_group", v)}
          placeholder="e.g. ICT, SMC, Price Action"
        />
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <TextInput
          label="Description"
          value={state.description}
          onChange={(v) => set("description", v)}
          placeholder="Brief description of the setup"
        />
        <TextInput
          label="Market Environment"
          value={state.market_environment}
          onChange={(v) => set("market_environment", v)}
          placeholder="e.g. Trending, Ranging, High Volatility"
        />
      </div>
      <TextArea
        label="Preconditions"
        value={state.preconditions}
        onChange={(v) => set("preconditions", v)}
        placeholder="Required market conditions before entry"
      />
      <TextArea
        label="Entry Criteria"
        value={state.entry_criteria}
        onChange={(v) => set("entry_criteria", v)}
        placeholder="Specific triggers for entry"
      />
      <TextArea
        label="Confirmation Rules"
        value={state.confirmation_rules}
        onChange={(v) => set("confirmation_rules", v)}
        placeholder="Additional confirmation needed"
      />
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <TextArea
          label="Stop Loss Rules"
          value={state.stop_loss_rules}
          onChange={(v) => set("stop_loss_rules", v)}
          placeholder="Where and how to set SL"
        />
        <TextArea
          label="Take Profit Rules"
          value={state.take_profit_rules}
          onChange={(v) => set("take_profit_rules", v)}
          placeholder="Where and how to set TP"
        />
      </div>
      <TextArea
        label="Invalidation Conditions"
        value={state.invalidation_conditions}
        onChange={(v) => set("invalidation_conditions", v)}
        placeholder="What cancels this setup"
      />
      <TextArea
        label="Common Mistakes"
        value={state.common_mistakes}
        onChange={(v) => set("common_mistakes", v)}
        placeholder="Frequent errors to watch for"
      />
      <TextArea
        label="Notes"
        value={state.notes}
        onChange={(v) => set("notes", v)}
      />
      {error && (
        <div className="bg-red-900/40 border border-red-700 text-red-300 text-xs px-3 py-2 rounded">
          {error}
        </div>
      )}
      <div className="flex gap-3">
        <button
          onClick={handleSave}
          disabled={saving}
          className="px-4 py-2 text-sm bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded"
        >
          {saving ? "Saving…" : isNew ? "Create Setup" : "Save Changes"}
        </button>
        <button
          onClick={onCancel}
          disabled={saving}
          className="px-4 py-2 text-sm bg-gray-700 hover:bg-gray-600 text-gray-200 rounded"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}

// ── Read-only expanded detail ─────────────────────────────────────────────────

function SetupDetail({ setup }: { setup: SetupDefinition }) {
  return (
    <div className="space-y-3 text-sm text-gray-300">
      {setup.description && <DetailField label="Description" value={setup.description} />}
      {setup.market_environment && <DetailField label="Market Environment" value={setup.market_environment} />}
      {setup.preconditions && <DetailField label="Preconditions" value={setup.preconditions} />}
      {setup.entry_criteria && <DetailField label="Entry Criteria" value={setup.entry_criteria} />}
      {setup.confirmation_rules && <DetailField label="Confirmation Rules" value={setup.confirmation_rules} />}
      {setup.stop_loss_rules && <DetailField label="Stop Loss Rules" value={setup.stop_loss_rules} />}
      {setup.take_profit_rules && <DetailField label="Take Profit Rules" value={setup.take_profit_rules} />}
      {setup.invalidation_conditions && <DetailField label="Invalidation" value={setup.invalidation_conditions} />}
      {setup.common_mistakes && <DetailField label="Common Mistakes" value={setup.common_mistakes} />}
      {setup.notes && <DetailField label="Notes" value={setup.notes} />}
    </div>
  );
}

function DetailField({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">{label}</p>
      <p className="whitespace-pre-wrap">{value}</p>
    </div>
  );
}

// ── R:R realization ranking table ─────────────────────────────────────────────

const MIN_RR_N = 1;   // show numbers with 1+ qualifying trades
const SIGNAL_RR_N = 3; // only show coaching color-coding with 3+

function rrColor(pct: number | undefined): string {
  if (pct == null) return "text-gray-400";
  if (pct >= 90) return "text-green-400";
  if (pct >= 60) return "text-yellow-400";
  return "text-red-400";
}

function SetupRRTable({ report }: { report: SetupReportResponse }) {
  const ranked = report.ranked_by_rr_realization.filter(
    (name) => (report.by_setup[name]?.rr_sample_count ?? 0) >= MIN_RR_N
  );
  if (ranked.length === 0) return null;

  return (
    <section className="bg-gray-900 border border-gray-800 rounded-lg p-5">
      <h2 className="text-xs uppercase tracking-wider text-gray-500 mb-3">
        R:R Realization by Setup
      </h2>
      <p className="text-xs text-gray-600 mb-4">
        Planned R:R vs realized R for trades with a linked plan and <code className="text-gray-500">planned_rr</code> set.
        Signals require ≥ {SIGNAL_RR_N} qualifying trades.
      </p>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-gray-500 border-b border-gray-800">
              <th className="text-left pb-2 pr-4 font-normal">Setup</th>
              <th className="text-right pb-2 pr-4 font-normal">n</th>
              <th className="text-right pb-2 pr-4 font-normal">Planned R</th>
              <th className="text-right pb-2 pr-4 font-normal">Realized R</th>
              <th className="text-right pb-2 pr-4 font-normal">Shortfall</th>
              <th className="text-right pb-2 pr-4 font-normal">Realization %</th>
              <th className="text-right pb-2 font-normal">Target Hit %</th>
            </tr>
          </thead>
          <tbody>
            {ranked.map((name) => {
              const s = report.by_setup[name];
              if (!s) return null;
              const hasSignal = s.rr_sample_count >= SIGNAL_RR_N;
              return (
                <tr key={name} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                  <td className="py-2 pr-4 text-gray-100 font-medium">{name}</td>
                  <td className="py-2 pr-4 text-right font-mono text-gray-300">
                    {s.rr_sample_count}
                    {!hasSignal && (
                      <span className="text-gray-600 ml-1" title="Need ≥ 3 trades for signals">*</span>
                    )}
                  </td>
                  <td className="py-2 pr-4 text-right font-mono text-gray-300">
                    {s.rr_avg_planned_rr != null ? `${s.rr_avg_planned_rr.toFixed(2)}R` : "—"}
                  </td>
                  <td className={`py-2 pr-4 text-right font-mono ${pnlColor(s.rr_avg_actual_r)}`}>
                    {s.rr_avg_actual_r != null ? `${s.rr_avg_actual_r > 0 ? "+" : ""}${s.rr_avg_actual_r.toFixed(2)}R` : "—"}
                  </td>
                  <td className={`py-2 pr-4 text-right font-mono ${pnlColor(s.rr_avg_shortfall)}`}>
                    {s.rr_avg_shortfall != null ? `${s.rr_avg_shortfall > 0 ? "+" : ""}${s.rr_avg_shortfall.toFixed(2)}R` : "—"}
                  </td>
                  <td className={`py-2 pr-4 text-right font-mono font-semibold ${hasSignal ? rrColor(s.rr_realization_pct) : "text-gray-400"}`}>
                    {s.rr_realization_pct != null ? `${s.rr_realization_pct.toFixed(0)}%` : "—"}
                  </td>
                  <td className={`py-2 text-right font-mono ${hasSignal ? rrColor(s.rr_pct_met_target) : "text-gray-400"}`}>
                    {s.rr_pct_met_target != null ? `${s.rr_pct_met_target.toFixed(0)}%` : "—"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {ranked.some((n) => (report.by_setup[n]?.rr_sample_count ?? 0) < SIGNAL_RR_N) && (
          <p className="text-xs text-gray-600 mt-2">* fewer than {SIGNAL_RR_N} qualifying trades — color signals not shown</p>
        )}
      </div>
    </section>
  );
}

// ── Setup card with edit/delete ───────────────────────────────────────────────

function SetupCard({
  setup,
  stats,
  onSaveEdit,
  onDelete,
}: {
  setup: SetupDefinition;
  stats?: SetupStatsResponse;
  onSaveEdit: (setupId: string, data: SetupFormState) => Promise<void>;
  onDelete: (setupId: string) => Promise<void>;
}) {
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  function openEdit() {
    setConfirmDelete(false);
    setDeleteError(null);
    setEditing(true);
    setOpen(true);
  }

  function cancelEdit() {
    setEditing(false);
  }

  async function handleSaveEdit(data: SetupFormState) {
    await onSaveEdit(setup.setup_id, data);
    setEditing(false);
    setOpen(false);
  }

  async function handleDelete() {
    setDeleting(true);
    try {
      await onDelete(setup.setup_id);
    } catch (err: unknown) {
      setDeleteError(err instanceof Error ? err.message : "Delete failed");
      setDeleting(false);
      setConfirmDelete(false);
    }
  }

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
      {/* Header row: name (toggle) + stats + actions */}
      <div className="flex items-center px-5 py-4">
        <button
          onClick={() => { if (!editing) setOpen((o) => !o); }}
          className="flex-1 min-w-0 text-left hover:opacity-80 transition-opacity"
        >
          <p className="text-sm font-medium text-gray-100">{setup.name}</p>
          {setup.strategy_group && (
            <p className="text-xs text-gray-500 mt-0.5">{setup.strategy_group}</p>
          )}
        </button>

        <div className="flex items-center gap-4 shrink-0 ml-4">
          {stats ? (
            <div className="flex items-center gap-6 text-right">
              <div>
                <p className="text-xs text-gray-500">Trades</p>
                <p className="text-sm font-mono">{stats.trade_count}</p>
              </div>
              <div>
                <p className="text-xs text-gray-500">Win Rate</p>
                <p className="text-sm font-mono">{fmtPct(stats.win_rate)}</p>
              </div>
              <div>
                <p className="text-xs text-gray-500">Avg R</p>
                <p className={`text-sm font-mono ${pnlColor(stats.avg_r_multiple)}`}>
                  {fmt(stats.avg_r_multiple)}
                </p>
              </div>
              <div>
                <p className="text-xs text-gray-500">Total PnL</p>
                <p className={`text-sm font-mono ${pnlColor(stats.total_net_profit)}`}>
                  {fmtPnl(stats.total_net_profit)}
                </p>
              </div>
              {stats.rr_sample_count > 0 && (
                <div title={`Based on ${stats.rr_sample_count} linked plan(s) with planned R:R set`}>
                  <p className="text-xs text-gray-500">R:R Real.</p>
                  <p className={`text-sm font-mono font-semibold ${stats.rr_sample_count >= SIGNAL_RR_N ? rrColor(stats.rr_realization_pct) : "text-gray-400"}`}>
                    {stats.rr_realization_pct != null ? `${stats.rr_realization_pct.toFixed(0)}%` : "—"}
                  </p>
                </div>
              )}
            </div>
          ) : (
            <p className="text-xs text-gray-600">No trade data</p>
          )}

          <div className="flex items-center gap-2 ml-2">
            {!confirmDelete && (
              <>
                <button
                  onClick={openEdit}
                  className="px-2.5 py-1 text-xs bg-gray-700 hover:bg-gray-600 text-gray-300 rounded transition-colors"
                >
                  Edit
                </button>
                <button
                  onClick={() => { setEditing(false); setConfirmDelete(true); }}
                  className="px-2.5 py-1 text-xs bg-gray-700 hover:bg-red-700 text-gray-400 hover:text-white rounded transition-colors"
                >
                  Delete
                </button>
                <span
                  onClick={() => { if (!editing) setOpen((o) => !o); }}
                  className="text-gray-500 cursor-pointer select-none text-xs"
                >
                  {open ? "▲" : "▼"}
                </span>
              </>
            )}
            {confirmDelete && (
              <div className="flex items-center gap-2">
                <span className="text-xs text-red-400">Delete?</span>
                <button
                  onClick={handleDelete}
                  disabled={deleting}
                  className="px-2.5 py-1 text-xs bg-red-700 hover:bg-red-600 disabled:opacity-50 text-white rounded"
                >
                  {deleting ? "…" : "Confirm"}
                </button>
                <button
                  onClick={() => { setConfirmDelete(false); setDeleteError(null); }}
                  disabled={deleting}
                  className="px-2.5 py-1 text-xs bg-gray-700 hover:bg-gray-600 text-gray-300 rounded"
                >
                  Cancel
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {deleteError && (
        <p className="text-xs text-red-400 px-5 pb-3">{deleteError}</p>
      )}

      {/* Edit form */}
      {editing && (
        <div className="border-t border-blue-700 px-5 py-4">
          <p className="text-xs uppercase tracking-wider text-blue-400 mb-4">Edit Setup</p>
          <SetupForm
            initial={fromSetup(setup)}
            isNew={false}
            onSave={handleSaveEdit}
            onCancel={cancelEdit}
          />
        </div>
      )}

      {/* Read-only expanded detail */}
      {open && !editing && (
        <div className="border-t border-gray-800 px-5 py-4">
          <SetupDetail setup={setup} />
        </div>
      )}
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function SetupsPage() {
  const { accountId } = useAccount();
  const { mutate } = useSWRConfig();
  const { data: setups = [], isLoading } = useSWR("setups", () => api.listSetups());
  const { data: setupReport } = useSWR(
    accountId ? `setup-report-${accountId}` : null,
    () => api.getSetupReport(accountId!)
  );

  const [showCreate, setShowCreate] = useState(false);

  const statsMap: Record<string, SetupStatsResponse> = setupReport?.by_setup ?? {};

  async function handleCreate(data: SetupFormState) {
    await api.createSetup(formToCreatePayload(data));
    await mutate("setups");
    setShowCreate(false);
  }

  async function handleUpdate(setupId: string, data: SetupFormState) {
    await api.updateSetup(setupId, formToUpdatePatch(data));
    await mutate("setups");
  }

  async function handleDelete(setupId: string) {
    await api.deleteSetup(setupId);
    await mutate("setups");
  }

  return (
    <div className="space-y-4">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Setup Library</h1>
        <div className="flex items-center gap-3">
          {!showCreate && (
            <button
              onClick={() => setShowCreate(true)}
              className="px-3 py-1.5 text-xs bg-blue-600 hover:bg-blue-500 text-white rounded"
            >
              + New Setup
            </button>
          )}
          <AccountSelector />
        </div>
      </div>

      {/* Create form (inline, same style as plan detail edit panel) */}
      {showCreate && (
        <section className="bg-gray-900 border border-blue-700 rounded-lg p-5 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-xs uppercase tracking-wider text-blue-400">New Setup</h2>
            <button
              onClick={() => setShowCreate(false)}
              className="text-xs text-gray-500 hover:text-gray-300"
            >
              ✕ Cancel
            </button>
          </div>
          <SetupForm
            initial={emptyForm()}
            isNew
            onSave={handleCreate}
            onCancel={() => setShowCreate(false)}
          />
        </section>
      )}

      {isLoading && <p className="text-gray-500 text-sm">Loading…</p>}

      {/* R:R realization ranking (only when account selected and data available) */}
      {accountId && setupReport && (
        <>
          <SetupRRTable report={setupReport} />
          {setupReport.trades_with_setup > 0 && setupReport.ranked_by_rr_realization.length === 0 && (
            <p className="text-xs text-gray-600 px-1">
              R:R Realization table appears when trades have a linked plan with{" "}
              <span className="font-mono">planned_rr &gt; 0</span> and{" "}
              <span className="font-mono">actual_r_multiple</span> set.
            </p>
          )}
        </>
      )}

      {/* Empty state */}
      {!isLoading && setups.length === 0 && !showCreate && (
        <div className="bg-gray-900 border border-gray-800 rounded-lg px-6 py-12 text-center">
          <p className="text-gray-400 text-sm mb-2">No setups defined yet.</p>
          <p className="text-gray-600 text-xs mb-5">
            Define your playbook — document each setup you trade so you can track performance by setup type.
          </p>
          <button
            onClick={() => setShowCreate(true)}
            className="px-4 py-2 text-sm bg-blue-600 hover:bg-blue-500 text-white rounded"
          >
            + Create First Setup
          </button>
        </div>
      )}

      {/* Setup list */}
      <div className="space-y-3">
        {setups.map((setup) => (
          <SetupCard
            key={setup.setup_id}
            setup={setup}
            stats={statsMap[setup.name] ?? statsMap[setup.setup_id]}
            onSaveEdit={handleUpdate}
            onDelete={handleDelete}
          />
        ))}
      </div>
    </div>
  );
}
