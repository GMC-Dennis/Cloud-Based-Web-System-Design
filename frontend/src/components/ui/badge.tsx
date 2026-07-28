import { cva, type VariantProps } from "class-variance-authority";
import type { HTMLAttributes } from "react";

import { cn } from "@/lib/utils";

const badgeVariants = cva("inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium", {
  variants: {
    tone: {
      neutral: "bg-slate-100 text-slate-700",
      success: "bg-green-100 text-green-800",
      warning: "bg-amber-100 text-amber-800",
      danger: "bg-red-100 text-red-800",
    },
  },
  defaultVariants: { tone: "neutral" },
});

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement>, VariantProps<typeof badgeVariants> {}

export function Badge({ className, tone, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ tone }), className)} {...props} />;
}

export function riskTierTone(tier: string): BadgeProps["tone"] {
  if (tier === "LOW") return "success";
  if (tier === "MEDIUM") return "warning";
  if (tier === "HIGH") return "danger";
  return "neutral";
}
