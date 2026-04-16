"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const nav = [
  { href: "/dashboard",  label: "Dashboard" },
  { href: "/trades",     label: "Trade Log" },
  { href: "/plans",      label: "Trade Plans" },
  { href: "/setups",     label: "Setups" },
  { href: "/daily",      label: "Daily Plans" },
  { href: "/coaching",   label: "AI Coach" },
  { href: "/import",     label: "Import" },
];

export default function Sidebar() {
  const path = usePathname();
  return (
    <aside className="w-48 bg-gray-900 border-r border-gray-800 flex flex-col py-6 px-3 shrink-0">
      <div className="mb-8 px-2">
        <span className="text-xs font-semibold uppercase tracking-widest text-gray-500">
          Trading Journal
        </span>
      </div>
      <nav className="flex flex-col gap-1">
        {nav.map(({ href, label }) => {
          const active = path.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={`px-3 py-2 rounded-md text-sm transition-colors ${
                active
                  ? "bg-blue-600 text-white"
                  : "text-gray-400 hover:bg-gray-800 hover:text-gray-100"
              }`}
            >
              {label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
