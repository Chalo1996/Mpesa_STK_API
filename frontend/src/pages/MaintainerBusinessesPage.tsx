import { useCallback, useEffect, useMemo, useState } from "react";
import { apiRequest } from "../lib/api";
import { JsonViewer } from "../components/JsonViewer";

type BusinessRow = {
  id: string;
  name: string;
  status: string;
  created_at?: string | null;
};

type ShortcodeRow = {
  id: number;
  shortcode: string;
  shortcode_type: string;
  is_active: boolean;
  default_account_reference_prefix: string;
  default_stk_callback_url: string;
};

type CredentialRow = {
  id: number;
  environment: string;
  is_active: boolean;
  consumer_key: string;
  consumer_secret: string;
  token_url: string;
};

export function MaintainerBusinessesPage() {
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<number | null>(null);
  const [data, setData] = useState<unknown>(null);

  const [businesses, setBusinesses] = useState<BusinessRow[]>([]);
  const [newBusinessName, setNewBusinessName] = useState("");

  const [selectedBusinessId, setSelectedBusinessId] = useState("");
  const selectedBusiness = useMemo(
    () => businesses.find((b) => b.id === selectedBusinessId) || null,
    [businesses, selectedBusinessId]
  );

  const defaultTokenUrl =
    "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials";

  const [environment, setEnvironment] = useState("sandbox");
  const [consumerKey, setConsumerKey] = useState("");
  const [consumerSecret, setConsumerSecret] = useState("");
  const [tokenUrl, setTokenUrl] = useState(defaultTokenUrl);

  const [shortcode, setShortcode] = useState("");
  const [shortcodeType, setShortcodeType] = useState("paybill");
  const [lipaPasskey, setLipaPasskey] = useState("");
  const [defaultAccountReferencePrefix, setDefaultAccountReferencePrefix] =
    useState("");
  const [defaultStkCallbackUrl, setDefaultStkCallbackUrl] = useState(
    typeof window !== "undefined"
      ? `${window.location.origin}/api/v1/c2b/stk/callback`
      : "/api/v1/c2b/stk/callback"
  );

  const [detailShortcodes, setDetailShortcodes] = useState<ShortcodeRow[]>([]);
  const [detailCredentials, setDetailCredentials] = useState<CredentialRow[]>(
    []
  );

  const loadBusinesses = useCallback(async () => {
    setLoading(true);
    setStatus(null);
    setData(null);
    try {
      const result = await apiRequest("/api/v1/maintainer/businesses", {
        method: "GET",
      });
      setStatus(result.status);
      setData(result.data);
      setBusinesses(
        Array.isArray(result.data?.results) ? result.data.results : []
      );

      const firstId = String((result.data?.results || [])[0]?.id || "");
      if (firstId) {
        setSelectedBusinessId((prev) => prev || firstId);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  const loadBusinessDetail = useCallback(async (businessId: string) => {
    if (!businessId) return;
    setLoading(true);
    setStatus(null);
    setData(null);
    try {
      const result = await apiRequest(
        `/api/v1/maintainer/businesses/${businessId}`,
        {
          method: "GET",
        }
      );
      setStatus(result.status);
      setData(result.data);
      setDetailShortcodes(
        Array.isArray(result.data?.shortcodes) ? result.data.shortcodes : []
      );
      setDetailCredentials(
        Array.isArray(result.data?.daraja_credentials)
          ? result.data.daraja_credentials
          : []
      );
    } finally {
      setLoading(false);
    }
  }, []);

  async function createBusiness() {
    const name = newBusinessName.trim();
    if (!name) {
      setStatus(400);
      setData({ error: "Business name is required." });
      return;
    }

    setLoading(true);
    setStatus(null);
    setData(null);
    try {
      const result = await apiRequest("/api/v1/maintainer/businesses", {
        method: "POST",
        body: JSON.stringify({ name }),
      });
      setStatus(result.status);
      setData(result.data);
      setNewBusinessName("");
      await loadBusinesses();
    } finally {
      setLoading(false);
    }
  }

  async function addDarajaCredential() {
    if (!selectedBusinessId) {
      setStatus(400);
      setData({ error: "Select a business first." });
      return;
    }

    const key = consumerKey.trim();
    const secret = consumerSecret.trim();
    if (!key || !secret) {
      setStatus(400);
      setData({ error: "consumer_key and consumer_secret are required." });
      return;
    }

    setLoading(true);
    setStatus(null);
    setData(null);
    try {
      const result = await apiRequest(
        `/api/v1/maintainer/businesses/${selectedBusinessId}/daraja-credentials`,
        {
          method: "POST",
          body: JSON.stringify({
            environment: environment.trim(),
            consumer_key: key,
            consumer_secret: secret,
            token_url: tokenUrl.trim(),
          }),
        }
      );
      setStatus(result.status);
      setData(result.data);
      setConsumerKey("");
      setConsumerSecret("");
      await loadBusinessDetail(selectedBusinessId);
    } finally {
      setLoading(false);
    }
  }

  async function addShortcode() {
    if (!selectedBusinessId) {
      setStatus(400);
      setData({ error: "Select a business first." });
      return;
    }

    const sc = shortcode.trim();
    if (!sc) {
      setStatus(400);
      setData({ error: "shortcode is required." });
      return;
    }

    setLoading(true);
    setStatus(null);
    setData(null);
    try {
      const result = await apiRequest(
        `/api/v1/maintainer/businesses/${selectedBusinessId}/shortcodes`,
        {
          method: "POST",
          body: JSON.stringify({
            shortcode: sc,
            shortcode_type: shortcodeType.trim(),
            lipa_passkey: lipaPasskey.trim(),
            default_account_reference_prefix:
              defaultAccountReferencePrefix.trim(),
            default_stk_callback_url: defaultStkCallbackUrl.trim(),
          }),
        }
      );
      setStatus(result.status);
      setData(result.data);
      setShortcode("");
      setLipaPasskey("");
      await loadBusinessDetail(selectedBusinessId);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadBusinesses();
  }, [loadBusinesses]);

  useEffect(() => {
    if (selectedBusinessId) loadBusinessDetail(selectedBusinessId);
  }, [selectedBusinessId, loadBusinessDetail]);

  return (
    <section className='page'>
      <h1 className='page__title'>Maintainer: Businesses</h1>
      <p className='page__desc'>
        Create businesses (tenants) and store per-business Daraja credentials +
        shortcodes.
      </p>
      <div className='muted'>
        This UI stores credentials/shortcodes per business, but it does not
        create Safaricom Daraja apps for you. Create credentials on Safaricom
        Daraja, then paste the Consumer Key/Secret and STK passkey here:{" "}
        <a
          href='https://developer.safaricom.co.ke/'
          target='_blank'
          rel='noreferrer'
        >
          https://developer.safaricom.co.ke/
        </a>
      </div>

      <section className='panel' aria-label='Create business'>
        <div className='panel__title'>Create business</div>
        <label className='label'>
          Business name
          <input
            className='input'
            value={newBusinessName}
            onChange={(e) => setNewBusinessName(e.target.value)}
            placeholder='e.g. Acme Shop'
          />
        </label>
        <div className='actions'>
          <button
            className='button'
            type='button'
            onClick={createBusiness}
            disabled={loading}
          >
            {loading ? "Working…" : "Create"}
          </button>
          <button
            className='button'
            type='button'
            onClick={loadBusinesses}
            disabled={loading}
          >
            {loading ? "Loading…" : "Refresh"}
          </button>
          {status !== null ? (
            <span className='badge'>HTTP {status}</span>
          ) : null}
        </div>
      </section>

      <section className='panel' aria-label='Business selection'>
        <div className='panel__title'>Select business</div>
        <label className='label'>
          Business
          <select
            className='input'
            value={selectedBusinessId}
            onChange={(e) => setSelectedBusinessId(e.target.value)}
          >
            <option value=''>Select…</option>
            {businesses.map((b) => (
              <option key={b.id} value={b.id}>
                {b.name} ({b.status})
              </option>
            ))}
          </select>
        </label>
        {selectedBusiness ? (
          <div className='muted'>Selected: {selectedBusiness.name}</div>
        ) : (
          <div className='muted'>No business selected.</div>
        )}
      </section>

      <section className='panel' aria-label='Daraja credentials'>
        <div className='panel__title'>Add Daraja credentials</div>
        <div className='muted'>
          Secrets are stored server-side; responses show masked values.
        </div>
        <div className='muted'>
          Tip: Sandbox token URL is usually{" "}
          <span className='mono'>
            https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials
          </span>
        </div>

        <label className='label'>
          Environment
          <select
            className='input'
            value={environment}
            onChange={(e) => setEnvironment(e.target.value)}
          >
            <option value='sandbox'>sandbox</option>
            <option value='production'>production</option>
          </select>
        </label>

        <label className='label'>
          Consumer key
          <input
            className='input'
            value={consumerKey}
            onChange={(e) => setConsumerKey(e.target.value)}
          />
        </label>

        <label className='label'>
          Consumer secret
          <input
            className='input'
            type='password'
            value={consumerSecret}
            onChange={(e) => setConsumerSecret(e.target.value)}
          />
        </label>

        <label className='label'>
          Token URL
          <input
            className='input'
            value={tokenUrl}
            onChange={(e) => setTokenUrl(e.target.value)}
          />
        </label>

        <div className='actions'>
          <button
            className='button'
            type='button'
            onClick={addDarajaCredential}
            disabled={loading}
          >
            {loading ? "Working…" : "Add credential"}
          </button>
        </div>

        {detailCredentials.length === 0 ? (
          <div className='muted'>No credentials yet.</div>
        ) : (
          <div className='table'>
            <div className='table__row table__row--head'>
              <div>ID</div>
              <div>Env</div>
              <div>Key</div>
              <div>Secret</div>
              <div>Token URL</div>
            </div>
            {detailCredentials.map((c) => (
              <div className='table__row' key={c.id}>
                <div>{c.id}</div>
                <div>{c.environment}</div>
                <div>{c.consumer_key}</div>
                <div>{c.consumer_secret}</div>
                <div className='mono'>{c.token_url}</div>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className='panel' aria-label='Shortcodes'>
        <div className='panel__title'>Add shortcode (PayBill/Till)</div>

        <label className='label'>
          Shortcode
          <input
            className='input'
            value={shortcode}
            onChange={(e) => setShortcode(e.target.value)}
          />
        </label>

        <label className='label'>
          Type
          <select
            className='input'
            value={shortcodeType}
            onChange={(e) => setShortcodeType(e.target.value)}
          >
            <option value='paybill'>paybill</option>
            <option value='till'>till</option>
          </select>
        </label>

        <label className='label'>
          Lipa passkey (STK)
          <input
            className='input'
            type='password'
            value={lipaPasskey}
            onChange={(e) => setLipaPasskey(e.target.value)}
            placeholder='Required for STK push'
          />
        </label>

        <label className='label'>
          Default account reference prefix
          <input
            className='input'
            value={defaultAccountReferencePrefix}
            onChange={(e) => setDefaultAccountReferencePrefix(e.target.value)}
            placeholder='e.g. ACME'
          />
        </label>

        <label className='label'>
          Default STK callback URL
          <input
            className='input'
            value={defaultStkCallbackUrl}
            onChange={(e) => setDefaultStkCallbackUrl(e.target.value)}
          />
        </label>

        <div className='actions'>
          <button
            className='button'
            type='button'
            onClick={addShortcode}
            disabled={loading}
          >
            {loading ? "Working…" : "Add shortcode"}
          </button>
        </div>

        {detailShortcodes.length === 0 ? (
          <div className='muted'>No shortcodes yet.</div>
        ) : (
          <div className='table'>
            <div className='table__row table__row--head'>
              <div>ID</div>
              <div>Shortcode</div>
              <div>Type</div>
              <div>Active</div>
              <div>Callback URL</div>
            </div>
            {detailShortcodes.map((s) => (
              <div className='table__row' key={s.id}>
                <div>{s.id}</div>
                <div>{s.shortcode}</div>
                <div>{s.shortcode_type}</div>
                <div>{String(s.is_active)}</div>
                <div className='mono'>{s.default_stk_callback_url}</div>
              </div>
            ))}
          </div>
        )}
      </section>

      {data ? (
        <section className='panel' aria-label='Last response'>
          <div className='panel__title'>Last response</div>
          <JsonViewer value={data} />
        </section>
      ) : null}
    </section>
  );
}
