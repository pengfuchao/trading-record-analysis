"use client";

import { useAccount } from "./AccountProvider";

export default function AccountSelector() {
  const { accounts, accountId, setAccountId, isLoadingAccounts, accountsError } = useAccount();

  if (isLoadingAccounts) {
    return (
      <span className="text-xs text-gray-500 px-3 py-1.5">Loading accounts…</span>
    );
  }

  if (accountsError) {
    return (
      <span
        className="text-xs text-red-400 border border-red-800/50 bg-red-900/20 rounded-md px-3 py-1.5"
        title={accountsError}
      >
        Account fetch failed
      </span>
    );
  }

  if (accounts.length === 0) {
    return (
      <span className="text-xs text-gray-500 px-3 py-1.5">No accounts — create one first</span>
    );
  }

  return (
    <select
      value={accountId}
      onChange={(e) => setAccountId(e.target.value)}
      className="bg-gray-800 border border-gray-700 text-gray-100 text-sm rounded-md px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-500"
    >
      {accounts.map((a) => (
        <option key={a.account_id} value={a.account_id}>
          {a.broker} — {a.account_id}
        </option>
      ))}
    </select>
  );
}
