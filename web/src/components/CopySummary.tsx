import { useState } from "react";

import { api } from "../api";

/** Copy the campaign verdict as markdown (with links back to this UI) for a PR or release thread. */
export default function CopySummary({ campaignId }: { campaignId: number }) {
  const [state, setState] = useState<"idle" | "copied" | "error">("idle");
  async function copy() {
    try {
      const md = await api.summary(campaignId, window.location.origin);
      await navigator.clipboard.writeText(md);
      setState("copied");
      setTimeout(() => setState("idle"), 2500);
    } catch {
      setState("error");
    }
  }
  return (
    <button onClick={copy} title="Verdict, KPIs and top clusters as markdown">
      {state === "copied" ? "Copied" : state === "error" ? "Copy failed" : "Copy summary"}
    </button>
  );
}
