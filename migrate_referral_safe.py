"""
Migration script to add total_wagered column to User table
Run this once to update your database schema
"""

from app import app, db
from models import User
from sqlalchemy import text

def migrate_database():
    with app.app_context():
        # Add total_wagered column if it doesn't exist
        try:
            # Check if column exists
            inspector = db.inspect(db.engine)
            columns = [c['name'] for c in inspector.get_columns('user')]
            
            if 'total_wagered' not in columns:
                print("Adding total_wagered column...")
                with db.engine.connect() as conn:
                    conn.execute(text(
                        'ALTER TABLE "user" ADD COLUMN total_wagered INTEGER DEFAULT 0'
                    ))
                    conn.commit()
                print("✓ Column added successfully")
            else:
                print("✓ Column already exists")
            
            # Update existing users to set total_wagered to 0
            print("Updating existing users...")
            with db.engine.connect() as conn:
                conn.execute(text(
                    'UPDATE "user" SET total_wagered = 0 WHERE total_wagered IS NULL'
                ))
                conn.commit()
            print("✓ Migration completed successfully")
            
        except Exception as e:
            print(f"Error during migration: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    migrate_database()