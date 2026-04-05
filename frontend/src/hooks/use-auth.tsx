'use client';
import { useUser } from '@auth0/nextjs-auth0/client';

export function useAuth() {
  const { user, error, isLoading } = useUser();

  const login = () => window.location.assign('/auth/login?returnTo=/');
  const logout = () => window.location.assign(`/auth/logout?returnTo=${encodeURIComponent(window.location.origin + '/landing')}`);
  const signup = () => window.location.assign('/auth/login?screen_hint=signup&returnTo=/');

  return { user, error, isLoading, isAuthenticated: !!user, login, logout, signup };
}
