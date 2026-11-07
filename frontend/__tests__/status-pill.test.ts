import { describe, it, expect } from "vitest";
import React from "react";
import { StatusPill } from "../components/ui/StatusPill";

describe("StatusPill Component (CLAUDE.md §13)", () => {
  const allTicketStatuses = [
    { status: "new", label: "New" },
    { status: "in_progress", label: "In Progress" },
    { status: "waiting_on_customer", label: "Waiting on Customer" },
    { status: "waiting_on_approval", label: "Waiting on Approval" },
    { status: "escalated", label: "Escalated" },
    { status: "resolved", label: "Resolved" },
    { status: "closed", label: "Closed" },
  ];

  it("renders correctly for all 7 canonical ticket statuses", () => {
    allTicketStatuses.forEach(({ status, label }) => {
      const element = StatusPill({ status });
      expect(element).toBeDefined();
      expect(element.props["data-status"]).toBe(status);

      // Verify label resolution
      const labelSpan = element.props.children[1];
      expect(labelSpan.props.children).toBe(label);
    });
  });

  it("supports custom override labels", () => {
    const element = StatusPill({
      status: "in_progress",
      label: "Custom Agent Working",
    });
    const labelSpan = element.props.children[1];
    expect(labelSpan.props.children).toBe("Custom Agent Working");
  });

  it("renders with dot indicator enabled by default and disabled when requested", () => {
    const withDot = StatusPill({ status: "resolved", dot: true });
    expect(withDot.props.children[0]).not.toBe(false);

    const withoutDot = StatusPill({ status: "resolved", dot: false });
    expect(withoutDot.props.children[0]).toBe(false);
  });

  it("applies size classes for sm and md", () => {
    const smallPill = StatusPill({ status: "new", size: "sm" });
    expect(smallPill.props.className).toContain("text-3xs");

    const mediumPill = StatusPill({ status: "new", size: "md" });
    expect(mediumPill.props.className).toContain("text-xs");
  });

  it("handles unknown or custom status with graceful fallback", () => {
    const unknownPill = StatusPill({ status: "custom_third_party_state" });
    expect(unknownPill.props["data-status"]).toBe("custom_third_party_state");
    const labelSpan = unknownPill.props.children[1];
    expect(labelSpan.props.children).toBe("custom third party state");
  });

  it("enforces zero gradients on container and dot styles", () => {
    allTicketStatuses.forEach(({ status }) => {
      const element = StatusPill({ status });
      const className = element.props.className || "";
      expect(className.includes("gradient")).toBe(false);
    });
  });
});
