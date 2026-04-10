"use client";

import { useAccount } from "./AccountProvider";

export default function AccountSelector() {
  const { accounts, accountId, setAccountId } = useAccount();
  if (accounts.length === 0) return null;
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
