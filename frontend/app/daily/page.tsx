"use client";

import { useState } from "react";
import useSWR, { mutate } from "swr";
import { api, DailyPlan, DailyReview } from "@/lib/api";
import { useAccount } from "@/components/AccountProvider";
import AccountSelector from "@/components/AccountSelector";
import { fmtDate, fmtPnl, pnlColor } from "@/lib/utils";

// ── Helpers ────────────────────────────────────────────────────────────────────

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

function Field({ label, value }: { label: string; value?: string | null }) {
  if (!value) return null;
  return (
    <div>
      <p className="text-xs text-gray-500 uppercase tracking-wider mb-0.5">{label}</p>
      <p className="text-sm text-gray-200 whitespace-pre-wrap">{value}</p>
    </div>
  );
}

// ── Plan card ─────────────────────────────────────────────────────────────────

function PlanCard({ plan }: { plan: DailyPlan }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-5 py-4 hover:bg-gray-800/50"
      >
        <div className="text-left">
          <p className="text-sm font-medium">{fmtDate(plan.trading_date)}</p>
          {plan.market_bias && (
            <p className="text-xs text-gray-500 mt-0.5">Bias: {plan.market_bias}</p>
          )}
        </div>
        <div className="flex items-center gap-4">
          {plan.symbols_in_focus.length > 0 && (
            <span className="text-xs text-gray-400">{plan.symbols_in_focus.join(", ")}</span>
          )}
          {plan.daily_max_risk_pct != null && (
            <span className="text-xs text-yellow-400">Max risk {plan.daily_max_risk_pct}%</span>
          )}
          <span className="text-gray-500">{open ? "▲" : "▼"}</span>
        </div>
      </button>

      {open && (
        <div className="border-t border-gray-800 px-5 py-4 space-y-3">
          <Field label="Key Levels" value={plan.key_levels} />
          <Field label="Major News" value={plan.major_news} />
          {plan.allowed_setups.length > 0 && (
            <div>
              <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">Allowed Setups</p>
              <div className="flex flex-wrap gap-1">
                {plan.allowed_setups.map((s) => (
                  <span key={s} className="text-xs bg-green-900/40 text-green-300 px-2 py-0.5 rounded">{s}</span>
                ))}
              </div>
            </div>
          )}
          {plan.disallowed_setups.length > 0 && (
            <div>
              <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">Disallowed Setups</p>
              <div className="flex flex-wrap gap-1">
                {plan.disallowed_setups.map((s) => (
                  <span key={s} className="text-xs bg-red-900/40 text-red-300 px-2 py-0.5 rounded">{s}</span>
                ))}
              </div>
            </div>
          )}
          <Field label="Behavioral Focus" value={plan.behavioral_focus} />
          <Field label="Special Rule" value={plan.special_rule} />
          {plan.max_trades != null && (
            <p className="text-xs text-gray-400">Max trades: {plan.max_trades}</p>
          )}
        </div>
      )}
    </div>
  );
}

// ── Review card ───────────────────────────────────────────────────────────────

function ReviewCard({ review }: { review: DailyReview }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-5 py-4 hover:bg-gray-800/50"
      >
        <div className="text-left">
          <p className="text-sm font-medium">{fmtDate(review.trading_date)}</p>
          <p className="text-xs text-gray-500 mt-0.5">
            {review.total_trades ?? "?"} trades
          </p>
        </div>
        <div className="flex items-center gap-4">
          {review.total_pnl != null && (
            <span className={`text-sm font-mono font-medium ${pnlColor(review.total_pnl)}`}>
              {fmtPnl(review.total_pnl)}
            </span>
          )}
          <span className={`text-xs px-2 py-0.5 rounded ${review.process_success ? "bg-green-900/40 text-green-300" : "bg-red-900/40 text-red-300"}`}>
            {review.process_success ? "Process ✓" : "Process ✗"}
          </span>
          <span className="text-gray-500">{open ? "▲" : "▼"}</span>
        </div>
      </button>

      {open && (
        <div className="border-t border-gray-800 px-5 py-4 space-y-3">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
            <div>
              <p className="text-xs text-gray-500">Planned Trades</p>
              <p>{review.planned_trades ?? "—"}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500">Unplanned Trades</p>
              <p className={review.unplanned_trades ? "text-yellow-300" : ""}>{review.unplanned_trades ?? "—"}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500">Total R</p>
              <p className={pnlColor(review.total_r)}>{review.total_r != null ? review.total_r.toFixed(2) : "—"}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500">PnL Success</p>
              <p className={review.pnl_success ? "text-green-400" : "text-red-400"}>
                {review.pnl_success == null ? "—" : review.pnl_success ? "Yes" : "No"}
              </p>
            </div>
          </div>
          <Field label="Biggest Mistake" value={review.biggest_mistake} />
          <Field label="Emotional Summary" value={review.emotional_summary} />
          <Field label="Improvement Point" value={review.improvement_point} />
          <Field label="Notes" value={review.notes} />
        </div>
      )}
    </div>
  );
}

// ── New Plan form ─────────────────────────────────────────────────────────────

function NewPlanForm({ accountId, onDone }: { accountId: string; onDone: () => void }) {
  const [form, setForm] = useState({
    trading_date: today(),
    market_bias: "",
    symbols_in_focus: "",
    key_levels: "",
    major_news: "",
    allowed_setups: "",
    disallowed_setups: "",
    daily_max_risk_pct: "",
    max_trades: "",
    behavioral_focus: "",
    special_rule: "",
  });
  const [saving, setSaving] = useState(false);

  const set = (k: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.value }));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      await api.createPlan(accountId, {
        trading_date: form.trading_date,
        market_bias: form.market_bias || undefined,
        symbols_in_focus: form.symbols_in_focus ? form.symbols_in_focus.split(",").map((s) => s.trim()) : [],
        key_levels: form.key_levels || undefined,
        major_news: form.major_news || undefined,
        allowed_setups: form.allowed_setups ? form.allowed_setups.split(",").map((s) => s.trim()) : [],
        disallowed_setups: form.disallowed_setups ? form.disallowed_setups.split(",").map((s) => s.trim()) : [],
        daily_max_risk_pct: form.daily_max_risk_pct ? parseFloat(form.daily_max_risk_pct) : undefined,
        max_trades: form.max_trades ? parseInt(form.max_trades) : undefined,
        behavioral_focus: form.behavioral_focus || undefined,
        special_rule: form.special_rule || undefined,
      });
      mutate(`plans-${accountId}`);
      onDone();
    } catch (err: any) {
      alert(err.message);
    } finally {
      setSaving(false);
    }
  };

  const inputCls = "bg-gray-800 border border-gray-700 rounded-md px-3 py-2 text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:ring-1 focus:ring-blue-500 w-full";
  const labelCls = "block text-xs text-gray-500 uppercase tracking-wider mb-1";

  return (
    <form onSubmit={handleSubmit} className="bg-gray-900 border border-gray-800 rounded-lg p-5 space-y-4">
      <h3 className="text-sm font-semibold text-gray-100">New Pre-Market Plan</h3>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div>
          <label className={labelCls}>Date *</label>
          <input type="date" value={form.trading_date} onChange={set("trading_date")} required className={inputCls} />
        </div>
        <div>
          <label className={labelCls}>Market Bias</label>
          <input placeholder="bullish / bearish / neutral" value={form.market_bias} onChange={set("market_bias")} className={inputCls} />
        </div>
        <div>
          <label className={labelCls}>Symbols in Focus (comma-separated)</label>
          <input placeholder="XAUUSD, US30, EURUSD" value={form.symbols_in_focus} onChange={set("symbols_in_focus")} className={inputCls} />
        </div>
        <div>
          <label className={labelCls}>Max Risk % / day</label>
          <input type="number" step="0.1" placeholder="2.0" value={form.daily_max_risk_pct} onChange={set("daily_max_risk_pct")} className={inputCls} />
        </div>
        <div>
          <label className={labelCls}>Max Trades</label>
          <input type="number" placeholder="3" value={form.max_trades} onChange={set("max_trades")} className={inputCls} />
        </div>
        <div>
          <label className={labelCls}>Allowed Setups (comma-separated)</label>
          <input value={form.allowed_setups} onChange={set("allowed_setups")} className={inputCls} />
        </div>
        <div>
          <label className={labelCls}>Disallowed Setups (comma-separated)</label>
          <input value={form.disallowed_setups} onChange={set("disallowed_setups")} className={inputCls} />
        </div>
      </div>
      <div>
        <label className={labelCls}>Key Levels</label>
        <textarea rows={2} value={form.key_levels} onChange={set("key_levels")} className={inputCls} />
      </div>
      <div>
        <label className={labelCls}>Major News</label>
        <textarea rows={2} value={form.major_news} onChange={set("major_news")} className={inputCls} />
      </div>
      <div>
        <label className={labelCls}>Behavioral Focus</label>
        <textarea rows={2} value={form.behavioral_focus} onChange={set("behavioral_focus")} className={inputCls} />
      </div>
      <div>
        <label className={labelCls}>Special Rule for Today</label>
        <input value={form.special_rule} onChange={set("special_rule")} className={inputCls} />
      </div>
      <div className="flex gap-3">
        <button type="submit" disabled={saving} className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm px-4 py-2 rounded-md transition-colors">
          {saving ? "Saving…" : "Save Plan"}
        </button>
        <button type="button" onClick={onDone} className="text-gray-400 hover:text-gray-100 text-sm px-4 py-2 rounded-md transition-colors">
          Cancel
        </button>
      </div>
    </form>
  );
}

// ── New Review form ───────────────────────────────────────────────────────────

function NewReviewForm({ accountId, onDone }: { accountId: string; onDone: () => void }) {
  const [form, setForm] = useState({
    trading_date: today(),
    total_trades: "",
    total_pnl: "",
    total_r: "",
    planned_trades: "",
    unplanned_trades: "",
    biggest_mistake: "",
    emotional_summary: "",
    improvement_point: "",
    notes: "",
    process_success: "",
    pnl_success: "",
  });
  const [saving, setSaving] = useState(false);

  const set = (k: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.value }));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      await api.createReview(accountId, {
        trading_date: form.trading_date,
        total_trades: form.total_trades ? parseInt(form.total_trades) : undefined,
        total_pnl: form.total_pnl ? parseFloat(form.total_pnl) : undefined,
        total_r: form.total_r ? parseFloat(form.total_r) : undefined,
        planned_trades: form.planned_trades ? parseInt(form.planned_trades) : undefined,
        unplanned_trades: form.unplanned_trades ? parseInt(form.unplanned_trades) : undefined,
        biggest_mistake: form.biggest_mistake || undefined,
        emotional_summary: form.emotional_summary || undefined,
        improvement_point: form.improvement_point || undefined,
        notes: form.notes || undefined,
        process_success: form.process_success === "" ? undefined : form.process_success === "true",
        pnl_success: form.pnl_success === "" ? undefined : form.pnl_success === "true",
      });
      mutate(`reviews-${accountId}`);
      onDone();
    } catch (err: any) {
      alert(err.message);
    } finally {
      setSaving(false);
    }
  };

  const inputCls = "bg-gray-800 border border-gray-700 rounded-md px-3 py-2 text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:ring-1 focus:ring-blue-500 w-full";
  const labelCls = "block text-xs text-gray-500 uppercase tracking-wider mb-1";

  return (
    <form onSubmit={handleSubmit} className="bg-gray-900 border border-gray-800 rounded-lg p-5 space-y-4">
      <h3 className="text-sm font-semibold text-gray-100">New Post-Market Review</h3>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div>
          <label className={labelCls}>Date *</label>
          <input type="date" value={form.trading_date} onChange={set("trading_date")} required className={inputCls} />
        </div>
        <div>
          <label className={labelCls}>Total Trades</label>
          <input type="number" value={form.total_trades} onChange={set("total_trades")} className={inputCls} />
        </div>
        <div>
          <label className={labelCls}>Total PnL ($)</label>
          <input type="number" step="0.01" value={form.total_pnl} onChange={set("total_pnl")} className={inputCls} />
        </div>
        <div>
          <label className={labelCls}>Total R</label>
          <input type="number" step="0.1" value={form.total_r} onChange={set("total_r")} className={inputCls} />
        </div>
        <div>
          <label className={labelCls}>Planned Trades</label>
          <input type="number" value={form.planned_trades} onChange={set("planned_trades")} className={inputCls} />
        </div>
        <div>
          <label className={labelCls}>Unplanned Trades</label>
          <input type="number" value={form.unplanned_trades} onChange={set("unplanned_trades")} className={inputCls} />
        </div>
        <div>
          <label className={labelCls}>Process Success?</label>
          <select value={form.process_success} onChange={set("process_success")} className={inputCls}>
            <option value="">—</option>
            <option value="true">Yes</option>
            <option value="false">No</option>
          </select>
        </div>
        <div>
          <label className={labelCls}>PnL Success?</label>
          <select value={form.pnl_success} onChange={set("pnl_success")} className={inputCls}>
            <option value="">—</option>
            <option value="true">Yes</option>
            <option value="false">No</option>
          </select>
        </div>
      </div>
      <div>
        <label className={labelCls}>Biggest Mistake</label>
        <input value={form.biggest_mistake} onChange={set("biggest_mistake")} className={inputCls} />
      </div>
      <div>
        <label className={labelCls}>Emotional Summary</label>
        <textarea rows={2} value={form.emotional_summary} onChange={set("emotional_summary")} className={inputCls} />
      </div>
      <div>
        <label className={labelCls}>Improvement Point for Tomorrow</label>
        <textarea rows={2} value={form.improvement_point} onChange={set("improvement_point")} className={inputCls} />
      </div>
      <div>
        <label className={labelCls}>Notes</label>
        <textarea rows={2} value={form.notes} onChange={set("notes")} className={inputCls} />
      </div>
      <div className="flex gap-3">
        <button type="submit" disabled={saving} className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm px-4 py-2 rounded-md transition-colors">
          {saving ? "Saving…" : "Save Review"}
        </button>
        <button type="button" onClick={onDone} className="text-gray-400 hover:text-gray-100 text-sm px-4 py-2 rounded-md transition-colors">
          Cancel
        </button>
      </div>
    </form>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function DailyPage() {
  const { accountId } = useAccount();
  const [tab, setTab] = useState<"plans" | "reviews">("plans");
  const [showNewPlan, setShowNewPlan] = useState(false);
  const [showNewReview, setShowNewReview] = useState(false);

  const { data: plans = [], isLoading: plansLoading } = useSWR(
    accountId ? `plans-${accountId}` : null,
    () => api.listPlans(accountId)
  );
  const { data: reviews = [], isLoading: reviewsLoading } = useSWR(
    accountId ? `reviews-${accountId}` : null,
    () => api.listReviews(accountId)
  );

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Daily Plans & Reviews</h1>
        <AccountSelector />
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-gray-800">
        {(["plans", "reviews"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm capitalize transition-colors border-b-2 -mb-px ${
              tab === t ? "border-blue-500 text-blue-400" : "border-transparent text-gray-500 hover:text-gray-300"
            }`}
          >
            {t === "plans" ? "Pre-Market Plans" : "Post-Market Reviews"}
          </button>
        ))}
      </div>

      {tab === "plans" && (
        <div className="space-y-3">
          <div className="flex justify-end">
            <button
              onClick={() => setShowNewPlan(!showNewPlan)}
              className="bg-blue-600 hover:bg-blue-700 text-white text-sm px-4 py-2 rounded-md transition-colors"
            >
              + New Plan
            </button>
          </div>
          {showNewPlan && accountId && (
            <NewPlanForm accountId={accountId} onDone={() => setShowNewPlan(false)} />
          )}
          {plansLoading && <p className="text-gray-500 text-sm">Loading…</p>}
          {!plansLoading && plans.length === 0 && !showNewPlan && (
            <p className="text-gray-500 text-sm">No pre-market plans yet.</p>
          )}
          {plans.map((p) => <PlanCard key={p.plan_id} plan={p} />)}
        </div>
      )}

      {tab === "reviews" && (
        <div className="space-y-3">
          <div className="flex justify-end">
            <button
              onClick={() => setShowNewReview(!showNewReview)}
              className="bg-blue-600 hover:bg-blue-700 text-white text-sm px-4 py-2 rounded-md transition-colors"
            >
              + New Review
            </button>
          </div>
          {showNewReview && accountId && (
            <NewReviewForm accountId={accountId} onDone={() => setShowNewReview(false)} />
          )}
          {reviewsLoading && <p className="text-gray-500 text-sm">Loading…</p>}
          {!reviewsLoading && reviews.length === 0 && !showNewReview && (
            <p className="text-gray-500 text-sm">No post-market reviews yet.</p>
          )}
          {reviews.map((r) => <ReviewCard key={r.review_id} review={r} />)}
        </div>
      )}
    </div>
  );
}
