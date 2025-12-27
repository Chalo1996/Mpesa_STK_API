import { useState } from "react";
import { apiRequest, extractStatusMessage } from "../lib/api";
import { JsonViewer } from "../components/JsonViewer";

export function RegisterC2BPage() {
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<number | null>(null);
  const [data, setData] = useState<unknown>(null);
  const [notice, setNotice] = useState<string>("");

  async function register() {
    setLoading(true);
    setStatus(null);
    setData(null);
    setNotice("");

    try {
      const result = await apiRequest("/api/v1/c2b/register", {
        method: "POST",
      });
      setStatus(result.status);
      setData(result.data);
      setNotice(extractStatusMessage(result.data));
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className='page'>
      <h1 className='page__title'>C2B Register URLs</h1>
      <p className='page__desc'>
        Calls <code>/api/v1/c2b/register</code> (protected).
      </p>

      <div className='actions'>
        <button
          className='button'
          type='button'
          onClick={register}
          disabled={loading}
        >
          {loading ? "Registering…" : "Register"}
        </button>
        {status !== null ? <span className='badge'>HTTP {status}</span> : null}
      </div>

      {notice ? <div className='notice'>{notice}</div> : null}

      <JsonViewer value={data} />
    </section>
  );
}
