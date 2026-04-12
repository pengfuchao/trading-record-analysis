"use client";

import { createContext, useContext, useEffect, useState } from "react";
import useSWR from "swr";
import { api, Account } from "@/lib/api";

interface AccountCtx {
  accounts: Account[];
  accountId: string;
  setAccountId: (id: string) => void;
  isLoadingAccounts: boolean;
  accountsError: string | null;
}

const Ctx = createContext<AccountCtx>({
  accounts: [],
  accountId: "",
  setAccountId: () => {},
  isLoadingAccounts: false,
  accountsError: null,
});

export function AccountProvider({ children }: { children: React.ReactNode }) {
  const { data: accounts, error, isLoading } = useSWR(
    "accounts",
    () => api.listAccounts(),
    { revalidateOnFocus: true, shouldRetryOnError: true, dedupingInterval: 5000 }
  );
  const [accountId, setAccountIdState] = useState<string>("");

  const accountList: Account[] = accounts ?? [];

  useEffect(() => {
    if (accountList.length === 0) return;
    const saved = localStorage.getItem("accountId");
    // Verify saved id still exists in the list
    if (saved && accountList.some((a) => a.account_id === saved)) {
      setAccountIdState(saved);
    } else {
      setAccountIdState(accountList[0].account_id);
    }
  }, [accountList]);

  const setAccountId = (id: string) => {
    setAccountIdState(id);
    localStorage.setItem("accountId", id);
  };

  const accountsError: string | null = error
    ? (error instanceof Error ? error.message : String(error))
    : null;

  return (
    <Ctx.Provider value={{
      accounts: accountList,
      accountId,
      setAccountId,
      isLoadingAccounts: isLoading,
      accountsError,
    }}>
      {children}
    </Ctx.Provider>
  );
}

export function useAccount() {
  return useContext(Ctx);
}
