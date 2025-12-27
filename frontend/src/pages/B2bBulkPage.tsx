import { useEffect, useState } from "react";
import { apiRequest } from "../lib/api";
import { JsonViewer } from "../components/JsonViewer";

type BatchSummary = {
  id: string;
  reference?: string;
  status?: string;
  items_count?: number;
  created_at?: string;
};

function safeJsonParse(text: string): unknown {
  if (!text.trim()) return null;
  return JSON.parse(text);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

export function B2bBulkPage() {
  const [reference, setReference] = useState("B2B-001");
  const [itemsText, setItemsText] = useState(
    JSON.stringify(
      [
        { recipient: "ACCT-001", amount: "1" },
        { recipient: "ACCT-002", amount: "2.50" },
      ],
      null,
      2
    )
  );

  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<number | null>(null);
  const [error, setError] = useState<string>("");
  const [data, setData] = useState<unknown>(null);

  const [batches, setBatches] = useState<BatchSummary[]>([]);
  const [selectedBatchId, setSelectedBatchId] = useState<string>("");
  const [detail, setDetail] = useState<unknown>(null);

  async function refreshList() {
    const res = await apiRequest("/api/v1/b2b/bulk/list?limit=50", {
      method: "GET",
    });
    if (res.status >= 200 && res.status < 300) {
      const results =
        isRecord(res.data) && Array.isArray(res.data["results"])
          ? (res.data["results"] as unknown[])
          : [];
      setBatches(results as BatchSummary[]);
    }
  }

  async function fetchDetail(batchId: string) {
    if (!batchId.trim()) return;
    const res = await apiRequest(`/api/v1/b2b/bulk/${batchId.trim()}`, {
      method: "GET",
    });
    setDetail(res.data);
  }

  useEffect(() => {
    void refreshList();
  }, []);

  useEffect(() => {
    const handler = () => {
      void refreshList();
    };
    window.addEventListener("mpesa-auth-changed", handler);
    return () => window.removeEventListener("mpesa-auth-changed", handler);
  }, []);

  async function submit() {
    setLoading(true);
    setStatus(null);
    setError("");
    setData(null);

    try {
      let parsed: unknown = null;
      try {
        parsed = safeJsonParse(itemsText);
      } catch (e: unknown) {
        const message = e instanceof Error ? e.message : String(e);
        setError(`Invalid JSON: ${message}`);
        return;
      }

      if (!Array.isArray(parsed) || parsed.length === 0) {
        setError("Items must be a non-empty JSON array.");
        return;
      }

      const items = parsed as unknown[];

      const payload = {
        reference: reference.trim(),
        items,
      };

      const res = await apiRequest("/api/v1/b2b/bulk", {
        method: "POST",
        body: JSON.stringify(payload),
      });

      setStatus(res.status);
      setData(res.data);

      if (res.status >= 200 && res.status < 300) {
        const batchObj = isRecord(res.data) ? res.data["batch"] : undefined;
        const batchId =
          isRecord(batchObj) && typeof batchObj["id"] === "string"
            ? (batchObj["id"] as string)
            : "";
        if (batchId) {
          setSelectedBatchId(batchId);
          await fetchDetail(batchId);
        }
        await refreshList();
      } else {
        const apiError =
          isRecord(res.data) && typeof res.data["error"] === "string"
            ? (res.data["error"] as string)
            : "";
        if (res.status === 401 && apiError === "Missing API key") {
          setError(
            "Please sign in with a staff account to create B2B batches."
          );
        } else {
          setError(
            typeof res.data === "object"
              ? JSON.stringify(res.data)
              : String(res.data || "Request failed")
          );
        }
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className='page'>
      <h1 className='page__title'>B2B Bulk</h1>
      <p className='page__desc'>
        Calls <code>/api/v1/b2b/bulk</code> (protected).
      </p>

      <div className='form'>
        <label className='label'>
          Batch reference (optional)
          <input
            className='input'
            value={reference}
            onChange={(e) => setReference(e.target.value)}
          />
        </label>

        <label className='label'>
          Items (JSON array)
          <textarea
            className='input'
            style={{ minHeight: 160 }}
            value={itemsText}
            onChange={(e) => setItemsText(e.target.value)}
          />
        </label>

        <div className='actions'>
          <button
            className='button'
            type='button'
            onClick={submit}
            disabled={loading}
          >
            {loading ? "Submitting…" : "Create batch"}
          </button>
          <button
            className='button'
            type='button'
            onClick={refreshList}
            disabled={loading}
          >
            Refresh list
          </button>
          {status !== null ? (
            <span className='badge'>HTTP {status}</span>
          ) : null}
        </div>
      </div>

      {error ? <div className='error'>{error}</div> : null}

      <JsonViewer value={data} />

      <h2 className='page__title' style={{ fontSize: 18 }}>
        Recent batches
      </h2>
      <div className='actions'>
        <input
          className='input'
          placeholder='Paste batch id to view…'
          value={selectedBatchId}
          onChange={(e) => setSelectedBatchId(e.target.value)}
        />
        <button
          className='button'
          type='button'
          onClick={() => fetchDetail(selectedBatchId)}
          disabled={!selectedBatchId.trim()}
        >
          View batch
        </button>
      </div>

      {batches.length === 0 ? (
        <div className='muted'>No batches</div>
      ) : (
        <div className='table-wrap'>
          <table className='table'>
            <thead>
              <tr>
                <th>id</th>
                <th>reference</th>
                <th>status</th>
                <th>items</th>
                <th>created_at</th>
              </tr>
            </thead>
            <tbody>
              {batches.map((b) => (
                <tr key={b.id}>
                  <td>
                    <button
                      className='button'
                      type='button'
                      onClick={() => {
                        setSelectedBatchId(b.id);
                        void fetchDetail(b.id);
                      }}
                    >
                      {b.id}
                    </button>
                  </td>
                  <td>{String(b.reference || "")}</td>
                  <td>{String(b.status || "")}</td>
                  <td>{String(b.items_count ?? "")}</td>
                  <td>{String(b.created_at || "")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <h2 className='page__title' style={{ fontSize: 18 }}>
        Batch detail
      </h2>
      <JsonViewer value={detail} />
    </section>
  );
}
