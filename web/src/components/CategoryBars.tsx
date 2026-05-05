import { CATEGORIES, type Verdict } from "../api";
import { CATEGORY_COLOR, CATEGORY_LABEL } from "../format";

/** Failures per category with the flag threshold, as in the campaign verdict. */
export default function CategoryBars({ verdict }: { verdict: Verdict }) {
  const max = Math.max(1, ...CATEGORIES.map((c) => verdict.categories[c]?.failures ?? 0));
  return (
    <div className="stack" style={{ gap: 8 }}>
      {CATEGORIES.map((c) => {
        const row = verdict.categories[c];
        const n = row?.failures ?? 0;
        return (
          <div key={c} className="row" style={{ alignItems: "center", gap: 10 }} data-testid={`bar-${c}`}>
            <div style={{ width: 150 }} className={row?.flagged ? "" : "muted"}>
              {CATEGORY_LABEL[c]}
            </div>
            <div style={{ flex: 1, background: "var(--panel-2)", borderRadius: 4, height: 14 }}>
              <div
                style={{
                  width: `${(100 * n) / max}%`,
                  height: "100%",
                  borderRadius: 4,
                  background: CATEGORY_COLOR[c],
                  opacity: row?.flagged ? 1 : 0.45,
                }}
              />
            </div>
            <div style={{ width: 150 }} className="num">
              {n} <span className="muted">({row?.per_1000 ?? 0}/1k)</span> {row?.flagged && <strong>flagged</strong>}
            </div>
          </div>
        );
      })}
    </div>
  );
}
