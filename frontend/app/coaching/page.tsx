"use client";

import { useState } from "react";
import useSWR from "swr";
import { api, WeeklyReviewResponse, CoachingReviewDetailResponse, CoachingReviewListItem } from "@/lib/api";
import { useAccount } from "@/components/AccountProvider";
import AccountSelector from "@/components/AccountSelector";

function isoWeekBounds(): { from: string; to: string } {
  const today = new Date();
  const dow = today.getDay();
  const mon = new Date(today);
  mon.setDate(today.getDate() - ((dow + 6) % 7));
  const sun = new Date(mon);
  sun.setDate(mon.getDate() + 6);
  const fmt = (d: Date) => d.toISOString().slice(0, 10);
  return { from: fmt(mon), to: fmt(sun) };
}

function SourceBadge({ source }: { source: string }) {
  if (source === "fallback") {
    return (
      <span className="text-xs bg-yellow-900/40 text-yellow-300 border border-yellow-700/50 px-2 py-0.5 rounded">
        Rule-based fallback
      </span>
    );
  }
  return (
    <span className="text-xs bg-green-900/40 text-green-300 border border-green-700/50 px-2 py-0.5 rounded">
      AI generated
    </span>
  );
}

function FallbackNotice() {
  return (
    <div className="bg-yellow-900/20 border border-yellow-700/50 rounded-lg px-4 py-3 flex gap-3 items-start">
      <span className="text-yellow-400 text-sm mt-0.5">⚠</span>
      <div className="space-y-1">
        <p className="text-yellow-300 text-sm font-medium">AI review unavailable — rule-based analysis used</p>
        <p className="text-yellow-200/70 text-xs leading-relaxed">
          This review was generated using rule-based pattern matching instead of the AI model.
          The most likely cause is a missing or invalid <code className="font-mono bg-yellow-900/40 px-1 rounded">ANTHROPIC_API_KEY</code> on
          the server. Set the key and regenerate to get a full AI-written review.
        </p>
      </div>
    </div>
  );
}

export default function CoachingPage() {
  const { accountId, accounts, isLoadingAccounts } = useAccount();
  const defaultDates = isoWeekBounds();

  const [fromDate, setFromDate] = useState(defaultDates.from);
  const [toDate, setToDate] = useState(defaultDates.to);
  const [loading, setLoading] = useState(false);
  const [review, setReview] = useState<WeeklyReviewResponse | CoachingReviewDetailResponse | null>(null);
  const [reviewIsHistory, setReviewIsHistory] = useState(false);
  const [loadingHistoryId, setLoadingHistoryId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const { data: history, mutate: refreshHistory } = useSWR(
    accountId ? `coaching-history-${accountId}` : null,
    () => api.listCoachingReviews(accountId!),
  );

  const handleGenerate = async () => {
    if (!accountId) return;
    setLoading(true);
    setError(null);
    setReview(null);
    setReviewIsHistory(false);
    try {
      const data = await api.generateWeeklyReview(accountId, {
        from_date: fromDate ? `${fromDate}T00:00:00` : undefined,
        to_date: toDate ? `${toDate}T23:59:59` : undefined,
      });
      setReview(data);
      refreshHistory();
    } catch (e: any) {
      setError(e.message ?? "Review generation failed");
    } finally {
      setLoading(false);
    }
  };

  const handleOpenHistoryItem = async (reviewId: string) => {
    if (!accountId) return;
    setLoadingHistoryId(reviewId);
    setError(null);
    try {
      const data = await api.getCoachingReview(accountId, reviewId);
      setReview(data);
      setReviewIsHistory(true);
    } catch (e: any) {
      setError(e.message ?? "Failed to load review");
    } finally {
      setLoadingHistoryId(null);
    }
  };

  return (
    <div className="space-y-6 max-w-3xl">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">AI Coach</h1>
        <AccountSelector />
      </div>

      {!accountId && !isLoadingAccounts && accounts.length === 0 && (
        <div className="rounded-lg border border-gray-800 bg-gray-900 px-5 py-10 text-center space-y-1">
          <p className="text-gray-300 text-sm font-medium">No accounts yet</p>
          <p className="text-gray-500 text-xs">Create your first account on the Dashboard, then import or sync trades to generate a coaching review.</p>
          <a href="/" className="inline-block mt-3 text-xs text-blue-400 hover:text-blue-300 transition-colors">
            → Go to Dashboard
          </a>
        </div>
      )}
      {!accountId && (accounts.length > 0 || isLoadingAccounts) && (
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
              {/* Metadata bar */}
              <div className="flex items-center gap-3 flex-wrap">
                <SourceBadge source={review.source} />
                {reviewIsHistory && (
                  <span className="text-xs bg-gray-800 text-gray-400 border border-gray-700 px-2 py-0.5 rounded">
                    From history
                  </span>
                )}
                <span className="text-xs text-gray-500">
                  {review.model_used} · {new Date(review.generated_at).toLocaleString()}
                </span>
                {reviewIsHistory && (
                  <button
                    onClick={() => { setReview(null); setReviewIsHistory(false); }}
                    className="text-xs text-gray-500 hover:text-gray-300 ml-auto"
                  >
                    ✕ Close
                  </button>
                )}
              </div>
              {review.source === "fallback" && <FallbackNotice />}

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

          {/* No data hint — shown when account has no reviews yet and nothing is loading */}
          {!loading && !review && history !== undefined && history.reviews.length === 0 && (
            <div className="rounded-lg border border-dashed border-gray-700 px-5 py-8 text-center space-y-1">
              <p className="text-gray-400 text-sm font-medium">No coaching reviews yet</p>
              <p className="text-gray-500 text-xs">
                Coaching reviews are generated from your trade data. Import trades or sync with MT5 first,
                then select a date range and click Generate Review.
              </p>
            </div>
          )}

          {/* Review history */}
          {history && history.reviews.length > 0 && (
            <section>
              <h2 className="text-xs uppercase tracking-wider text-gray-500 mb-3">Past Reviews</h2>
              <div className="bg-gray-900 border border-gray-800 rounded-lg divide-y divide-gray-800">
                {history.reviews.map((r: CoachingReviewListItem) => (
                  <button
                    key={r.review_id}
                    onClick={() => handleOpenHistoryItem(r.review_id)}
                    disabled={loadingHistoryId === r.review_id}
                    className="w-full px-4 py-3 flex items-start justify-between gap-4 text-left hover:bg-gray-800/50 transition-colors disabled:opacity-50"
                  >
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        {r.from_date && r.to_date && (
                          <span className="text-xs text-gray-400">
                            {r.from_date} – {r.to_date}
                          </span>
                        )}
                        <SourceBadge source={r.source} />
                      </div>
                      <p className="text-xs text-gray-500 truncate">{r.summary_preview}</p>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <span className="text-xs text-gray-600 whitespace-nowrap">
                        {new Date(r.generated_at).toLocaleDateString()}
                      </span>
                      {loadingHistoryId === r.review_id ? (
                        <span className="w-3 h-3 border border-gray-500 border-t-transparent rounded-full animate-spin" />
                      ) : (
                        <span className="text-gray-600 text-xs">›</span>
                      )}
                    </div>
                  </button>
                ))}
              </div>
            </section>
          )}
        </>
      )}
    </div>
  );
}
