import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { KPI } from "./KPI";

describe("<KPI>", () => {
  it("renders label and value", () => {
    render(<KPI label="Today tokens" value="1.2K" accent="var(--amber)" />);
    expect(screen.getByText("Today tokens")).toBeInTheDocument();
    expect(screen.getByText("1.2K")).toBeInTheDocument();
  });

  it("up delta has the up class (red for cost-up)", () => {
    const { container } = render(
      <KPI label="cost" value="$10" delta="+3%" deltaDir="up" accent="var(--red)" />,
    );
    const delta = container.querySelector(".kpi-delta.up");
    expect(delta).not.toBeNull();
    expect(delta?.textContent).toContain("+3%");
  });

  it("down delta has the down class (green for cost-down)", () => {
    const { container } = render(
      <KPI label="cost" value="$10" delta="-3%" deltaDir="down" accent="var(--green)" />,
    );
    expect(container.querySelector(".kpi-delta.down")).not.toBeNull();
  });

  it("renders unit span when provided", () => {
    render(<KPI label="eff" value={72} unit="/100" accent="var(--green)" />);
    expect(screen.getByText("/100")).toBeInTheDocument();
  });

  it("renders the sparkline when spark data is provided", () => {
    const { container } = render(
      <KPI
        label="trend"
        value="42"
        accent="var(--blue)"
        spark={[1, 2, 3, 4, 5]}
        sparkColor="var(--blue)"
      />,
    );
    const spark = container.querySelector(".kpi-spark svg");
    expect(spark).not.toBeNull();
  });
});
