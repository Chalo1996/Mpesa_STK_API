import { useEffect, useState } from "react";
import { apiRequest } from "../lib/api";
import { JsonViewer } from "../components/JsonViewer";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function pickString(value: unknown): string {
  return typeof value === "string" ? value : "";
}

export function OnboardingPage() {
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<number | null>(null);
  const [data, setData] = useState<unknown>(null);

  const [businessName, setBusinessName] = useState("");
  const [businessType, setBusinessType] = useState("");

  const [shortcode, setShortcode] = useState("");
  const [shortcodeType, setShortcodeType] = useState<"paybill" | "till">(
    "paybill"
  );
  const [defaultAccountReferencePrefix, setDefaultAccountReferencePrefix] =
    useState("");
  const [defaultStkCallbackUrl, setDefaultStkCallbackUrl] = useState("");
  const [defaultRatibaCallbackUrl, setDefaultRatibaCallbackUrl] = useState("");
  const [lipaPasskey, setLipaPasskey] = useState("");

  const [txnStatusInitiatorName, setTxnStatusInitiatorName] = useState("");
  const [txnStatusSecurityCredential, setTxnStatusSecurityCredential] =
    useState("");
  const [txnStatusResultUrl, setTxnStatusResultUrl] = useState("");
  const [txnStatusTimeoutUrl, setTxnStatusTimeoutUrl] = useState("");
  const [txnStatusIdentifierType, setTxnStatusIdentifierType] = useState("4");

  const [environment, setEnvironment] = useState<"sandbox" | "production">(
    "sandbox"
  );
  const [consumerKey, setConsumerKey] = useState("");
  const [consumerSecret, setConsumerSecret] = useState("");
  const [tokenUrl, setTokenUrl] = useState("");

  async function loadCurrent() {
    setLoading(true);
    setStatus(null);
    setData(null);

    try {
      const result = await apiRequest("/api/v1/business/onboarding", {
        method: "GET",
      });
      setStatus(result.status);
      setData(result.data);

      if (
        result.status >= 200 &&
        result.status < 300 &&
        isRecord(result.data)
      ) {
        const business = isRecord(result.data["business"])
          ? (result.data["business"] as Record<string, unknown>)
          : null;
        const activeShortcode = isRecord(result.data["active_shortcode"])
          ? (result.data["active_shortcode"] as Record<string, unknown>)
          : null;
        const activeCred = isRecord(result.data["active_daraja_credential"])
          ? (result.data["active_daraja_credential"] as Record<string, unknown>)
          : null;

        setBusinessName(pickString(business?.["name"]).trim());
        setBusinessType(pickString(business?.["business_type"]).trim());

        setShortcode(pickString(activeShortcode?.["shortcode"]).trim());
        setShortcodeType(
          pickString(activeShortcode?.["shortcode_type"]) === "till"
            ? "till"
            : "paybill"
        );
        setDefaultAccountReferencePrefix(
          pickString(
            activeShortcode?.["default_account_reference_prefix"]
          ).trim()
        );
        setDefaultStkCallbackUrl(
          pickString(activeShortcode?.["default_stk_callback_url"]).trim()
        );
        setDefaultRatibaCallbackUrl(
          pickString(activeShortcode?.["default_ratiba_callback_url"]).trim()
        );

        setTxnStatusInitiatorName(
          pickString(activeShortcode?.["txn_status_initiator_name"]).trim()
        );
        setTxnStatusResultUrl(
          pickString(activeShortcode?.["txn_status_result_url"]).trim()
        );
        setTxnStatusTimeoutUrl(
          pickString(activeShortcode?.["txn_status_timeout_url"]).trim()
        );
        setTxnStatusIdentifierType(
          pickString(activeShortcode?.["txn_status_identifier_type"]).trim() ||
            "4"
        );

        setEnvironment(
          pickString(activeCred?.["environment"]) === "production"
            ? "production"
            : "sandbox"
        );
        setTokenUrl(pickString(activeCred?.["token_url"]).trim());

        // Never prefill secrets from server responses.
        setConsumerKey("");
        setConsumerSecret("");
        setLipaPasskey("");
        setTxnStatusSecurityCredential("");
      }
    } finally {
      setLoading(false);
    }
  }

  async function save() {
    const bt = businessType.trim();
    if (!bt) {
      setStatus(400);
      setData({ error: "business_type is required" });
      return;
    }

    setLoading(true);
    setStatus(null);
    setData(null);

    try {
      const body: Record<string, unknown> = {
        business_name: businessName.trim(),
        business_type: bt,
        shortcode: shortcode.trim(),
        shortcode_type: shortcodeType,
        default_account_reference_prefix: defaultAccountReferencePrefix.trim(),
        default_stk_callback_url: defaultStkCallbackUrl.trim(),
        default_ratiba_callback_url: defaultRatibaCallbackUrl.trim(),
        txn_status_initiator_name: txnStatusInitiatorName.trim(),
        txn_status_result_url: txnStatusResultUrl.trim(),
        txn_status_timeout_url: txnStatusTimeoutUrl.trim(),
        txn_status_identifier_type: txnStatusIdentifierType.trim(),
      };

      if (lipaPasskey.trim()) body["lipa_passkey"] = lipaPasskey.trim();

      if (txnStatusSecurityCredential.trim()) {
        body["txn_status_security_credential"] =
          txnStatusSecurityCredential.trim();
      }

      // Only send credential fields if user is updating them.
      const ck = consumerKey.trim();
      const cs = consumerSecret.trim();
      if (ck || cs) {
        body["environment"] = environment;
        body["consumer_key"] = ck;
        body["consumer_secret"] = cs;
        body["token_url"] = tokenUrl.trim();
      }

      const result = await apiRequest("/api/v1/business/onboarding", {
        method: "POST",
        body: JSON.stringify(body),
      });
      setStatus(result.status);
      setData(result.data);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadCurrent();
  }, []);

  return (
    <section className='page'>
      <h1 className='page__title'>Onboarding</h1>
      <p className='page__desc'>
        Persists business/shortcode defaults so you don’t have to pass them with
        every request.
      </p>

      <section className='panel' aria-label='Business'>
        <div className='panel__row'>
          <div className='panel__title'>Business</div>
          <div className='panel__hint'>Bound from your OAuth client</div>
        </div>
        <div className='panel__row' style={{ display: "block" }}>
          <label className='label'>
            Business name
            <input
              className='input'
              value={businessName}
              onChange={(e) => setBusinessName(e.target.value)}
              placeholder='e.g. My Shop'
            />
          </label>

          <label className='label'>
            Business type
            <input
              className='input'
              value={businessType}
              onChange={(e) => setBusinessType(e.target.value)}
              placeholder='e.g. retail'
            />
          </label>
        </div>
      </section>

      <section className='panel' aria-label='Shortcode defaults'>
        <div className='panel__row'>
          <div className='panel__title'>Shortcode</div>
          <div className='panel__hint'>Defaults used by STK/QR/Ratiba</div>
        </div>
        <div className='panel__row' style={{ display: "block" }}>
          <label className='label'>
            Shortcode
            <input
              className='input'
              value={shortcode}
              onChange={(e) => setShortcode(e.target.value)}
              placeholder='e.g. 174379'
            />
          </label>

          <label className='label'>
            Shortcode type
            <select
              className='select'
              value={shortcodeType}
              onChange={(e) =>
                setShortcodeType(e.target.value === "till" ? "till" : "paybill")
              }
            >
              <option value='paybill'>PayBill</option>
              <option value='till'>Till</option>
            </select>
          </label>

          <label className='label'>
            Default account reference prefix
            <input
              className='input'
              value={defaultAccountReferencePrefix}
              onChange={(e) => setDefaultAccountReferencePrefix(e.target.value)}
              placeholder='e.g. INV'
            />
          </label>

          <label className='label'>
            Default STK callback URL
            <input
              className='input'
              value={defaultStkCallbackUrl}
              onChange={(e) => setDefaultStkCallbackUrl(e.target.value)}
              placeholder='https://.../api/v1/c2b/stk/callback'
            />
          </label>

          <label className='label'>
            Default Ratiba callback URL
            <input
              className='input'
              value={defaultRatibaCallbackUrl}
              onChange={(e) => setDefaultRatibaCallbackUrl(e.target.value)}
              placeholder='https://.../api/v1/ratiba/callback'
            />
          </label>

          <label className='label'>
            Lipa Na Mpesa passkey (optional)
            <input
              className='input'
              type='password'
              autoComplete='off'
              value={lipaPasskey}
              onChange={(e) => setLipaPasskey(e.target.value)}
              placeholder='Only stored if provided'
            />
          </label>

          <label className='label'>
            Transaction Status initiator name
            <input
              className='input'
              value={txnStatusInitiatorName}
              onChange={(e) => setTxnStatusInitiatorName(e.target.value)}
              placeholder='Optional if set in server env'
            />
          </label>
          <label className='label'>
            Transaction Status security credential
            <input
              className='input'
              type='password'
              autoComplete='off'
              value={txnStatusSecurityCredential}
              onChange={(e) => setTxnStatusSecurityCredential(e.target.value)}
              placeholder='Only stored if provided'
            />
          </label>
          <label className='label'>
            Transaction Status Result URL
            <input
              className='input'
              value={txnStatusResultUrl}
              onChange={(e) => setTxnStatusResultUrl(e.target.value)}
              placeholder='https://.../api/v1/c2b/transaction-status/result'
            />
          </label>
          <label className='label'>
            Transaction Status Timeout URL
            <input
              className='input'
              value={txnStatusTimeoutUrl}
              onChange={(e) => setTxnStatusTimeoutUrl(e.target.value)}
              placeholder='https://.../api/v1/c2b/transaction-status/timeout'
            />
          </label>
          <label className='label'>
            Transaction Status identifier type
            <input
              className='input'
              value={txnStatusIdentifierType}
              onChange={(e) => setTxnStatusIdentifierType(e.target.value)}
              placeholder='Default 4'
            />
          </label>
        </div>
      </section>

      <section className='panel' aria-label='Daraja credentials'>
        <div className='panel__row'>
          <div className='panel__title'>Daraja Credentials</div>
          <div className='panel__hint'>Used for B2C/B2B access tokens</div>
        </div>
        <div className='panel__row' style={{ display: "block" }}>
          <label className='label'>
            Environment
            <select
              className='select'
              value={environment}
              onChange={(e) =>
                setEnvironment(
                  e.target.value === "production" ? "production" : "sandbox"
                )
              }
            >
              <option value='sandbox'>Sandbox</option>
              <option value='production'>Production</option>
            </select>
          </label>

          <label className='label'>
            Token URL (optional override)
            <input
              className='input'
              value={tokenUrl}
              onChange={(e) => setTokenUrl(e.target.value)}
              placeholder='Leave blank to use defaults'
            />
          </label>

          <label className='label'>
            Consumer Key
            <input
              className='input'
              value={consumerKey}
              onChange={(e) => setConsumerKey(e.target.value)}
              placeholder='Only sent if updating credentials'
            />
          </label>

          <label className='label'>
            Consumer Secret
            <input
              className='input'
              type='password'
              autoComplete='off'
              value={consumerSecret}
              onChange={(e) => setConsumerSecret(e.target.value)}
              placeholder='Only sent if updating credentials'
            />
          </label>
        </div>
      </section>

      <div className='actions'>
        <button
          className='button'
          type='button'
          onClick={loadCurrent}
          disabled={loading}
        >
          {loading ? "Loading…" : "Load Current"}
        </button>
        <button
          className='button'
          type='button'
          onClick={save}
          disabled={loading}
        >
          {loading ? "Saving…" : "Save"}
        </button>
        {status !== null ? <span className='badge'>HTTP {status}</span> : null}
      </div>

      <JsonViewer value={data} />
    </section>
  );
}
