"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { getCurrentRole, isAuthenticated, landingPageForRole } from "@/lib/auth";

export default function HomePage() {
  const router = useRouter();

  useEffect(() => {
    if (!isAuthenticated()) {
      router.replace("/login");
      return;
    }
    router.replace(landingPageForRole(getCurrentRole() ?? ""));
  }, [router]);

  return null;
}
