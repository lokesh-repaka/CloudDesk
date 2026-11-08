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
            className="text-[#7d97a3] hover:text-white transition-colors flex items-center p-0.5 rounded focus-visible:ring-2 focus-visible:ring-[#00d2b4]"
            title="Dashboard Home"
          >
            <HomeIcon size={14} className="text-[#5a7683] hover:text-white transition-colors" />
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
              <li className="text-[#334b56] flex items-center" aria-hidden="true">
                <ChevronRightIcon size={12} />
              </li>
              <li>
                {isLast ? (
                  <span
                    className="font-medium text-white truncate max-w-[200px]"
                    aria-current="page"
                  >
                    {label}
                  </span>
                ) : (
                  <Link
                    href={href}
                    className="text-[#7d97a3] hover:text-white transition-colors truncate max-w-[150px] focus-visible:ring-2 focus-visible:ring-[#00d2b4] rounded"
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
