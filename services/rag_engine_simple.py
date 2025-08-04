"""Simple RAG engine using basic text classification"""
import logging
import json
from typing import List, Dict, Any, Optional
from models import Node, Topic, Document, ClassificationLog
from services.embeddings_simple import SimpleEmbeddingService
from config import Config

logger = logging.getLogger(__name__)

class SimpleRAGEngine:
    """Simple RAG engine for text classification and topic management"""
    
    def __init__(self, db):
        self.db = db
        self.embedding_service = SimpleEmbeddingService()
        
        # Classification parameters
        self.categories = Config.DEFAULT_CATEGORIES
        self.similarity_threshold = 0.6
        self.confidence_threshold = 0.7
        
        logger.info("Simple RAG Engine initialized")
    
    def classify_text(self, text: str, metadata: Dict = None) -> Dict[str, Any]:
        """Classify input text and return category prediction with confidence"""
        try:
            if not text or len(text.strip()) == 0:
                raise ValueError("Empty text provided")
            
            # Generate embedding for input text
            text_embedding = self.embedding_service.encode(text)
            
            # Simple rule-based classification
            predicted_category, confidence = self._predict_category_simple(text)
            
            # Create document record
            doc = Document(
                content=text,
                embedding=json.dumps(text_embedding),
                predicted_category=predicted_category,
                confidence_score=confidence,
                meta_data=metadata or {}
            )
            
            self.db.session.add(doc)
            self.db.session.commit()
            
            # Log classification
            log = ClassificationLog(
                input_text=text,
                predicted_category=predicted_category,
                confidence_score=confidence,
                similar_topics=[],
                similar_nodes=[],
                processing_time=0.1,
                meta_data=metadata or {}
            )
            
            self.db.session.add(log)
            self.db.session.commit()
            
            return {
                'predicted_category': predicted_category,
                'confidence_score': confidence,
                'similar_topics': [],
                'similar_nodes': [],
                'document_id': doc.doc_id
            }
            
        except Exception as e:
            logger.error(f"Text classification failed: {str(e)}")
            raise
    
    def _predict_category_simple(self, text: str) -> tuple:
        """Simple rule-based category prediction"""
        text_lower = text.lower().strip()
        
        # Work-related keywords
        work_keywords = ['work', 'job', 'office', 'meeting', 'client', 'project', 'deadline', 'business', 'colleague', 'boss']
        if any(keyword in text_lower for keyword in work_keywords):
            return 'work', 0.8
        
        # Personal keywords
        personal_keywords = ['personal', 'family', 'home', 'myself', 'friend', 'hobby', 'vacation', 'weekend']
        if any(keyword in text_lower for keyword in personal_keywords):
            return 'personal', 0.8
        
        # Academic keywords
        academic_keywords = ['study', 'school', 'learn', 'academic', 'research', 'university', 'exam', 'homework', 'class']
        if any(keyword in text_lower for keyword in academic_keywords):
            return 'academic', 0.8
        
        # Health keywords
        health_keywords = ['health', 'doctor', 'medical', 'sick', 'hospital', 'medicine', 'exercise', 'diet']
        if any(keyword in text_lower for keyword in health_keywords):
            return 'health', 0.8
        
        # Finance keywords
        finance_keywords = ['money', 'buy', 'pay', 'finance', 'bank', 'budget', 'investment', 'expense', 'income']
        if any(keyword in text_lower for keyword in finance_keywords):
            return 'finance', 0.8
        
        # Technology keywords
        tech_keywords = ['technology', 'computer', 'software', 'app', 'website', 'internet', 'digital', 'code']
        if any(keyword in text_lower for keyword in tech_keywords):
            return 'technology', 0.7
        
        # Entertainment keywords
        entertainment_keywords = ['movie', 'music', 'game', 'entertainment', 'tv', 'show', 'concert', 'sports']
        if any(keyword in text_lower for keyword in entertainment_keywords):
            return 'entertainment', 0.7
        
        # Travel keywords
        travel_keywords = ['travel', 'trip', 'vacation', 'hotel', 'flight', 'destination', 'tourism']
        if any(keyword in text_lower for keyword in travel_keywords):
            return 'travel', 0.7
        
        # Shopping keywords
        shopping_keywords = ['shopping', 'store', 'purchase', 'retail', 'order', 'delivery', 'product']
        if any(keyword in text_lower for keyword in shopping_keywords):
            return 'shopping', 0.7
        
        # Political keywords
        political_keywords = ['political', 'government', 'policy', 'vote', 'election', 'senator', 'congress']
        if any(keyword in text_lower for keyword in political_keywords):
            return 'political', 0.7
        
        # Default to 'other' with lower confidence
        return 'other', 0.5
    
    def get_topics(self, limit: int = 10) -> List[Dict]:
        """Get all topics"""
        try:
            topics = Topic.query.limit(limit).all()
            return [topic.to_dict() for topic in topics]
        except Exception as e:
            logger.error(f"Failed to get topics: {str(e)}")
            return []
    
    def create_topic(self, label: str, category: str = None) -> Dict:
        """Create a new topic"""
        try:
            topic = Topic(
                label=label,
                category=category,
                total_weight=1.0,
                coherence_score=0.8,
                meta_data={}
            )
            
            self.db.session.add(topic)
            self.db.session.commit()
            
            return topic.to_dict()
            
        except Exception as e:
            logger.error(f"Failed to create topic: {str(e)}")
            raise