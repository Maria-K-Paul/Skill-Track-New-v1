@echo off
REM Migration runner script for SkillTrack (Windows)
REM This script runs database migrations safely

echo.
echo 🔄 SkillTrack Database Migration
echo ================================
echo.

REM Check if DATABASE_URL is set
if "%DATABASE_URL%"=="" (
    echo ❌ ERROR: DATABASE_URL environment variable is not set
    echo    Please set DATABASE_URL before running migrations
    echo    Example: set DATABASE_URL=postgresql+psycopg://user:pass@localhost/skilltrack
    exit /b 1
)

echo 📊 Database: %DATABASE_URL%
echo.

REM Run migration
python migrate_db.py

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ✅ Migration completed successfully!
    echo    You can now start the application.
) else (
    echo.
    echo ❌ Migration failed!
    echo    Please check the error messages above.
    exit /b 1
)
