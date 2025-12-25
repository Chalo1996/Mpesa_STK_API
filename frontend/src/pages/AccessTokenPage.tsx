import { useState } from 'react'
import { apiRequest } from '../lib/api'
import { JsonViewer } from '../components/JsonViewer'

export function AccessTokenPage() {
  const [loading, setLoading] = useState(false)
  const [status, setStatus] = useState<number | null>(null)
  const [data, setData] = useState<any>(null)

  async function fetchToken() {
    setLoading(true)
    setStatus(null)
    setData(null)

    try {
      const result = await apiRequest('/api/v1/access/token', { method: 'GET' })
      setStatus(result.status)
      setData(result.data)
    } finally {
      setLoading(false)
    }
  }

  return (
    <section className="page">
      <h1 className="page__title">Access Token</h1>
      <p className="page__desc">Calls <code>/api/v1/access/token</code> (protected).</p>

      <div className="actions">
        <button className="button" type="button" onClick={fetchToken} disabled={loading}>
          {loading ? 'Loading…' : 'Get Token'}
        </button>
        {status !== null ? <span className="badge">HTTP {status}</span> : null}
      </div>

      <JsonViewer value={data} />
    </section>
  )
}
