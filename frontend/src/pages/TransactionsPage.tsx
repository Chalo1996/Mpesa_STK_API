import { useCallback, useEffect, useMemo, useState } from "react";
import { apiRequest } from "../lib/api";
import { JsonViewer } from "../components/JsonViewer";

type TransactionRecord = Record<string, unknown>;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function getErrorString(data: unknown): string {
  if (!isRecord(data)) return "";
  const err = data["error"];
  return typeof err === "string" ? err : "";
}

function normalize(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean")
    return String(value);
  return JSON.stringify(value);
}

export function TransactionsPage() {
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<number | null>(null);
  const [error, setError] = useState<string>("");
  const [mode, setMode] = useState<"all" | "completed">("all");
  const [transactions, setTransactions] = useState<TransactionRecord[]>([]);

  const [txnStatusLoading, setTxnStatusLoading] = useState(false);
  const [txnStatusId, setTxnStatusId] = useState("");
  const [txnStatusShortcode, setTxnStatusShortcode] = useState("");
  const [txnStatusHttp, setTxnStatusHttp] = useState<number | null>(null);
  const [txnStatusResp, setTxnStatusResp] = useState<unknown>(null);

  const [aggLoading, setAggLoading] = useState(false);
  const [aggHttp, setAggHttp] = useState<number | null>(null);
  const [aggResp, setAggResp] = useState<unknown>(null);

  const fetchTransactions = useCallback(
    async (selectedMode: "all" | "completed") => {
      setLoading(true);
      setStatus(null);
      setError("");

      try {
        const path =
          selectedMode === "completed"
            ? "/api/v1/c2b/transactions/completed"
            : "/api/v1/c2b/transactions/all";
        const result = await apiRequest(path, { method: "GET" });
        setStatus(result.status);

        if (result.status >= 200 && result.status < 300) {
          const tx = isRecord(result.data)
            ? result.data["transactions"]
            : undefined;
          const list = Array.isArray(tx) ? (tx as TransactionRecord[]) : [];
          setTransactions(list);
        } else {
          setTransactions([]);
          const apiError = getErrorString(result.data);

          if (result.status === 401 && apiError === "Missing API key") {
            setError(
              "Please sign in with a staff account to view transactions."
            );
          } else if (
            result.status === 401 &&
            apiError === "Authentication required"
          ) {
            setError(
              "Please sign in with a staff account to view transactions."
            );
          } else if (
            result.status === 403 &&
            apiError === "Staff access required"
          ) {
            setError(
              "Staff access required. Please sign in with a staff account."
            );
          } else {
            setError(
              typeof result.data === "object"
                ? JSON.stringify(result.data)
                : String(result.data || "Request failed")
            );
          }
        }
      } finally {
        setLoading(false);
      }
    },
    []
  );

  useEffect(() => {
    void fetchTransactions(mode);
  }, [mode, fetchTransactions]);

  useEffect(() => {
    const handler = () => {
      void fetchTransactions(mode);
    };
    window.addEventListener("mpesa-auth-changed", handler);
    return () => window.removeEventListener("mpesa-auth-changed", handler);
  }, [mode, fetchTransactions]);

  function parseMode(value: string): "all" | "completed" {
    return value === "completed" ? "completed" : "all";
  }

  const columns = useMemo(() => {
    const keys = new Set<string>();
    for (const row of transactions) {
      Object.keys(row).forEach((k) => keys.add(k));
    }
    return Array.from(keys);
  }, [transactions]);

  async function submitTxnStatusQuery() {
    const txid = txnStatusId.trim();
    if (!txid) {
      setTxnStatusHttp(400);
      setTxnStatusResp({ error: "transaction_id is required" });
      return;
    }

    setTxnStatusLoading(true);
    setTxnStatusHttp(null);
    setTxnStatusResp(null);

    try {
      const body: Record<string, unknown> = {
        transaction_id: txid,
      };
      const sc = txnStatusShortcode.trim();
      if (sc) body["shortcode"] = sc;

      const result = await apiRequest("/api/v1/c2b/transaction-status/query", {
        method: "POST",
        body: JSON.stringify(body),
      });
      setTxnStatusHttp(result.status);
      setTxnStatusResp(result.data);
    } finally {
      setTxnStatusLoading(false);
    }
  }

  async function fetchAggregates() {
    setAggLoading(true);
    setAggHttp(null);
    setAggResp(null);

    try {
      const result = await apiRequest("/api/v1/c2b/transactions/aggregate", {
        method: "GET",
      });
      setAggHttp(result.status);
      setAggResp(result.data);
    } finally {
      setAggLoading(false);
    }
  }

  return (
    <section className='page'>
      <h1 className='page__title'>Transactions</h1>
      <p className='page__desc'>
        Calls <code>/api/v1/c2b/transactions/all</code> or{" "}
        <code>/api/v1/c2b/transactions/completed</code> (protected).
      </p>

      <div className='actions'>
        <select
          className='select'
          value={mode}
          onChange={(e) => setMode(parseMode(e.target.value))}
        >
          <option value='all'>All</option>
          <option value='completed'>Completed</option>
        </select>
        <button
          className='button'
          type='button'
          onClick={() => fetchTransactions(mode)}
          disabled={loading}
        >
          {loading ? "Refreshing…" : "Refresh"}
        </button>
        {status !== null ? <span className='badge'>HTTP {status}</span> : null}
      </div>

      <section className='panel' aria-label='Transaction status'>
        <div className='panel__row'>
          <div className='panel__title'>Transaction Status</div>
          <div className='panel__hint'>
            Calls <code>/api/v1/c2b/transaction-status/query</code>
          </div>
        </div>
        <div className='panel__row' style={{ display: "block" }}>
          <label className='label'>
            transaction_id / mpesa_receipt_number
            <input
              className='input'
              value={txnStatusId}
              onChange={(e) => setTxnStatusId(e.target.value)}
              placeholder='e.g. QH12ABCDEF'
            />
          </label>
          <label className='label'>
            shortcode (optional)
            <input
              className='input'
              value={txnStatusShortcode}
              onChange={(e) => setTxnStatusShortcode(e.target.value)}
              placeholder='Leave blank to use onboarding defaults'
            />
          </label>
          <div className='actions'>
            <button
              className='button'
              type='button'
              onClick={submitTxnStatusQuery}
              disabled={txnStatusLoading}
            >
              {txnStatusLoading ? "Working…" : "Transaction Status"}
            </button>
            {txnStatusHttp !== null ? (
              <span className='badge'>HTTP {txnStatusHttp}</span>
            ) : null}
          </div>
        </div>
        <JsonViewer value={txnStatusResp} />
      </section>

      <section className='panel' aria-label='Transaction aggregates'>
        <div className='panel__row'>
          <div className='panel__title'>Aggregates</div>
          <div className='panel__hint'>
            Calls <code>/api/v1/c2b/transactions/aggregate</code>
          </div>
        </div>
        <div className='panel__row' style={{ display: "block" }}>
          <div className='actions'>
            <button
              className='button'
              type='button'
              onClick={fetchAggregates}
              disabled={aggLoading}
            >
              {aggLoading ? "Working…" : "Aggregate"}
            </button>
            {aggHttp !== null ? (
              <span className='badge'>HTTP {aggHttp}</span>
            ) : null}
          </div>
        </div>
        <JsonViewer value={aggResp} />
      </section>

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
            {transactions.length === 0 ? (
              <tr>
                <td colSpan={Math.max(columns.length, 1)} className='muted'>
                  No transactions
                </td>
              </tr>
            ) : (
              transactions.map((row, idx) => (
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
