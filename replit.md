# TopicSense - RAG Classifier API

## Overview

TopicSense is an intelligent Retrieval-Augmented Generation (RAG) classifier API designed for automatic task categorization and topic detection. The system leverages semantic embeddings and weighted node convergence to classify text into categories like personal, work, academic, political, and others. Built with a focus on productivity automation, TopicSense integrates seamlessly with AxTask and Google Sheets to provide intelligent task organization capabilities.

The system implements a sophisticated architecture where topics emerge from weighted node convergence using clustering algorithms, allowing for dynamic discovery of new patterns and categories in text data. This approach enables the system to adapt and learn from usage patterns while maintaining high classification accuracy.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Backend Framework
- **Flask Application**: Core web framework with RESTful API design
- **SQLAlchemy ORM**: Database abstraction layer with declarative models
- **Blueprint Architecture**: Modular API organization with separate blueprints for classification and topic management

### Database Design
- **PostgreSQL with pgvector**: Primary database with vector similarity search capabilities
- **Vector Embeddings**: 384-dimensional vectors using sentence-transformers
- **Node-Based Architecture**: Discrete semantic units stored as weighted nodes
- **Topic Emergence**: Topics automatically detected through weighted node convergence using DBSCAN clustering
- **Relationship Modeling**: Captures semantic relationships between nodes and topics

### Core Services
- **RAG Engine**: Central classification engine coordinating embeddings, similarity search, and prediction
- **Embedding Service**: Text-to-vector conversion using sentence-transformers (all-MiniLM-L6-v2)
- **Topic Detector**: Clustering-based topic emergence detection with configurable thresholds
- **Vector Similarity Search**: PostgreSQL pgvector with IVFFLAT indexing for fast nearest-neighbor search

### API Architecture
- **Classification Endpoint**: `/api/v1/classify` for single text classification
- **Topics Management**: `/api/v1/topics` for topic discovery and retrieval
- **Batch Processing**: Support for processing up to 100 texts simultaneously
- **Confidence Scoring**: Each classification includes confidence scores and similar topic/node discovery

### Frontend Components
- **Web Interface**: Bootstrap-based dark theme UI for testing and documentation
- **API Documentation**: Interactive documentation with code examples
- **Test Interface**: Real-time classification testing with metadata support

### Integration Layer
- **AxTask Client**: Python client for seamless AxTask productivity integration
- **Google Apps Script**: JavaScript integration for Google Sheets automation
- **RESTful API**: Platform-independent integration support

## External Dependencies

### Core Technologies
- **Flask**: Web framework and API server
- **SQLAlchemy**: Database ORM and query builder
- **PostgreSQL**: Primary database with JSONB and array support
- **pgvector**: Vector similarity search extension
- **sentence-transformers**: Text embedding generation (all-MiniLM-L6-v2 model)

### Machine Learning Libraries
- **scikit-learn**: Clustering algorithms (DBSCAN, KMeans) for topic detection
- **numpy**: Numerical computing for vector operations
- **scipy**: Scientific computing for similarity calculations

### Integration Services
- **AxTask**: Productivity automation platform integration
- **Google Sheets API**: Apps Script integration for spreadsheet automation
- **Google Apps Script**: Server-side JavaScript for Google Workspace

### Development Tools
- **Docker**: Containerization with PostgreSQL and pgvector setup
- **Bootstrap**: Frontend UI framework with dark theme
- **Font Awesome**: Icon library for UI components
- **JavaScript Fetch API**: Client-side API communication

### Optional Enhancements
- **Redis**: Caching layer for improved response times (configurable)
- **OpenAI API**: Alternative embedding provider (configurable)
- **Various Embedding Models**: Configurable through environment variables