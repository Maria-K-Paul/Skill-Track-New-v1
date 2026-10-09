# Checks before deploying

Scripts used to test changes (for example a merge of Nizzy's `main`) against a **copy of the production
database** before they go live. Each script that writes data refuses to run against the production host, which it
reads from `skilltrack-api/.env`. Run them from `skilltrack-api/`.

## 1. Get a test database
Either:
- **Neon test branch (easiest).** In the Neon console: Branches → Create branch from `production`. Use its
  connection string as the test `DATABASE_URL`. Confirm it is really separate:
  `TEST_BRANCH_URL=<branch url> python checks/check_branch.py` ("separate branches: True"; the row counts match
  until tests start writing to the branch). It reads production from `.env`, so a `DATABASE_URL` set in the shell
  cannot fool it. Delete the branch afterwards.
- **Local PostgreSQL copy.** Create an empty database, then
  `python checks/copy_database.py --target <local url> [--backup-dir <folder>]`
  (with `DATABASE_URL` unset in the shell, so the source is production from `.env`, read-only).

## 2. Run the checks (set `DATABASE_URL` to the TEST database for each)
| Step | Command | Expected |
|---|---|---|
| Rows before | `python checks/row_counts.py BEFORE` | |
| Database script, twice | `python migrate_db.py` (twice) | "Migration completed" both times |
| Rows after | `python checks/row_counts.py AFTER` | same counts as before |
| Models vs tables | `python checks/schema_vs_models.py` | `serious mismatches: 0` |
| Every role's endpoints | `python checks/smoke_roles.py` | `server errors: 0` |
| Sessions & tokens | `python checks/set_demo_passwords.py` then `python checks/test_session_tokens.py` | 43/43 pass (rotation, theft detection, sign-out, upgrade handover incl. old tabs, deactivation) |
| Exam keys | `python checks/test_exam_keys.py` | all checks pass |
| Nizzy's feature tests | start `uvicorn app.main:app --port 8002` against the test database, then `python checks/run_feature_tests.py` | 18 PASS, 1 known FAIL (see the script) |
| Website | `npm --prefix ../skilltrack run build` | builds with no type errors |

Only after all of that: merge into `deploy-maria-safe` and push (Render deploys it and runs `migrate_db.py` on the
real database during the build).
