"""
Run this migration to add referral + bonus system to existing database
Usage: python migrate_referral.py
"""

from app import app, db
from models import User
import random
import string
from sqlalchemy import text

def generate_referral_code():
    """Generate unique 6-character referral code"""
    while True:
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        if not User.query.filter_by(referral_code=code).first():
            return code

def column_exists(table_name, column_name):
    inspector = db.inspect(db.engine)
    return column_name in [col["name"] for col in inspector.get_columns(table_name)]

def migrate():
    with app.app_context():
        print("🚀 Starting migration...")

        # Ensure tables exist
        db.create_all()
        print("✓ Tables created / verified")

        try:
            with db.engine.begin() as conn:
                # USER TABLE MIGRATIONS
                if not column_exists("user", "referral_code"):
                    conn.execute(text(
                        'ALTER TABLE "user" ADD COLUMN referral_code VARCHAR(10)'
                    ))
                    print("✓ referral_code added")

                if not column_exists("user", "referred_by"):
                    conn.execute(text(
                        'ALTER TABLE "user" ADD COLUMN referred_by VARCHAR(10)'
                    ))
                    print("✓ referred_by added")

                if not column_exists("user", "bonus_balance"):
                    conn.execute(text(
                        'ALTER TABLE "user" ADD COLUMN bonus_balance INTEGER DEFAULT 2500'
                    ))
                    print("✓ bonus_balance added (default 2500 for new users)")

                if not column_exists("user", "created_at"):
                    conn.execute(text(
                        'ALTER TABLE "user" ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP'
                    ))
                    print("✓ created_at added")

                # BET TABLE MIGRATION
                if not column_exists("bet", "used_bonus"):
                    conn.execute(text(
                        'ALTER TABLE "bet" ADD COLUMN used_bonus INTEGER DEFAULT 0'
                    ))
                    print("✓ used_bonus added to bet table")

            # --------------------------------------------------
            # EXISTING USERS FIXUP (NO RETROACTIVE BONUS)
            # --------------------------------------------------
            users = User.query.all()
            updated = 0

            for user in users:
                if not user.referral_code:
                    user.referral_code = generate_referral_code()
                    updated += 1

                # Existing users should NOT get signup bonus
                if user.bonus_balance is None:
                    user.bonus_balance = 0

            db.session.commit()
            print(f"✓ Referral codes generated for {updated} users")
            print("🎉 Migration completed successfully!")

        except Exception as e:
            db.session.rollback()
            print(f"❌ Migration failed: {e}")

if __name__ == "__main__":
    migrate()
