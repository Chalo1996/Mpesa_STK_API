type JsonViewerProps = {
  value: unknown
}

export function JsonViewer({ value }: JsonViewerProps) {
  if (value === undefined) return null

  return (
    <pre className="json">
      {typeof value === 'string' ? value : JSON.stringify(value, null, 2)}
    </pre>
  )
}
