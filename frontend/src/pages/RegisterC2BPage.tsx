import { useState } from 'react'
import { apiRequest } from '../lib/api'
import { JsonViewer } from '../components/JsonViewer'

export function RegisterC2BPage() {
  const [loading, setLoading] = useState(false)
  const [status, setStatus] = useState<number | null>(null)
  const [data, setData] = useState<any>(null)

  async function register() {
    setLoading(true)
    setStatus(null)
    setData(null)

    try {
      const result = await apiRequest('/api/v1/c2b/register', { method: 'POST' })
      setStatus(result.status)
      setData(result.data)
    } finally {
      setLoading(false)
    }
  }

  return (
    <section className="page">
      <h1 className="page__title">C2B Register URLs</h1>
      <p className="page__desc">Calls <code>/api/v1/c2b/register</code> (protected).</p>

      <div className="actions">
        <button className="button" type="button" onClick={register} disabled={loading}>
          {loading ? 'Registering…' : 'Register'}
        </button>
        {status !== null ? <span className="badge">HTTP {status}</span> : null}
      </div>

      <JsonViewer value={data} />
    </section>
  )
}
