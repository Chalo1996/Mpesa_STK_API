import { useState } from "react";
import { apiRequest } from "../lib/api";
import { JsonViewer } from "../components/JsonViewer";

export function RatibaPage() {
  const defaultCallbackUrl =
    typeof window !== "undefined"
      ? `${window.location.origin}/api/v1/ratiba/callback`
      : "/api/v1/ratiba/callback";

  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<number | null>(null);
  const [data, setData] = useState<any>(null);
  const [lookupId, setLookupId] = useState("");

  const [standingOrderName, setStandingOrderName] = useState(
    "Test Standing Order"
  );
  const [startDate, setStartDate] = useState("20240905");
  const [endDate, setEndDate] = useState("20250905");
  const [businessShortCode, setBusinessShortCode] = useState("174379");
  const [transactionType, setTransactionType] = useState(
    "Standing Order Customer Pay Bill"
  );
  const [receiverPartyIdentifierType, setReceiverPartyIdentifierType] =
    useState("4");
  const [amount, setAmount] = useState("4500");
  const [partyA, setPartyA] = useState("254708374149");
  const [callBackURL, setCallBackURL] = useState(defaultCallbackUrl);
  const [accountReference, setAccountReference] = useState("Test-001");
  const [transactionDesc, setTransactionDesc] = useState("Test");
  const [frequency, setFrequency] = useState("2");

  async function createStandingOrder() {
    setLoading(true);
    setStatus(null);
    setData(null);

    try {
      const payload = {
        StandingOrderName: standingOrderName.trim(),
        StartDate: startDate.trim(),
        EndDate: endDate.trim(),
        BusinessShortCode: businessShortCode.trim(),
        TransactionType: transactionType.trim(),
        ReceiverPartyIdentifierType: receiverPartyIdentifierType.trim(),
        Amount: amount.trim(),
        PartyA: partyA.trim(),
        CallBackURL: callBackURL.trim(),
        AccountReference: accountReference.trim(),
        TransactionDesc: transactionDesc.trim(),
        Frequency: frequency.trim(),
      };

      const result = await apiRequest("/api/v1/ratiba/create", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      setStatus(result.status);
      setData(result.data);
    } finally {
      setLoading(false);
    }
  }

  async function loadHistory() {
    setLoading(true);
    setStatus(null);
    setData(null);

    try {
      const result = await apiRequest("/api/v1/ratiba/history", {
        method: "GET",
      });
      setStatus(result.status);
      setData(result.data);
    } finally {
      setLoading(false);
    }
  }

  async function fetchById() {
    const trimmedId = lookupId.trim();
    if (!trimmedId) {
      setStatus(400);
      setData({ error: "Please enter an order id." });
      return;
    }

    setLoading(true);
    setStatus(null);
    setData(null);

    try {
      const result = await apiRequest(`/api/v1/ratiba/${trimmedId}`, {
        method: "GET",
      });
      setStatus(result.status);
      setData(result.data);
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className='page'>
      <h1 className='page__title'>Ratiba</h1>
      <p className='page__desc'>
        Calls <code>/api/v1/ratiba/create</code> (protected).
      </p>

      <div className='form'>
        <label className='label'>
          Standing Order Name
          <input
            className='input'
            value={standingOrderName}
            onChange={(e) => setStandingOrderName(e.target.value)}
          />
        </label>

        <label className='label'>
          Start Date (YYYYMMDD)
          <input
            className='input'
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            placeholder='YYYYMMDD'
          />
        </label>

        <label className='label'>
          End Date (YYYYMMDD)
          <input
            className='input'
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
            placeholder='YYYYMMDD'
          />
        </label>

        <label className='label'>
          Business Short Code
          <input
            className='input'
            value={businessShortCode}
            onChange={(e) => setBusinessShortCode(e.target.value)}
            inputMode='numeric'
          />
        </label>

        <label className='label'>
          Transaction Type
          <input
            className='input'
            value={transactionType}
            onChange={(e) => setTransactionType(e.target.value)}
          />
        </label>

        <label className='label'>
          Receiver Party Identifier Type
          <input
            className='input'
            value={receiverPartyIdentifierType}
            onChange={(e) => setReceiverPartyIdentifierType(e.target.value)}
            inputMode='numeric'
          />
        </label>

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
          PartyA (MSISDN)
          <input
            className='input'
            value={partyA}
            onChange={(e) => setPartyA(e.target.value)}
            inputMode='numeric'
          />
        </label>

        <label className='label'>
          CallBack URL
          <input
            className='input'
            value={callBackURL}
            onChange={(e) => setCallBackURL(e.target.value)}
          />
        </label>

        <label className='label'>
          Account Reference
          <input
            className='input'
            value={accountReference}
            onChange={(e) => setAccountReference(e.target.value)}
          />
        </label>

        <label className='label'>
          Transaction Description
          <input
            className='input'
            value={transactionDesc}
            onChange={(e) => setTransactionDesc(e.target.value)}
          />
        </label>

        <label className='label'>
          Frequency
          <input
            className='input'
            value={frequency}
            onChange={(e) => setFrequency(e.target.value)}
            inputMode='numeric'
          />
        </label>

        <div className='actions'>
          <button
            className='button'
            type='button'
            onClick={createStandingOrder}
            disabled={loading}
          >
            {loading ? "Submitting…" : "Create Standing Order"}
          </button>
          <button
            className='button'
            type='button'
            onClick={loadHistory}
            disabled={loading}
          >
            {loading ? "Loading…" : "Load History"}
          </button>
          {status !== null ? (
            <span className='badge'>HTTP {status}</span>
          ) : null}
        </div>

        <label className='label'>
          Fetch by Order ID
          <div className='actions'>
            <input
              className='input'
              value={lookupId}
              onChange={(e) => setLookupId(e.target.value)}
              placeholder='e.g. 9d3d4a50-3d2c-4c7f-a3c2-9b7f8f0e1234'
            />
            <button
              className='button'
              type='button'
              onClick={fetchById}
              disabled={loading}
            >
              {loading ? "Loading…" : "Fetch"}
            </button>
          </div>
        </label>
      </div>

      <JsonViewer value={data} />
    </section>
  );
}
