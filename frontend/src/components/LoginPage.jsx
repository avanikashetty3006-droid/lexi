import { useState } from 'react';
import { GoogleLogin } from '@react-oauth/google';
import { useAuth } from '../state/auth';
import LexiLogo from './LexiLogo';

export default function LoginPage() {
  const { signIn, continueAsGuest } = useAuth();
  const [errorMsg, setErrorMsg] = useState('');

  const hasClientId = Boolean(import.meta.env.VITE_GOOGLE_CLIENT_ID);

  return (
    <div className="min-h-screen bg-ink text-silver flex items-center justify-center p-6">
      <div className="w-full max-w-md bg-panel border border-line rounded-2xl p-8 text-center space-y-6">
        <div className="flex flex-col items-center gap-3">
          <LexiLogo size={76} animated />
          <h1 className="text-2xl font-bold text-crisp">Lexi</h1>
          <p className="text-sm text-silver">Asks instead of guessing.</p>
        </div>

        {errorMsg && (
          <div
            role="alert"
            className="text-xs text-crisp bg-ink border border-[#F43F5E]/60 rounded-lg p-3"
          >
            {errorMsg}
          </div>
        )}

        <div className="flex flex-col items-center gap-4">
          {hasClientId ? (
            <GoogleLogin
              theme="filled_black"
              shape="pill"
              onSuccess={(res) => {
                try {
                  if (!res?.credential) {
                    throw new Error('No credential returned from Google.');
                  }
                  setErrorMsg('');
                  signIn(res.credential);
                } catch (err) {
                  setErrorMsg(err?.message || 'Sign-in failed. Please try again.');
                }
              }}
              onError={() => {
                setErrorMsg(
                  'Google sign-in was blocked or failed. Check popup permissions or authorized origin, or continue as guest.'
                );
              }}
            />
          ) : (
            <p className="text-xs text-slate">
              Google Sign-In is not configured (missing VITE_GOOGLE_CLIENT_ID).
            </p>
          )}

          <button
            type="button"
            onClick={continueAsGuest}
            className="text-sm text-silver hover:text-crisp underline underline-offset-4 focus:outline-none focus:ring-2 focus:ring-[#6C5CE7] rounded px-2 py-1"
          >
            Continue as guest
          </button>
        </div>
      </div>
    </div>
  );
}
