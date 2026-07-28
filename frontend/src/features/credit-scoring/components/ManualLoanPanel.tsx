"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useBorrowerSearch, useCreateLoan } from "@/features/credit-scoring/api";
import type { BorrowerSearchResult } from "@/features/credit-scoring/types";

const METHODS = ["MANUAL", "OVERRIDE"] as const;

function BorrowerSearch({ onSelect }: { onSelect: (borrower: BorrowerSearchResult) => void }) {
  const [phoneQuery, setPhoneQuery] = useState("");
  const [searchTerm, setSearchTerm] = useState("");
  const { data: results, isLoading } = useBorrowerSearch(searchTerm);

  return (
    <div className="space-y-2">
      <div className="flex gap-2">
        <Input placeholder="Search by phone number" value={phoneQuery} onChange={(e) => setPhoneQuery(e.target.value)} />
        <Button onClick={() => setSearchTerm(phoneQuery)} disabled={phoneQuery.length < 3}>
          Search
        </Button>
      </div>
      {isLoading && <p className="text-sm text-slate-500">Searching...</p>}
      {searchTerm && !isLoading && !results?.length && <p className="text-sm text-slate-500">No matching borrower found.</p>}
      {!!results?.length && (
        <ul className="space-y-1">
          {results.map((r) => (
            <li key={r.id}>
              <button
                className="w-full rounded-md bg-slate-100 px-3 py-2 text-left text-sm hover:bg-slate-200"
                onClick={() => onSelect(r)}
              >
                {r.full_name} · {r.phone_number} · {r.role}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function ManualLoanForm({ borrower, onDone }: { borrower: BorrowerSearchResult; onDone: () => void }) {
  const [method, setMethod] = useState<(typeof METHODS)[number]>("MANUAL");
  const [principal, setPrincipal] = useState("");
  const [interestRate, setInterestRate] = useState("0.05");
  const [overrideReason, setOverrideReason] = useState("");
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const createLoan = useCreateLoan();

  async function handleSubmit() {
    setFieldError(null);
    setSuccess(false);
    try {
      await createLoan.mutateAsync({
        borrower_id: borrower.id,
        underwriting_method: method,
        override_reason: overrideReason,
        principal,
        interest_rate: interestRate,
      });
      setSuccess(true);
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } }).response?.status;
      setFieldError(status === 422 ? "A reason is required for a MANUAL or OVERRIDE loan." : "Could not create the loan.");
    }
  }

  return (
    <div className="space-y-2 rounded-md border border-slate-200 p-3">
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium text-slate-700">
          {borrower.full_name} · {borrower.phone_number}
        </p>
        <Button size="sm" variant="secondary" onClick={onDone}>
          Change borrower
        </Button>
      </div>

      <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
        <select
          className="h-10 rounded-md border border-slate-300 bg-white px-3 text-sm"
          value={method}
          onChange={(e) => setMethod(e.target.value as (typeof METHODS)[number])}
        >
          {METHODS.map((m) => (
            <option key={m} value={m}>
              {m}
            </option>
          ))}
        </select>
        <Input placeholder="Principal" inputMode="decimal" value={principal} onChange={(e) => setPrincipal(e.target.value)} />
        <Input placeholder="Interest rate (0.05)" inputMode="decimal" value={interestRate} onChange={(e) => setInterestRate(e.target.value)} />
      </div>
      <Input
        placeholder="Reason for this manual/override decision (required)"
        value={overrideReason}
        onChange={(e) => setOverrideReason(e.target.value)}
      />

      {fieldError && <p className="text-sm text-red-600">{fieldError}</p>}
      {success && <p className="text-sm text-green-600">Loan created.</p>}

      <Button disabled={createLoan.isPending || !principal || !interestRate || !overrideReason} onClick={handleSubmit}>
        Create loan
      </Button>
    </div>
  );
}

export function ManualLoanPanel() {
  const [selectedBorrower, setSelectedBorrower] = useState<BorrowerSearchResult | null>(null);

  return (
    <div className="space-y-3">
      <p className="text-sm text-slate-500">
        For a decision on a known, named applicant outside the algorithmic scoring pipeline (e.g. someone reviewed in person with
        paperwork). Unlike the applicant table, this flow is <strong>not anonymized</strong> — you look up a real person by phone
        number.
      </p>

      {selectedBorrower ? (
        <ManualLoanForm borrower={selectedBorrower} onDone={() => setSelectedBorrower(null)} />
      ) : (
        <BorrowerSearch onSelect={setSelectedBorrower} />
      )}
    </div>
  );
}
