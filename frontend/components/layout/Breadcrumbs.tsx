"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ChevronRightIcon, HomeIcon } from "./Icons";
import { MAIN_NAV_ITEMS } from "./nav";

export interface BreadcrumbsProps {
  pathname?: string;
  className?: string;
}

export function Breadcrumbs({ pathname: propPathname, className = "" }: BreadcrumbsProps) {
  const currentPathname = usePathname();
  const path = propPathname ?? currentPathname ?? "/dashboard";

  // Create lookup for known nav labels
  const navLabelMap: Record<string, string> = {};
  for (const item of MAIN_NAV_ITEMS) {
    const segment = item.href.replace(/^\//, "");
    navLabelMap[segment] = item.label;
  }

  const segments = path.split("/").filter(Boolean);

  return (
    <nav aria-label="Breadcrumb" className={`flex items-center text-xs ${className}`}>
      <ol className="flex items-center space-x-1.5 list-none p-0 m-0">
        <li>
          <Link
            href="/dashboard"
            className="text-slate-500 hover:text-slate-700 transition-colors flex items-center p-0.5 rounded focus-visible:ring-2 focus-visible:ring-brand-500"
            title="Dashboard Home"
          >
            <HomeIcon size={14} className="text-slate-400" />
            <span className="sr-only">Home</span>
          </Link>
        </li>

        {segments.map((segment, index) => {
          const href = `/${segments.slice(0, index + 1).join("/")}`;
          const isLast = index === segments.length - 1;
          const label =
            navLabelMap[segment] ||
            decodeURIComponent(segment).replace(/[-_]/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

          return (
            <React.Fragment key={href}>
              <li className="text-slate-400 flex items-center" aria-hidden="true">
                <ChevronRightIcon size={12} />
              </li>
              <li className="flex items-center">
                {isLast ? (
                  <span
                    className="font-medium text-slate-800 truncate max-w-xs"
                    aria-current="page"
                  >
                    {label}
                  </span>
                ) : (
                  <Link
                    href={href}
                    className="text-slate-500 hover:text-slate-700 transition-colors truncate max-w-xs focus-visible:ring-2 focus-visible:ring-brand-500 rounded"
                  >
                    {label}
                  </Link>
                )}
              </li>
            </React.Fragment>
          );
        })}
      </ol>
    </nav>
  );
}

