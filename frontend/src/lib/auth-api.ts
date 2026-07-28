import { apiClient } from "@/lib/api-client";

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user_id: string;
  role: string;
}

export async function requestOtp(phoneNumber: string): Promise<void> {
  await apiClient.post("/auth/otp/request", { phone_number: phoneNumber });
}

export async function verifyOtp(params: {
  phoneNumber: string;
  code: string;
  fullName?: string;
  role?: string;
}): Promise<TokenPair> {
  const { data } = await apiClient.post<TokenPair>("/auth/otp/verify", {
    phone_number: params.phoneNumber,
    code: params.code,
    full_name: params.fullName,
    role: params.role,
  });
  return data;
}
