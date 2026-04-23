// NEXT_PUBLIC_API_URL is the backend *origin* (e.g. http://localhost:8000).
// /api/v1 is always appended here so it is enforced regardless of what the
// env var contains — avoids silent 404s when the suffix is accidentally omitted.
const BASE = `${(process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/+$/, "")}/api/v1`;

/** Append T23:59:59 so a plain YYYY-MM-DD to_date includes all trades on that day. */
function endOfDay(date: string | undefined): string | undefined {
  return date ? `${date}T23:59:59` : undefined;
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const method = (options?.method ?? "GET").toUpperCase();
  const hasBody = method !== "GET" && method !== "HEAD" && method !== "DELETE";
  const res = await fetch(`${BASE}${path}`, {
    headers: hasBody ? { "Content-Type": "application/json" } : {},
    ...options,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`${res.status} ${text}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

async function uploadFile<T>(path: string, file: File, extraParams?: Record<string, string>): Promise<T> {
  const form = new FormData();
  form.append("file", file);
  const url = new URL(`${BASE}${path}`);
  if (extraParams) {
    Object.entries(extraParams).forEach(([k, v]) => url.searchParams.set(k, v));
  }
  const res = await fetch(url.toString(), { method: "POST", body: form });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`${res.status} ${text}`);
  }
  return res.json();
}

export const api = {
  // Accounts
  getAccount: (id: string) => request<Account>(`/accounts/${id}`),
  listAccounts: () => request<Account[]>("/accounts"),
  updateAccount: (accountId: string, body: Partial<Account>) =>
    request<Account>(`/accounts/${accountId}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),

  // Trades
  listTrades: (accountId: string, params?: TradeFilters) => {
    const q = new URLSearchParams();
    if (params?.symbol) q.set("symbol", params.symbol);
    if (params?.result) q.set("result", params.result);
    if (params?.from_date) q.set("from_date", params.from_date);
    if (params?.to_date) q.set("to_date", endOfDay(params.to_date)!);
    if (params?.page != null) q.set("page", String(params.page));
    if (params?.page_size != null) q.set("page_size", String(params.page_size));
    return request<TradeListResponse>(`/accounts/${accountId}/trades?${q}`);
  },
  getTrade: (accountId: string, tradeId: string) =>
    request<Trade>(`/accounts/${accountId}/trades/${tradeId}`),
  updateTrade: (accountId: string, tradeId: string, body: Partial<Trade>) =>
    request<Trade>(`/accounts/${accountId}/trades/${tradeId}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),

  // Import
  previewImport: (accountId: string, file: File) =>
    uploadFile<ImportPreviewResponse>(`/accounts/${accountId}/import/preview`, file),
  importCsv: (accountId: string, file: File, duplicateStrategy: string) =>
    uploadFile<ImportResponse>(`/accounts/${accountId}/import`, file, { duplicate_strategy: duplicateStrategy }),

  // Coaching
  generateWeeklyReview: (accountId: string, params?: { from_date?: string; to_date?: string }) => {
    const q = new URLSearchParams();
    if (params?.from_date) q.set("from_date", params.from_date);
    if (params?.to_date) q.set("to_date", params.to_date);
    return request<WeeklyReviewResponse>(
      `/accounts/${accountId}/coaching/weekly-review?${q}`,
      { method: "POST" }
    );
  },
  listCoachingReviews: (accountId: string, limit = 20) =>
    request<CoachingReviewListResponse>(`/accounts/${accountId}/coaching/reviews?limit=${limit}`),
  getCoachingReview: (accountId: string, reviewId: string) =>
    request<CoachingReviewDetailResponse>(`/accounts/${accountId}/coaching/reviews/${reviewId}`),

  // Import — derived field recompute
  recomputeDerived: (
    accountId: string,
    opts: { recalculate_r?: boolean; recalculate_session?: boolean; overwrite_session?: boolean; broker_utc_offset?: number } = {}
  ) => {
    const q = new URLSearchParams();
    if (opts.recalculate_r !== undefined) q.set("recalculate_r", String(opts.recalculate_r));
    if (opts.recalculate_session !== undefined) q.set("recalculate_session", String(opts.recalculate_session));
    if (opts.overwrite_session !== undefined) q.set("overwrite_session", String(opts.overwrite_session));
    if (opts.broker_utc_offset !== undefined) q.set("broker_utc_offset", String(opts.broker_utc_offset));
    return request<RecomputeResponse>(`/accounts/${accountId}/import/recompute-derived?${q}`, { method: "POST" });
  },

  // Analytics
  getAnalytics: (accountId: string, params?: DateRange) => {
    const q = new URLSearchParams();
    if (params?.from_date) q.set("from_date", params.from_date);
    if (params?.to_date) q.set("to_date", endOfDay(params.to_date)!);
    const qs = q.toString();
    return request<AccountAnalytics>(`/accounts/${accountId}/analytics${qs ? `?${qs}` : ""}`);
  },

  // FTMO / prop firm status
  getFtmoStatus: (
    accountId: string,
    params?: { daily_loss_limit_pct?: number; max_loss_limit_pct?: number; broker_utc_offset?: number }
  ) => {
    const q = new URLSearchParams();
    if (params?.daily_loss_limit_pct != null) q.set("daily_loss_limit_pct", String(params.daily_loss_limit_pct));
    if (params?.max_loss_limit_pct != null) q.set("max_loss_limit_pct", String(params.max_loss_limit_pct));
    if (params?.broker_utc_offset != null) q.set("broker_utc_offset", String(params.broker_utc_offset));
    const qs = q.toString();
    return request<FtmoStatus>(`/accounts/${accountId}/ftmo-status${qs ? `?${qs}` : ""}`);
  },

  // Mistakes
  getMistakes: (accountId: string, params?: DateRange) => {
    const q = new URLSearchParams();
    if (params?.from_date) q.set("from_date", params.from_date);
    if (params?.to_date) q.set("to_date", endOfDay(params.to_date)!);
    const qs = q.toString();
    return request<MistakeReport>(`/accounts/${accountId}/mistakes${qs ? `?${qs}` : ""}`);
  },

  // Setups
  listSetups: () => request<SetupDefinition[]>("/setups"),
  getSetup: (setupId: string) => request<SetupDefinition>(`/setups/${setupId}`),
  createSetup: (body: Record<string, unknown>) =>
    request<SetupDefinition>("/setups", { method: "POST", body: JSON.stringify(body) }),
  updateSetup: (setupId: string, body: Partial<SetupDefinition>) =>
    request<SetupDefinition>(`/setups/${setupId}`, { method: "PATCH", body: JSON.stringify(body) }),
  deleteSetup: (setupId: string) =>
    request<{ deleted: boolean }>(`/setups/${setupId}`, { method: "DELETE" }),
  getSetupReport: (accountId: string) =>
    request<SetupReportResponse>(`/accounts/${accountId}/setups`),

  // R:R realization trend
  getRRTrend: (accountId: string, params?: DateRange) => {
    const q = new URLSearchParams();
    if (params?.from_date) q.set("from_date", params.from_date);
    if (params?.to_date) q.set("to_date", endOfDay(params.to_date)!);
    const qs = q.toString();
    return request<RRTrendReportResponse>(`/accounts/${accountId}/rr-trend${qs ? `?${qs}` : ""}`);
  },

  // Behavioral trend
  getBehavioralTrend: (accountId: string, params?: DateRange) => {
    const q = new URLSearchParams();
    if (params?.from_date) q.set("from_date", params.from_date);
    if (params?.to_date) q.set("to_date", endOfDay(params.to_date)!);
    const qs = q.toString();
    return request<BehavioralTrendReportResponse>(`/accounts/${accountId}/behavioral-trend${qs ? `?${qs}` : ""}`);
  },

  // Daily Plans
  listPlans: (accountId: string, params?: DateRange) => {
    const q = new URLSearchParams();
    if (params?.from_date) q.set("from_date", params.from_date);
    if (params?.to_date) q.set("to_date", params.to_date);
    return request<DailyPlan[]>(`/accounts/${accountId}/daily-plans?${q}`);
  },
  getPlan: (accountId: string, planId: string) =>
    request<DailyPlan>(`/accounts/${accountId}/daily-plans/${planId}`),
  createPlan: (accountId: string, body: Partial<DailyPlan>) =>
    request<DailyPlan>(`/accounts/${accountId}/daily-plans`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  updatePlan: (accountId: string, planId: string, body: Partial<DailyPlan>) =>
    request<DailyPlan>(`/accounts/${accountId}/daily-plans/${planId}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  deletePlan: (accountId: string, planId: string) =>
    request<void>(`/accounts/${accountId}/daily-plans/${planId}`, { method: "DELETE" }),
  getDailyAdherence: (accountId: string, planId: string) =>
    request<DailyAdherenceResponse>(`/accounts/${accountId}/daily-plans/${planId}/adherence`),

  // Trade Plans
  listTradePlans: (accountId: string, status?: string) => {
    const q = new URLSearchParams();
    if (status) q.set("status", status);
    return request<TradePlan[]>(`/accounts/${accountId}/trade-plans?${q}`);
  },
  getTradePlan: (accountId: string, planId: string) =>
    request<TradePlan>(`/accounts/${accountId}/trade-plans/${planId}`),
  createTradePlan: (accountId: string, body: Partial<TradePlan>) =>
    request<TradePlan>(`/accounts/${accountId}/trade-plans`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  updateTradePlan: (accountId: string, planId: string, body: Partial<TradePlan>) =>
    request<TradePlan>(`/accounts/${accountId}/trade-plans/${planId}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  deleteTradePlan: (accountId: string, planId: string) =>
    request<void>(`/accounts/${accountId}/trade-plans/${planId}`, { method: "DELETE" }),
  linkPlanToTrade: (accountId: string, planId: string, tradeId: string) =>
    request<Trade>(`/accounts/${accountId}/trade-plans/${planId}/link/${tradeId}`, { method: "POST" }),
  unlinkPlanFromTrade: (accountId: string, planId: string, tradeId: string) =>
    request<Trade>(`/accounts/${accountId}/trade-plans/${planId}/link/${tradeId}`, { method: "DELETE" }),
  getLinkedTrades: (accountId: string, planId: string) =>
    request<Trade[]>(`/accounts/${accountId}/trade-plans/${planId}/trades`),
  getSuggestedTrades: (accountId: string, planId: string) =>
    request<TradePlanSuggestion[]>(`/accounts/${accountId}/trade-plans/${planId}/suggestions`),
  getUnlinkedTrades: (accountId: string) =>
    request<Trade[]>(`/accounts/${accountId}/trades/unlinked`),

  // MT5 Sync
  getMt5Config: (accountId: string) =>
    request<MT5Config>(`/accounts/${accountId}/mt5-config`),
  saveMt5Config: (accountId: string, body: MT5ConfigCreate) =>
    request<MT5Config>(`/accounts/${accountId}/mt5-config`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getMt5Status: (accountId: string, limit = 10) =>
    request<MT5SyncStatus>(`/accounts/${accountId}/mt5-sync/status?limit=${limit}`),
  triggerMt5Sync: (accountId: string, body: MT5SyncTrigger = {}) =>
    request<MT5SyncResponse>(`/accounts/${accountId}/mt5-sync`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getOpenPositions: (accountId: string) =>
    request<OpenPositionsResponse>(`/accounts/${accountId}/open-positions`),

  // Daily Reviews
  listReviews: (accountId: string, params?: DateRange) => {
    const q = new URLSearchParams();
    if (params?.from_date) q.set("from_date", params.from_date);
    if (params?.to_date) q.set("to_date", params.to_date);
    return request<DailyReview[]>(`/accounts/${accountId}/daily-reviews?${q}`);
  },
  getReview: (accountId: string, reviewId: string) =>
    request<DailyReview>(`/accounts/${accountId}/daily-reviews/${reviewId}`),
  createReview: (accountId: string, body: Partial<DailyReview>) =>
    request<DailyReview>(`/accounts/${accountId}/daily-reviews`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  updateReview: (accountId: string, reviewId: string, body: Partial<DailyReview>) =>
    request<DailyReview>(`/accounts/${accountId}/daily-reviews/${reviewId}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  deleteReview: (accountId: string, reviewId: string) =>
    request<void>(`/accounts/${accountId}/daily-reviews/${reviewId}`, { method: "DELETE" }),

  // Plan adherence analytics
  getPlanAdherence: (accountId: string, params?: DateRange) => {
    const q = new URLSearchParams();
    if (params?.from_date) q.set("from_date", params.from_date);
    if (params?.to_date) q.set("to_date", endOfDay(params.to_date)!);
    const qs = q.toString();
    return request<PlanAdherenceResponse>(`/accounts/${accountId}/plan-adherence${qs ? `?${qs}` : ""}`);
  },

  // Per-symbol / per-session segment analytics
  getSegmentAnalytics: (accountId: string, params?: DateRange) => {
    const q = new URLSearchParams();
    if (params?.from_date) q.set("from_date", params.from_date);
    if (params?.to_date) q.set("to_date", endOfDay(params.to_date)!);
    const qs = q.toString();
    return request<SegmentAnalyticsResponse>(`/accounts/${accountId}/segment-analytics${qs ? `?${qs}` : ""}`);
  },

  // Exit outcome decomposition
  getExitDecomposition: (accountId: string, params?: DateRange) => {
    const q = new URLSearchParams();
    if (params?.from_date) q.set("from_date", params.from_date);
    if (params?.to_date) q.set("to_date", endOfDay(params.to_date)!);
    const qs = q.toString();
    return request<ExitDecompositionResponse>(`/accounts/${accountId}/exit-decomposition${qs ? `?${qs}` : ""}`);
  },

  // Entry vs exit quality decomposition
  getEntryExitQuality: (accountId: string, params?: DateRange) => {
    const q = new URLSearchParams();
    if (params?.from_date) q.set("from_date", params.from_date);
    if (params?.to_date) q.set("to_date", endOfDay(params.to_date)!);
    const qs = q.toString();
    return request<EntryExitQualityResponse>(`/accounts/${accountId}/entry-exit-quality${qs ? `?${qs}` : ""}`);
  },
};

// ── Types ──────────────────────────────────────────────────────────────────────

export interface Account {
  account_id: string;
  broker: string;
  platform: string;
  prop_firm?: string;
  challenge_phase?: string;
  starting_balance?: number;
  account_currency: string;
  created_at: string;
}

export interface TradeFilters {
  symbol?: string;
  result?: string;
  from_date?: string;
  to_date?: string;
  page?: number;
  page_size?: number;
}

export interface TradeListResponse {
  items: Trade[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface DateRange {
  from_date?: string;
  to_date?: string;
}

export interface Trade {
  trade_id: string;
  account_id: string;
  symbol?: string;
  asset_class?: string;
  direction?: string;
  session?: string;
  entry_datetime?: string;
  exit_datetime?: string;
  holding_duration?: string;
  entry_price?: number;
  exit_price?: number;
  stop_loss?: number;
  take_profit?: number;
  lot_size?: number;
  gross_pnl?: number;
  net_pnl?: number;
  commission?: number;
  swap?: number;
  actual_r_multiple?: number;
  result?: string;
  setup_type?: string;
  strategy?: string;
  higher_tf_bias?: string;
  entry_timeframe?: string;
  market_condition?: string;
  key_levels?: string;
  news_context?: string;
  pre_trade_bias?: string;
  entry_reason?: string;
  trigger_confirmation?: string;
  stop_loss_logic?: string;
  take_profit_logic?: string;
  exit_reason?: string;
  followed_plan?: boolean;
  is_a_plus_setup?: boolean;
  early_entry?: boolean;
  chasing?: boolean;
  fomo?: boolean;
  emotional_trade?: boolean;
  revenge_trade?: boolean;
  overtrading?: boolean;
  hesitation?: boolean;
  moved_stop?: boolean;
  premature_exit?: boolean;
  held_loser_too_long?: boolean;
  trade_quality?: string;
  problem_source?: string;
  mistake_tags?: string[];
  lesson_learned?: string;
  repeat_next_time?: string;
  avoid_next_time?: string;
  screenshot_before?: string;
  screenshot_during?: string;
  screenshot_after?: string;
  notes?: string;
  trade_plan_id?: string;
  created_at: string;
  updated_at: string;
}

export interface TradePlan {
  plan_id: string;
  account_id: string;
  status: string;                      // planned | linked | cancelled
  symbol?: string;
  intended_direction?: string;         // long | short
  setup_type?: string;
  strategy?: string;
  bias?: string;
  thesis?: string;
  entry_logic?: string;
  stop_loss_logic?: string;
  take_profit_logic?: string;
  invalidation_logic?: string;
  planned_entry_zone?: string;
  planned_stop_loss?: number;
  planned_take_profit?: number;
  planned_rr?: number;
  is_a_plus_setup?: boolean;
  notes?: string;
  created_at?: string;
  updated_at?: string;
}

export interface TradePlanSuggestion {
  trade: Trade;
  score: number;
  reasons: string[];
}

export interface AccountAnalytics {
  account_id: string;
  generated_at: string;

  // Account state
  starting_balance?: number;
  current_balance?: number;           // starting_balance + total_net_pnl

  // Counts
  total_trades: number;
  winning_trades: number;
  losing_trades: number;

  // Rates (0.0–1.0)
  win_rate?: number;                  // wins / total (includes breakevens in denominator)
  win_rate_ex_be?: number;            // wins / (wins + losses) — excludes breakevens
  loss_rate?: number;

  // PnL
  total_net_pnl?: number;
  total_gross_pnl?: number;
  total_return_pct?: number;          // (total_net_pnl / starting_balance) * 100

  // Averages
  average_win?: number;
  average_loss?: number;              // negative value
  largest_win?: number;
  largest_loss?: number;              // negative value

  // Quality
  profit_factor?: number;
  expectancy?: number;                // avg $ per trade
  payoff_ratio?: number;
  average_r_multiple?: number;        // price-based: signed_price_move / sl_distance

  // Drawdown / period loss
  max_drawdown?: number;                          // peak-to-trough absolute $ (≤ 0)
  max_drawdown_pct?: number;                      // % of peak equity (≤ 0)
  max_drawdown_pct_of_starting_balance?: number;  // % of starting balance (≤ 0); FTMO-style
  daily_drawdown?: number;                        // worst calendar-day closed-trade net PnL
  weekly_drawdown?: number;                       // worst ISO-week closed-trade net PnL

  // Risk-adjusted
  sharpe_ratio?: number;
  sortino_ratio?: number;

  // Streaks
  max_consecutive_wins: number;
  max_consecutive_losses: number;

  // Equity / drawdown curves
  equity_curve: number[];
  drawdown_curve: number[];
  trade_dates: string[];
}

export interface FtmoStatus {
  account_id: string;
  generated_at: string;

  // Account state
  starting_balance?: number;
  estimated_current_balance?: number;
  total_net_pnl?: number;
  total_return_pct?: number;

  // Daily loss
  today_date: string;
  today_pnl: number;
  daily_loss_limit_pct: number;           // configured limit e.g. 5.0
  daily_loss_limit_abs?: number;          // limit in $
  daily_loss_used_pct?: number;           // |today_pnl| / starting_balance * 100
  daily_loss_remaining?: number;          // $ remaining before breach

  // Overall drawdown
  max_loss_limit_pct: number;             // configured limit e.g. 10.0
  max_loss_limit_abs?: number;            // limit in $
  current_max_drawdown?: number;          // absolute $ drawdown from peak
  current_max_drawdown_pct?: number;      // as % of starting_balance (positive number)
  max_loss_remaining?: number;            // $ remaining before breach

  // Status
  daily_status: string;                   // SAFE | AT_RISK | BREACHED | UNKNOWN
  overall_status: string;
  account_status: string;                 // worst of daily/overall
}

export interface MistakeStats {
  mistake_tag: string;
  occurrence_count: number;
  occurrence_pct: number;
  total_cost: number;
  avg_cost_per_trade: number;
  win_rate?: number;
  loss_rate?: number;
  avg_net_pnl?: number;
  by_session: Record<string, number>;
  by_symbol: Record<string, number>;
  after_loss_rate?: number;
}

export interface MistakeReport {
  account_id: string;
  generated_at: string;
  total_trades_analyzed: number;
  trades_with_any_mistake: number;
  mistake_rate?: number;
  by_mistake: Record<string, MistakeStats>;
  ranked_by_frequency: string[];
  ranked_by_cost: string[];
}

export interface SetupDefinition {
  setup_id: string;
  name: string;
  strategy_group?: string;
  description?: string;
  market_environment?: string;
  preconditions?: string;
  entry_criteria?: string;
  confirmation_rules?: string;
  stop_loss_rules?: string;
  take_profit_rules?: string;
  invalidation_conditions?: string;
  common_mistakes?: string;
  notes?: string;
  created_at: string;
  updated_at: string;
}

export interface SetupStatsResponse {
  setup_type: string;
  trade_count: number;
  win_rate?: number;
  loss_rate?: number;
  breakeven_rate?: number;
  expectancy?: number;
  avg_r_multiple?: number;
  profit_factor?: number;
  total_net_profit: number;
  avg_win?: number;
  avg_loss?: number;
  max_drawdown?: number;
  max_consecutive_losses: number;
  avg_holding_duration_seconds?: number;
  a_plus_rate?: number;
  followed_plan_rate?: number;
  by_session: Record<string, number>;
  by_market_condition: Record<string, number>;
  by_symbol: Record<string, number>;
  best_session?: string;
  worst_session?: string;
  best_market_condition?: string;
  worst_market_condition?: string;
  best_symbol?: string;
  worst_symbol?: string;
  common_mistakes: Record<string, number>;
  rr_sample_count: number;
  rr_avg_planned_rr?: number;
  rr_avg_actual_r?: number;
  rr_avg_shortfall?: number;
  rr_realization_pct?: number;
  rr_pct_met_target?: number;
}

export interface SetupReportResponse {
  account_id: string;
  generated_at: string;
  total_trades_analyzed: number;
  trades_with_setup: number;
  by_setup: Record<string, SetupStatsResponse>;
  ranked_by_win_rate: string[];
  ranked_by_expectancy: string[];
  ranked_by_avg_r: string[];
  ranked_by_total_profit: string[];
  ranked_by_drawdown: string[];
  ranked_by_rr_realization: string[];
}

export interface RRTrendBucket {
  bucket: string;         // "2026-W15"
  bucket_start: string;
  n: number;
  avg_planned_rr: number;
  avg_actual_r: number;
  avg_shortfall: number;
  realization_pct: number | null;
}

export interface RRTrendReportResponse {
  buckets: RRTrendBucket[];
  total_qualifying: number;
  trend_signal: string | null;  // "improving" | "worsening" | "stable" | null
}

export interface BehavioralTrendBucket {
  bucket: string;           // "2026-W15"
  bucket_start: string;
  n: number;
  win_rate: number | null;
  mistake_rate: number | null;
  plan_link_rate: number | null;
  followed_plan_rate: number | null;
}

export interface BehavioralTrendReportResponse {
  buckets: BehavioralTrendBucket[];
  total_trades: number;
  win_rate_trend: string | null;
  mistake_rate_trend: string | null;
  plan_link_rate_trend: string | null;
  followed_plan_rate_trend: string | null;
}

export interface SegmentRow {
  name: string;
  count: number;
  win_rate: number | null;
  avg_pnl: number | null;
  total_pnl: number;
  profit_factor: number | null;
  avg_r: number | null;
  low_sample: boolean;  // count < 3
}

export interface SegmentAnalyticsResponse {
  by_symbol: SegmentRow[];
  by_session: SegmentRow[];
  best_symbol: string | null;
  worst_symbol: string | null;
  best_session: string | null;
  worst_session: string | null;
}

export interface DailyPlan {
  plan_id: string;
  account_id: string;
  trading_date: string;
  market_bias?: string;
  symbols_in_focus: string[];
  key_levels?: string;
  major_news?: string;
  allowed_setups: string[];
  disallowed_setups: string[];
  daily_max_risk_pct?: number;
  max_trades?: number;
  behavioral_focus?: string;
  special_rule?: string;
  created_at?: string;
  updated_at?: string;
}

export interface DailyReview {
  review_id: string;
  account_id: string;
  trading_date: string;
  plan_id?: string;
  total_trades?: number;
  total_pnl?: number;
  total_r?: number;
  planned_trades?: number;
  unplanned_trades?: number;
  best_trade_id?: string;
  worst_trade_id?: string;
  biggest_mistake?: string;
  emotional_summary?: string;
  improvement_point?: string;
  notes?: string;
  process_success?: boolean;
  pnl_success?: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface ImportPreviewRow {
  trade_id: string;
  symbol?: string;
  direction?: string;
  entry_datetime?: string;
  exit_datetime?: string;
  lot_size?: number;
  gross_pnl?: number;
  net_pnl?: number;
  result?: string;
  is_existing: boolean;
}

export interface ImportPreviewResponse {
  account_id: string;
  detected_platform: string;
  total_rows_in_file: number;
  trade_rows_parsed: number;
  new_trade_count: number;
  existing_trade_count: number;
  validation_error_count: number;
  preview_rows: ImportPreviewRow[];
  skipped_rows: { row_index: number; trade_id?: string; reason: string }[];
  validation_errors: { trade_id?: string; field?: string; message: string }[];
}

export interface ImportResponse {
  account_id: string;
  import_run_id: string;
  trades_imported: number;
  trades_new: number;
  trades_updated: number;
  trades_skipped: number;
  duplicate_strategy: string;
  validation_error_count: number;
  skipped_rows: { row_index: number; trade_id?: string; reason: string }[];
  validation_errors: { trade_id?: string; field?: string; message: string }[];
}

export interface RecomputeResponse {
  account_id: string;
  trades_processed: number;
  trades_updated_r: number;
  trades_skipped_r: number;
  trades_updated_session: number;
  trades_skipped_session: number;
}

export interface MistakeInsight {
  tag: string;
  pattern: string;
}

export interface WeeklyReviewResponse {
  review_id: string;
  account_id: string;
  from_date?: string;
  to_date?: string;
  generated_at: string;
  model_used: string;
  source: "ai" | "fallback";
  status: "success" | "fallback" | "error";
  summary: string;
  top_mistakes: MistakeInsight[];
  diagnosis: string;
  improvement: string;
}

export interface CoachingReviewListItem {
  review_id: string;
  account_id: string;
  from_date?: string;
  to_date?: string;
  generated_at: string;
  model_used: string;
  source: "ai" | "fallback";
  status: "success" | "fallback" | "error";
  summary_preview: string;
}

export interface CoachingReviewListResponse {
  account_id: string;
  total: number;
  reviews: CoachingReviewListItem[];
}

export interface CoachingReviewDetailResponse {
  review_id: string;
  account_id: string;
  from_date?: string;
  to_date?: string;
  generated_at: string;
  model_used: string;
  source: "ai" | "fallback";
  status: "success" | "fallback" | "error";
  summary: string;
  top_mistakes: MistakeInsight[];
  diagnosis: string;
  improvement: string;
}

export interface MT5Config {
  account_id: string;
  mt5_login: number;
  mt5_server: string;
  terminal_path?: string;
  broker_utc_offset: number;
  polling_interval_minutes: number;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface MT5ConfigCreate {
  mt5_login: number;
  mt5_server: string;
  terminal_path?: string;
  broker_utc_offset: number;
  polling_interval_minutes?: number;
  enabled?: boolean;
}

export interface MT5SyncTrigger {
  from_date?: string;
  to_date?: string;
}

export interface MT5SyncResponse {
  run_id: string;
  account_id: string;
  status: string;
  deals_fetched: number;
  positions_built: number;
  trades_new: number;
  trades_updated: number;
  trades_skipped: number;
  open_positions_count: number;
  error_message?: string;
  started_at: string;
  completed_at?: string;
}

export interface OpenPosition {
  account_id: string;
  ticket: number;
  symbol: string;
  direction: string;
  lot_size: number;
  entry_price: number;
  current_price?: number;
  stop_loss?: number;
  take_profit?: number;
  floating_pnl?: number;
  opened_at?: string;
  magic?: number;
  comment?: string;
  source: string;
  synced_at: string;
}

export interface OpenPositionsResponse {
  account_id: string;
  count: number;
  positions: OpenPosition[];
}

export interface MT5SyncRunSummary {
  run_id: string;
  triggered_by: string;
  started_at: string;
  completed_at?: string;
  status: string;
  from_date?: string;
  to_date?: string;
  deals_fetched?: number;
  positions_built?: number;
  trades_new?: number;
  trades_updated?: number;
  trades_skipped?: number;
  error_message?: string;
}

export interface MT5SyncStatus {
  account_id: string;
  sync_configured: boolean;
  enabled: boolean;
  polling_interval_minutes?: number;
  next_poll_at?: string;
  last_sync_at?: string;
  last_runs: MT5SyncRunSummary[];
}

export interface PlanAdherenceGroup {
  count: number;
  win_rate?: number;
  avg_pnl?: number;
  avg_r?: number;
  total_pnl: number;
  profit_factor?: number;
}

export interface RRComparisonResponse {
  sample_count: number;
  avg_planned_rr?: number;
  avg_actual_r?: number;
  avg_r_shortfall?: number;
  realization_pct?: number;
  met_target_count: number;
  missed_target_count: number;
  pct_met_target?: number;
  coaching_signals: string[];
}

export interface ExitBucket {
  count: number;
  total_pnl: number;
  avg_r: number | null;
  pct_of_total: number | null;
}

export interface ExitDecompositionResponse {
  total_classified: number;
  total_unclassified: number;
  stop_hit: ExitBucket;
  manual_cut: ExitBucket;
  target_hit: ExitBucket;
  exit_before_target: ExitBucket;
  unclear: ExitBucket;
  coaching_signals: string[];
}

export interface EntryExitQualityResponse {
  total_trades: number;
  classified_trades: number;
  // Exit quality (directly observable)
  wins_total: number;
  wins_with_tp_info: number;
  wins_hit_target: number;
  wins_before_target: number;
  early_exit_pct: number | null;
  // Loss context
  losses_total: number;
  stop_hit_count: number;
  manual_cut_count: number;
  stop_hit_pct_of_losses: number | null;
  // Entry quality (self-reported)
  entry_flagged_losses: number;
  entry_flagged_stop_hits: number;
  entry_flagged_stop_hit_pct: number | null;
  flag_coverage_pct: number;
  flag_early_entry: number;
  flag_chasing: number;
  flag_fomo: number;
  flag_plan_deviation_on_loss: number;
  flag_weak_setup_on_loss: number;
  flag_problem_analysis: number;
  flag_premature_exit: number;
  flag_moved_stop: number;
  // Diagnosis
  primary_diagnosis: "exit_discipline" | "entry_quality" | "mixed" | "unclear";
  confidence: "low" | "moderate" | "high";
  coaching_signals: string[];
}

export interface SetupViolation {
  trade_id: string;
  setup_type?: string;
}

export interface DailyAdherenceResponse {
  trading_date: string;
  trades_taken: number;
  planned_count: number;
  unplanned_count: number;
  max_trades_limit?: number;
  max_trades_exceeded: boolean;
  max_trades_exceeded_by: number;
  allowed_setups_configured: boolean;
  outside_allowed_count: number;
  outside_allowed_setups: string[];
  disallowed_setups_configured: boolean;
  disallowed_violation_count: number;
  disallowed_violations: SetupViolation[];
  untagged_count: number;
  discipline_signals: string[];
  plan_allowed_setups: string[];
  plan_disallowed_setups: string[];
  plan_max_trades?: number;
}

export interface PlanAdherenceResponse {
  total_trades: number;

  // Dimension 1: formal plan linkage (trade_plan_id)
  planned_count: number;
  unplanned_count: number;
  planned_pct?: number;
  planned: PlanAdherenceGroup;
  unplanned: PlanAdherenceGroup;

  // Dimension 2: self-reported adherence (followed_plan)
  followed_count: number;
  deviated_count: number;
  not_tagged_count: number;
  followed: PlanAdherenceGroup;
  deviated: PlanAdherenceGroup;

  // Intersection
  linked_but_deviated_count: number;

  // Planned R:R vs realized R (null when < 1 qualifying trade)
  rr_comparison?: RRComparisonResponse;

  // Pre-computed coaching signals
  coaching_signals: string[];
}
