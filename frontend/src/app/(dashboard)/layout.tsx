"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { clearSession, getCurrentRole, isAuthenticated } from "@/lib/auth";

const NAV_ITEMS = [
  { href: "/ledger", label: "Duka Ledger", roles: ["MERCHANT"] },
  { href: "/chama", label: "Chama Portal", roles: ["MERCHANT", "CHAMA_MEMBER"] },
  { href: "/underwriting", label: "Underwriting", roles: ["UNDERWRITER"] },
  { href: "/admin", label: "Admin", roles: ["ADMIN"] },
];

export default function DashboardLayout({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (!isAuthenticated()) {
      router.replace("/login");
    }
  }, [router]);

  const role = getCurrentRole();

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3">
          <span className="font-semibold text-slate-900">DukaCred</span>
          <nav className="flex items-center gap-4">
            {NAV_ITEMS.filter((item) => !role || item.roles.includes(role)).map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className={pathname?.startsWith(item.href) ? "text-sm font-medium text-slate-900" : "text-sm text-slate-500 hover:text-slate-900"}
              >
                {item.label}
              </Link>
            ))}
            <Button
              variant="secondary"
              size="sm"
              onClick={() => {
                clearSession();
                router.push("/login");
              }}
            >
              Log out
            </Button>
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-4 py-6">{children}</main>
    </div>
  );
}
