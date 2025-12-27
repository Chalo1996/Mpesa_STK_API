import { useEffect, useState } from "react";
import { apiRequest, extractStatusMessage } from "../lib/api";
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
  const [mode, setMode] = useState<"bulk" | "single">("bulk");
  const [businessId, setBusinessId] = useState("");

  const [singlePrimaryShortCode, setSinglePrimaryShortCode] =
    useState("000001");
  const [singleReceiverShortCode, setSingleReceiverShortCode] =
    useState("000002");
  const [singleAmount, setSingleAmount] = useState("100");
  const [singlePaymentRef, setSinglePaymentRef] = useState("paymentRef");
  const [singlePartnerName, setSinglePartnerName] = useState("Vendor");
  const [singleCallbackUrl, setSingleCallbackUrl] = useState("");
  const [singleStatus, setSingleStatus] = useState<number | null>(null);
  const [singleError, setSingleError] = useState<string>("");
  const [singleData, setSingleData] = useState<unknown>(null);
  const [singleNotice, setSingleNotice] = useState<string>("");

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
  const [notice, setNotice] = useState<string>("");

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
    setNotice("");

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
        business_id: businessId.trim(),
        reference: reference.trim(),
        items,
      };

      const res = await apiRequest("/api/v1/b2b/bulk", {
        method: "POST",
        body: JSON.stringify(payload),
      });

      setStatus(res.status);
      setData(res.data);
      setNotice(extractStatusMessage(res.data));

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

  async function submitSingle() {
    setSingleStatus(null);
    setSingleError("");
    setSingleData(null);
    setSingleNotice("");

    const payload = {
      business_id: businessId.trim(),
      primary_short_code: singlePrimaryShortCode.trim(),
      receiver_short_code: singleReceiverShortCode.trim(),
      amount: singleAmount.trim(),
      payment_ref: singlePaymentRef.trim(),
      partner_name: singlePartnerName.trim(),
      callback_url: singleCallbackUrl.trim(),
    };

    const res = await apiRequest("/api/v1/b2b/single", {
      method: "POST",
      body: JSON.stringify(payload),
    });

    setSingleStatus(res.status);
    setSingleData(res.data);
    setSingleNotice(extractStatusMessage(res.data));
    if (res.status < 200 || res.status >= 300) {
      const apiError =
        isRecord(res.data) && typeof res.data["error"] === "string"
          ? (res.data["error"] as string)
          : "";
      if (res.status === 401 && apiError === "Missing API key") {
        setSingleError("Please sign in with a staff account to submit B2B.");
      } else {
        setSingleError(
          typeof res.data === "object"
            ? JSON.stringify(res.data)
            : String(res.data || "Request failed")
        );
      }
    }
  }

  return (
    <section className='page'>
      <h1 className='page__title'>B2B</h1>
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
            Single (USSD push)
          </h2>
          <div className='form'>
            <label className='label'>
              Primary Short Code
              <input
                className='input'
                value={singlePrimaryShortCode}
                onChange={(e) => setSinglePrimaryShortCode(e.target.value)}
              />
            </label>

            <label className='label'>
              Receiver Short Code
              <input
                className='input'
                value={singleReceiverShortCode}
                onChange={(e) => setSingleReceiverShortCode(e.target.value)}
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
              Payment Ref
              <input
                className='input'
                value={singlePaymentRef}
                onChange={(e) => setSinglePaymentRef(e.target.value)}
              />
            </label>

            <label className='label'>
              Partner Name
              <input
                className='input'
                value={singlePartnerName}
                onChange={(e) => setSinglePartnerName(e.target.value)}
              />
            </label>

            <label className='label'>
              Callback URL
              <input
                className='input'
                value={singleCallbackUrl}
                onChange={(e) => setSingleCallbackUrl(e.target.value)}
                placeholder='https://.../api/v1/b2b/callback/result'
              />
            </label>

            <div className='actions'>
              <button
                className='button'
                type='button'
                onClick={submitSingle}
                disabled={!businessId.trim()}
              >
                Send single
              </button>
              {singleStatus !== null ? (
                <span className='badge'>HTTP {singleStatus}</span>
              ) : null}
            </div>
          </div>

          {singleNotice ? <div className='notice'>{singleNotice}</div> : null}
          {singleError ? <div className='error'>{singleError}</div> : null}
          <JsonViewer value={singleData} />
        </>
      ) : (
        <>
          <h2 className='page__title' style={{ fontSize: 18 }}>
            Bulk
          </h2>
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
                disabled={loading || !businessId.trim()}
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

          {notice ? <div className='notice'>{notice}</div> : null}
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
        </>
      )}
    </section>
  );
}
