"use client";

import { useState } from "react";
import { api, WeeklyReviewResponse } from "@/lib/api";
import { useAccount } from "@/components/AccountProvider";
import AccountSelector from "@/components/AccountSelector";

function isoWeekBounds(): { from: string; to: string } {
  const today = new Date();
  const dow = today.getDay(); // 0=Sun
  const mon = new Date(today);
  mon.setDate(today.getDate() - ((dow + 6) % 7));
  const sun = new Date(mon);
  sun.setDate(mon.getDate() + 6);
  const fmt = (d: Date) => d.toISOString().slice(0, 10);
  return { from: fmt(mon), to: fmt(sun) };
}

export default function CoachingPage() {
  const { accountId } = useAccount();
  const defaultDates = isoWeekBounds();

  const [fromDate, setFromDate] = useState(defaultDates.from);
  const [toDate, setToDate] = useState(defaultDates.to);
  const [loading, setLoading] = useState(false);
  const [review, setReview] = useState<WeeklyReviewResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleGenerate = async () => {
    if (!accountId) return;
    setLoading(true);
    setError(null);
    setReview(null);
    try {
      const data = await api.generateWeeklyReview(accountId, {
        from_date: fromDate ? `${fromDate}T00:00:00` : undefined,
        to_date: toDate ? `${toDate}T23:59:59` : undefined,
      });
      setReview(data);
    } catch (e: any) {
      setError(e.message ?? "Review generation failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6 max-w-3xl">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">AI Coach</h1>
        <AccountSelector />
      </div>

      {!accountId && (
        <p className="text-gray-500 text-sm">Select an account to generate a review.</p>
      )}

      {accountId && (
        <>
          {/* Date range + generate */}
          <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 flex flex-wrap items-end gap-4">
            <div className="flex flex-col gap-1">
              <label className="text-xs text-gray-500 uppercase tracking-wider">From</label>
              <input
                type="date"
                value={fromDate}
                onChange={(e) => setFromDate(e.target.value)}
                className="bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm text-gray-100 focus:outline-none focus:border-blue-500"
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs text-gray-500 uppercase tracking-wider">To</label>
              <input
                type="date"
                value={toDate}
                onChange={(e) => setToDate(e.target.value)}
                className="bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm text-gray-100 focus:outline-none focus:border-blue-500"
              />
            </div>
            <button
              onClick={handleGenerate}
              disabled={loading}
              className="bg-blue-600 hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm px-5 py-2 rounded-md transition-colors font-medium"
            >
              {loading ? (
                <span className="flex items-center gap-2">
                  <span className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  Generating…
                </span>
              ) : (
                "Generate Review"
              )}
            </button>
          </div>

          {error && (
            <div className="bg-red-900/40 border border-red-700 text-red-300 text-sm px-4 py-3 rounded-md">
              {error}
            </div>
          )}

          {review && (
            <div className="space-y-4">
              {/* Summary */}
              <section className="bg-gray-900 border border-gray-800 rounded-lg p-5">
                <h2 className="text-xs uppercase tracking-wider text-gray-500 mb-3">
                  Week Summary
                  {review.from_date && review.to_date && (
                    <span className="ml-2 normal-case text-gray-600">
                      {review.from_date} – {review.to_date}
                    </span>
                  )}
                </h2>
                <p className="text-sm text-gray-200 leading-relaxed">{review.summary}</p>
              </section>

              {/* Top mistakes */}
              {review.top_mistakes.length > 0 && (
                <section className="bg-gray-900 border border-gray-800 rounded-lg p-5">
                  <h2 className="text-xs uppercase tracking-wider text-gray-500 mb-3">Top Recurring Mistakes</h2>
                  <div className="space-y-3">
                    {review.top_mistakes.map((m, i) => (
                      <div key={i} className="flex gap-3">
                        <span className="text-xs font-semibold text-blue-400 bg-blue-900/30 px-2 py-0.5 rounded h-fit whitespace-nowrap">
                          {m.tag.replace(/_/g, " ")}
                        </span>
                        <p className="text-sm text-gray-300 leading-relaxed">{m.pattern}</p>
                      </div>
                    ))}
                  </div>
                </section>
              )}

              {/* Diagnosis */}
              <section className="bg-gray-900 border border-gray-800 rounded-lg p-5">
                <h2 className="text-xs uppercase tracking-wider text-gray-500 mb-3">Execution vs Analysis Diagnosis</h2>
                <p className="text-sm text-gray-200 leading-relaxed">{review.diagnosis}</p>
              </section>

              {/* Improvement priority */}
              <section className="bg-blue-950/40 border border-blue-800/60 rounded-lg p-5">
                <h2 className="text-xs uppercase tracking-wider text-blue-400/80 mb-3">Priority Improvement</h2>
                <p className="text-sm text-blue-100 leading-relaxed font-medium">{review.improvement}</p>
              </section>
            </div>
          )}
        </>
      )}
    </div>
  );
}
