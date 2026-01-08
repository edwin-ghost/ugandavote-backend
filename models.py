from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import random
import string

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'user'
    
    id = db.Column(db.Integer, primary_key=True)
    phone = db.Column(db.String(20), unique=True, nullable=False)
    pin_hash = db.Column(db.String(255), nullable=False)
    balance = db.Column(db.Integer, default=0)
    bonus_balance = db.Column(db.Integer, default=2500)  # Non-withdrawable signup bonus
    referral_code = db.Column(db.String(10), unique=True, nullable=False)
    referred_by = db.Column(db.String(10), nullable=True)  # Code of referrer
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    total_wagered = db.Column(db.Integer, default=0)



    @property
    def withdrawable_amount(self):
        """User can only withdraw what they've wagered"""
        return min(self.balance, self.total_wagered)

    def generate_referral_code(self):
        """Generate unique 6-character referral code"""
        while True:
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            if not User.query.filter_by(referral_code=code).first():
                return code
            
    

class Bet(db.Model):
    __tablename__ = 'bet'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    stake = db.Column(db.Integer)
    total_odds = db.Column(db.Float)
    possible_win = db.Column(db.Integer)
    status = db.Column(db.String(20), default="pending")
    used_bonus = db.Column(db.Integer, default=0)  # Track bonus used in this bet
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class BetSelection(db.Model):
    __tablename__ = 'bet_selection'
    
    id = db.Column(db.Integer, primary_key=True)
    bet_id = db.Column(db.Integer, db.ForeignKey("bet.id"))
    candidate_name = db.Column(db.String(100))
    odds = db.Column(db.Float)

class Withdrawal(db.Model):
    __tablename__ = 'withdrawal'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    amount = db.Column(db.Integer)
    method = db.Column(db.String(20))  # MTN / Airtel
    status = db.Column(db.String(20), default="pending")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class MpesaTransaction(db.Model):
    __tablename__ = 'mpesa_transaction'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    phone = db.Column(db.String(20))
    amount = db.Column(db.Integer)
    checkout_request_id = db.Column(db.String(100))
    status = db.Column(db.String(50), default="PENDING")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ReferralReward(db.Model):
    """Track referral rewards"""
    __tablename__ = 'referral_reward'
    
    id = db.Column(db.Integer, primary_key=True)
    referrer_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    referred_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    reward_amount = db.Column(db.Integer, default=10000)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)