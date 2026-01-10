from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import random
import string

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    phone = db.Column(db.String(20), unique=True, nullable=False)
    pin_hash = db.Column(db.String(255), nullable=False)
    balance = db.Column(db.Integer, default=0)
    bonus_balance = db.Column(db.Integer, default=0)
    total_wagered = db.Column(db.Integer, default=0)
    referral_code = db.Column(db.String(10), unique=True)
    referred_by = db.Column(db.String(10), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # NEW: Add indexes for better query performance
    __table_args__ = (
        db.Index('idx_user_phone', 'phone'),
        db.Index('idx_user_referral_code', 'referral_code'),
        db.Index('idx_user_referred_by', 'referred_by'),
        db.Index('idx_user_created_at', 'created_at'),
    )
    
    def generate_referral_code(self):
        """Generate a unique 6-character referral code"""
        while True:
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            if not User.query.filter_by(referral_code=code).first():
                return code


class Bet(db.Model):
    __tablename__ = 'bets'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    stake = db.Column(db.Integer, nullable=False)
    total_odds = db.Column(db.Float, nullable=False)
    possible_win = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), default='pending')
    used_bonus = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # NEW: Relationship for efficient loading
    selections = db.relationship('BetSelection', backref='bet', lazy='select')
    
    # NEW: Add indexes
    __table_args__ = (
        db.Index('idx_bet_user_id', 'user_id'),
        db.Index('idx_bet_created_at', 'created_at'),
        db.Index('idx_bet_status', 'status'),
        db.Index('idx_bet_user_created', 'user_id', 'created_at'),  # Composite index
    )


class BetSelection(db.Model):
    __tablename__ = 'bet_selections'
    
    id = db.Column(db.Integer, primary_key=True)
    bet_id = db.Column(db.Integer, db.ForeignKey('bets.id'), nullable=False)
    candidate_name = db.Column(db.String(100), nullable=False)
    odds = db.Column(db.Float, nullable=False)
    
    # NEW: Add index
    __table_args__ = (
        db.Index('idx_bet_selection_bet_id', 'bet_id'),
    )


class Withdrawal(db.Model):
    __tablename__ = 'withdrawals'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    method = db.Column(db.String(50), default='MTN')
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # NEW: Add indexes
    __table_args__ = (
        db.Index('idx_withdrawal_user_id', 'user_id'),
        db.Index('idx_withdrawal_status', 'status'),
        db.Index('idx_withdrawal_created_at', 'created_at'),
        db.Index('idx_withdrawal_user_status', 'user_id', 'status'),  # Composite
    )


class MpesaTransaction(db.Model):
    __tablename__ = 'mpesa_transactions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    phone = db.Column(db.String(20), nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    checkout_request_id = db.Column(db.String(100), unique=True)
    status = db.Column(db.String(20), default='PENDING')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # NEW: Add indexes
    __table_args__ = (
        db.Index('idx_mpesa_user_id', 'user_id'),
        db.Index('idx_mpesa_checkout_request_id', 'checkout_request_id'),
        db.Index('idx_mpesa_status', 'status'),
        db.Index('idx_mpesa_phone', 'phone'),
        db.Index('idx_mpesa_created_at', 'created_at'),
        db.Index('idx_mpesa_user_status', 'user_id', 'status'),  # Composite
    )


class ReferralReward(db.Model):
    __tablename__ = 'referral_rewards'
    
    id = db.Column(db.Integer, primary_key=True)
    referrer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    referred_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    reward_amount = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # NEW: Add indexes
    __table_args__ = (
        db.Index('idx_referral_reward_referrer_id', 'referrer_id'),
        db.Index('idx_referral_reward_referred_id', 'referred_id'),
        db.Index('idx_referral_reward_created_at', 'created_at'),
    )


class Election(db.Model):
    __tablename__ = 'elections'
    
    id = db.Column(db.String(50), primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    constituency = db.Column(db.String(200))
    type = db.Column(db.String(50), default='presidential')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # NEW: Relationship for efficient loading
    candidates = db.relationship('Candidate', backref='election', lazy='select')
    
    # NEW: Add index
    __table_args__ = (
        db.Index('idx_election_type', 'type'),
    )


class Candidate(db.Model):
    __tablename__ = 'candidates'
    
    id = db.Column(db.Integer, primary_key=True)
    election_id = db.Column(db.String(50), db.ForeignKey('elections.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    party = db.Column(db.String(200))
    odds = db.Column(db.Float, default=1.0)
    image = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # NEW: Add index
    __table_args__ = (
        db.Index('idx_candidate_election_id', 'election_id'),
    )