// Dev-mode simplification: tokens live in localStorage rather than the
// HttpOnly refresh-cookie flow described in the TDD (§8). That flow assumes
// frontend and backend share a site (both under Google infra in production);
// cross-origin localhost:3000 <-> localhost:8001 in local dev makes an
// HttpOnly cookie impractical to wire up correctly. Swap this out when
// deploying behind a shared domain/proxy.

const ACCESS_TOKEN_KEY = "dukacred_access_token";
const REFRESH_TOKEN_KEY = "dukacred_refresh_token";
const USER_ID_KEY = "dukacred_user_id";
const ROLE_KEY = "dukacred_role";

export interface StoredSession {
  accessToken: string;
  refreshToken: string;
  userId: string;
  role: string;
}

export function saveSession(session: StoredSession): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(ACCESS_TOKEN_KEY, session.accessToken);
  localStorage.setItem(REFRESH_TOKEN_KEY, session.refreshToken);
  localStorage.setItem(USER_ID_KEY, session.userId);
  localStorage.setItem(ROLE_KEY, session.role);
}

export function updateTokens(accessToken: string, refreshToken: string): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
  localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
}

export function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function getRefreshToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(REFRESH_TOKEN_KEY);
}

export function getCurrentUserId(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(USER_ID_KEY);
}

export function getCurrentRole(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(ROLE_KEY);
}

export function clearSession(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
  localStorage.removeItem(USER_ID_KEY);
  localStorage.removeItem(ROLE_KEY);
}

export function isAuthenticated(): boolean {
  return getAccessToken() !== null;
}
