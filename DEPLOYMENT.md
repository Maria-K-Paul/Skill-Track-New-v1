# SkillTrack Deployment Guide

## 🚀 Deploying to Render

### Prerequisites
- GitHub repository connected to Render
- Render account

### One-Click Deploy

1. **Connect your GitHub repo to Render**
2. **Use the `render.yaml` Blueprint**
   - Render will automatically detect the `render.yaml` file
   - It will create:
     - PostgreSQL database (`skilltrack-db`)
     - Backend API (`skilltrack-api`)
     - Frontend static site (`skilltrack-web`)

3. **Set Required Environment Variables**
   
   The following are automatically set by `render.yaml`:
   - `DATABASE_URL` - from the PostgreSQL database
   - `SECRET_KEY` - auto-generated
   - `CORS_ORIGINS` - set to your frontend URL
   - `PYTHON_VERSION` - 3.12.1
   - `VITE_API_URL` - set to your backend API URL

   **You must manually add:**
   - `GEMINI_API_KEY` - Get from Google AI Studio (https://makersuite.google.com/app/apikey)
   - Optionally: `GEMINI_MODEL` (defaults to gemini-3.8-flash) and `GEMINI_FALLBACK_MODELS` (defaults to gemini-3.5-flash-lite,gemini-3.7-flash)

4. **Update URLs in render.yaml**
   
   After first deployment, update these URLs in `render.yaml`:
   ```yaml
   # Line 26: CORS_ORIGINS for backend
   value: https://YOUR-FRONTEND-URL.onrender.com
   
   # Line 38: VITE_API_URL for frontend  
   value: https://YOUR-BACKEND-URL.onrender.com
   ```

### Database Migrations

**Automatic Migration:**
The deployment automatically runs database migrations during build:
- `buildCommand` in `render.yaml` includes `python migrate_db.py`
- Migrations also run on app startup as a fallback

**Manual Migration (if needed):**
```bash
# SSH into Render instance or run locally with production DATABASE_URL
python skilltrack-api/migrate_db.py
```

The migration script:
- ✅ Works with both SQLite and PostgreSQL
- ✅ Is idempotent (safe to run multiple times)
- ✅ Adds all new columns and tables
- ✅ Creates indexes and constraints
- ✅ Backfills data where needed

### Schema Changes from v1 (b6c684e) to v2 (current)

The following database changes are handled automatically by migrations:

#### New Tables:
- `badges` - Per-level achievement badges

#### Schema Changes:
- **domains**: Added `description`, `difficulty`
- **enrollments**: Added `enrolled_at`, `completed_at`, `is_common_enrollment`
- **slots**: Added `domain_id` (CRITICAL!)
- **slot_bookings**: Added `status`, `booked_at`, `change_cancel_deadline`, `acknowledgement_acknowledged_at`
- **certificates**: Added `domain_id`, `student_name`, `domain_name`, `verification_token`, `status`
- **exam_keys**: Added `slot_id` (if missing)

### Troubleshooting

#### Backend fails to start
1. **Check DATABASE_URL**: Ensure it's set correctly
   ```bash
   # In Render dashboard, check Environment Variables
   # Should look like: postgresql+psycopg://user:pass@host/db
   ```

2. **Check migration logs**:
   ```bash
   # Look for "🔄 Starting migration..." in build logs
   # Should show "✅ Migration completed successfully!"
   ```

3. **Check Secret Key**:
   ```bash
   # Ensure SECRET_KEY is set and is a long random string
   ```

#### Frontend fails to build
1. **Check Node version**: Should be Node 18+ (Render auto-detects)
2. **Check VITE_API_URL**: Must point to your backend
3. **Clear build cache**: In Render dashboard, trigger manual deploy with cache cleared

#### Database connection errors
1. **Verify PostgreSQL is running**: Check database status in Render dashboard
2. **Check connection string format**:
   ```
   postgresql+psycopg://user:password@host:5432/database
   ```
   Not: `postgresql://` (needs `+psycopg`)

#### Migration errors
1. **"column already exists"**: This is OK, migration handles it
2. **"table doesn't exist"**: Run `Base.metadata.create_all()` first (automatic on startup)
3. **Permission denied**: Check database user has ALTER TABLE permissions

### Deployment Checklist

Before deploying:
- [ ] All tests passing locally
- [ ] Environment variables configured in Render
- [ ] `render.yaml` URLs updated to your actual URLs
- [ ] Database is created and accessible
- [ ] GEMINI_API_KEY is set (for AI features)
- [ ] Migrations tested locally

After deploying:
- [ ] Check build logs for migration success
- [ ] Test health endpoint: `https://YOUR-API.onrender.com/health`
- [ ] Test frontend loads
- [ ] Test login/registration
- [ ] Test exam flow
- [ ] Check database has all tables and columns

### Rolling Back

If deployment fails:
1. **In Render Dashboard**: Click "Rollback to Previous Deploy"
2. **Or manually**: Deploy the last working commit (b6c684e)
   ```bash
   git checkout b6c684e
   git push origin HEAD:main --force  # BE CAREFUL!
   ```

### Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| DATABASE_URL | ✅ | - | PostgreSQL connection string |
| SECRET_KEY | ✅ | - | JWT signing key (auto-generated) |
| CORS_ORIGINS | ✅ | - | Frontend URL for CORS |
| GEMINI_API_KEY | ⚠️ | - | Required for AI features |
| GEMINI_MODEL | ❌ | gemini-3.8-flash | AI model to use |
| GEMINI_FALLBACK_MODELS | ❌ | gemini-3.5-flash-lite,gemini-3.7-flash | Models tried when the main one is busy or rate-limited |
| PYTHON_VERSION | ❌ | 3.12.1 | Python runtime version |
| FRONTEND_URL | ❌ | - | Used in emails/links |
| PUBLIC_BASE_URL | ❌ | - | Used in certificate QR codes |
| ACCESS_TOKEN_MINUTES | ❌ | 480 | JWT expiry time |
| DB_POOL_SIZE | ❌ | 10 | Database connection pool size |
| DB_MAX_OVERFLOW | ❌ | 10 | Max overflow connections |
| VITE_API_URL | ✅ | - | Backend API URL (frontend) |

### Support

If you encounter issues:
1. Check Render build/runtime logs
2. Check application logs in Render dashboard
3. Verify all environment variables are set
4. Check database connectivity
5. Review migration logs

## Local Development

```bash
# Backend
cd skilltrack-api
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
python migrate_db.py  # Run migrations
uvicorn app.main:app --reload

# Frontend
cd skilltrack
npm install
npm run dev
```

### Local Database Setup

**PostgreSQL (Recommended):**
```bash
# Install PostgreSQL
# Create database
createdb skilltrack

# Set environment variable
export DATABASE_URL="postgresql+psycopg://localhost/skilltrack"

# Run migrations
python migrate_db.py
```

**SQLite (Development only):**
```bash
export DATABASE_URL="sqlite:///./skilltrack.db"
python migrate_db.py
```

## Production Best Practices

1. **Always backup database before schema changes**
2. **Test migrations locally first**
3. **Use staging environment for testing**
4. **Monitor error logs after deployment**
5. **Keep GEMINI_API_KEY secure**
6. **Regularly update dependencies**
7. **Use separate databases for dev/staging/production**

## Monitoring

- **Health Check**: `GET /health` - Returns `{"status": "ok"}`
- **Render Metrics**: Check CPU, memory, and request metrics in Render dashboard
- **Database Metrics**: Monitor connection count and query performance
- **Error Tracking**: Check logs for exceptions and errors
