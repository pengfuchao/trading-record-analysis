"use client";

import { useState } from "react";
import useSWR from "swr";
import { api, SetupDefinition } from "@/lib/api";
import { useAccount } from "@/components/AccountProvider";
import AccountSelector from "@/components/AccountSelector";
import { fmtPct, fmt, fmtPnl, pnlColor } from "@/lib/utils";

function SetupCard({ setup, stats }: { setup: SetupDefinition; stats?: any }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-5 py-4 hover:bg-gray-800/50 transition-colors"
      >
        <div className="text-left">
          <p className="text-sm font-medium text-gray-100">{setup.name}</p>
          {setup.strategy_group && (
            <p className="text-xs text-gray-500 mt-0.5">{setup.strategy_group}</p>
          )}
        </div>
        <div className="flex items-center gap-6 text-right">
          {stats ? (
            <>
              <div>
                <p className="text-xs text-gray-500">Trades</p>
                <p className="text-sm font-mono">{stats.total_trades}</p>
              </div>
              <div>
                <p className="text-xs text-gray-500">Win Rate</p>
                <p className="text-sm font-mono">{fmtPct(stats.win_rate)}</p>
              </div>
              <div>
                <p className="text-xs text-gray-500">Avg R</p>
                <p className={`text-sm font-mono ${pnlColor(stats.average_r)}`}>{fmt(stats.average_r)}</p>
              </div>
              <div>
                <p className="text-xs text-gray-500">Total PnL</p>
                <p className={`text-sm font-mono ${pnlColor(stats.total_pnl)}`}>{fmtPnl(stats.total_pnl)}</p>
              </div>
            </>
          ) : (
            <p className="text-xs text-gray-600">No trade data</p>
          )}
          <span className="text-gray-500 ml-2">{open ? "▲" : "▼"}</span>
        </div>
      </button>

      {open && (
        <div className="border-t border-gray-800 px-5 py-4 space-y-3 text-sm text-gray-300">
          {setup.description && (
            <div>
              <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">Description</p>
              <p>{setup.description}</p>
            </div>
          )}
          {setup.market_environment && (
            <div>
              <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">Market Environment</p>
              <p>{setup.market_environment}</p>
            </div>
          )}
          {setup.preconditions && (
            <div>
              <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">Preconditions</p>
              <p className="whitespace-pre-wrap">{setup.preconditions}</p>
            </div>
          )}
          {setup.entry_criteria && (
            <div>
              <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">Entry Criteria</p>
              <p className="whitespace-pre-wrap">{setup.entry_criteria}</p>
            </div>
          )}
          {setup.confirmation_rules && (
            <div>
              <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">Confirmation Rules</p>
              <p className="whitespace-pre-wrap">{setup.confirmation_rules}</p>
            </div>
          )}
          {setup.stop_loss_rules && (
            <div>
              <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">Stop Loss Rules</p>
              <p className="whitespace-pre-wrap">{setup.stop_loss_rules}</p>
            </div>
          )}
          {setup.take_profit_rules && (
            <div>
              <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">Take Profit Rules</p>
              <p className="whitespace-pre-wrap">{setup.take_profit_rules}</p>
            </div>
          )}
          {setup.invalidation_conditions && (
            <div>
              <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">Invalidation</p>
              <p className="whitespace-pre-wrap">{setup.invalidation_conditions}</p>
            </div>
          )}
          {setup.common_mistakes && (
            <div>
              <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">Common Mistakes</p>
              <p className="whitespace-pre-wrap">{setup.common_mistakes}</p>
            </div>
          )}
          {setup.notes && (
            <div>
              <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">Notes</p>
              <p className="whitespace-pre-wrap">{setup.notes}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function SetupsPage() {
  const { accountId } = useAccount();
  const { data: setups = [], isLoading } = useSWR("setups", () => api.listSetups());
  const { data: statsArr = [] } = useSWR(
    accountId ? `setup-stats-${accountId}` : null,
    () => api.getSetupStats(accountId)
  );

  const statsMap = Object.fromEntries(statsArr.map((s) => [s.setup_type, s]));

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Setup Library</h1>
        <AccountSelector />
      </div>

      {isLoading && <p className="text-gray-500 text-sm">Loading…</p>}
      {!isLoading && setups.length === 0 && (
        <p className="text-gray-500 text-sm">No setups defined yet.</p>
      )}

      <div className="space-y-3">
        {setups.map((setup) => (
          <SetupCard
            key={setup.setup_id}
            setup={setup}
            stats={statsMap[setup.name]}
          />
        ))}
      </div>
    </div>
  );
}
