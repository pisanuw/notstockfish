import { useEffect, useRef, useState } from "react";
import type {
  AuthConfig,
  AuthSessionResponse,
  AuthUser,
  MagicLinkStartResponse,
} from "../services/api";

declare global {
  interface Window {
    google?: {
      accounts?: {
        id?: {
          initialize: (config: { client_id: string; callback: (response: { credential: string }) => void }) => void;
          renderButton: (element: HTMLElement, options: Record<string, unknown>) => void;
        };
      };
    };
  }
}

interface AuthPanelProps {
  config: AuthConfig | null;
  user: AuthUser | null;
  pending: boolean;
  onRequestMagicLink: (email: string, displayName?: string) => Promise<MagicLinkStartResponse>;
  onVerifyMagicLink: (token: string) => Promise<AuthSessionResponse>;
  onGoogleCredential: (token: string) => Promise<void>;
  onLogout: () => Promise<void>;
}

export default function AuthPanel({
  config,
  user,
  pending,
  onRequestMagicLink,
  onVerifyMagicLink,
  onGoogleCredential,
  onLogout,
}: AuthPanelProps) {
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [token, setToken] = useState("");
  const [magicResult, setMagicResult] = useState<MagicLinkStartResponse | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const googleButtonRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const googleClientId: string | null = typeof config?.google_client_id === "string"
      ? config.google_client_id
      : null;
    if (!config?.google_enabled || !googleClientId || user) {
      return;
    }

    let cancelled = false;

    function renderGoogleButton() {
      if (cancelled || !googleButtonRef.current || !window.google?.accounts?.id) {
        return;
      }
      googleButtonRef.current.innerHTML = "";
      window.google.accounts.id.initialize({
        client_id: googleClientId as string,
        callback: ({ credential }) => {
          void onGoogleCredential(credential).catch((error: unknown) => {
            setMessage(error instanceof Error ? error.message : String(error));
          });
        },
      });
      window.google.accounts.id.renderButton(googleButtonRef.current, {
        theme: "outline",
        size: "large",
        shape: "pill",
        text: "continue_with",
      });
    }

    if (window.google?.accounts?.id) {
      renderGoogleButton();
      return () => {
        cancelled = true;
      };
    }

    const script = document.createElement("script");
    script.src = "https://accounts.google.com/gsi/client";
    script.async = true;
    script.defer = true;
    script.onload = () => renderGoogleButton();
    document.body.appendChild(script);

    return () => {
      cancelled = true;
    };
  }, [config, onGoogleCredential, user]);

  async function handleRequestMagicLink() {
    setMessage(null);
    const result = await onRequestMagicLink(email, displayName || undefined);
    setMagicResult(result);
    setToken(result.magic_link_token);
    setMessage("Magic link created. Copy the URL or verify with the token below.");
  }

  async function handleVerifyMagicLink() {
    setMessage(null);
    await onVerifyMagicLink(token);
    setMagicResult(null);
    setToken("");
  }

  async function handleCopy(value: string) {
    try {
      await navigator.clipboard.writeText(value);
      setMessage("Copied to clipboard.");
    } catch {
      setMessage("Copy failed. Select and copy it manually.");
    }
  }

  return (
    <div className="panel">
      <h3>Account</h3>

      {user ? (
        <div className="stack-sm">
          <p className="engine-description">
            Signed in as <strong>{user.display_name}</strong>
          </p>
          <p className="engine-meta">
            {user.email} via {user.provider}
          </p>
          <button className="btn btn-secondary" onClick={() => void onLogout()}>
            Sign out
          </button>
        </div>
      ) : (
        <div className="stack-md">
          <div className="stack-sm">
            <label className="stack-xs">
              <span>Email</span>
              <input
                className="text-input"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
              />
            </label>
            <label className="stack-xs">
              <span>Display name</span>
              <input
                className="text-input"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                placeholder="Optional"
              />
            </label>
            <button className="btn btn-primary" onClick={() => void handleRequestMagicLink()} disabled={pending || !email.trim()}>
              Send magic link
            </button>
          </div>

          {magicResult && (
            <div className="tool-box stack-sm">
              <div className="inline-actions">
                <span className="muted">Magic link ready</span>
                <button className="btn btn-secondary" onClick={() => void handleCopy(magicResult.magic_link_url)}>
                  Copy URL
                </button>
              </div>
              <div className="path-preview">{magicResult.magic_link_url}</div>
            </div>
          )}

          <div className="stack-sm">
            <label className="stack-xs">
              <span>Magic token</span>
              <input
                className="text-input"
                value={token}
                onChange={(e) => setToken(e.target.value)}
                placeholder="Paste token from magic link"
              />
            </label>
            <button className="btn btn-secondary" onClick={() => void handleVerifyMagicLink()} disabled={pending || !token.trim()}>
              Verify token
            </button>
          </div>

          {config?.google_enabled && config.google_client_id ? (
            <div className="stack-sm">
              <p className="muted">Google sign-in</p>
              <div ref={googleButtonRef} />
            </div>
          ) : (
            <p className="muted">Google sign-in appears here when GOOGLE_CLIENT_ID is configured.</p>
          )}
        </div>
      )}

      {message && <p className="muted">{message}</p>}
    </div>
  );
}