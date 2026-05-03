import os
import logging
import threading
from datetime import datetime
from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)


def _add_cors_headers(response, allowed_origins):
    origin = request.headers.get('Origin', '')
    if '*' in allowed_origins:
        response.headers['Access-Control-Allow-Origin'] = '*'
    elif origin in allowed_origins:
        response.headers['Access-Control-Allow-Origin'] = origin
        response.headers['Vary'] = 'Origin'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, X-API-Key, Authorization'
    response.headers['Access-Control-Max-Age'] = '86400'
    return response


def create_app():
    app = Flask(__name__)
    app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key-change-in-production")
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

    # CORS configuration from env var (comma-separated origins, default '*' in dev)
    raw_origins = os.environ.get('NODEWEAVER_ALLOWED_ORIGINS', '*')
    allowed_origins = [o.strip() for o in raw_origins.split(',') if o.strip()]
    app.config['ALLOWED_ORIGINS'] = allowed_origins

    # Configure the database
    database_url = os.environ.get("DATABASE_URL", "postgresql://rag_user:rag_pass@localhost:5432/topicsense")
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_recycle": 300,
        "pool_pre_ping": True,
    }
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)

    if not hasattr(app, 'extensions'):
        app.extensions = {}

    with app.app_context():
        import models
        db.create_all()

        from services.rag_engine_simple import SimpleRAGEngine
        from services.classification_pipeline import ClassificationPipeline
        from config import Config

        rag_engine = SimpleRAGEngine(db)
        app.extensions['rag_engine'] = rag_engine

        pipeline = ClassificationPipeline(
            rag_engine=rag_engine,
            db=db,
            l1_threshold=Config.NW_L1_CONFIDENCE_THRESHOLD,
            l2_threshold=Config.NW_L2_CONFIDENCE_THRESHOLD,
        )
        app.extensions['classification_pipeline'] = pipeline
        logger.info("Simple RAG Engine and Classification Pipeline initialized")

    # ------------------------------------------------------------------ #
    # CORS: handle OPTIONS preflight before any auth check fires          #
    # ------------------------------------------------------------------ #
    @app.before_request
    def handle_preflight():
        if request.method == 'OPTIONS':
            response = app.make_default_options_response()
            return _add_cors_headers(response, app.config['ALLOWED_ORIGINS'])

    @app.after_request
    def apply_cors(response):
        return _add_cors_headers(response, app.config['ALLOWED_ORIGINS'])

    # ------------------------------------------------------------------ #
    # API key authentication for /api/v1/* routes (except /health)        #
    # ------------------------------------------------------------------ #
    api_key = os.environ.get('NODEWEAVER_API_KEY')

    @app.before_request
    def check_api_key():
        if not request.path.startswith('/api/v1/'):
            return
        if request.path == '/api/v1/health':
            return
        if request.method == 'OPTIONS':
            return
        if not api_key:
            # Dev mode: no key configured, skip validation
            return
        provided = request.headers.get('X-API-Key', '')
        if provided != api_key:
            return jsonify({
                'error': 'Unauthorized',
                'message': 'Missing or invalid X-API-Key header'
            }), 401

    # Register blueprints
    from api.classifier import classifier_bp
    from api.topics import topics_bp
    from api.audio import audio_bp, init_audio_processor

    app.register_blueprint(classifier_bp, url_prefix='/api/v1')
    app.register_blueprint(topics_bp, url_prefix='/api/v1')
    app.register_blueprint(audio_bp, url_prefix='/api/v1')

    with app.app_context():
        init_audio_processor(app.extensions['rag_engine'])

    # ------------------------------------------------------------------ #
    # /api/v1/health — unauthenticated, AxTask polls this                 #
    # ------------------------------------------------------------------ #
    @app.route('/api/v1/health')
    def api_health():
        """Structured health endpoint for AxTask connectivity checks"""
        from config import Config
        db_status = 'healthy'
        try:
            db.session.execute(db.text('SELECT 1'))
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            db_status = 'unhealthy'

        rag_engine = app.extensions.get('rag_engine')
        embedding_status = 'unavailable'
        if rag_engine is not None:
            try:
                embedding_service = getattr(rag_engine, 'embedding_service', None)
                if embedding_service is not None:
                    vec = embedding_service.encode('probe')
                    embedding_status = 'ready' if vec is not None and len(vec) > 0 else 'unavailable'
                else:
                    embedding_status = 'ready'
            except Exception:
                embedding_status = 'unavailable'

        overall_healthy = db_status == 'healthy' and embedding_status == 'ready'
        status_code = 200 if overall_healthy else 503
        return jsonify({
            'status': 'healthy' if overall_healthy else 'degraded',
            'service': 'nodeweaver',
            'version': Config.APP_VERSION,
            'api_version': Config.API_VERSION,
            'components': {
                'database': db_status,
                'embedding_model': embedding_status,
            },
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }), status_code

    # ------------------------------------------------------------------ #
    # Legacy /health (load-balancer / Docker healthcheck)                 #
    # ------------------------------------------------------------------ #
    @app.route('/health')
    def health_check():
        """Health check endpoint for load balancers and monitoring"""
        from config import Config
        try:
            db.session.execute(db.text('SELECT 1'))
            db_status = 'healthy'
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            db_status = 'unhealthy'

        return jsonify({
            'status': 'healthy' if db_status == 'healthy' else 'unhealthy',
            'version': Config.APP_VERSION,
            'database': db_status,
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }), 200 if db_status == 'healthy' else 503

    # Main UI routes
    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/docs')
    def api_docs():
        return render_template('api_docs.html')

    @app.route('/test')
    def test_interface():
        return render_template('test_interface.html')

    @app.route('/live')
    def live_audio():
        return render_template('live_audio.html')

    @app.route('/api/v1/version')
    def version_info():
        from config import Config
        return jsonify({
            'version': Config.APP_VERSION,
            'api_version': Config.API_VERSION,
            'name': 'NodeWeaver',
            'description': 'RAG Classifier API for automatic task categorization with audio processing capabilities'
        })

    @app.errorhandler(404)
    def not_found(error):
        return jsonify({'error': 'Endpoint not found'}), 404

    @app.errorhandler(500)
    def internal_error(error):
        logger.error(f"Internal server error: {error}")
        return jsonify({'error': 'Internal server error'}), 500

    return app


# Create app instance
app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
