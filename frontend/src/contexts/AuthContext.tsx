import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import {
  type User,
  signInWithPopup,
  signInWithEmailAndPassword,
  signOut as firebaseSignOut,
  onAuthStateChanged
} from 'firebase/auth';
import { auth, googleProvider } from '../lib/firebase';
import api from '../utils/api';

interface AuthContextType {
  user: User | null;
  loading: boolean;
  isAuthorized: boolean;
  isAdmin: boolean;
  userRole: string | null;
  userScope: string | null;
  userTools: string[];
  authError: string | null;
  signInWithGoogle: () => Promise<void>;
  signInWithEmail: (email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
  getIdToken: () => Promise<string | null>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api';

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [isAuthorized, setIsAuthorized] = useState(false);
  const [isAdmin, setIsAdmin] = useState(false);
  const [userRole, setUserRole] = useState<string | null>(null);
  const [userScope, setUserScope] = useState<string | null>(null);
  const [userTools, setUserTools] = useState<string[]>([]);
  const [authError, setAuthError] = useState<string | null>(null);

  // Check if user is in allowlist and get role info
  const checkAuthorization = async (email: string) => {
    try {
      const response = await fetch(`${API_BASE}/admin/users/${encodeURIComponent(email)}/check`);
      if (response.ok) {
        const data = await response.json();
        return data;
      }
      return false;
    } catch (error) {
      console.error('Error checking authorization:', error);
      // If backend is unavailable, allow access (dev mode)
      return true;
    }
  };

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, async (user) => {
      setUser(user);
      setAuthError(null);

      if (user?.email) {
        // Set auth token on ApiClient for all api.* calls
        try {
          const token = await user.getIdToken();
          api.setAuthToken(token);
        } catch {
          // Token may not be available yet, will retry on next call
        }

        const authData = await checkAuthorization(user.email);
        const authorized = typeof authData === 'object' ? authData.allowed : authData;
        setIsAuthorized(authorized);
        if (authorized && typeof authData === 'object') {
          setIsAdmin(authData.is_admin || false);
          setUserRole(authData.role || 'user');
          setUserScope(authData.scope || 'all');
          setUserTools(authData.tools || []);
        } else {
          setIsAdmin(false);
          setUserRole(null);
          setUserScope(null);
          setUserTools([]);
        }
        if (!authorized) {
          setAuthError('Your account is not authorized to access this application. Please contact an administrator.');
        }
      } else {
        setIsAuthorized(false);
        setIsAdmin(false);
        setUserRole(null);
        setUserScope(null);
        setUserTools([]);
        api.clearAuthToken();
      }

      setLoading(false);
    });

    return () => unsubscribe();
  }, []);

  const signInWithGoogle = async () => {
    try {
      await signInWithPopup(auth, googleProvider);
    } catch (error) {
      console.error('Error signing in with Google:', error);
      throw error;
    }
  };

  const signInWithEmail = async (email: string, password: string) => {
    try {
      await signInWithEmailAndPassword(auth, email, password);
    } catch (error: unknown) {
      console.error('Error signing in with email:', error);
      // Provide user-friendly error messages
      const firebaseError = error as { code?: string };
      if (firebaseError.code === 'auth/user-not-found') {
        throw new Error('No account found with this email address.');
      } else if (firebaseError.code === 'auth/wrong-password') {
        throw new Error('Incorrect password.');
      } else if (firebaseError.code === 'auth/invalid-email') {
        throw new Error('Invalid email address.');
      } else if (firebaseError.code === 'auth/invalid-credential') {
        throw new Error('Invalid email or password.');
      } else if (firebaseError.code === 'auth/too-many-requests') {
        throw new Error('Too many failed attempts. Please try again later.');
      }
      throw new Error('Login failed. Please try again.');
    }
  };

  const signOut = async () => {
    try {
      await firebaseSignOut(auth);
    } catch (error) {
      console.error('Error signing out:', error);
      throw error;
    }
  };

  const getIdToken = async (): Promise<string | null> => {
    if (!user) return null;
    try {
      return await user.getIdToken();
    } catch (error) {
      console.error('Error getting ID token:', error);
      return null;
    }
  };

  const value = {
    user,
    loading,
    isAuthorized,
    isAdmin,
    userRole,
    userScope,
    userTools,
    authError,
    signInWithGoogle,
    signInWithEmail,
    signOut,
    getIdToken,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
