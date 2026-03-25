import { useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { Navigate } from 'react-router-dom';

export default function Login() {
  const { user, loading, isAuthorized, authError, backendReachable, signInWithEmail, signOut } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [emailError, setEmailError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleEmailLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setEmailError('');
    setIsSubmitting(true);

    try {
      await signInWithEmail(email, password);
    } catch (error: unknown) {
      const errorMessage = error instanceof Error ? error.message : 'Login failed';
      setEmailError(errorMessage);
    } finally {
      setIsSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-tre-navy flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-tre-teal"></div>
      </div>
    );
  }

  // User is logged in and authorized
  if (user && isAuthorized) {
    return <Navigate to="/" replace />;
  }

  return (
    <div className="min-h-screen bg-tre-navy flex flex-col items-center justify-center px-4">
      {/* Logo */}
      <div className="mb-8 text-center">
        <img
          src="/logo.png"
          alt="Table Rock Energy"
          className="w-[300px] mx-auto mb-4"
        />
        <p className="text-tre-tan text-sm">
          Energy Industry Data Processing Suite
        </p>
      </div>

      {/* Backend unreachable banner */}
      {!backendReachable && (
        <div className="mb-4 p-4 bg-yellow-900/30 border border-yellow-500/50 rounded-lg w-full max-w-md">
          <p className="text-yellow-300 text-sm font-medium">Cannot connect to backend</p>
          <p className="text-yellow-400 text-xs mt-1">Start the backend server to continue.</p>
        </div>
      )}

      {/* Login Card */}
      <div className="bg-tre-navy border border-tre-teal/30 rounded-lg shadow-2xl p-8 w-full max-w-md">
        <h2 className="text-2xl font-oswald font-semibold text-white text-center mb-6">
          {user && !isAuthorized ? 'Access Denied' : 'Sign In'}
        </h2>

        {/* Show error if user is not authorized */}
        {authError && (
          <div className="mb-6 p-4 bg-red-900/30 border border-red-500/50 rounded-lg">
            <p className="text-red-300 text-sm">{authError}</p>
            {user?.email && (
              <p className="text-red-400 text-xs mt-2">
                Signed in as: {user.email}
              </p>
            )}
          </div>
        )}

        {user && !isAuthorized ? (
          <button
            onClick={signOut}
            className="w-full flex items-center justify-center gap-3 bg-tre-brown-dark border border-tre-tan/30 rounded-lg px-4 py-3 text-tre-tan font-medium hover:bg-tre-brown-medium transition-colors"
          >
            Sign Out & Try Different Account
          </button>
        ) : (
          <>
            {/* Email/Password Form */}
            <form onSubmit={handleEmailLogin} className="space-y-4">
              <div>
                <label htmlFor="email" className="block text-tre-tan text-sm mb-1">
                  Email
                </label>
                <input
                  type="email"
                  id="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full bg-white border border-tre-teal/30 rounded-lg px-4 py-3 text-gray-900 placeholder-gray-400 focus:outline-none focus:border-tre-teal focus:ring-1 focus:ring-tre-teal transition-colors"
                  placeholder="you@tablerocktx.com"
                  required
                />
              </div>
              <div>
                <label htmlFor="password" className="block text-tre-tan text-sm mb-1">
                  Password
                </label>
                <input
                  type="password"
                  id="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full bg-white border border-tre-teal/30 rounded-lg px-4 py-3 text-gray-900 placeholder-gray-400 focus:outline-none focus:border-tre-teal focus:ring-1 focus:ring-tre-teal transition-colors"
                  placeholder="Enter your password"
                  required
                />
              </div>

              {emailError && (
                <p className="text-red-400 text-sm">{emailError}</p>
              )}

              <button
                type="submit"
                disabled={isSubmitting}
                className="w-full bg-tre-teal text-tre-navy font-semibold rounded-lg px-4 py-3 hover:bg-tre-teal/90 transition-colors disabled:opacity-50"
              >
                {isSubmitting ? 'Signing in...' : 'Sign In'}
              </button>
            </form>
          </>
        )}

        <p className="text-center text-gray-500 text-sm mt-6">
          {user && !isAuthorized
            ? 'Contact james@tablerocktx.com for access'
            : 'Sign in with your Table Rock Energy account'}
        </p>
      </div>

      {/* Footer */}
      <p className="text-gray-600 text-xs mt-8">
        &copy; {new Date().getFullYear()} Table Rock Energy
      </p>
    </div>
  );
}
