import os
import time

from dotenv import load_dotenv
from pyngrok import ngrok


def main() -> int:
    # Load environment variables from .env if present
    load_dotenv()

    # Optional auth token (recommended but not strictly required)
    auth_token = os.getenv("NGROK_AUTHTOKEN")
    if auth_token:
        ngrok.set_auth_token(auth_token)

    port = int(os.getenv("NGROK_PORT", "8000"))
    tunnel = ngrok.connect(addr=port)
    public_url = tunnel.public_url

    print(f"Ngrok tunnel is running at: {public_url}")
    print("Press Ctrl+C to stop.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        return 0
    finally:
        # Best-effort cleanup
        try:
            ngrok.disconnect(public_url)
        except Exception:
            pass
        try:
            ngrok.kill()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())