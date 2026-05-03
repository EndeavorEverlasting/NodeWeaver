import os


class Config:
    # Database configuration
    DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://rag_user:rag_pass@localhost:5432/nodeweaver')

    # Flask configuration
    SECRET_KEY = os.environ.get('SESSION_SECRET', 'dev-secret-key-change-in-production')

    # RAG Engine configuration
    EMBEDDING_MODEL = os.environ.get('EMBEDDING_MODEL', 'all-MiniLM-L6-v2')
    VECTOR_DIMENSION = int(os.environ.get('VECTOR_DIMENSION', '384'))

    # Topic detection thresholds
    CONVERGENCE_THRESHOLD = float(os.environ.get('CONVERGENCE_THRESHOLD', '0.7'))
    MIN_CLUSTER_SIZE = int(os.environ.get('MIN_CLUSTER_SIZE', '3'))
    COHERENCE_THRESHOLD = float(os.environ.get('COHERENCE_THRESHOLD', '0.6'))

    # Classification categories
    DEFAULT_CATEGORIES = [
        'personal', 'work', 'academic', 'political', 'legal', 'health', 'finance',
        'entertainment', 'travel', 'shopping', 'technology', 'other'
    ]

    # API configuration
    API_VERSION = 'v1'
    APP_VERSION = '1.0.3'
    MAX_INPUT_LENGTH = int(os.environ.get('MAX_INPUT_LENGTH', '10000'))

    # Logging configuration
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')

    # Classification pipeline thresholds
    NW_L1_CONFIDENCE_THRESHOLD = float(os.environ.get('NW_L1_CONFIDENCE_THRESHOLD', '0.7'))
    NW_L2_CONFIDENCE_THRESHOLD = float(os.environ.get('NW_L2_CONFIDENCE_THRESHOLD', '0.55'))

    # Zero-shot model override (Layer 3)
    NW_ZS_MODEL = os.environ.get('NW_ZS_MODEL', 'cross-encoder/nli-deberta-v3-small')
    # Eagerly download and load the zero-shot model at startup when set to true
    NW_ZS_PRELOAD = os.environ.get('NW_ZS_PRELOAD', 'false').strip().lower() in ('1', 'true', 'yes')

    # AxTask integration — NodeWeaver side
    NODEWEAVER_API_KEY = os.environ.get('NODEWEAVER_API_KEY')
    NODEWEAVER_ALLOWED_ORIGINS = os.environ.get('NODEWEAVER_ALLOWED_ORIGINS', '*')
    AXTASK_WEBHOOK_URL = os.environ.get('AXTASK_WEBHOOK_URL')
