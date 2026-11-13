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
              className={`group flex items-center gap-3 px-3 py-2 text-xs rounded-xl transition-all outline-none focus-visible:ring-2 focus-visible:ring-[#00d2b4] ${
                isActive
                  ? "bg-[#0f2429] text-[#2dd4bf] font-bold border-l-2 border-[#00d2b4] shadow-xs"
                  : "text-[#7d97a3] hover:text-white hover:bg-[#0c181d] font-normal"
              }`}
            >
              <span
                className={`flex-shrink-0 transition-colors ${
                  isActive ? "text-[#00d2b4]" : "text-[#5a7683] group-hover:text-white"
                }`}
              >
                {renderNavIcon(item.icon, { size: 18 })}
              </span>

              {!collapsed && (
                <div className="flex-1 flex items-center justify-between min-w-0">
                  <span className="truncate">{item.label}</span>
                  {badgeCount > 0 && (
                    <div className="flex items-center gap-1.5 ml-2">
                      <span className="inline-flex items-center px-1.5 py-0.5 rounded-full text-3xs font-semibold bg-[#143239] text-[#2dd4bf] border border-[#1b4c57]">
                        {badgeCount}
                      </span>
                    </div>
                  )}
                </div>
              )}
            </Link>
          </li>
        );
      })}
    </ul>
  );
}
