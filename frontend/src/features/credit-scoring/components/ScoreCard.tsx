"use client";

import { Badge, riskTierTone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useEvaluateMerchant, useLatestScore } from "@/features/credit-scoring/api";

export function ScoreCard({ userId }: { userId: string }) {
  const { data: score, isLoading, error } = useLatestScore(userId);
  const evaluate = useEvaluateMerchant();

  const maxAbs = score ? Math.max(...Object.values(score.shap_explanation).map((v) => Math.abs(v)), 0.0001) : 1;

  return (
    <div className="space-y-4">
      {isLoading && <p className="text-sm text-slate-500">Loading score...</p>}
      {error && !score && <p className="text-sm text-slate-500">No score on file yet.</p>}

      {score && (
        <div className="space-y-3">
          <div className="flex items-center gap-3">
            <span className="text-3xl font-semibold text-slate-900">{score.credit_score}</span>
            <Badge tone={riskTierTone(score.risk_tier)}>{score.risk_tier}</Badge>
          </div>
          <p className="text-sm text-slate-500">Recommended limit: KES {score.recommended_limit}</p>

          <div className="space-y-1">
            <p className="text-xs font-medium uppercase tracking-wide text-slate-400">Feature contribution (SHAP)</p>
            {Object.entries(score.shap_explanation).map(([feature, value]) => (
              <div key={feature} className="flex items-center gap-2 text-xs">
                <span className="w-32 shrink-0 text-slate-600">{feature}</span>
                <div className="h-2 flex-1 rounded-full bg-slate-100">
                  <div
                    className={`h-2 rounded-full ${value >= 0 ? "bg-red-400" : "bg-green-400"}`}
                    style={{ width: `${(Math.abs(value) / maxAbs) * 100}%` }}
                  />
                </div>
                <span className="w-16 text-right text-slate-500">{value.toFixed(4)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <Button onClick={() => evaluate.mutate(userId)} disabled={evaluate.isPending} variant="secondary" size="sm">
        {evaluate.isPending ? "Evaluating..." : "Re-evaluate"}
      </Button>
    </div>
  );
}
