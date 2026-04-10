"use client";

import { createContext, useContext, useEffect, useState } from "react";
import useSWR from "swr";
import { api, Account } from "@/lib/api";

interface AccountCtx {
  accounts: Account[];
  accountId: string;
  setAccountId: (id: string) => void;
}

const Ctx = createContext<AccountCtx>({ accounts: [], accountId: "", setAccountId: () => {} });

export function AccountProvider({ children }: { children: React.ReactNode }) {
  const { data: accounts = [] } = useSWR("accounts", () => api.listAccounts());
  const [accountId, setAccountIdState] = useState<string>("");

  useEffect(() => {
    const saved = localStorage.getItem("accountId");
    if (saved) {
      setAccountIdState(saved);
    } else if (accounts.length > 0) {
      setAccountIdState(accounts[0].account_id);
    }
  }, [accounts]);

  const setAccountId = (id: string) => {
    setAccountIdState(id);
    localStorage.setItem("accountId", id);
  };

  return <Ctx.Provider value={{ accounts, accountId, setAccountId }}>{children}</Ctx.Provider>;
}

export function useAccount() {
  return useContext(Ctx);
}
