from pyngrok import ngrok
import time
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Authenticate with ngrok
auth_token = os.getenv("NGROK_AUTHTOKEN")
if not auth_token:
    raise ValueError("NGROK_AUTHTOKEN is not set in .env file!")

ngrok.set_auth_token(auth_token)

# Establish connectivity
public_url = ngrok.connect(8000).public_url

# Output ngrok URL to console
print(f"Ngrok tunnel is running at: {public_url}")

# Keep the listener alive
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("Shutting down ngrok tunnel...")
    ngrok.kill()