# TopicSense - RAG Classifier API

**TopicSense** is an intelligent, platform-independent RAG (Retrieval-Augmented Generation) classifier API designed for automatic task categorization. It integrates seamlessly with AxTask and Google Sheets to eliminate manual task classification through advanced topic emergence detection and weighted node convergence algorithms.

![TopicSense Architecture](https://img.shields.io/badge/Architecture-RAG%20Classifier-blue) ![Python](https://img.shields.io/badge/Python-3.8%2B-green) ![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15%2B-blue) ![Docker](https://img.shields.io/badge/Docker-Ready-blue)

## 🚀 Features

### Core Capabilities
- **Automatic Text Classification**: Intelligent categorization into personal, work, academic, political, and other categories
- **Topic Emergence Detection**: Discovers new topics through weighted node convergence using DBSCAN clustering
- **Vector Similarity Search**: PostgreSQL with pgvector for high-performance semantic search
- **Batch Processing**: Process up to 100 texts simultaneously for efficiency
- **RESTful API**: Clean, well-documented API endpoints for easy integration

### Integration Support
- **AxTask Integration**: Seamless connection with AxTask for productivity automation
- **Google Sheets**: Apps Script integration for automatic spreadsheet categorization
- **Extensible Architecture**: Easy to integrate with other productivity tools and platforms

### Advanced Features
- **Confidence Scoring**: Each classification includes a confidence score (0-1)
- **Similar Topic/Node Discovery**: Find related concepts and patterns
- **Training Capabilities**: Improve accuracy with custom training data
- **Performance Monitoring**: Built-in metrics and logging for system health
- **Caching**: Redis integration for improved response times

## 🏗️ Architecture

TopicSense uses a sophisticated multi-layer architecture:

