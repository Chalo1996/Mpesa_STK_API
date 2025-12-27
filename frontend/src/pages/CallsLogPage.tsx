import { useEffect, useMemo, useState } from "react";
import { apiRequest } from "../lib/api";

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

export function CallsLogPage() {
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [rows, setRows] = useState<Row[]>([]);

  async function load() {
    setLoading(true);
    setStatus(null);
    setError("");

    try {
      const result = await apiRequest("/api/v1/admin/logs/calls", {
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

  useEffect(() => {
    load();
  }, []);

  const columns = useMemo(() => {
    const keys = new Set<string>();
    for (const row of rows) Object.keys(row).forEach((k) => keys.add(k));
    return Array.from(keys);
  }, [rows]);

  return (
    <section className='page'>
      <h1 className='page__title'>Call Logs</h1>
      <p className='page__desc'>
        Calls <code>/api/v1/admin/logs/calls</code> (protected).
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

      <div className='table-wrap'>
        <table className='table'>
          <thead>
            <tr>
              {columns.map((c) => (
                <th key={c}>{c}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td colSpan={Math.max(columns.length, 1)} className='muted'>
                  No call logs
                </td>
              </tr>
            ) : (
              rows.map((row, idx) => (
                <tr key={idx}>
                  {columns.map((c) => (
                    <td key={c}>{normalize(row[c])}</td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
