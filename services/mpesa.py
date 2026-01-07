# services/mpesa.py
import time, math, base64, requests
from datetime import datetime
from requests.auth import HTTPBasicAuth
from config import Config
from models import MpesaTransaction, User, db


class MpesaService:
    def __init__(self):
        self.shortcode = Config.SAF_SHORTCODE
        self.consumer_key = Config.SAF_CONSUMER_KEY
        self.consumer_secret = Config.SAF_CONSUMER_SECRET
        self.passkey = Config.SAF_PASS_KEY
        self.stk_push_url = Config.SAF_STK_PUSH_API
        self.query_url = Config.SAF_STK_PUSH_QUERY_API
        self.token_url = Config.SAF_ACCESS_TOKEN_API
        self.callback_url = Config.CALLBACK_URL

        self.timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        self.password = self._generate_password()
        self.headers = self._get_headers()

    def _generate_password(self):
        raw = f"{self.shortcode}{self.passkey}{self.timestamp}"
        return base64.b64encode(raw.encode()).decode()

    def _get_headers(self):
        r = requests.get(
            self.token_url,
            auth=HTTPBasicAuth(self.consumer_key, self.consumer_secret),
            timeout=30
        )
        r.raise_for_status()
        token = r.json()["access_token"]
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

    def stk_push(self, phone, amount, reference, user_id=None):
        payload = {
            "BusinessShortCode": self.shortcode,
            "Password": self.password,
            "Timestamp": self.timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": math.ceil(amount),
            "PartyA": phone,
            "PartyB": self.shortcode,
            "PhoneNumber": phone,
            "CallBackURL": self.callback_url,
            "AccountReference": reference,
            "TransactionDesc": "Account top up",
        }

        r = requests.post(self.stk_push_url, json=payload, headers=self.headers)
        res_json = r.json()

        checkout_request_id = res_json.get("CheckoutRequestID")
        if checkout_request_id:
            txn = MpesaTransaction(
                user_id=user_id,
                phone=phone,
                amount=int(amount),
                checkout_request_id=checkout_request_id,
                status="PENDING"
            )
            db.session.add(txn)
            db.session.commit()

        return res_json

    def query_transaction(self, checkout_request_id):
        payload = {
            "BusinessShortCode": self.shortcode,
            "Password": self.password,
            "Timestamp": self.timestamp,
            "CheckoutRequestID": checkout_request_id
        }
        r = requests.post(self.query_url, json=payload, headers=self.headers, timeout=30)
        r.raise_for_status()
        return r.json()

    def update_pending_transactions(self):
        pending_txns = MpesaTransaction.query.filter_by(status="PENDING").all()
        for txn in pending_txns:
            try:
                response = self.query_transaction(txn.checkout_request_id)
                result_code = int(response.get("ResultCode", 1))

                if result_code == 0:
                    txn.status = "SUCCESS"
                    if txn.phone:
                        user = User.query.filter_by(phone=txn.phone).first()
                        if user:
                            print(f"Crediting {txn.amount} to user {user.phone}")
                            user.balance += int(txn.amount)
                else:
                    txn.status = "FAILED"

                db.session.commit()
            except Exception as e:
                print(f"Failed to update txn {txn.checkout_request_id}: {e}")
