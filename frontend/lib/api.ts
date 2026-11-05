import { supabase } from './supabase';

const API_URL = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000').replace(/\/$/, '');

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const { data: { session } } = supabase ? await supabase.auth.getSession() : { data: { session: null } };
  const headers = new Headers(init.headers);
  if (session?.access_token) {
    headers.set('Authorization', `Bearer ${session.access_token}`);
  } else if (typeof window !== 'undefined') {
    const localToken = localStorage.getItem('eduagents_auth_token');
    if (localToken) {
      headers.set('Authorization', `Bearer ${localToken}`);
    } else {
      headers.set('Authorization', 'Bearer mock-faculty-token:00000000-0000-0000-0000-000000000101');
    }
  }
  if (init.body && !(init.body instanceof FormData)) headers.set('Content-Type', 'application/json');
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, { ...init, headers, cache: 'no-store' });
  } catch {
    throw new ApiError(`Cannot reach EduAgents API at ${API_URL}. Start the FastAPI backend or set NEXT_PUBLIC_API_URL.`, 0);
  }
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new ApiError(body?.error?.message || body?.detail || `Request failed (${response.status})`, response.status);
  }
  return body as T;
}

export async function getSessionUser() {
  if (!supabase) return null;
  const { data: { session } } = await supabase.auth.getSession();
  return session?.user ?? null;
}
