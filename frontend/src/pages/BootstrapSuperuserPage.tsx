import { useState } from "react";
import { apiRequest } from "../lib/api";
import { JsonViewer } from "../components/JsonViewer";

export function BootstrapSuperuserPage() {
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<number | null>(null);
  const [data, setData] = useState<unknown>(null);

  const [bootstrapToken, setBootstrapToken] = useState("");
  const [username, setUsername] = useState("admin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");

  async function createSuperuser() {
    const token = bootstrapToken.trim();
    const u = username.trim();
    const e = email.trim();

    if (!token) {
      setStatus(400);
      setData({ error: "Bootstrap token is required." });
      return;
    }
    if (!u) {
      setStatus(400);
      setData({ error: "Username is required." });
      return;
    }
    if (!password) {
      setStatus(400);
      setData({ error: "Password is required." });
      return;
    }
    if (password !== confirmPassword) {
      setStatus(400);
      setData({ error: "Passwords do not match." });
      return;
    }

    setLoading(true);
    setStatus(null);
    setData(null);
    try {
      const result = await apiRequest("/api/v1/bootstrap/superuser", {
        method: "POST",
        headers: {
          "X-Bootstrap-Token": token,
        },
        body: JSON.stringify({
          username: u,
          email: e,
          password,
        }),
      });
      setStatus(result.status);
      setData(result.data);
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className='page'>
      <h1 className='page__title'>Bootstrap: Create Superuser</h1>
      <p className='page__desc'>
        Use this once to create the first admin account. This endpoint is
        disabled after a superuser exists.
      </p>
      <div className='muted'>
        Requires server env var{" "}
        <span className='mono'>BOOTSTRAP_SUPERUSER_TOKEN</span>
        and the same value entered below.
      </div>

      <section className='panel' aria-label='Bootstrap superuser form'>
        <div className='panel__title'>Create first superuser</div>

        <label className='label'>
          Bootstrap token
          <input
            className='input'
            value={bootstrapToken}
            onChange={(e) => setBootstrapToken(e.target.value)}
            placeholder='Paste BOOTSTRAP_SUPERUSER_TOKEN'
          />
        </label>

        <label className='label'>
          Username
          <input
            className='input'
            value={username}
            onChange={(e) => setUsername(e.target.value)}
          />
        </label>

        <label className='label'>
          Email (optional)
          <input
            className='input'
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </label>

        <label className='label'>
          Password
          <input
            className='input'
            type='password'
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </label>

        <label className='label'>
          Confirm password
          <input
            className='input'
            type='password'
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
          />
        </label>

        <div className='actions'>
          <button
            className='button'
            type='button'
            onClick={createSuperuser}
            disabled={loading}
          >
            {loading ? "Working…" : "Create superuser"}
          </button>
          {status !== null ? (
            <span className='badge'>HTTP {status}</span>
          ) : null}
        </div>

        <div className='muted'>
          After success, sign in via the staff login banner or use Django admin
          at
          <span className='mono'> /admin/</span>.
        </div>
      </section>

      {data ? (
        <section className='panel' aria-label='Last response'>
          <div className='panel__title'>Last response</div>
          <JsonViewer value={data} />
        </section>
      ) : null}
    </section>
  );
}
