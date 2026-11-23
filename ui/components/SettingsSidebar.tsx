"use client";

import { isFieldOverridden } from "@/lib/settings-utils";
import type { SettingsGroup } from "@/lib/types";

interface SettingsSidebarProps {
  groups: SettingsGroup[];
  selectedGroup: string | null;
  onSelectGroup: (groupName: string | null) => void;
  searchQuery: string;
  onSearchChange: (q: string) => void;
  onlyOverridden: boolean;
  onOnlyOverriddenChange: (value: boolean) => void;
}

export function SettingsSidebar({
  groups,
  selectedGroup,
  onSelectGroup,
  searchQuery,
  onSearchChange,
  onlyOverridden,
  onOnlyOverriddenChange,
}: SettingsSidebarProps) {
  const totalOverridden = groups.reduce(
    (sum, g) => sum + g.fields.filter(isFieldOverridden).length,
    0,
  );

  return (
    <aside className="w-full shrink-0 space-y-4 lg:w-72">
      <div className="space-y-2 rounded-lg border border-zinc-200 bg-white p-3 dark:border-zinc-800 dark:bg-zinc-950">
        <input
          type="search"
          value={searchQuery}
          onChange={(e) => onSearchChange(e.target.value)}
          placeholder="Search group, field, env_key..."
          className="w-full rounded-md border border-zinc-300 bg-transparent px-3 py-1.5 text-sm outline-none focus:border-zinc-500 dark:border-zinc-700"
        />
        <label className="flex cursor-pointer items-center justify-between text-xs text-zinc-600 dark:text-zinc-400">
          <span>Only overridden ({totalOverridden})</span>
          <input
            type="checkbox"
            checked={onlyOverridden}
            onChange={(e) => onOnlyOverriddenChange(e.target.checked)}
            className="h-4 w-4 accent-zinc-900 dark:accent-zinc-100"
          />
        </label>
      </div>

      <nav className="rounded-lg border border-zinc-200 bg-white p-2 dark:border-zinc-800 dark:bg-zinc-950">
        <button
          type="button"
          onClick={() => onSelectGroup(null)}
          className={`flex w-full items-center justify-between rounded-md px-3 py-2 text-left text-sm transition-colors ${
            selectedGroup === null
              ? "bg-zinc-900 font-medium text-white dark:bg-zinc-100 dark:text-zinc-900"
              : "text-zinc-700 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-900"
          }`}
        >
          <span>All Groups</span>
          <span className="text-xs opacity-75">{groups.length}</span>
        </button>

        <div className="mt-1 space-y-0.5">
          {groups.map((g) => {
            const overriddenCount = g.fields.filter(isFieldOverridden).length;
            const active = selectedGroup === g.group;
            return (
              <button
                key={g.group}
                type="button"
                onClick={() => onSelectGroup(g.group)}
                className={`flex w-full items-center justify-between gap-2 rounded-md px-3 py-1.5 text-left text-sm transition-colors ${
                  active
                    ? "bg-zinc-900 font-medium text-white dark:bg-zinc-100 dark:text-zinc-900"
                    : "text-zinc-700 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-900"
                }`}
              >
                <span className="truncate">{g.group}</span>
                <span className="flex shrink-0 items-center gap-1.5 text-xs">
                  {overriddenCount > 0 && (
                    <span
                      className={`rounded-full px-1.5 py-0.5 text-[11px] font-medium ${
                        active
                          ? "bg-amber-400 text-zinc-950"
                          : "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300"
                      }`}
                    >
                      {overriddenCount}
                    </span>
                  )}
                  <span className="opacity-60">{g.fields.length}</span>
                </span>
              </button>
            );
          })}
        </div>
      </nav>
    </aside>
  );
}
