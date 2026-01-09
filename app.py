import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_jwt_extended import (
    JWTManager, create_access_token,
    jwt_required, get_jwt_identity
)
from sqlalchemy import func
from werkzeug.security import generate_password_hash, check_password_hash
from config import Config
from models import Candidate, Election, db, User, Bet, BetSelection, Withdrawal, MpesaTransaction, ReferralReward
from utils.phone import normalize_phone

app = Flask(__name__)
app.config.from_object(Config)


CORS(app)
CORS(app, resources={r"/api/*": {"origins": "https://ugandavote.today"}})

database_url = os.getenv("DATABASE_URL", "postgresql://uganda_postgres_user:oSwtZYjUmvGZU0sxnwEJ9oZklgaQrDHH@dpg-d5fc3p0gjchc73f2h2v0-a.oregon-postgres.render.com/uganda_postgres")
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    
db.init_app(app)
jwt = JWTManager(app)


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

    # Create new user with bonus balance
    user = User(
        phone=phone,
        pin_hash=generate_password_hash(data["pin"]),
        balance=0,
        bonus_balance=2500,  # Signup bonus
        total_wagered=0  # Track total amount bet
    )

    # Generate unique referral code
    user.referral_code = user.generate_referral_code()

    # Process referral if code provided
    if referral_code:
        referrer = User.query.filter_by(referral_code=referral_code).first()
        if referrer:
            user.referred_by = referral_code
            
            # Give referrer 10,000 UGX reward
            referrer.balance += 10000
            
            # Record the referral reward
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


# ---------------- BALANCE ----------------
@app.get("/api/balance")
@jwt_required()
def balance():
    user = User.query.get(get_jwt_identity())


        # Check if user has at least one successful MPESA transaction
    has_mpesa_txn = MpesaTransaction.query.filter_by(
        user_id=user.id, status="SUCCESS"
    ).first() is not None

    DISPLAY_RATE = 30 if has_mpesa_txn else 1

    
    # Calculate withdrawable amount (must have wagered at least 1x deposit)
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


# ---------------- BETS ----------------
@app.post("/api/bets")
@jwt_required()
def place_bet():
    user = User.query.get(get_jwt_identity())
    data = request.json
    stake = int(data["stake"])

    # Calculate how much real money and bonus to use
    real_money_used = min(stake, user.balance)
    bonus_used = min(stake - real_money_used, user.bonus_balance)
    
    total_available = real_money_used + bonus_used

    if total_available < stake:
        return jsonify({"error": "Insufficient balance"}), 400

    # Calculate total odds
    total_odds = 1
    for s in data["selections"]:
        total_odds *= float(s["odds"])

    possible_win = int(stake * total_odds)

    # Create bet
    bet = Bet(
        user_id=user.id,
        stake=stake,
        total_odds=round(total_odds, 2),
        possible_win=possible_win,
        used_bonus=bonus_used
    )
    db.session.add(bet)
    db.session.flush()

    # Add selections
    for s in data["selections"]:
        db.session.add(BetSelection(
            bet_id=bet.id,
            candidate_name=s["candidate"],
            odds=s["odds"]
        ))

    # Deduct from balances
    user.balance -= real_money_used
    user.bonus_balance -= bonus_used
    
    # Track total wagered (only real money, not bonus)
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
def history():
    user_id = int(get_jwt_identity())
    bets = Bet.query.filter_by(user_id=user_id).order_by(Bet.created_at.desc()).all()

    bet_history = []
    for bet in bets:
        bet_selections = BetSelection.query.filter_by(bet_id=bet.id).all()
        
        selections = []
        for bs in bet_selections:
            selections.append({
                "candidate_name": bs.candidate_name,
                "odds": bs.odds
            })
        
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


# ---------------- REFERRAL STATS ----------------
@app.get("/api/referrals/stats")
@jwt_required()
def referral_stats():
    user = User.query.get(get_jwt_identity())
    
    # Count successful referrals
    referred_users = User.query.filter_by(referred_by=user.referral_code).count()
    
    # Total earnings from referrals
    rewards = ReferralReward.query.filter_by(referrer_id=user.id).all()
    total_earned = sum(r.reward_amount for r in rewards)
    
    return jsonify({
        "referral_code": user.referral_code,
        "total_referrals": referred_users,
        "total_earned": total_earned,
        "recent_referrals": [
            {
                "reward": r.reward_amount,
                "date": r.created_at.isoformat()
            }
            for r in rewards[-5:]  # Last 5 referrals
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

    # Minimum withdrawal
    if amount < 1000:
        return jsonify({"error": "Minimum withdrawal is UGX 1,000"}), 400

    # Cannot withdraw bonus
    if user.balance < amount:
        return jsonify({"error": "Insufficient balance"}), 400

    # Referral earnings are NOT withdrawable
    referral_earned = get_referral_earned_amount(user.id)

    # Max withdrawable = balance minus referral earnings
    withdrawable_amount = max(user.balance - referral_earned, 0)

    if withdrawable_amount <= 0:
        return jsonify({
            "error": "Your balance is from referrals and cannot be withdrawn"
        }), 400

    if amount > withdrawable_amount:
        return jsonify({
            "error": f"You can only withdraw up to UGX {withdrawable_amount:,}. Referral earnings are locked."
        }), 400

    # Create withdrawal
    withdrawal = Withdrawal(
        user_id=user.id,
        amount=amount,
        method=data.get("method", "MTN"),
        status="pending"
    )

    # Deduct balance
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
def withdrawal_history():
    user_id = int(get_jwt_identity())
    withdrawals = Withdrawal.query.filter_by(user_id=user_id).order_by(Withdrawal.created_at.desc()).all()
    
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



@app.get("/api/admin/users")
@jwt_required()
def list_users():
    users = (
        User.query
        .order_by(User.created_at.desc())
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



# ---------------- PAYMENTS ----------------
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

        # Credit user balance on success
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



# ---------------- ADMIN MPESA ----------------
@app.get("/api/admin/mpesa-transactions")
@jwt_required()
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



# ------------------------------
# Elections & Candidates
# ------------------------------



@app.post("/election")
def create_election():
    """Create a new election"""
    data = request.json
    
    # Check if election already exists
    existing = Election.query.get(data.get("id"))
    if existing:
        return jsonify({"error": "Election with this ID already exists"}), 400
    
    # Validate required fields
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
def get_election(id):
    """Get a single election with its candidates"""
    election = Election.query.get(id)
    
    if not election:
        return jsonify({"error": "Election not found"}), 404
    
    candidates = Candidate.query.filter_by(election_id=election.id).all()
    
    return jsonify({
        "id": election.id,
        "title": election.title,
        "constituency": election.constituency,
        "type": election.type,
        "candidates": [{
            "id": c.id,
            "name": c.name,
            "party": c.party,
            "odds": c.odds,
            "image": c.image
        } for c in candidates]
    })


@app.put("/election/<string:id>")
def update_election(id):
    """Update an existing election"""
    data = request.json
    election = Election.query.get(id)
    
    if not election:
        return jsonify({"error": "Election not found"}), 404
    
    # Update fields
    election.title = data.get("title", election.title)
    election.constituency = data.get("constituency", election.constituency)
    election.type = data.get("type", election.type)
    
    db.session.commit()
    
    return jsonify({"success": True})


@app.delete("/election/<string:id>")
def delete_election(id):
    """Delete an election and all its candidates"""
    election = Election.query.get(id)
    
    if not election:
        return jsonify({"error": "Election not found"}), 404
    
    # Delete all candidates first (if no cascade is set)
    Candidate.query.filter_by(election_id=id).delete()
    
    # Delete the election
    db.session.delete(election)
    db.session.commit()
    
    return jsonify({"success": True})

@app.get("/elections")
def get_elections():
    elections = Election.query.all()
    result = []
    for e in elections:
        candidates = Candidate.query.filter_by(election_id=e.id).all()
        result.append({
            "id": e.id,
            "title": e.title,
            "constituency": e.constituency,
            "type": e.type,
            "candidates": [{
                "id": c.id,
                "name": c.name,
                "party": c.party,
                "odds": c.odds,
                "image": c.image
            } for c in candidates]
        })
    return jsonify(result)

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