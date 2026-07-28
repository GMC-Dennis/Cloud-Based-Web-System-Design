"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { isAuthenticated } from "@/lib/auth";

export default function HomePage() {
  const router = useRouter();

  useEffect(() => {
    router.replace(isAuthenticated() ? "/ledger" : "/login");
  }, [router]);

  return null;
}
