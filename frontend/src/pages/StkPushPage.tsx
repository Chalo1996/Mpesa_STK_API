import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { apiRequest, extractStatusMessage } from "../lib/api";
import { JsonViewer } from "../components/JsonViewer";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function getStringField(obj: unknown, key: string): string {
  if (!isRecord(obj)) return "";
  const value = obj[key];
  if (typeof value === "string") return value;
  if (value === null || value === undefined) return "";
  return String(value);
}

export function StkPushPage() {
  const navigate = useNavigate();

  const [amount, setAmount] = useState("1");
  const [phoneNumber, setPhoneNumber] = useState("");
  const [partyA, setPartyA] = useState("");

  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<number | null>(null);
  const [data, setData] = useState<unknown>(null);
  const [notice, setNotice] = useState<string>("");
  const [waitingForCallback, setWaitingForCallback] = useState(false);
  const pollTimerRef = useRef<number | null>(null);

  function clearPoll() {
    if (pollTimerRef.current !== null) {
      window.clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
  }

  useEffect(() => {
    return () => {
      clearPoll();
    };
  }, []);

  async function pollForTransaction(
    ids: { merchantRequestId?: string; checkoutRequestId?: string },
    timeoutMs = 60_000
  ) {
    setWaitingForCallback(true);
    const startedAt = Date.now();

    clearPoll();

    const tick = async () => {
      if (Date.now() - startedAt > timeoutMs) {
        clearPoll();
        setWaitingForCallback(false);
        return;
      }

      const res = await apiRequest(`/api/v1/transactions/all`, {
        method: "GET",
      });

      if (!(res.status >= 200 && res.status < 300)) {
        // If we can't read transactions (not logged in / not authorized), stop polling.
        clearPoll();
        setWaitingForCallback(false);
        return;
      }

      const tx = isRecord(res.data) ? res.data["transactions"] : undefined;
      const rows: unknown[] = Array.isArray(tx) ? (tx as unknown[]) : [];

      const merchantRequestId = (ids.merchantRequestId || "").trim();
      const checkoutRequestId = (ids.checkoutRequestId || "").trim();
      const matched = rows.find((r) => {
        const rowMerchantRequestId = getStringField(r, "merchant_request_id");
        const rowCheckoutRequestId = getStringField(r, "checkout_request_id");
        if (merchantRequestId && rowMerchantRequestId === merchantRequestId)
          return true;
        if (checkoutRequestId && rowCheckoutRequestId === checkoutRequestId)
          return true;
        return false;
      });

      if (matched) {
        clearPoll();
        setWaitingForCallback(false);
        navigate("/transactions");
      }
    };

    // Run once immediately, then every 2s.
    await tick();
    pollTimerRef.current = window.setInterval(() => {
      void tick();
    }, 2000);
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setStatus(null);
    setData(null);
    setNotice("");
    setWaitingForCallback(false);
    clearPoll();

    const payload: Record<string, unknown> = {
      amount: Number(amount || "0") || 1,
      phone_number: phoneNumber.trim(),
    };
    if (partyA.trim()) payload.party_a = partyA.trim();

    try {
      const result = await apiRequest("/api/v1/c2b/stk/push", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      setStatus(result.status);
      setData(result.data);
      setNotice(extractStatusMessage(result.data));

      // If this looks like a successful STK push initiation, poll transactions
      // until the callback has been persisted, then redirect to Transactions.
      const merchantRequestId = isRecord(result.data)
        ? result.data["MerchantRequestID"] ?? result.data["merchant_request_id"]
        : undefined;
      const checkoutRequestId = isRecord(result.data)
        ? result.data["CheckoutRequestID"] ?? result.data["checkout_request_id"]
        : undefined;
      if (
        result.status >= 200 &&
        result.status < 300 &&
        ((typeof merchantRequestId === "string" && merchantRequestId) ||
          (typeof checkoutRequestId === "string" && checkoutRequestId))
      ) {
        await pollForTransaction({
          merchantRequestId:
            typeof merchantRequestId === "string"
              ? merchantRequestId
              : undefined,
          checkoutRequestId:
            typeof checkoutRequestId === "string"
              ? checkoutRequestId
              : undefined,
        });
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className='page'>
      <h1 className='page__title'>STK Push</h1>
      <p className='page__desc'>
        Calls <code>/api/v1/c2b/stk/push</code> (protected).
      </p>

      <form className='form' onSubmit={submit}>
        <label className='label'>
          Amount
          <input
            className='input'
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            inputMode='numeric'
          />
        </label>

        <label className='label'>
          Phone number (2547…)
          <input
            className='input'
            value={phoneNumber}
            onChange={(e) => setPhoneNumber(e.target.value)}
          />
        </label>

        <label className='label'>
          Party A (optional)
          <input
            className='input'
            value={partyA}
            onChange={(e) => setPartyA(e.target.value)}
          />
        </label>

        <div className='actions'>
          <button
            className='button'
            type='submit'
            disabled={loading || waitingForCallback || !phoneNumber.trim()}
          >
            {loading
              ? "Sending…"
              : waitingForCallback
              ? "Waiting for callback…"
              : "Initiate STK Push"}
          </button>
          {status !== null ? (
            <span className='badge'>HTTP {status}</span>
          ) : null}
        </div>
      </form>

      {notice ? <div className='notice'>{notice}</div> : null}

      <JsonViewer value={data} />
    </section>
  );
}
