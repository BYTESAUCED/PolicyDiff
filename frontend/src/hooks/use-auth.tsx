'use client';
import { useUser } from '@auth0/nextjs-auth0/client';

export function useAuth() {
  const { user, error, isLoading } = useUser();

  const login = () => window.location.assign('/api/auth/login');
  const logout = () => window.location.assign('/api/auth/logout');
  const signup = () => window.location.assign('/api/auth/login?screen_hint=signup');

  return { user, error, isLoading, isAuthenticated: !!user, login, logout, signup };
}
