"use client";

import { useEffect, useState } from "react";

import { getCurrentUserId } from "@/lib/auth";
import { ScoreCard } from "@/features/credit-scoring/components/ScoreCard";

export function MyScorePanel() {
  // Read localStorage post-mount only, to avoid an SSR/client hydration mismatch.
  const [userId, setUserId] = useState<string | null>(null);
  useEffect(() => setUserId(getCurrentUserId()), []);

  if (!userId) return null;
  return <ScoreCard userId={userId} />;
}
