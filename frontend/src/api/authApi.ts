import api, { AUTH_TOKEN_KEY } from './client';

export interface AuthUser {
  id: number;
  email: string;
  display_name: string;
  created_at: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: AuthUser;
}

export function storeToken(token: string) {
  localStorage.setItem(AUTH_TOKEN_KEY, token);
}

export function clearToken() {
  localStorage.removeItem(AUTH_TOKEN_KEY);
}

export function hasToken() {
  return Boolean(localStorage.getItem(AUTH_TOKEN_KEY));
}

export async function register(email: string, password: string, displayName: string) {
  const response = await api.post<AuthResponse>('/api/auth/register', {
    email,
    password,
    display_name: displayName,
  });
  return response.data;
}

export async function login(email: string, password: string) {
  const response = await api.post<AuthResponse>('/api/auth/login', { email, password });
  return response.data;
}

export async function fetchMe() {
  const response = await api.get<{ user: AuthUser }>('/api/auth/me');
  return response.data.user;
}
