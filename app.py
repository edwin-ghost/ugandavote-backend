import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_jwt_extended import (
    JWTManager, create_access_token,
    jwt_required, get_jwt_identity
)
from werkzeug.security import generate_password_hash, check_password_hash
from config import Config
from models import db, User, Bet, BetSelection, Withdrawal, MpesaTransaction
from utils.phone import normalize_phone

app = Flask(__name__)
app.config.from_object(Config)

CORS(app)

CORS(app, resources={r"/api/*": {"origins": "https://ugandavote.vercel.app"}})


database_url = os.getenv("DATABASE_URL", "postgresql://uganda_postgres_user:oSwtZYjUmvGZU0sxnwEJ9oZklgaQrDHH@dpg-d5fc3p0gjchc73f2h2v0-a.oregon-postgres.render.com/uganda_postgres")
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    
db.init_app(app)
jwt = JWTManager(app)

# with app.app_context():
#     db.create_all()
    

# ---------------- AUTH ----------------

@app.post("/api/auth/register")
def register():
    data = request.json

    phone = data["phone"]

    if User.query.filter_by(phone=phone).first():
        return jsonify({"error": "User exists"}), 400

    user = User(
        phone=phone,
        pin_hash=generate_password_hash(data["pin"]),
        balance=0
    )

    db.session.add(user)
    db.session.commit()

    token = create_access_token(identity=str(user.id))

    return jsonify({
        "token": token,
        "user": {
            "id": user.id,
            "phone": user.phone,
            "balance": user.balance
        }
    }), 201


@app.post("/api/auth/login")
def login():
    data = request.json
    user = User.query.filter_by(phone=data["phone"]).first()

    if not user or not check_password_hash(user.pin_hash, data["pin"]):
        return jsonify({"error": "Invalid login"}), 401

    token = create_access_token(identity=str(user.id))

    return jsonify({
        "token": token,
        "user": {
            "id": user.id,
            "phone": user.phone,
            "balance": user.balance
        }
    })


# ---------------- BALANCE ----------------

@app.get("/api/balance")
@jwt_required()
def balance():
    user = User.query.get(get_jwt_identity())
    return jsonify({"balance": user.balance, "currency": "UGX"})


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

    if user.balance < stake:
        return jsonify({"error": "Insufficient balance"}), 400

    total_odds = 1
    for s in data["selections"]:
        total_odds *= float(s["odds"])

    possible_win = int(stake * total_odds)

    bet = Bet(
        user_id=user.id,
        stake=stake,
        total_odds=round(total_odds, 2),
        possible_win=possible_win
    )
    db.session.add(bet)
    db.session.flush()

    for s in data["selections"]:
        db.session.add(BetSelection(
            bet_id=bet.id,
            candidate_name=s["candidate"],
            odds=s["odds"]
        ))

    user.balance -= stake
    db.session.commit()

    return jsonify({"message": "Bet placed", "possible_win": possible_win})


@app.get("/api/bets/history")
@jwt_required()
def history():
    user_id = int(get_jwt_identity())

    bets = Bet.query.filter_by(user_id=user_id).order_by(Bet.created_at.desc()).all()

    bet_history = []
    for bet in bets:
        # Get all bet selections for this bet
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
            "created_at": bet.created_at.isoformat(),
            "selections": selections
        })

    return jsonify(bet_history)


# ---------------- WITHDRAW ----------------

@app.post("/api/withdraw")
@jwt_required()
def withdraw():
    user = User.query.get(get_jwt_identity())
    data = request.json
    amount = int(data["amount"])

    if user.balance < amount:
        return jsonify({"error": "Insufficient balance"}), 400

    withdrawal = Withdrawal(
        user_id=user.id,
        amount=amount,
        method=data["method"]
    )

    user.balance -= amount
    db.session.add(withdrawal)
    db.session.commit()

    return jsonify({"message": "Withdrawal request submitted"})



# ---------------- PAYMENTS ----------------

from services.mpesa import MpesaService

@app.post("/api/payments/mpesa")
@jwt_required()
def mpesa_payment():
    user = User.query.get(get_jwt_identity())
    data = request.json

    try:
        phone = normalize_phone(data.get("phone"))
        amount = int(data.get("amount"))
    except Exception:
        return jsonify({"message": "Invalid phone number"}), 400
    
    amount = data.get("amount")

    if not phone or not amount:
        return jsonify({"message": "Phone and amount required"}), 400

    try:
        mpesa = MpesaService()
        response = mpesa.stk_push(
            phone=phone,
            amount=int(amount),
            reference=f"TOPUP-{user.id}", user_id=user.id
        )

      

        return jsonify({
            "message": "STK Push sent",
            "mpesa": response
        })

    except Exception as e:
        print(e)
        return jsonify({
            "message": "Failed to initiate Mpesa payment"
        }), 500
    


# app.py

@app.post("/api/payments/mpesa/callback")
def mpesa_callback():
    data = request.json
    print("Mpesa callback received:", data)
    try:
        callback_items = data.get("Body", {}).get("stkCallback", {}).get("CallbackMetadata", {}).get("Item", [])
        checkout_request_id = data.get("Body", {}).get("stkCallback", {}).get("CheckoutRequestID")
        result_code = int(data.get("Body", {}).get("stkCallback", {}).get("ResultCode", 1))

        amount = next((i["Value"] for i in callback_items if i["Name"] == "Amount"), 0)
        phone = next((i["Value"] for i in callback_items if i["Name"] == "PhoneNumber"), None)

        txn = MpesaTransaction.query.filter_by(checkout_request_id=checkout_request_id).first()
        if not txn:
            txn = MpesaTransaction(
                user_id=None,
                phone=phone,
                amount=amount,
                checkout_request_id=checkout_request_id,
                status="SUCCESS" if result_code == 0 else "FAILED"
            )
            db.session.add(txn)
        else:
            txn.status = "SUCCESS" if result_code == 0 else "FAILED"

        if result_code == 0 and phone:
            user = User.query.filter_by(phone=phone).first()
            if user:
                user.balance += int(amount)

        db.session.commit()
        return jsonify({"message": "Callback processed"}), 200
    except Exception as e:
        print("Mpesa callback error:", e)
        return jsonify({"message": "Callback failed"}), 500
    

@app.post("/api/payments/mpesa/update_pending")
def update_pending():
    try:
        mpesa = MpesaService()
        mpesa.update_pending_transactions()
        return jsonify({"message": "Pending transactions updated"}), 200
    except Exception as e:
        print("Update pending error:", e)
        return jsonify({"message": "Failed to update pending"}), 500


# ---------------- RUN ----------------

if __name__ == "__main__":
    app.run()
