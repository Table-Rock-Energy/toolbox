import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import api from '../utils/api';

export interface LocalUser {
  email: string;
  displayName: string | null;
  photoURL: string | null;
  id: string;
}

interface AuthContextType {
  user: LocalUser | null;
  userName: string | null;
  loading: boolean;
  isAuthorized: boolean;
  isAdmin: boolean;
  userRole: string | null;
  userScope: string | null;
  userTools: string[];
  authError: string | null;
  backendReachable: boolean;
  signInWithEmail: (email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
  getToken: () => string | null;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api';

interface UserProfileResponse {
  email: string;
  role: string;
  scope: string;
  tools: string[];
  first_name?: string | null;
  last_name?: string | null;
  is_admin: boolean;
}

interface LoginResponse {
  access_token: string;
  token_type: string;
  user: UserProfileResponse;
}

function buildLocalUser(profile: UserProfileResponse): LocalUser {
  const displayName = [profile.first_name, profile.last_name].filter(Boolean).join(' ') || null;
  return {
    email: profile.email,
    displayName,
    photoURL: null,
    id: profile.email,
  };
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<LocalUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [isAuthorized, setIsAuthorized] = useState(false);
  const [isAdmin, setIsAdmin] = useState(false);
  const [userRole, setUserRole] = useState<string | null>(null);
  const [userScope, setUserScope] = useState<string | null>(null);
  const [userTools, setUserTools] = useState<string[]>([]);
  const [userName, setUserName] = useState<string | null>(null);
  const [authError, setAuthError] = useState<string | null>(null);
  const [backendReachable, setBackendReachable] = useState(true);

  const applyProfile = (profile: UserProfileResponse) => {
    const localUser = buildLocalUser(profile);
    setUser(localUser);
    setIsAuthorized(true);
    setIsAdmin(profile.is_admin);
    setUserRole(profile.role);
    setUserScope(profile.scope);
    setUserTools(profile.tools || []);
    setUserName(localUser.displayName);
  };

  const clearAuth = () => {
    localStorage.removeItem('auth_token');
    api.clearAuthToken();
    setUser(null);
    setIsAuthorized(false);
    setIsAdmin(false);
    setUserRole(null);
    setUserScope(null);
    setUserTools([]);
    setUserName(null);
  };

  // Session restore on mount
  useEffect(() => {
    const restore = async () => {
      const token = localStorage.getItem('auth_token');
      if (!token) {
        setLoading(false);
        return;
      }

      api.setAuthToken(token);

      // Probe backend health with retry for cold starts
      let reachable = false;
      for (let attempt = 0; attempt < 3; attempt++) {
        try {
          const controller = new AbortController();
          const timeoutId = setTimeout(() => controller.abort(), 10000);
          await fetch(`${API_BASE}/health`, { signal: controller.signal });
          clearTimeout(timeoutId);
          reachable = true;
          break;
        } catch {
          if (attempt < 2) await new Promise(r => setTimeout(r, 2000));
        }
      }

      setBackendReachable(reachable);
      if (!reachable) {
        setLoading(false);
        return;
      }

      // Validate token with /auth/me
      try {
        const response = await fetch(`${API_BASE}/auth/me`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (response.ok) {
          const profile: UserProfileResponse = await response.json();
          applyProfile(profile);
        } else {
          // Token expired or invalid
          clearAuth();
        }
      } catch {
        clearAuth();
      }

      setLoading(false);
    };

    // Register 401 handler -- session expired, no retry
    api.setUnauthorizedHandler(async () => {
      clearAuth();
      setAuthError('Your session has expired. Please sign in again.');
      return false;
    });

    restore();
  }, []);

  const signInWithEmail = async (email: string, password: string) => {
    const response = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail || 'Login failed');
    }

    const loginData = data as LoginResponse;
    localStorage.setItem('auth_token', loginData.access_token);
    api.setAuthToken(loginData.access_token);
    applyProfile(loginData.user);
    setAuthError(null);
  };

  const signOut = async () => {
    clearAuth();
  };

  const getToken = (): string | null => {
    return localStorage.getItem('auth_token');
  };

  const value = {
    user,
    userName,
    loading,
    isAuthorized,
    isAdmin,
    userRole,
    userScope,
    userTools,
    authError,
    backendReachable,
    signInWithEmail,
    signOut,
    getToken,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
