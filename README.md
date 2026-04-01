# NodeWeaver - RAG Classifier API

![Version](https://img.shields.io/badge/Version-1.0.5-brightgreen) ![Python](https://img.shields.io/badge/Python-3.11%2B-blue) ![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15%2B-blue) ![Docker](https://img.shields.io/badge/Docker-Ready-blue)

**NodeWeaver** is an intelligent, production-ready RAG (Retrieval-Augmented Generation) classifier API designed for automatic task categorization with real-time audio processing capabilities. It integrates seamlessly with AxTask and Google Sheets to eliminate manual task classification through advanced topic emergence detection and weighted node convergence algorithms.

## 🤝 AxTask Contract Workflow

- **AxTask `main` is the public contract**: pull it, read it, and index it before changing compatibility logic in NodeWeaver.
- **AxTask stays read-only from this workflow**: do not implement fixes there from NodeWeaver work.
- **NodeWeaver adapts**: schema normalization, keyword heuristics, metadata handling, and docs should be updated here.
- **Compatibility changes require tests**: if AxTask behavior shifts, add or update focused AxTask tests in `tests/test_axtask_compatibility.py`.

## 🚀 Quick Start

```bash
# Clone and setup
git clone <your-repository-url>
cd nodeweaver && python -m venv venv && source venv/bin/activate

# Start with Docker (recommended)
docker-compose up -d

# Or local setup
pip install -e . && python main.py
```

**➜** Visit `http://localhost:5000` to get started! 

**📖** New here? Check out our [Getting Started Guide](GETTING_STARTED.md)

## 🚀 Features

### Core Capabilities
- **Automatic Text Classification**: Intelligent categorization across universal profiles plus the AxTask canonical categories `Crisis`, `Development`, `Meeting`, `Research`, `Maintenance`, `Administrative`, and `General`
- **Topic Emergence Detection**: Discovers new topics through weighted node convergence using DBSCAN clustering
- **Vector Similarity Search**: PostgreSQL with pgvector for high-performance semantic search
- **Batch Processing**: Process up to 100 texts simultaneously for efficiency
- **RESTful API**: Clean, well-documented API endpoints for easy integration

### Integration Support
- **AxTask Integration**: Seamless connection with AxTask for productivity automation
- **AxTask Contract Hardening**: Accepts AxTask payloads (`activity`, `notes`, `prerequisites`), preserves task metadata in batch requests, and normalizes output to AxTask-safe labels
- **Priority-Engine Signal Matching**: Uses AxTask-inspired urgency, impact, effort, tag, and time-sensitive boosts so NodeWeaver stays stricter than generic classifiers
- **Google Sheets**: Apps Script integration for automatic spreadsheet categorization
- **Extensible Architecture**: Easy to integrate with other productivity tools and platforms

### Advanced Features
- **Confidence Scoring**: Each classification includes a confidence score (0-1)
- **Similar Topic/Node Discovery**: Find related concepts and patterns
- **Training Capabilities**: Improve accuracy with custom training data
- **Performance Monitoring**: Built-in metrics and logging for system health
- **Caching**: Redis integration for improved response times
- **Meeting & Debate Topic Tracking**: Continuously identify when participants change topics, dwell on specific ones, or diverge into tangents. Useful for meeting summarization, political discourse analysis, and podcast breakdowns.
- **Logical Fallacy Heuristics**: Infer topic shifts that defy internal consistency, helping flag potential red herrings, strawman arguments, or non sequiturs. This is built on the foundation of graph-weight discontinuities or abrupt semantic distance jumps between nodes.
- **Temporal Topic Heatmaps**: Visualize which topics dominate in a time window and how they evolve across sessions. Ideal for trend analysis or longitudinal research.

## 🏗️ Architecture

NodeWeaver uses a sophisticated multi-layer architecture:

