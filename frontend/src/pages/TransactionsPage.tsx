import { useEffect, useMemo, useState } from 'react'
import { apiRequest } from '../lib/api'

type TransactionRecord = Record<string, unknown>

function normalize(value: unknown): string {
  if (value === null || value === undefined) return ''
  if (typeof value === 'string') return value
  if (typeof value === 'number' || typeof value === 'boolean') return String(value)
  return JSON.stringify(value)
}

export function TransactionsPage() {
  const [loading, setLoading] = useState(false)
  const [status, setStatus] = useState<number | null>(null)
  const [error, setError] = useState<string>('')
  const [mode, setMode] = useState<'all' | 'completed'>('all')
  const [transactions, setTransactions] = useState<TransactionRecord[]>([])

  async function fetchTransactions(selectedMode: 'all' | 'completed') {
    setLoading(true)
    setStatus(null)
    setError('')

    try {
      const path = selectedMode === 'completed' ? '/api/v1/transactions/completed' : '/api/v1/transactions/all'
      const result = await apiRequest(path, { method: 'GET' })
      setStatus(result.status)

      if (result.status >= 200 && result.status < 300) {
        const list = Array.isArray(result.data?.transactions) ? result.data.transactions : []
        setTransactions(list)
      } else {
        setTransactions([])
        setError(typeof result.data === 'object' ? JSON.stringify(result.data) : String(result.data || 'Request failed'))
      }
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchTransactions(mode)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode])

  const columns = useMemo(() => {
    const keys = new Set<string>()
    for (const row of transactions) {
      Object.keys(row).forEach((k) => keys.add(k))
    }
    return Array.from(keys)
  }, [transactions])

  return (
    <section className="page">
      <h1 className="page__title">Transactions</h1>
      <p className="page__desc">Calls <code>/api/v1/transactions/all</code> or <code>/api/v1/transactions/completed</code> (protected).</p>

      <div className="actions">
        <select className="select" value={mode} onChange={(e) => setMode(e.target.value as any)}>
          <option value="all">All</option>
          <option value="completed">Completed</option>
        </select>
        <button className="button" type="button" onClick={() => fetchTransactions(mode)} disabled={loading}>
          {loading ? 'Refreshing…' : 'Refresh'}
        </button>
        {status !== null ? <span className="badge">HTTP {status}</span> : null}
      </div>

      {error ? <div className="error">{error}</div> : null}

      <div className="table-wrap">
        <table className="table">
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
                <td colSpan={Math.max(columns.length, 1)} className="muted">
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
  )
}
