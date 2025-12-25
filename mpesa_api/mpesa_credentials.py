import requests
from requests.auth import HTTPBasicAuth
from datetime import datetime
import base64
from dotenv import load_dotenv
import os

load_dotenv()


class MpesaC2bCredential:
    """Handles Mpesa API credentials"""
    CONSUMER_KEY = os.getenv('CONSUMER_KEY')
    CONSUMER_SECRET = os.getenv('CONSUMER_SECRET')
    TOKEN_URL = os.getenv('TOKEN_URL')

    @staticmethod
    def get_access_token():
        """Fetches and returns the Mpesa access token"""
        if not MpesaC2bCredential.TOKEN_URL:
            return None
        if not MpesaC2bCredential.CONSUMER_KEY or not MpesaC2bCredential.CONSUMER_SECRET:
            return None
        response = requests.get(
            MpesaC2bCredential.TOKEN_URL,
            auth=HTTPBasicAuth(MpesaC2bCredential.CONSUMER_KEY, MpesaC2bCredential.CONSUMER_SECRET),
            timeout=30,
        )
        try:
            response_data = response.json()
        except Exception:
            return None
        return response_data.get('access_token')


class LipanaMpesaPassword:
    """Generates and encodes the Lipa Na Mpesa password"""
    BUSINESS_SHORT_CODE = os.getenv('BUSINESS_SHORTCODE')
    PASSKEY = os.getenv('LIPA_NA_MPESA_PASSKEY')

    @staticmethod
    def generate_password():
        """Generates Base64 encoded password"""
        lipa_time = datetime.now().strftime('%Y%m%d%H%M%S')
        if not LipanaMpesaPassword.BUSINESS_SHORT_CODE or not LipanaMpesaPassword.PASSKEY:
            raise ValueError("BUSINESS_SHORTCODE and LIPA_NA_MPESA_PASSKEY must be set")
        data_to_encode = LipanaMpesaPassword.BUSINESS_SHORT_CODE + LipanaMpesaPassword.PASSKEY + lipa_time
        encoded_password = base64.b64encode(data_to_encode.encode()).decode('utf-8')
        return encoded_password, lipa_time


if __name__ == "__main__":
    access_token = MpesaC2bCredential.get_access_token()
    password, timestamp = LipanaMpesaPassword.generate_password()

    print(f"Access Token: {access_token}")
    print(f"Generated Password: {password}")
    print(f"Timestamp: {timestamp}")
