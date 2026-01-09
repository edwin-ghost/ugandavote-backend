# init_database.py
# Run this FIRST to create all database tables

from app import app, db

def init_db():
    """Initialize the database by creating all tables"""
    with app.app_context():
        print("Creating all database tables...")
        
        # Create all tables defined in your models
        db.create_all()
        
        print("✅ Database tables created successfully!")
        
        # List all created tables
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        
        print(f"\nCreated tables: {', '.join(tables)}")

if __name__ == '__main__':
    init_db()