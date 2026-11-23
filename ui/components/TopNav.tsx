"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useFuelTerminal } from "@/components/FuelProgressPanel";

const NAV_ITEMS = [
  { href: "/", label: "Settings" },
  { href: "/worlds", label: "Worlds" },
  { href: "/models", label: "Models" },
  { href: "/vehicles", label: "Vehicles" },
  { href: "/fleet", label: "Fleet" },
];

export function TopNav() {
  const pathname = usePathname();
  const { busy, setTerminalOpen } = useFuelTerminal();

  return (
    <header className="border-b border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-950">
      <div className="mx-auto flex w-full max-w-6xl items-center justify-between px-6 py-3">
        <div className="flex items-center gap-6">
          <Link href="/" className="font-mono text-sm font-semibold">
            s7gz
          </Link>
          <nav className="flex items-center gap-1">
            {NAV_ITEMS.map((item) => {
              const active = pathname === item.href;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                    active
                      ? "bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900"
                      : "text-zinc-600 hover:bg-zinc-100 dark:text-zinc-400 dark:hover:bg-zinc-900"
                  }`}
                >
                  {item.label}
                </Link>
              );
            })}
          </nav>
        </div>

        <button
          type="button"
          onClick={() => setTerminalOpen(true)}
          className="flex items-center gap-2 rounded-md border border-zinc-300 bg-zinc-50 px-3 py-1.5 font-mono text-xs font-medium text-zinc-800 transition hover:bg-zinc-100 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-200 dark:hover:bg-zinc-800"
        >
          <span
            className={`h-2 w-2 rounded-full ${
              busy ? "animate-pulse bg-sky-500" : "bg-emerald-500"
            }`}
          />
          <span>{busy ? "Terminal (Running)" : "Terminal"}</span>
        </button>
      </div>
    </header>
  );
}
