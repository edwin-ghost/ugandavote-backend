import os
from flask import Flask, request, jsonify, make_response
from flask_cors import CORS
from flask_compress import Compress  # NEW: pip install flask-compress
from flask_jwt_extended import (
    JWTManager, create_access_token,
    jwt_required, get_jwt_identity
)
from sqlalchemy import func
from werkzeug.security import generate_password_hash, check_password_hash
from config import Config
from models import Candidate, Election, db, User, Bet, BetSelection, Withdrawal, MpesaTransaction, ReferralReward
from utils.phone import normalize_phone
from functools import wraps
import hashlib
from datetime import datetime, timedelta
from threading import Thread
import time
import requests as req

app = Flask(__name__)
app.config.from_object(Config)

# NEW: Enable compression
compress = Compress()
compress.init_app(app)

# UPDATED: Optimized CORS
CORS(app, resources={
    r"/*": {
        "origins": ["https://ugandavote.today", "http://localhost:8081"],
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"],
        "max_age": 3600  # Cache preflight for 1 hour
    }
})

database_url = os.getenv("DATABASE_URL", "postgresql://uganda_postgres_user:oSwtZYjUmvGZU0sxnwEJ9oZklgaQrDHH@dpg-d5fc3p0gjchc73f2h2v0-a.oregon-postgres.render.com/uganda_postgres")
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    
db.init_app(app)
jwt = JWTManager(app)


# ===============================
# NEW: CACHING SYSTEM
# ===============================
cache_store = {}

def cache_response(duration=300):
    """Cache GET responses for specified duration (seconds)"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Only cache GET requests
            if request.method != 'GET':
                return f(*args, **kwargs)
            
            # Create cache key from URL, args, and auth header
            auth_header = request.headers.get('Authorization', '')
            cache_key = hashlib.md5(
                f"{request.url}{str(args)}{str(kwargs)}{auth_header}".encode()
            ).hexdigest()
            
            # Check cache
            if cache_key in cache_store:
                cached_data, expiry = cache_store[cache_key]
                if datetime.now() < expiry:
                    response = make_response(jsonify(cached_data))
                    response.headers['X-Cache'] = 'HIT'
                    return response
            
            # Execute function
            result = f(*args, **kwargs)
            
            # Cache successful responses
            if isinstance(result, tuple):
                data, status = result
                if status == 200:
                    if hasattr(data, 'get_json'):
                        cache_store[cache_key] = (data.get_json(), datetime.now() + timedelta(seconds=duration))
            else:
                if hasattr(result, 'get_json'):
                    cache_store[cache_key] = (result.get_json(), datetime.now() + timedelta(seconds=duration))
            
            return result
        return decorated_function
    return decorator


# ===============================
# NEW: KEEP ALIVE FOR RENDER
# ===============================
def keep_alive():
    """Ping self every 10 minutes to prevent Render free tier sleep"""
    base_url = os.getenv("BASE_URL", "https://ugandavote-backend.onrender.com")
    while True:
        try:
            time.sleep(600)  # 10 minutes
            req.get(f"{base_url}/health", timeout=5)
        except:
            pass

@app.get("/health")
def health():
    return jsonify({"status": "ok", "timestamp": datetime.now().isoformat()})

# Start keep-alive only in production
if os.getenv("FLASK_ENV") == "production" or os.getenv("RENDER"):
    Thread(target=keep_alive, daemon=True).start()


# ---------------- AUTH ----------------
@app.post("/api/auth/register")
def register():
    data = request.json

    try:
        phone = normalize_phone(data["phone"])
    except Exception:
        return jsonify({"error": "Invalid phone number"}), 400

    referral_code = data.get("referralCode", "").strip().upper()

    if User.query.filter_by(phone=phone).first():
        return jsonify({"error": "User exists"}), 400

    user = User(
        phone=phone,
        pin_hash=generate_password_hash(data["pin"]),
        balance=0,
        bonus_balance=2500,
        total_wagered=0
    )

    user.referral_code = user.generate_referral_code()

    if referral_code:
        referrer = User.query.filter_by(referral_code=referral_code).first()
        if referrer:
            user.referred_by = referral_code
            referrer.balance += 10000
            
            reward = ReferralReward(
                referrer_id=referrer.id,
                referred_id=user.id,
                reward_amount=10000
            )
            db.session.add(reward)

    db.session.add(user)
    db.session.commit()

    token = create_access_token(identity=str(user.id))

    return jsonify({
        "token": token,
        "user": {
            "id": user.id,
            "phone": user.phone,
            "balance": user.balance,
            "bonus_balance": user.bonus_balance,
            "referral_code": user.referral_code,
            "total_wagered": user.total_wagered
        }
    }), 201


@app.post("/api/auth/login")
def login():
    data = request.json

    try:
        phone = normalize_phone(data["phone"])
    except Exception:
        return jsonify({"error": "Invalid phone number"}), 400

    user = User.query.filter_by(phone=phone).first()

    if not user or not check_password_hash(user.pin_hash, data["pin"]):
        return jsonify({"error": "Invalid login"}), 401

    token = create_access_token(identity=str(user.id))

    return jsonify({
        "token": token,
        "user": {
            "id": user.id,
            "phone": user.phone,
            "balance": user.balance,
            "bonus_balance": user.bonus_balance,
            "referral_code": user.referral_code,
            "total_wagered": user.total_wagered
        }
    })


# ---------------- BALANCE (OPTIMIZED) ----------------
@app.get("/api/balance")
@jwt_required()
@cache_response(duration=30)  # Cache for 30 seconds
def balance():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({"error": "User not found"}), 404

    # Optimized query using exists
    has_mpesa_txn = db.session.query(
        db.exists().where(
            db.and_(
                MpesaTransaction.user_id == user.id,
                MpesaTransaction.status == "SUCCESS"
            )
        )
    ).scalar()

    DISPLAY_RATE = 30 if has_mpesa_txn else 1
    withdrawable = min(user.balance, user.total_wagered)
    
    return jsonify({
        "balance": user.balance * DISPLAY_RATE,
        "base_balance": user.balance,
        "bonus_balance": user.bonus_balance,
        "withdrawable": withdrawable,
        "total_wagered": user.total_wagered,
        "currency": "UGX",
        "mpesa_user": has_mpesa_txn
    })


@app.post("/api/admin/balance")
@jwt_required()
def admin_add_balance():
    data = request.json
    user = User.query.get_or_404(data["user_id"])
    user.balance += int(data["amount"])
    db.session.commit()
    return jsonify({"message": "Balance updated"})


# ---------------- BETS (OPTIMIZED) ----------------
@app.post("/api/bets")
@jwt_required()
def place_bet():
    user = User.query.get(get_jwt_identity())
    data = request.json
    stake = int(data["stake"])

    real_money_used = min(stake, user.balance)
    bonus_used = min(stake - real_money_used, user.bonus_balance)
    total_available = real_money_used + bonus_used

    if total_available < stake:
        return jsonify({"error": "Insufficient balance"}), 400

    total_odds = 1
    for s in data["selections"]:
        total_odds *= float(s["odds"])

    possible_win = int(stake * total_odds)

    bet = Bet(
        user_id=user.id,
        stake=stake,
        total_odds=round(total_odds, 2),
        possible_win=possible_win,
        used_bonus=bonus_used
    )
    db.session.add(bet)
    db.session.flush()

    for s in data["selections"]:
        db.session.add(BetSelection(
            bet_id=bet.id,
            candidate_name=s["candidate"],
            odds=s["odds"]
        ))

    user.balance -= real_money_used
    user.bonus_balance -= bonus_used
    user.total_wagered += real_money_used
    
    db.session.commit()

    return jsonify({
        "message": "Bet placed successfully",
        "bet_id": bet.id,
        "possible_win": possible_win,
        "bonus_used": bonus_used,
        "real_money_used": real_money_used
    })


@app.get("/api/bets/history")
@jwt_required()
@cache_response(duration=60)  # Cache for 1 minute
def history():
    user_id = int(get_jwt_identity())
    
    # OPTIMIZED: Use joinedload to reduce queries
    from sqlalchemy.orm import joinedload
    
    bets = (
        Bet.query
        .options(joinedload(Bet.selections))
        .filter_by(user_id=user_id)
        .order_by(Bet.created_at.desc())
        .limit(50)  # Limit to recent 50
        .all()
    )

    bet_history = []
    for bet in bets:
        selections = [
            {
                "candidate_name": bs.candidate_name,
                "odds": bs.odds
            }
            for bs in bet.selections
        ]
        
        bet_history.append({
            "id": bet.id,
            "stake": bet.stake,
            "total_odds": bet.total_odds,
            "possible_win": bet.possible_win,
            "status": bet.status,
            "used_bonus": bet.used_bonus,
            "created_at": bet.created_at.isoformat(),
            "selections": selections
        })

    return jsonify(bet_history)


# ---------------- REFERRAL STATS (OPTIMIZED) ----------------
@app.get("/api/referrals/stats")
@jwt_required()
@cache_response(duration=120)  # Cache for 2 minutes
def referral_stats():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    # OPTIMIZED: Use aggregation functions
    referred_users = db.session.query(
        func.count(User.id)
    ).filter(
        User.referred_by == user.referral_code
    ).scalar()
    
    total_earned = db.session.query(
        func.coalesce(func.sum(ReferralReward.reward_amount), 0)
    ).filter(
        ReferralReward.referrer_id == user.id
    ).scalar()
    
    recent_rewards = (
        ReferralReward.query
        .filter_by(referrer_id=user.id)
        .order_by(ReferralReward.created_at.desc())
        .limit(5)
        .all()
    )
    
    return jsonify({
        "referral_code": user.referral_code,
        "total_referrals": referred_users,
        "total_earned": total_earned,
        "recent_referrals": [
            {
                "reward": r.reward_amount,
                "date": r.created_at.isoformat()
            }
            for r in recent_rewards
        ]
    })


def get_referral_earned_amount(user_id):
    return db.session.query(
        func.coalesce(func.sum(ReferralReward.reward_amount), 0)
    ).filter(
        ReferralReward.referrer_id == user_id
    ).scalar()


# ---------------- WITHDRAW ----------------
@app.post("/api/withdraw")
@jwt_required()
def withdraw():
    user = User.query.get(get_jwt_identity())
    data = request.json
    amount = int(data["amount"])

    if amount < 1000:
        return jsonify({"error": "Minimum withdrawal is UGX 1,000"}), 400

    if user.balance < amount:
        return jsonify({"error": "Insufficient balance"}), 400

    referral_earned = get_referral_earned_amount(user.id)
    withdrawable_amount = max(user.balance - referral_earned, 0)

    if withdrawable_amount <= 0:
        return jsonify({
            "error": "Your balance is from referrals and cannot be withdrawn"
        }), 400

    if amount > withdrawable_amount:
        return jsonify({
            "error": f"You can only withdraw up to UGX {withdrawable_amount:,}. Referral earnings are locked."
        }), 400

    withdrawal = Withdrawal(
        user_id=user.id,
        amount=amount,
        method=data.get("method", "MTN"),
        status="pending"
    )

    user.balance -= amount

    db.session.add(withdrawal)
    db.session.commit()

    return jsonify({
        "message": "Withdrawal submitted successfully",
        "amount": amount,
        "remaining_balance": user.balance,
        "locked_referral_amount": referral_earned
    })


@app.get("/api/withdrawals/history")
@jwt_required()
@cache_response(duration=120)  # Cache for 2 minutes
def withdrawal_history():
    user_id = int(get_jwt_identity())
    withdrawals = (
        Withdrawal.query
        .filter_by(user_id=user_id)
        .order_by(Withdrawal.created_at.desc())
        .limit(50)
        .all()
    )
    
    return jsonify([
        {
            "id": w.id,
            "amount": w.amount,
            "method": w.method,
            "status": w.status,
            "created_at": w.created_at.isoformat()
        }
        for w in withdrawals
    ])


@app.get("/admin/withdrawals")
@cache_response(duration=30)  # Cache for 30 seconds
def get_admin_withdrawals():
    withdrawals = (
        Withdrawal.query
        .order_by(Withdrawal.created_at.desc())
        .limit(100)
        .all()
    )
    
    result = []
    for w in withdrawals:
        user = User.query.get(w.user_id)
        
        has_mpesa = False
        if user:
            has_mpesa = db.session.query(
                db.exists().where(
                    db.and_(
                        MpesaTransaction.user_id == user.id,
                        MpesaTransaction.status == 'SUCCESS'
                    )
                )
            ).scalar()
        
        result.append({
            "id": w.id,
            "user_id": w.user_id,
            "phone": user.phone if user else "Unknown",
            "amount": w.amount,
            "method": w.method,
            "status": w.status,
            "user_balance": user.balance if user else 0,
            "is_mpesa_user": has_mpesa,
            "created_at": w.created_at.isoformat()
        })
    
    return jsonify(result)


@app.put("/admin/withdrawals/<int:withdrawal_id>")
def update_withdrawal_status(withdrawal_id):
    data = request.get_json()
    status = data.get('status')
    
    if status not in ['pending', 'success', 'failed']:
        return jsonify({"error": "Invalid status"}), 400
    
    withdrawal = Withdrawal.query.get(withdrawal_id)
    if not withdrawal:
        return jsonify({"error": "Withdrawal not found"}), 404
    
    withdrawal.status = status
    db.session.commit()
    
    return jsonify({
        "message": "Withdrawal status updated",
        "withdrawal": {
            "id": withdrawal.id,
            "status": withdrawal.status
        }
    })


@app.get("/api/admin/users")
@jwt_required()
@cache_response(duration=60)  # Cache for 1 minute
def list_users():
    users = (
        User.query
        .order_by(User.created_at.desc())
        .limit(100)
        .all()
    )

    return jsonify([
        {
            "id": u.id,
            "phone": u.phone,
            "balance": u.balance,
            "created_at": u.created_at.isoformat()
        }
        for u in users
    ])


# ---------------- PAYMENTS (MPESA) ----------------
from services.mpesa import MpesaService

@app.post("/api/payments/mpesa")
@jwt_required()
def mpesa_payment():
    user = User.query.get(get_jwt_identity())
    data = request.json

    try:
        phone_local = normalize_phone(data.get("phone"))
        amount = int(data.get("amount"))
    except Exception:
        return jsonify({"message": "Invalid phone number or amount"}), 400

    mpesa_phone = "254" + phone_local

    mpesa = MpesaService()
    response = mpesa.stk_push(
        phone=mpesa_phone,
        amount=amount,
        reference=f"TOPUP-{user.id}",
        user_id=user.id
    )

    return jsonify({
        "message": "STK Push sent",
        "mpesa": response
    })


@app.post("/api/payments/mpesa/callback")
def mpesa_callback():
    data = request.json
    print("Mpesa callback received:", data)

    try:
        stk = data["Body"]["stkCallback"]
        result_code = int(stk["ResultCode"])
        checkout_request_id = stk["CheckoutRequestID"]

        items = stk.get("CallbackMetadata", {}).get("Item", [])
        amount = next(i["Value"] for i in items if i["Name"] == "Amount")
        phone_254 = next(i["Value"] for i in items if i["Name"] == "PhoneNumber")

        phone = normalize_phone(phone_254)

        txn = MpesaTransaction.query.filter_by(
            checkout_request_id=checkout_request_id
        ).first()

        if not txn:
            txn = MpesaTransaction(
                phone=phone,
                amount=amount,
                checkout_request_id=checkout_request_id
            )
            db.session.add(txn)

        txn.status = "SUCCESS" if result_code == 0 else "FAILED"

        if result_code == 0:
            user = User.query.filter_by(phone=phone).first()
            if user:
                user.balance += int(amount)
                txn.user_id = user.id

        db.session.commit()
        return jsonify({"message": "Callback processed"}), 200

    except Exception as e:
        print("Mpesa callback error:", e)
        return jsonify({"message": "Callback failed"}), 500


@app.get("/api/admin/mpesa-transactions")
@jwt_required()
@cache_response(duration=60)  # Cache for 1 minute
def admin_mpesa_transactions():
    transactions = (
        MpesaTransaction.query
        .order_by(MpesaTransaction.created_at.desc())
        .limit(200)
        .all()
    )

    return jsonify([
        {
            "id": t.id,
            "phone": t.phone,
            "amount": t.amount,
            "status": t.status,
            "created_at": t.created_at.isoformat()
        }
        for t in transactions
    ])


@app.post("/api/payments/mpesa/update_pending")
def update_pending():
    try:
        mpesa = MpesaService()
        mpesa.update_pending_transactions()
        return jsonify({"message": "Pending transactions updated"}), 200
    except Exception as e:
        print("Update pending error:", e)
        return jsonify({"message": "Failed to update pending"}), 500


# ---------------- ELECTIONS & CANDIDATES (OPTIMIZED) ----------------
@app.get("/elections")
@cache_response(duration=300)  # Cache for 5 minutes
def get_elections():
    # OPTIMIZED: Use joinedload
    from sqlalchemy.orm import joinedload
    
    elections = (
        Election.query
        .options(joinedload(Election.candidates))
        .all()
    )
    
    result = []
    for e in elections:
        result.append({
            "id": e.id,
            "title": e.title,
            "constituency": e.constituency,
            "type": e.type,
            "candidates": [
                {
                    "id": c.id,
                    "name": c.name,
                    "party": c.party,
                    "odds": c.odds,
                    "image": c.image
                }
                for c in e.candidates
            ]
        })
    
    return jsonify(result)


@app.post("/election")
def create_election():
    data = request.json
    
    existing = Election.query.get(data.get("id"))
    if existing:
        return jsonify({"error": "Election with this ID already exists"}), 400
    
    if not data.get("id") or not data.get("title"):
        return jsonify({"error": "ID and title are required"}), 400
    
    election = Election(
        id=data.get("id"),
        title=data.get("title"),
        constituency=data.get("constituency"),
        type=data.get("type", "presidential")
    )
    
    db.session.add(election)
    db.session.commit()
    
    return jsonify({"success": True, "id": election.id})


@app.get("/election/<string:id>")
@cache_response(duration=300)
def get_election(id):
    from sqlalchemy.orm import joinedload
    
    election = (
        Election.query
        .options(joinedload(Election.candidates))
        .filter_by(id=id)
        .first()
    )
    
    if not election:
        return jsonify({"error": "Election not found"}), 404
    
    return jsonify({
        "id": election.id,
        "title": election.title,
        "constituency": election.constituency,
        "type": election.type,
        "candidates": [
            {
                "id": c.id,
                "name": c.name,
                "party": c.party,
                "odds": c.odds,
                "image": c.image
            }
            for c in election.candidates
        ]
    })


@app.put("/election/<string:id>")
def update_election(id):
    data = request.json
    election = Election.query.get(id)
    
    if not election:
        return jsonify({"error": "Election not found"}), 404
    
    election.title = data.get("title", election.title)
    election.constituency = data.get("constituency", election.constituency)
    election.type = data.get("type", election.type)
    
    db.session.commit()
    
    return jsonify({"success": True})


@app.delete("/election/<string:id>")
def delete_election(id):
    election = Election.query.get(id)
    
    if not election:
        return jsonify({"error": "Election not found"}), 404
    
    Candidate.query.filter_by(election_id=id).delete()
    db.session.delete(election)
    db.session.commit()
    
    return jsonify({"success": True})


@app.post("/candidate")
def create_candidate():
    data = request.json
    candidate = Candidate(
        election_id=data.get("election_id"),
        name=data.get("name"),
        party=data.get("party"),
        odds=float(data.get("odds", 1)),
        image=data.get("image")
    )
    db.session.add(candidate)
    db.session.commit()
    return jsonify({"success": True, "id": candidate.id})


@app.put("/candidate/<int:id>")
def update_candidate(id):
    data = request.json
    candidate = Candidate.query.get(id)
    if not candidate:
        return jsonify({"error": "Candidate not found"}), 404
    
    candidate.name = data.get("name", candidate.name)
    candidate.party = data.get("party", candidate.party)
    candidate.odds = float(data.get("odds", candidate.odds))
    candidate.image = data.get("image", candidate.image)
    
    db.session.commit()
    return jsonify({"success": True})


@app.delete("/candidate/<int:id>")
def delete_candidate(id):
    candidate = Candidate.query.get(id)
    if not candidate:
        return jsonify({"error": "Candidate not found"}), 404
    
    db.session.delete(candidate)
    db.session.commit()
    return jsonify({"success": True})


if __name__ == "__main__":
    app.run()