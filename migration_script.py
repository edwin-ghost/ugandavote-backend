# migration_script.py
# Run this AFTER init_database.py to populate your database with existing election data

from app import app, db, Election, Candidate
from datetime import datetime

def migrate_elections():
    """Migrate hardcoded elections to database"""
    
    elections_data = [
        {
            'id': 'presidential-2026',
            'title': 'Presidential Election 2026',
            'type': 'presidential',
            'constituency': 'National',
            'candidates': [
                {
                    'name': 'Yoweri Museveni',
                    'party': 'NRM',
                    'odds': 1.45,
                    'image': 'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcRFTRur4rl0RhW8v9r2S9Ag3PLXHriDGl2mjA&s',
                },
                {
                    'name': 'Robert Kyagulanyi',
                    'party': 'NUP',
                    'odds': 3.20,
                    'image': '/candidates/bobi.jpg',
                },
                {
                    'name': 'Kizza Besigye',
                    'party': 'FDC',
                    'odds': 8.50,
                    'image': '/candidates/besigye.jpg',
                },
                {
                    'name': 'Mugisha Muntu',
                    'party': 'ANT',
                    'odds': 15.00,
                    'image': '/candidates/muntu.jpg',
                },
            ],
        },
        {
            'id': 'kampala-mp-2026',
            'title': 'Kampala Central MP',
            'type': 'parliamentary',
            'constituency': 'Kampala District',
            'candidates': [
                {
                    'name': 'Muhammad Nsereko',
                    'party': 'Independent',
                    'odds': 1.85,
                    'image': '/candidates/nsereko.jpg',
                },
                {
                    'name': 'Ibrahim Ssemujju',
                    'party': 'FDC',
                    'odds': 2.40,
                    'image': '/candidates/ssemujju.jpg',
                },
            ],
        },
        {
            'id': 'wakiso-woman-2026',
            'title': 'Wakiso Woman MP',
            'type': 'special',
            'constituency': 'Wakiso District',
            'candidates': [
                {
                    'name': 'Idah Nantaba',
                    'party': 'NRM',
                    'odds': 2.10,
                    'image': '/candidates/nantaba.jpg',
                },
                {
                    'name': 'Persis Namuganza',
                    'party': 'NRM',
                    'odds': 2.50,
                    'image': '/candidates/namuganza.jpg',
                },
            ],
        },
        {
            'id': 'gulu-mayor-2026',
            'title': 'Gulu City Mayor',
            'type': 'gubernatorial',
            'constituency': 'Gulu District',
            'candidates': [
                {
                    'name': 'Alfred Ojara',
                    'party': 'FDC',
                    'odds': 1.95,
                    'image': '/candidates/ojara.jpg',
                },
                {
                    'name': 'George Lakony',
                    'party': 'NRM',
                    'odds': 2.20,
                    'image': '/candidates/lakony.jpg',
                },
            ],
        },
        {
            'id': 'jinja-mp-2026',
            'title': 'Jinja East MP',
            'type': 'parliamentary',
            'constituency': 'Jinja District',
            'candidates': [
                {
                    'name': 'Paul Nabwiso',
                    'party': 'NUP',
                    'odds': 1.75,
                    'image': '/candidates/nabwiso.jpg',
                },
                {
                    'name': 'Nathan Kyakulaga',
                    'party': 'NRM',
                    'odds': 2.80,
                    'image': '/candidates/kyakulaga.jpg',
                },
            ],
        },
        {
            'id': 'youth-rep-2026',
            'title': 'National Youth Representative',
            'type': 'special',
            'constituency': 'National',
            'candidates': [
                {
                    'name': 'Francis Zaake',
                    'party': 'NUP',
                    'odds': 2.00,
                    'image': '/candidates/zaake.jpg',
                },
                {
                    'name': 'Muwanga Kivumbi',
                    'party': 'DP',
                    'odds': 3.50,
                    'image': '/candidates/munyagwa.jpg',
                },
            ],
        },
    ]
    
    with app.app_context():
        # Check if tables exist
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        
        if 'election' not in tables or 'candidate' not in tables:
            print("❌ Error: Tables don't exist yet!")
            print("Please run 'python init_database.py' first to create tables.")
            return
        
        # Clear existing data (optional - comment out if you want to keep existing data)
        print("Clearing existing election data...")
        try:
            Candidate.query.delete()
            Election.query.delete()
            db.session.commit()
            print("✓ Cleared existing data")
        except Exception as e:
            print(f"Warning: Could not clear data - {e}")
            db.session.rollback()
        
        print("\nMigrating elections and candidates...")
        
        for election_data in elections_data:
            # Check if election already exists
            existing = Election.query.get(election_data['id'])
            if existing:
                print(f"⊘ Skipping: {election_data['title']} (already exists)")
                continue
            
            # Create election
            election = Election(
                id=election_data['id'],
                title=election_data['title'],
                constituency=election_data['constituency'],
                type=election_data['type']
            )
            db.session.add(election)
            db.session.flush()  # Get the election ID
            
            # Create candidates
            for candidate_data in election_data['candidates']:
                candidate = Candidate(
                    election_id=election.id,
                    name=candidate_data['name'],
                    party=candidate_data['party'],
                    odds=candidate_data['odds'],
                    image=candidate_data['image']
                )
                db.session.add(candidate)
            
            print(f"✓ Added: {election.title} with {len(election_data['candidates'])} candidates")
        
        db.session.commit()
        print("\n✅ Migration completed successfully!")
        print(f"Total elections: {Election.query.count()}")
        print(f"Total candidates: {Candidate.query.count()}")

if __name__ == '__main__':
    migrate_elections()