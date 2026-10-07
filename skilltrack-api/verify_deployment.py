#!/usr/bin/env python3
"""
Deployment verification script for SkillTrack.
Run this after deployment to verify everything is working correctly.
"""
import sys
from sqlalchemy import inspect, text
from app.config import DATABASE_URL
from app.database import engine

def verify_deployment():
    """Verify database schema and configuration."""
    print("🔍 SkillTrack Deployment Verification")
    print("=" * 50)
    print()

    # Check database connection
    print("1️⃣ Testing database connection...")
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("   ✅ Database connection successful")
    except Exception as e:
        print(f"   ❌ Database connection failed: {e}")
        return False

    # Check tables exist
    print("\n2️⃣ Checking tables...")
    inspector = inspect(engine)
    expected_tables = [
        'users', 'domains', 'levels', 'questions', 'enrollments',
        'slots', 'slot_bookings', 'attempts', 'certificates', 'badges',
        'activity_logs', 'exam_keys', 'exam_sessions', 'settings', 'ai_cache'
    ]

    existing_tables = inspector.get_table_names()
    missing_tables = [t for t in expected_tables if t not in existing_tables]

    if missing_tables:
        print(f"   ❌ Missing tables: {', '.join(missing_tables)}")
        return False
    else:
        print(f"   ✅ All {len(expected_tables)} tables exist")

    # Check critical columns
    print("\n3️⃣ Checking critical schema updates...")
    checks = [
        ('slots', 'domain_id', 'Slots need domain_id for proper functioning'),
        ('slot_bookings', 'status', 'Booking status tracking'),
        ('certificates', 'domain_id', 'Domain certificates'),
        ('certificates', 'verification_token', 'Certificate verification'),
        ('enrollments', 'is_common_enrollment', 'Enrollment type tracking'),
        ('domains', 'description', 'Domain descriptions'),
    ]

    all_ok = True
    for table, column, description in checks:
        columns = [col['name'] for col in inspector.get_columns(table)]
        if column in columns:
            print(f"   ✅ {table}.{column} - {description}")
        else:
            print(f"   ❌ {table}.{column} missing - {description}")
            all_ok = False

    if not all_ok:
        print("\n   ⚠️  Some columns are missing. Run migrations: python migrate_db.py")
        return False

    # Check indexes
    print("\n4️⃣ Checking indexes...")
    critical_indexes = [
        ('slots', 'idx_slots_level_time_venue'),
        ('badges', 'idx_badges_user_level'),
    ]

    for table, index_name in critical_indexes:
        indexes = [idx['name'] for idx in inspector.get_indexes(table)]
        if index_name in indexes:
            print(f"   ✅ {index_name}")
        else:
            print(f"   ⚠️  {index_name} missing (non-critical)")

    # Count records
    print("\n5️⃣ Database statistics...")
    with engine.connect() as conn:
        for table in ['users', 'domains', 'levels', 'enrollments']:
            if table in existing_tables:
                result = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                count = result.scalar()
                print(f"   📊 {table}: {count} records")

    # Environment check
    print("\n6️⃣ Environment configuration...")
    from app import config

    checks = [
        ('DATABASE_URL', DATABASE_URL.split('@')[0] if '@' in DATABASE_URL else DATABASE_URL[:50]),
        ('SECRET_KEY', 'set' if config.SECRET_KEY != 'change-me' else '❌ NOT SET (using default)'),
        ('GEMINI_API_KEY', 'set' if config.GEMINI_API_KEY else '❌ NOT SET (AI features disabled)'),
        ('FRONTEND_URL', config.FRONTEND_URL),
        ('PUBLIC_BASE_URL', config.PUBLIC_BASE_URL),
    ]

    for key, value in checks:
        if '❌' in str(value):
            print(f"   ⚠️  {key}: {value}")
        else:
            print(f"   ✅ {key}: {value}")

    print("\n" + "=" * 50)
    print("✅ Deployment verification complete!")
    print()
    print("Next steps:")
    print("1. Test the health endpoint: curl http://localhost:8000/health")
    print("2. Try registering a user")
    print("3. Check logs for any errors")
    return True

if __name__ == "__main__":
    try:
        success = verify_deployment()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Verification failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
