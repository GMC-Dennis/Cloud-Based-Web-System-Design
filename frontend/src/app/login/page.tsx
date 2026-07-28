"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { requestOtp, verifyOtp } from "@/lib/auth-api";
import { landingPageForRole, saveSession } from "@/lib/auth";

type Step = "phone" | "otp";

// UNDERWRITER/ADMIN are deliberately excluded -- those accounts must be
// provisioned by an existing admin (see /admin), not self-assigned here.
// The backend enforces this independently of what this list offers.
const ROLES = ["MERCHANT", "CHAMA_MEMBER"] as const;

export default function LoginPage() {
  const router = useRouter();
  const [step, setStep] = useState<Step>("phone");
  const [phoneNumber, setPhoneNumber] = useState("");
  const [code, setCode] = useState("");
  const [fullName, setFullName] = useState("");
  const [role, setRole] = useState<(typeof ROLES)[number]>("MERCHANT");
  const [needsRegistration, setNeedsRegistration] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleRequestOtp() {
    setError(null);
    setBusy(true);
    try {
      await requestOtp(phoneNumber);
      setStep("otp");
    } catch {
      setError("Could not send OTP. Check the phone number and try again.");
    } finally {
      setBusy(false);
    }
  }

  async function handleVerify() {
    setError(null);
    setBusy(true);
    try {
      const result = await verifyOtp({
        phoneNumber,
        code,
        fullName: needsRegistration ? fullName : undefined,
        role: needsRegistration ? role : undefined,
      });
      saveSession({
        accessToken: result.access_token,
        refreshToken: result.refresh_token,
        userId: result.user_id,
        role: result.role,
      });
      router.push(landingPageForRole(result.role));
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } }).response?.status;
      if (status === 404) {
        setNeedsRegistration(true);
        setError("First time here -- tell us your name and role to finish signing up.");
      } else if (status === 403) {
        setError("This account has been deactivated. Contact an administrator.");
      } else {
        setError("Incorrect or expired code.");
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 p-4">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>Sign in to DukaCred</CardTitle>
        </CardHeader>

        {step === "phone" && (
          <div className="space-y-3">
            <Input placeholder="+254712345678" value={phoneNumber} onChange={(e) => setPhoneNumber(e.target.value)} />
            <Button className="w-full" disabled={busy || !phoneNumber} onClick={handleRequestOtp}>
              Send code
            </Button>
          </div>
        )}

        {step === "otp" && (
          <div className="space-y-3">
            <p className="text-sm text-slate-500">Enter the code sent to {phoneNumber}.</p>
            <Input placeholder="123456" value={code} onChange={(e) => setCode(e.target.value)} />

            {needsRegistration && (
              <>
                <Input placeholder="Full name" value={fullName} onChange={(e) => setFullName(e.target.value)} />
                <select
                  className="h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm"
                  value={role}
                  onChange={(e) => setRole(e.target.value as (typeof ROLES)[number])}
                >
                  {ROLES.map((r) => (
                    <option key={r} value={r}>
                      {r}
                    </option>
                  ))}
                </select>
              </>
            )}

            {error && <p className="text-sm text-red-600">{error}</p>}

            <Button className="w-full" disabled={busy || !code || (needsRegistration && !fullName)} onClick={handleVerify}>
              Verify
            </Button>
          </div>
        )}
      </Card>
    </main>
  );
}
