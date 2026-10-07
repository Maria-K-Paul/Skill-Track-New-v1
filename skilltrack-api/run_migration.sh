#!/bin/bash
# Migration runner script for SkillTrack
# This script runs database migrations safely

set -e  # Exit on error

echo "🔄 SkillTrack Database Migration"
echo "================================"

# Check if DATABASE_URL is set
if [ -z "$DATABASE_URL" ]; then
    echo "❌ ERROR: DATABASE_URL environment variable is not set"
    echo "   Please set DATABASE_URL before running migrations"
    echo "   Example: export DATABASE_URL='postgresql+psycopg://user:pass@localhost/skilltrack'"
    exit 1
fi

# Print database info (hide password)
DB_INFO=$(echo $DATABASE_URL | sed 's/:\/\/[^:]*:[^@]*@/:\/\/***:***@/')
echo "📊 Database: $DB_INFO"
echo ""

# Run migration
python migrate_db.py

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Migration completed successfully!"
    echo "   You can now start the application."
else
    echo ""
    echo "❌ Migration failed!"
    echo "   Please check the error messages above."
    exit 1
fi
