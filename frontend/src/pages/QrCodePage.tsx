import { useState } from "react";
import { apiRequest } from "../lib/api";
import { JsonViewer } from "../components/JsonViewer";

export function QrCodePage() {
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<number | null>(null);
  const [data, setData] = useState<any>(null);

  const [merchantName, setMerchantName] = useState("My Shop");
  const [refNo, setRefNo] = useState("INV-001");
  const [amount, setAmount] = useState("1");
  const [trxCode, setTrxCode] = useState("BG");
  const [cpi, setCpi] = useState("");
  const [size, setSize] = useState("300");

  async function generate() {
    setLoading(true);
    setStatus(null);
    setData(null);

    try {
      const payload: any = {
        MerchantName: merchantName.trim(),
        RefNo: refNo.trim(),
        Amount: Number(amount || "0") || 0,
        TrxCode: trxCode.trim(),
      };
      if (cpi.trim()) payload.CPI = cpi.trim();
      if (size.trim()) payload.Size = size.trim();

      const result = await apiRequest("/api/v1/qr/generate", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      setStatus(result.status);
      setData(result.data);
    } finally {
      setLoading(false);
    }
  }

  const qrBase64 =
    typeof data?.QRCode === "string" && data.QRCode ? data.QRCode : "";

  return (
    <section className='page'>
      <h1 className='page__title'>QR Code</h1>
      <p className='page__desc'>
        Calls <code>/api/v1/qr/generate</code> (protected).
      </p>

      <div className='form'>
        <label className='label'>
          Merchant Name
          <input
            className='input'
            value={merchantName}
            onChange={(e) => setMerchantName(e.target.value)}
          />
        </label>

        <label className='label'>
          Ref No
          <input
            className='input'
            value={refNo}
            onChange={(e) => setRefNo(e.target.value)}
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
          Trx Code
          <input
            className='input'
            value={trxCode}
            onChange={(e) => setTrxCode(e.target.value)}
            placeholder='BG'
          />
        </label>

        <label className='label'>
          CPI (optional)
          <input
            className='input'
            value={cpi}
            onChange={(e) => setCpi(e.target.value)}
          />
        </label>

        <label className='label'>
          Size (optional)
          <input
            className='input'
            value={size}
            onChange={(e) => setSize(e.target.value)}
            placeholder='300'
          />
        </label>

        <div className='actions'>
          <button
            className='button'
            type='button'
            onClick={generate}
            disabled={loading}
          >
            {loading ? "Generating…" : "Generate QR"}
          </button>
          {status !== null ? (
            <span className='badge'>HTTP {status}</span>
          ) : null}
        </div>
      </div>

      {qrBase64 ? (
        <section className='panel' aria-label='QR Result'>
          <div className='panel__row'>
            <div className='panel__title'>QR Preview</div>
            <div className='panel__hint'>Returned as base64</div>
          </div>
          <div className='panel__row'>
            <img
              alt='QR code'
              src={`data:image/png;base64,${qrBase64}`}
              style={{ maxWidth: 320, width: "100%" }}
            />
          </div>
        </section>
      ) : null}

      <JsonViewer value={data} />
    </section>
  );
}
