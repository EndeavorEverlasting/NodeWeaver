from app import app

if __name__ == '__main__':
    import os

    env = os.environ.get("FLASK_ENV", "").strip().lower()
    debug_env = os.environ.get("FLASK_DEBUG", "").strip().lower()
    debug = debug_env in ("1", "true", "yes", "on") or env == "development"
    port = int(os.environ.get("PORT", "5000"))
    app.run(host='0.0.0.0', port=port, debug=debug)
