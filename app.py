import os
import logging
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

def create_app():
    # Create the app
    app = Flask(__name__)
    app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key-change-in-production")
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
    
    # Configure the database
    database_url = os.environ.get("DATABASE_URL", "postgresql://rag_user:rag_pass@localhost:5432/topicsense")
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_recycle": 300,
        "pool_pre_ping": True,
    }
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    
    # Initialize the app with the extension
    db.init_app(app)
    
    with app.app_context():
        # Import models to ensure tables are created
        import models
        db.create_all()
        
        # Initialize services
        from services.rag_engine_simple import SimpleRAGEngine
        app.rag_engine = SimpleRAGEngine(db)
        logger.info("Simple RAG Engine initialized")
    
    # Register blueprints
    from api.classifier import classifier_bp
    from api.topics import topics_bp
    
    app.register_blueprint(classifier_bp, url_prefix='/api/v1')
    app.register_blueprint(topics_bp, url_prefix='/api/v1')
    
    # Main routes
    @app.route('/')
    def index():
        return render_template('index.html')
    
    @app.route('/docs')
    def api_docs():
        return render_template('api_docs.html')
    
    @app.route('/test')
    def test_interface():
        return render_template('test_interface.html')
    
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
