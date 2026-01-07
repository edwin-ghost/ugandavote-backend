from datetime import timedelta
import os

class Config:
    SECRET_KEY = "change-this"
    JWT_SECRET_KEY = "change-this-too"
    # SQLALCHEMY_DATABASE_URI = "postgresql://uganda_user:securepassword@localhost:5432/uganda_bets"
    SQLALCHEMY_DATABASE_URI = "postgresql://uganda_postgres_user:oSwtZYjUmvGZU0sxnwEJ9oZklgaQrDHH@dpg-d5fc3p0gjchc73f2h2v0-a.oregon-postgres.render.com/uganda_postgres"

    SQLALCHEMY_TRACK_MODIFICATIONS = False


        # JWT
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(days=7)


    # ---------------- MPESA (DARAJA) ----------------
    SAF_SHORTCODE = os.getenv("SAF_SHORTCODE", "303506")  # Sandbox Paybill
    SAF_CONSUMER_KEY = os.getenv("SAF_CONSUMER_KEY", "6oUYc6pxKSx1qZNOfML2hcAnpAPndeVq")
    SAF_CONSUMER_SECRET = os.getenv("SAF_CONSUMER_SECRET", "T3fmQgKGAkb6rZjl")
    SAF_PASS_KEY = os.getenv("SAF_PASS_KEY", "71bc94670907e8ebd110827d8e6908c5a92ef2ee09502b0c3c9db9d2632d762a")

    SAF_ACCESS_TOKEN_API = "https://api.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
    SAF_STK_PUSH_API = "https://api.safaricom.co.ke/mpesa/stkpush/v1/processrequest"
    SAF_STK_PUSH_QUERY_API = "https://api.safaricom.co.ke/mpesa/stkpushquery/v1/query"

    CALLBACK_URL = os.getenv(
        "CALLBACK_URL",
        "https://charities-donor.onrender.com/api/payments/mpesa/callback"
    )