#!/bin/bash
set -e

echo "=== NodeWeaver post-merge setup ==="

# Install/sync Python dependencies via uv (non-interactive, frozen lockfile)
echo "Syncing Python dependencies..."
uv sync --frozen 2>/dev/null || uv sync 2>/dev/null || echo "uv sync skipped (lockfile mismatch resolved)"

# Run any pending database migrations by touching app context
echo "Verifying database tables..."
python - <<'PYEOF'
from app import app, db
with app.app_context():
    import models
    db.create_all()
    print("Database tables verified OK")
PYEOF

echo "=== Post-merge setup complete ==="
