export const fmt = {
  n: (n: number) => n.toLocaleString("en-US"),
  k: (n: number) => {
    if (n >= 1e9) return (n / 1e9).toFixed(2) + "B";
    if (n >= 1e6) return (n / 1e6).toFixed(2) + "M";
    if (n >= 1e3) return (n / 1e3).toFixed(1) + "K";
    return n.toString();
  },
  usd: (n: number) => "$" + n.toFixed(2),
  pct: (n: number) => (n * 100).toFixed(1) + "%",
  delta: (n: number) => (n >= 0 ? "+" : "") + (n * 100).toFixed(1) + "%",
};
