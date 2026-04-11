const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
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

  // Trades
  listTrades: (accountId: string, params?: TradeFilters) => {
    const q = new URLSearchParams();
    if (params?.symbol) q.set("symbol", params.symbol);
    if (params?.result) q.set("result", params.result);
    if (params?.from_date) q.set("from_date", params.from_date);
    if (params?.to_date) q.set("to_date", params.to_date);
    return request<Trade[]>(`/accounts/${accountId}/trades?${q}`);
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
  getAnalytics: (accountId: string) =>
    request<AccountAnalytics>(`/accounts/${accountId}/analytics`),

  // Mistakes
  getMistakes: (accountId: string) =>
    request<MistakeReport>(`/accounts/${accountId}/mistakes`),

  // Setups
  listSetups: () => request<SetupDefinition[]>("/setups"),
  getSetup: (setupId: string) => request<SetupDefinition>(`/setups/${setupId}`),
  getSetupStats: (accountId: string) =>
    request<SetupStats[]>(`/accounts/${accountId}/setups/stats`),

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
  notes?: string;
  created_at: string;
  updated_at: string;
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

export interface SetupStats {
  setup_type: string;
  total_trades: number;
  win_rate?: number;
  expectancy?: number;
  average_r?: number;
  total_pnl?: number;
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
  account_id: string;
  from_date?: string;
  to_date?: string;
  summary: string;
  top_mistakes: MistakeInsight[];
  diagnosis: string;
  improvement: string;
}
