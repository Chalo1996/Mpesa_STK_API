import { useState } from "react";
import type { FormEvent } from "react";
import { apiRequest } from "../lib/api";
import { JsonViewer } from "../components/JsonViewer";

export function StkPushPage() {
  const [amount, setAmount] = useState("1");
  const [phoneNumber, setPhoneNumber] = useState("");
  const [partyA, setPartyA] = useState("");

  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<number | null>(null);
  const [data, setData] = useState<any>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setStatus(null);
    setData(null);

    const payload: any = {
      amount: Number(amount || "0") || 1,
      phone_number: phoneNumber.trim(),
    };
    if (partyA.trim()) payload.party_a = partyA.trim();

    try {
      const result = await apiRequest("/api/v1/online/lipa", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      setStatus(result.status);
      setData(result.data);
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className='page'>
      <h1 className='page__title'>STK Push</h1>
      <p className='page__desc'>
        Calls <code>/api/v1/online/lipa</code> (protected).
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
            disabled={loading || !phoneNumber.trim()}
          >
            {loading ? "Sending…" : "Initiate STK Push"}
          </button>
          {status !== null ? (
            <span className='badge'>HTTP {status}</span>
          ) : null}
        </div>
      </form>

      <JsonViewer value={data} />
    </section>
  );
}
