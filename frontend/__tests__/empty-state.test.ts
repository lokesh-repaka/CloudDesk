import { describe, it, expect } from "vitest";
import React from "react";
import { EmptyState } from "../components/ui/EmptyState";

describe("EmptyState Component (CLAUDE.md §13)", () => {
  it("renders with required title and default icon", () => {
    const element = EmptyState({
      title: "No Tickets Found",
    });

    expect(element).toBeDefined();
    expect(element.props.className).toContain("border-dashed");

    const children = React.Children.toArray(element.props.children);
    expect(children.length).toBeGreaterThanOrEqual(2);

    // Verify title text
    const titleElement = children.find(
      (child: any) => child?.props?.className?.includes("font-semibold")
    ) as any;
    expect(titleElement).toBeDefined();
    expect(titleElement.props.children).toBe("No Tickets Found");
  });

  it("renders description when provided", () => {
    const element = EmptyState({
      title: "Queue Empty",
      description: "There are currently no tickets matching your filter criteria.",
    });

    const children = React.Children.toArray(element.props.children);
    const descElement = children.find(
      (child: any) => child?.props?.className?.includes("text-slate-500")
    ) as any;

    expect(descElement).toBeDefined();
    expect(descElement.props.children).toBe(
      "There are currently no tickets matching your filter criteria."
    );
  });

  it("renders action button or container when provided", () => {
    const actionNode = React.createElement("button", { id: "reset-btn" }, "Reset Filter");
    const element = EmptyState({
      title: "No Results",
      action: actionNode,
    });

    const children = React.Children.toArray(element.props.children);
    const actionContainer = children.find(
      (child: any) => child?.props?.className?.includes("mt-5")
    ) as any;

    expect(actionContainer).toBeDefined();
    expect(actionContainer.props.children).toBe(actionNode);
  });

  it("renders custom icon when provided", () => {
    const customIcon = React.createElement("svg", { "data-testid": "custom-icon" });
    const element = EmptyState({
      title: "Custom Empty",
      icon: customIcon,
    });

    const children = React.Children.toArray(element.props.children);
    const iconContainer = children[0] as any;
    expect(iconContainer.props.children).toBe(customIcon);
  });

  it("enforces zero gradients across container styling", () => {
    const element = EmptyState({
      title: "Zero Gradient Check",
      description: "Ensure no gradient classes exist.",
    });

    const className = element.props.className || "";
    expect(className.includes("gradient")).toBe(false);
  });
});
