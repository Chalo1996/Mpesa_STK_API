import { useCallback, useEffect, useState } from "react";
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

export function B2cBulkPage() {
  const [mode, setMode] = useState<"bulk" | "single">("bulk");
  const [businessId, setBusinessId] = useState("");

  const [singleRecipient, setSingleRecipient] = useState("254700000000");
  const [singleAmount, setSingleAmount] = useState("1");
  const [singleRemarks, setSingleRemarks] = useState("");
  const [singleOccasion, setSingleOccasion] = useState("");
  const [singleStatus, setSingleStatus] = useState<number | null>(null);
  const [singleError, setSingleError] = useState<string>("");
  const [singleData, setSingleData] = useState<unknown>(null);

  const [reference, setReference] = useState("B2C-001");
  const [itemsText, setItemsText] = useState(
    JSON.stringify(
      [
        { recipient: "254700000000", amount: "1" },
        { recipient: "254711111111", amount: "2.50" },
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

  const refreshList = useCallback(async () => {
    const res = await apiRequest("/api/v1/b2c/bulk/list?limit=50", {
      method: "GET",
    });
    if (res.status >= 200 && res.status < 300) {
      const results =
        isRecord(res.data) && Array.isArray(res.data["results"])
          ? (res.data["results"] as unknown[])
          : [];
      setBatches(results as BatchSummary[]);
    }
  }, []);

  const fetchDetail = useCallback(async (batchId: string) => {
    if (!batchId.trim()) return;
    const res = await apiRequest(`/api/v1/b2c/bulk/${batchId.trim()}`, {
      method: "GET",
    });
    setDetail(res.data);
  }, []);

  useEffect(() => {
    void refreshList();
  }, [refreshList]);

  useEffect(() => {
    const handler = () => {
      void refreshList();
    };
    window.addEventListener("mpesa-auth-changed", handler);
    return () => window.removeEventListener("mpesa-auth-changed", handler);
  }, [refreshList]);

  const submit = useCallback(async () => {
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

      const payload = {
        business_id: businessId.trim(),
        reference: reference.trim(),
        items: parsed as unknown[],
      };

      const res = await apiRequest("/api/v1/b2c/bulk", {
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
            "Please sign in with a staff account to create B2C batches."
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
  }, [businessId, fetchDetail, itemsText, reference, refreshList]);

  const submitSingle = useCallback(async () => {
    setSingleStatus(null);
    setSingleError("");
    setSingleData(null);

    const payload = {
      business_id: businessId.trim(),
      party_b: singleRecipient.trim(),
      amount: singleAmount.trim(),
      remarks: singleRemarks.trim(),
      occasion: singleOccasion.trim(),
    };

    const res = await apiRequest("/api/v1/b2c/single", {
      method: "POST",
      body: JSON.stringify(payload),
    });

    setSingleStatus(res.status);
    setSingleData(res.data);
    if (res.status < 200 || res.status >= 300) {
      const apiError =
        isRecord(res.data) && typeof res.data["error"] === "string"
          ? (res.data["error"] as string)
          : "";
      if (res.status === 401 && apiError === "Missing API key") {
        setSingleError("Please sign in with a staff account to submit B2C.");
      } else {
        setSingleError(
          typeof res.data === "object"
            ? JSON.stringify(res.data)
            : String(res.data || "Request failed")
        );
      }
    }
  }, [
    businessId,
    singleAmount,
    singleOccasion,
    singleRecipient,
    singleRemarks,
  ]);

  return (
    <section className='page'>
      <h1 className='page__title'>B2C</h1>
      <p className='page__desc'>Choose single or bulk transaction.</p>

      <div className='form'>
        <label className='label'>
          Transaction type
          <select
            className='input'
            value={mode}
            onChange={(e) =>
              setMode(e.target.value === "single" ? "single" : "bulk")
            }
          >
            <option value='bulk'>Bulk</option>
            <option value='single'>Single</option>
          </select>
        </label>

        <label className='label'>
          Business ID (required)
          <input
            className='input'
            value={businessId}
            onChange={(e) => setBusinessId(e.target.value)}
            placeholder='UUID…'
          />
        </label>
      </div>

      {mode === "single" ? (
        <>
          <h2 className='page__title' style={{ fontSize: 18 }}>
            Single payout
          </h2>
          <div className='form'>
            <label className='label'>
              Recipient (PartyB)
              <input
                className='input'
                value={singleRecipient}
                onChange={(e) => setSingleRecipient(e.target.value)}
              />
            </label>

            <label className='label'>
              Amount
              <input
                className='input'
                value={singleAmount}
                onChange={(e) => setSingleAmount(e.target.value)}
              />
            </label>

            <label className='label'>
              Remarks (optional)
              <input
                className='input'
                value={singleRemarks}
                onChange={(e) => setSingleRemarks(e.target.value)}
              />
            </label>

            <label className='label'>
              Occasion (optional)
              <input
                className='input'
                value={singleOccasion}
                onChange={(e) => setSingleOccasion(e.target.value)}
              />
            </label>

            <div className='actions'>
              <button
                className='button'
                type='button'
                onClick={() => void submitSingle()}
                disabled={!businessId.trim()}
              >
                Submit single
              </button>
              {singleStatus !== null ? (
                <span className='badge'>HTTP {singleStatus}</span>
              ) : null}
            </div>
          </div>

          {singleError ? <div className='error'>{singleError}</div> : null}
          <JsonViewer value={singleData} />
        </>
      ) : (
        <>
          <h2 className='page__title' style={{ fontSize: 18 }}>
            Bulk payouts
          </h2>

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
                onClick={() => void submit()}
                disabled={loading || !businessId.trim()}
              >
                {loading ? "Submitting…" : "Create batch"}
              </button>
              <button
                className='button'
                type='button'
                onClick={() => void refreshList()}
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
              onClick={() => void fetchDetail(selectedBatchId)}
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
        </>
      )}
    </section>
  );
}
