import { useEffect, useState } from "react";
import { apiRequest } from "../lib/api";
import { JsonViewer } from "../components/JsonViewer";

type ClientRow = {
  client_id: string;
  name: string;
  client_type: string;
  authorization_grant_type: string;
  created?: string | null;
};

export function MaintainerClientsPage() {
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<number | null>(null);
  const [data, setData] = useState<any>(null);

  const [clients, setClients] = useState<ClientRow[]>([]);
  const [newName, setNewName] = useState("");

  async function refresh() {
    setLoading(true);
    setStatus(null);

    try {
      const result = await apiRequest("/api/v1/maintainer/clients", {
        method: "GET",
      });
      setStatus(result.status);
      setData(result.data);
      setClients(
        Array.isArray(result.data?.results) ? result.data.results : []
      );
    } finally {
      setLoading(false);
    }
  }

  async function createClient() {
    const name = newName.trim();
    if (!name) {
      setStatus(400);
      setData({ error: "Please enter a client name." });
      return;
    }

    setLoading(true);
    setStatus(null);

    try {
      const result = await apiRequest("/api/v1/maintainer/clients", {
        method: "POST",
        body: JSON.stringify({ name }),
      });
      setStatus(result.status);
      setData(result.data);
      setNewName("");
      await refresh();
    } finally {
      setLoading(false);
    }
  }

  async function rotateSecret(clientId: string) {
    setLoading(true);
    setStatus(null);

    try {
      const result = await apiRequest(
        `/api/v1/maintainer/clients/${clientId}/rotate-secret`,
        {
          method: "POST",
        }
      );
      setStatus(result.status);
      setData(result.data);
      await refresh();
    } finally {
      setLoading(false);
    }
  }

  async function revokeClient(clientId: string) {
    setLoading(true);
    setStatus(null);

    try {
      const result = await apiRequest(
        `/api/v1/maintainer/clients/${clientId}/revoke`,
        {
          method: "POST",
        }
      );
      setStatus(result.status);
      setData(result.data);
      await refresh();
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <section className='page'>
      <h1 className='page__title'>Maintainer: OAuth Clients</h1>
      <p className='page__desc'>
        Manage third-party OAuth2 clients. Token endpoint:{" "}
        <code>/api/v1/oauth/token/</code>
      </p>

      <div className='form'>
        <label className='label'>
          New Client Name
          <input
            className='input'
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder='e.g. Acme Payments Ltd'
          />
        </label>

        <div className='actions'>
          <button
            className='button'
            type='button'
            onClick={createClient}
            disabled={loading}
          >
            {loading ? "Working…" : "Create Client"}
          </button>
          <button
            className='button'
            type='button'
            onClick={refresh}
            disabled={loading}
          >
            {loading ? "Loading…" : "Refresh"}
          </button>
          {status !== null ? (
            <span className='badge'>HTTP {status}</span>
          ) : null}
        </div>
      </div>

      <section className='panel' aria-label='Clients list'>
        <div className='panel__row'>
          <div className='panel__title'>Clients</div>
          <div className='panel__hint'>Superuser-only</div>
        </div>

        <div className='panel__row' style={{ display: "block" }}>
          {clients.length === 0 ? (
            <div className='muted'>No clients found.</div>
          ) : (
            <div style={{ display: "grid", gap: 10 }}>
              {clients.map((c) => (
                <div
                  key={c.client_id}
                  className='panel'
                  style={{ padding: 12 }}
                >
                  <div
                    className='panel__row'
                    style={{ justifyContent: "space-between" }}
                  >
                    <div>
                      <div style={{ fontWeight: 600 }}>{c.name}</div>
                      <div className='muted'>
                        <code>{c.client_id}</code>
                      </div>
                    </div>

                    <div className='actions'>
                      <button
                        className='button'
                        type='button'
                        onClick={() => rotateSecret(c.client_id)}
                        disabled={loading}
                      >
                        Rotate Secret
                      </button>
                      <button
                        className='button'
                        type='button'
                        onClick={() => revokeClient(c.client_id)}
                        disabled={loading}
                      >
                        Revoke
                      </button>
                    </div>
                  </div>

                  <div className='muted'>
                    grant: {c.authorization_grant_type} • type: {c.client_type}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>

      <JsonViewer value={data} />
    </section>
  );
}
