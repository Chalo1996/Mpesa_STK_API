import { useEffect, useState } from "react";
import {
  apiRequest,
  clearStoredOAuthAccessToken,
  getStoredOAuthAccessToken,
  setStoredOAuthAccessToken,
} from "../lib/api";
import { JsonViewer } from "../components/JsonViewer";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

export function AccessTokenPage() {
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<number | null>(null);
  const [data, setData] = useState<unknown>(null);

  const [oauthToken, setOauthToken] = useState("");

  const [clientId, setClientId] = useState("");
  const [clientSecret, setClientSecret] = useState("");
  const [scope, setScope] = useState(
    "business:read business:write transactions:read c2b:write qr:write ratiba:write b2c:write b2b:write"
  );

  useEffect(() => {
    setOauthToken(getStoredOAuthAccessToken());
  }, []);

  async function fetchToken() {
    setLoading(true);
    setStatus(null);
    setData(null);

    try {
      const result = await apiRequest("/api/v1/access/token", {
        method: "GET",
      });
      setStatus(result.status);
      setData(result.data);
    } finally {
      setLoading(false);
    }
  }

  function saveOauthToken() {
    setStoredOAuthAccessToken(oauthToken);
    setStatus(200);
    setData({ ok: true, saved: true });
  }

  function clearOauthToken() {
    clearStoredOAuthAccessToken();
    setOauthToken("");
    setStatus(200);
    setData({ ok: true, cleared: true });
  }

  async function fetchOAuthToken() {
    const id = clientId.trim();
    const secret = clientSecret.trim();
    const requestedScope = scope.trim();

    if (!id || !secret) {
      setStatus(400);
      setData({ error: "client_id and client_secret are required" });
      return;
    }

    setLoading(true);
    setStatus(null);
    setData(null);

    try {
      const body = new URLSearchParams();
      body.set("grant_type", "client_credentials");
      body.set("client_id", id);
      body.set("client_secret", secret);
      if (requestedScope) body.set("scope", requestedScope);

      const result = await apiRequest("/api/v1/oauth/token/", {
        method: "POST",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
        },
        body: body.toString(),
      });

      setStatus(result.status);
      setData(result.data);

      const token =
        isRecord(result.data) && typeof result.data["access_token"] === "string"
          ? (result.data["access_token"] as string)
          : "";
      if (result.status >= 200 && result.status < 300 && token) {
        setOauthToken(token);
        setStoredOAuthAccessToken(token);
        setClientSecret("");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className='page'>
      <h1 className='page__title'>Access Token</h1>
      <p className='page__desc'>
        Calls <code>/api/v1/access/token</code> (protected).
      </p>

      <section className='panel' aria-label='OAuth2 access token'>
        <div className='panel__row'>
          <div className='panel__title'>OAuth2 Bearer Token</div>
          <div className='panel__hint'>Used for third-party gateway calls</div>
        </div>
        <div className='panel__row' style={{ display: "block" }}>
          <label className='label'>
            Access token
            <input
              className='input'
              value={oauthToken}
              onChange={(e) => setOauthToken(e.target.value)}
              placeholder='Paste access token from /api/v1/oauth/token/'
            />
          </label>
          <div className='actions'>
            <button
              className='button'
              type='button'
              onClick={saveOauthToken}
              disabled={loading}
            >
              Save
            </button>
            <button
              className='button'
              type='button'
              onClick={clearOauthToken}
              disabled={loading}
            >
              Clear
            </button>
          </div>
        </div>
      </section>

      <section className='panel' aria-label='Get OAuth2 token'>
        <div className='panel__row'>
          <div className='panel__title'>Get OAuth2 Token</div>
          <div className='panel__hint'>Calls /api/v1/oauth/token/</div>
        </div>
        <div className='panel__row' style={{ display: "block" }}>
          <label className='label'>
            client_id
            <input
              className='input'
              value={clientId}
              onChange={(e) => setClientId(e.target.value)}
              placeholder='Client ID'
            />
          </label>
          <label className='label'>
            client_secret
            <input
              className='input'
              type='password'
              autoComplete='off'
              value={clientSecret}
              onChange={(e) => setClientSecret(e.target.value)}
              placeholder='Client Secret'
            />
          </label>
          <label className='label'>
            scope (space-separated)
            <input
              className='input'
              value={scope}
              onChange={(e) => setScope(e.target.value)}
              placeholder='e.g. transactions:read c2b:write'
            />
          </label>

          <div className='actions'>
            <button
              className='button'
              type='button'
              onClick={fetchOAuthToken}
              disabled={loading}
            >
              {loading ? "Working…" : "Get OAuth Token"}
            </button>
          </div>
        </div>
      </section>

      <div className='actions'>
        <button
          className='button'
          type='button'
          onClick={fetchToken}
          disabled={loading}
        >
          {loading ? "Loading…" : "Get Token"}
        </button>
        {status !== null ? <span className='badge'>HTTP {status}</span> : null}
      </div>

      <JsonViewer value={data} />
    </section>
  );
}
