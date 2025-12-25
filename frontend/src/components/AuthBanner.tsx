import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { apiRequest, ensureCsrfCookie } from "../lib/api";

type MeResponse = {
  authenticated: boolean;
  username?: string;
  is_staff?: boolean;
};

export function AuthBanner() {
  const [me, setMe] = useState<MeResponse>({ authenticated: false });
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");

  async function refreshMe() {
    const result = await apiRequest("/api/v1/auth/me", { method: "GET" });
    if (result.status >= 200 && result.status < 300) {
      setMe(result.data || { authenticated: false });
    } else {
      setMe({ authenticated: false });
    }
  }

  useEffect(() => {
    refreshMe();
  }, []);

  async function onLogin(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setMessage("");

    try {
      await ensureCsrfCookie();
      const result = await apiRequest("/api/v1/auth/login", {
        method: "POST",
        body: JSON.stringify({ username: username.trim(), password }),
      });

      if (result.status >= 200 && result.status < 300) {
        setPassword("");
        await refreshMe();
      } else {
        setMessage(
          typeof result.data === "object"
            ? JSON.stringify(result.data)
            : String(result.data || "Login failed")
        );
      }
    } finally {
      setLoading(false);
    }
  }

  async function onLogout() {
    setLoading(true);
    setMessage("");

    try {
      await ensureCsrfCookie();
      const result = await apiRequest("/api/v1/auth/logout", {
        method: "POST",
      });
      if (result.status >= 200 && result.status < 300) {
        await refreshMe();
      } else {
        setMessage(
          typeof result.data === "object"
            ? JSON.stringify(result.data)
            : String(result.data || "Logout failed")
        );
      }
    } finally {
      setLoading(false);
    }
  }

  if (me.authenticated) {
    return (
      <section className='panel' aria-label='Authentication'>
        <div className='panel__row'>
          <div className='panel__title'>Signed in</div>
          <div className='panel__hint'>
            {me.username} {me.is_staff ? "(staff)" : ""}
          </div>
          <button
            className='button'
            type='button'
            onClick={onLogout}
            disabled={loading}
          >
            Logout
          </button>
        </div>
        {message ? <div className='error'>{message}</div> : null}
      </section>
    );
  }

  return (
    <section className='panel' aria-label='Authentication'>
      <div className='panel__row'>
        <div className='panel__title'>Staff Login</div>
        <div className='panel__hint'>
          Use a Django admin/staff account (session cookie).
        </div>
      </div>

      <form className='panel__row' onSubmit={onLogin}>
        <input
          className='input'
          placeholder='Username'
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          autoComplete='username'
        />
        <input
          className='input'
          type='password'
          placeholder='Password'
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete='current-password'
        />
        <button
          className='button'
          type='submit'
          disabled={loading || !username.trim() || !password}
        >
          {loading ? "Signing in…" : "Login"}
        </button>
      </form>

      {message ? <div className='error'>{message}</div> : null}
    </section>
  );
}
