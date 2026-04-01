# Changelog

All notable changes to NodeWeaver will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.5] - 2026-04-01

### Added
- AxTask priority-engine signal boosts for urgency, impact, effort, due-soon language, and explicit urgency tags
- AxTask metadata merging from request payloads so classify, batch, train, and correction flows see the same task context
- Contributor workflow guidance documenting AxTask as a public, read-only contract that NodeWeaver must follow

### Changed
- Updated NodeWeaverAxTaskClient metadata capture to preserve AxTask scoring fields and canonical alternative categories
- Refreshed README, Getting Started, API docs, and workspace notes to center the AxTask-contract workflow
- Updated package and application version metadata to 1.0.5

### Fixed
- AxTask documentation examples that still showed generic categories or outdated client usage
- Install instructions and environment examples that still referenced stale TopicSense-era values
- AxTask client training requests no longer overwrite caller-provided metadata sources such as `axtask_historical`, and they avoid mutating the caller's training payload in place

## [1.0.4] - 2026-04-01

### Added
- AxTask-compatible `Crisis` classification profile support aligned with current AxTask expectations
- Batch metadata preservation for AxTask task arrays and client-side alternative category capture

### Changed
- Normalized AxTask profile results to canonical categories before returning API responses or storing training labels
- Hardened AxTask integration metadata so task identifiers, schedule fields, and source markers stay attached during classify/train flows
- Updated package and application version metadata to 1.0.4

### Fixed
- Prioritization of crisis/emergency matches over generic development or maintenance keywords
- Legacy documentation branding drift that still referenced TopicSense in release notes and API examples

## [1.0.1] - 2025-08-04

### Fixed
- Flask extensions compatibility issue causing LSP type checking errors
- Service initialization pattern to use proper Flask extensions approach
- Application startup AttributeError in production deployment
- RAG engine storage using app.extensions['rag_engine'] instead of direct attribute

### Technical Details
- Moved from `app.rag_engine = SimpleRAGEngine(db)` to `app.extensions['rag_engine'] = rag_engine`
- Added proper extensions dictionary initialization check
- Resolved type checking warnings for Flask application structure

## [1.0.0] - 2025-08-04

### Added
- Complete RAG classification system with semantic embeddings
- Real-time audio processing and topic detection
- PostgreSQL database with pgvector for vector similarity search
- RESTful API with comprehensive endpoints
- Web interface for testing and live audio processing
- Topic emergence detection using clustering algorithms
- AxTask and Google Sheets integration capabilities
- Docker containerization support
- Comprehensive logging and error handling
- Production-ready configuration management
- Automated database schema creation
- Weighted node convergence algorithms
- Confidence scoring for classifications
- Batch processing capabilities
- Live audio streaming support

### Technical Details
- Flask 3.1.1+ web framework with blueprint architecture
- SQLAlchemy ORM with declarative models
- Sentence Transformers for 384-dimensional embeddings
- LibROSA and PyAudio for audio processing
- Scikit-learn for clustering and machine learning
- Gunicorn WSGI server for production deployment
- Environment-based configuration system
- Modular service architecture

### API Endpoints
- `POST /api/v1/classify` - Text classification
- `POST /api/v1/audio/upload` - Audio file processing
- `GET /api/v1/audio/live` - Live audio interface
- `GET /api/v1/topics` - Topic management
- `GET /api/v1/topics/detect` - Topic emergence detection

### Documentation
- Complete README with architecture overview
- API documentation with examples
- Integration guides for AxTask and Google Sheets
- Docker deployment instructions
- Configuration reference

## [Unreleased]

### Planned
- Enhanced audio processing algorithms
- Real-time collaboration features
- Advanced analytics dashboard
- Mobile application support
- Multi-language support

---

## Release Types

- **Added** for new features
- **Changed** for changes in existing functionality
- **Deprecated** for soon-to-be removed features
- **Removed** for now removed features
- **Fixed** for any bug fixes
- **Security** for vulnerability fixes