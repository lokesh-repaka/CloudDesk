"use client";

import React from "react";
import Link from "next/link";
import { NavItem } from "./nav";
import { renderNavIcon } from "./Icons";
import { Role } from "@/lib/types";

export interface NavItemsProps {
  items: NavItem[];
  currentPath: string;
  userRole?: Role;
  collapsed?: boolean;
  badgeCounts?: Record<string, number>;
  onItemClick?: () => void;
}

export function NavItems({
  items,
  currentPath,
  userRole = "viewer",
  collapsed = false,
  badgeCounts = {},
  onItemClick,
}: NavItemsProps) {
  const roleRank: Record<Role, number> = {
    viewer: 1,
    agent: 2,
    admin: 3,
  };

  const currentRank = roleRank[userRole] ?? 1;

  return (
    <ul className="space-y-1" role="list">
      {items.map((item) => {
        const isAuthorized = roleRank[item.minRole] <= currentRank;
        if (!isAuthorized) {
          return null;
        }

        const isActive =
          item.href === "/"
            ? currentPath === "/"
            : currentPath === item.href || currentPath.startsWith(`${item.href}/`);

        const badgeCount = item.badgeKey ? badgeCounts[item.badgeKey] ?? 0 : 0;

        return (
          <li key={item.id}>
            <Link
              href={item.href}
              onClick={onItemClick}
              aria-current={isActive ? "page" : undefined}
              title={collapsed ? `${item.label}: ${item.description}` : undefined}
              className={`group flex items-center gap-3 px-3 py-2 text-sm rounded-md transition-colors outline-none focus-visible:ring-2 focus-visible:ring-brand-500 ${
                isActive
                  ? "bg-brand-50 text-brand-700 font-semibold border-l-2 border-brand-600"
                  : "text-slate-600 hover:text-slate-900 hover:bg-slate-100 font-normal"
              }`}
            >
              <span
                className={`flex-shrink-0 transition-colors ${
                  isActive ? "text-brand-600" : "text-slate-500 group-hover:text-slate-700"
                }`}
              >
                {renderNavIcon(item.icon, { size: 18 })}
              </span>

              {!collapsed && (
                <div className="flex-1 flex items-center justify-between min-w-0">
                  <span className="truncate">{item.label}</span>
                  <div className="flex items-center gap-1.5 ml-2">
                    {badgeCount > 0 && (
                      <span className="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-amber-100 text-amber-800">
                        {badgeCount}
                      </span>
                    )}
                    {item.shortcut && (
                      <kbd className="hidden sm:inline-block px-1.5 py-0.5 text-3xs font-mono text-slate-500 bg-slate-100 border border-slate-200 rounded">
                        {item.shortcut}
                      </kbd>
                    )}
                  </div>
                </div>
              )}
            </Link>
          </li>
        );
      })}
    </ul>
  );
}

