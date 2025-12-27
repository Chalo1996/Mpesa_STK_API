import { useEffect, useState } from "react";
import { apiRequest } from "../lib/api";
import { JsonViewer } from "../components/JsonViewer";

type Row = Record<string, unknown>;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function normalize(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean")
    return String(value);
  return JSON.stringify(value);
}

export function B2cSingleLogPage() {
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<number | null>(null);
  const [error, setError] = useState("");

  const [rows, setRows] = useState<Row[]>([]);
  const [selectedId, setSelectedId] = useState<string>("");
  const [detail, setDetail] = useState<unknown>(null);

  async function load() {
    setLoading(true);
    setStatus(null);
    setError("");

    try {
      const result = await apiRequest("/api/v1/b2c/single/list?limit=50", {
        method: "GET",
      });
      setStatus(result.status);
      if (result.status >= 200 && result.status < 300) {
        const results =
          isRecord(result.data) && Array.isArray(result.data["results"])
            ? (result.data["results"] as unknown[])
            : [];
        setRows(results as Row[]);
      } else {
        setRows([]);
        setError(
          typeof result.data === "object"
            ? JSON.stringify(result.data)
            : String(result.data || "Request failed")
        );
      }
    } finally {
      setLoading(false);
    }
  }

  async function loadDetail(id: string) {
    const clean = id.trim();
    if (!clean) return;
    const result = await apiRequest(`/api/v1/b2c/single/${clean}`, {
      method: "GET",
    });
    if (result.status >= 200 && result.status < 300) {
      setDetail(result.data);
    } else {
      setDetail(result.data);
    }
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <section className='page'>
      <h1 className='page__title'>B2C Single Logs</h1>
      <p className='page__desc'>
        Calls <code>/api/v1/b2c/single/list</code> (staff-only).
      </p>

      <div className='actions'>
        <button
          className='button'
          type='button'
          onClick={load}
          disabled={loading}
        >
          {loading ? "Refreshing…" : "Refresh"}
        </button>
        {status !== null ? <span className='badge'>HTTP {status}</span> : null}
      </div>

      {error ? <div className='error'>{error}</div> : null}

      <h2 className='page__title' style={{ fontSize: 18 }}>
        Recent requests
      </h2>

      <div className='table-wrap'>
        <table className='table'>
          <thead>
            <tr>
              <th>id</th>
              <th>originator_conversation_id</th>
              <th>status</th>
              <th>result_code</th>
              <th>transaction_id</th>
              <th>created_at</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td colSpan={6} className='muted'>
                  No single requests
                </td>
              </tr>
            ) : (
              rows.map((row, idx) => (
                <tr key={idx}>
                  <td>
                    <button
                      className='button'
                      type='button'
                      onClick={() => {
                        const id = String(row["id"] || "");
                        setSelectedId(id);
                        void loadDetail(id);
                      }}
                    >
                      {normalize(row["id"])}
                    </button>
                  </td>
                  <td>{normalize(row["originator_conversation_id"])}</td>
                  <td>{normalize(row["status"])}</td>
                  <td>{normalize(row["result_code"])}</td>
                  <td>{normalize(row["transaction_id"])}</td>
                  <td>{normalize(row["created_at"])}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <h2 className='page__title' style={{ fontSize: 18 }}>
        Detail
      </h2>
      <div className='actions'>
        <input
          className='input'
          placeholder='Paste payment request id to view…'
          value={selectedId}
          onChange={(e) => setSelectedId(e.target.value)}
        />
        <button
          className='button'
          type='button'
          onClick={() => loadDetail(selectedId)}
          disabled={!selectedId.trim()}
        >
          View
        </button>
      </div>

      <JsonViewer value={detail} />
    </section>
  );
}
