# services/mpesa.py
import time, math, base64, requests
from datetime import datetime
from requests.auth import HTTPBasicAuth
from config import Config
from models import MpesaTransaction, User, db


class MpesaService:

    KSH_TO_UGX_RATE = 30

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


    def _convert_ksh_to_ugx(self, ksh_amount):
        """Convert KSH to UGX"""
        ugx_amount = int(ksh_amount * self.KSH_TO_UGX_RATE)
        return ugx_amount
    
    def stk_push(self, phone, amount, reference, user_id=None):
        
        amount_ksh = math.ceil(amount / self.KSH_TO_UGX_RATE)

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
        
        print(f"\n{'='*60}")
        print(f"🔄 Processing {len(pending_txns)} pending transactions")
        print(f"{'='*60}\n")
        
        updated_count = 0
        
        for txn in pending_txns:
            try:
                print(f"📋 Transaction #{txn.id}")
                print(f"   User ID: {txn.user_id}")
                print(f"   Amount: {txn.amount:,} UGX")
                print(f"   Checkout: {txn.checkout_request_id}")
                
                # Query M-Pesa for transaction status
                response = self.query_transaction(txn.checkout_request_id)
                result_code = int(response.get("ResultCode", 1))
                result_desc = response.get("ResultDesc", "Unknown")
                
                print(f"   M-Pesa Response: {result_code} - {result_desc}")

                if result_code == 0:
                    # ✅ Transaction successful
                    print(f"   ✅ Payment SUCCESSFUL")
                    
                    # Get the user
                    user = User.query.get(txn.user_id)
                    
                    if user:
                        # Update user balance
                        old_balance = user.balance
                        user.balance += int(txn.amount)
                        new_balance = user.balance
                        
                        # Update transaction status
                        txn.status = "SUCCESS"
                        txn.updated_at = datetime.utcnow()
                        
                        # Commit to database
                        db.session.commit()
                        
                        print(f"   💰 CREDITED USER!")
                        print(f"      Phone: {user.phone}")
                        print(f"      Old Balance: {old_balance:,} UGX")
                        print(f"      Added: +{txn.amount:,} UGX")
                        print(f"      New Balance: {new_balance:,} UGX")
                        
                        updated_count += 1
                    else:
                        print(f"   ❌ ERROR: User ID {txn.user_id} not found!")
                        txn.status = "SUCCESS_NO_USER"
                        txn.updated_at = datetime.utcnow()
                        db.session.commit()
                        
                elif result_code == 1032:
                    # 🚫 User cancelled
                    print(f"   🚫 CANCELLED by user")
                    txn.status = "CANCELLED"
                    txn.updated_at = datetime.utcnow()
                    db.session.commit()
                    
                elif result_code == 1:
                    # ⏳ Still pending
                    print(f"   ⏳ Still PENDING")
                    
                else:
                    # ❌ Failed
                    print(f"   ❌ FAILED")
                    txn.status = "FAILED"
                    txn.updated_at = datetime.utcnow()
                    db.session.commit()
                
                print()  # Empty line between transactions
                
            except Exception as e:
                print(f"   💥 ERROR: {e}")
                import traceback
                traceback.print_exc()
                db.session.rollback()
                print()
        
        print(f"{'='*60}")
        print(f"✨ Complete! Updated {updated_count} transaction(s)")
        print(f"{'='*60}\n")
        
        return updated_count