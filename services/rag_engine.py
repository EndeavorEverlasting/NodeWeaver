import json
import logging
import numpy as np
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from models import Node, Topic, Document, ClassificationLog
from services.embeddings import EmbeddingService
from config import Config

logger = logging.getLogger(__name__)


class RAGEngine:
    """Full RAG engine using sentence-transformer embeddings for classification."""

    def __init__(self, db):
        self.db = db
        self.embedding_service = EmbeddingService()

        self.categories = list(Config.DEFAULT_CATEGORIES)
        self.similarity_threshold = 0.6
        self.confidence_threshold = 0.7

        logger.info("RAG Engine initialized")

    # ------------------------------------------------------------------
    # Public classification API
    # ------------------------------------------------------------------

    def classify_text(self, text: str, metadata: Dict = None) -> Dict[str, Any]:
        """Classify input text; return prediction with confidence and topic associations."""
        if not text or not text.strip():
            raise ValueError("Empty text provided")

        try:
            text_embedding = self.embedding_service.encode(text)

            # Multi-label keyword classification (Layer 1 signal)
            all_categories = self._predict_categories_multi(text)
            primary = all_categories[0] if all_categories else {'category': 'other', 'confidence': 0.3}

            # Embedding-based DB retrieval
            similar_topics = self._find_similar_topics_db(text_embedding)
            similar_nodes = self._find_similar_nodes_db(text_embedding)

            # Re-score using DB evidence
            db_category, db_confidence = self._predict_category(similar_topics, similar_nodes)

            # Pick best: prefer DB evidence if confidence is significant
            if db_category != 'other' and db_confidence >= self.confidence_threshold:
                predicted_category = db_category
                confidence_score = db_confidence
            else:
                predicted_category = primary['category']
                confidence_score = primary['confidence']

            # Associate with top matching topics
            topic_ids = [t['topic_id'] for t in similar_topics[:3]]

            doc = Document(
                content=text,
                embedding=json.dumps(text_embedding.tolist()),
                predicted_category=predicted_category,
                confidence_score=confidence_score,
                topic_ids=topic_ids,
                meta_data=metadata or {}
            )
            self.db.session.add(doc)
            self.db.session.commit()

            return {
                'predicted_category': predicted_category,
                'confidence_score': confidence_score,
                'all_categories': all_categories,
                'similar_topics': similar_topics,
                'similar_nodes': [
                    {'node_id': n['node_id'], 'content': n['content'],
                     'category': n['category'], 'similarity': n['similarity']}
                    for n in similar_nodes
                ],
                'topic_associations': topic_ids,
                'document_id': doc.doc_id,
            }

        except Exception as e:
            logger.error(f"Text classification failed: {str(e)}")
            raise

    def add_training_data(self, text: str, category: str, metadata: Dict = None) -> int:
        """Add a labelled training example; returns the stored document id."""
        try:
            if category not in self.categories:
                logger.warning(f"Unknown category: {category}. Adding.")
                self.categories.append(category)

            embedding = self.embedding_service.encode(text)
            node = self._find_or_create_node(text, embedding, category, metadata)

            # Also persist as a Document so the training example is queryable
            doc = Document(
                content=text,
                embedding=json.dumps(embedding.tolist()),
                predicted_category=category,
                confidence_score=0.95,
                meta_data={
                    **(metadata or {}),
                    'is_training_data': True,
                    'training_timestamp': str(datetime.utcnow()),
                }
            )
            self.db.session.add(doc)
            self.db.session.commit()

            self._update_category_keywords(text, category)
            logger.info(f"Added training data: {category} — {text[:50]}...")
            return doc.doc_id

        except Exception as e:
            logger.error(f"Training data addition failed: {str(e)}")
            raise

    def correct_classification(self, text: str, correct_category: str,
                               metadata: Dict = None) -> bool:
        """Correct a misclassification and learn from it."""
        try:
            original = ClassificationLog.query.filter_by(
                input_text=text
            ).order_by(ClassificationLog.log_id.desc()).first()

            correction_meta = {
                **(metadata or {}),
                'original_category': original.predicted_category if original else None,
                'corrected_category': correct_category,
                'correction_timestamp': str(datetime.utcnow()),
                'is_correction': True,
            }

            self.add_training_data(text, correct_category, correction_meta)

            if original:
                logger.info(
                    f"Corrected: '{text[:50]}' from {original.predicted_category} to {correct_category}"
                )
                return True

            logger.warning(f"No original log found for: {text[:50]}")
            return False

        except Exception as e:
            logger.error(f"Correction failed: {str(e)}")
            raise

    def detect_emerging_topics(self) -> List[Dict]:
        """Detect emerging topics from weighted node convergence."""
        try:
            from services.topic_detector import TopicDetector
            detector = TopicDetector(self.embedding_service)
            topics = detector.detect_emerging_topics()
            return topics
        except Exception as e:
            logger.error(f"Topic detection failed: {str(e)}")
            # Fallback: return existing top-weighted topics
            try:
                topics = Topic.query.order_by(Topic.total_weight.desc()).limit(5).all()
                return [t.to_dict() for t in topics]
            except Exception:
                return []

    def find_similar_topics(self, text: str, limit: int = 10,
                            threshold: float = 0.5) -> List[Dict]:
        """Find topics similar to input text using embedding similarity."""
        try:
            query_vec = self.embedding_service.encode(text)
            return self._find_similar_topics_db(query_vec, limit=limit, threshold=threshold)
        except Exception as e:
            logger.error(f"Similar topic search failed: {str(e)}")
            return []

    def get_topics(self, limit: int = 10) -> List[Dict]:
        """Return all stored topics."""
        try:
            topics = Topic.query.limit(limit).all()
            return [t.to_dict() for t in topics]
        except Exception as e:
            logger.error(f"Failed to get topics: {str(e)}")
            return []

    def create_topic(self, label: str, category: str = None) -> Dict:
        """Create a new topic."""
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

    # ------------------------------------------------------------------
    # Internal helpers — embedding-based similarity (Python-side)
    # ------------------------------------------------------------------

    def _find_similar_topics_db(self, query_embedding: np.ndarray, limit: int = 5,
                                 threshold: float = 0.0) -> List[Dict]:
        """Return topics ranked by cosine similarity; uses Python-side comparison
        because the centroid_embedding column is JSON Text, not a pgvector column."""
        try:
            topics = self.db.session.query(Topic).filter(
                Topic.centroid_embedding.isnot(None)
            ).limit(500).all()

            scored: List[Tuple[float, Dict]] = []
            for topic in topics:
                try:
                    vec = json.loads(topic.centroid_embedding)
                    sim = self._cosine_similarity(query_embedding.tolist(), vec)
                    if sim >= threshold:
                        scored.append((sim, {
                            'topic_id': topic.topic_id,
                            'label': topic.label,
                            'category': topic.category,
                            'total_weight': topic.total_weight,
                            'coherence_score': topic.coherence_score,
                            'similarity': sim,
                        }))
                except Exception:
                    continue

            scored.sort(key=lambda x: x[0], reverse=True)
            return [entry for _, entry in scored[:limit]]

        except Exception as e:
            logger.error(f"Topic similarity search failed: {str(e)}")
            return []

    def _find_similar_nodes_db(self, query_embedding: np.ndarray, limit: int = 10) -> List[Dict]:
        """Return nodes ranked by cosine similarity above similarity_threshold."""
        try:
            nodes = self.db.session.query(Node).filter(
                Node.embedding.isnot(None)
            ).limit(500).all()

            scored: List[Tuple[float, Dict]] = []
            for node in nodes:
                try:
                    vec = json.loads(node.embedding)
                    sim = self._cosine_similarity(query_embedding.tolist(), vec)
                    if sim > self.similarity_threshold:
                        scored.append((sim, {
                            'node_id': node.node_id,
                            'content': node.content,
                            'category': node.category,
                            'weight': node.weight,
                            'frequency': node.frequency,
                            'similarity': sim,
                        }))
                except Exception:
                    continue

            scored.sort(key=lambda x: x[0], reverse=True)
            return [entry for _, entry in scored[:limit]]

        except Exception as e:
            logger.error(f"Node similarity search failed: {str(e)}")
            return []

    def _predict_category(self, similar_topics: List[Dict],
                          similar_nodes: List[Dict]) -> Tuple[str, float]:
        """Predict category from DB evidence (topics + nodes), weighted by similarity."""
        try:
            category_scores: Dict[str, float] = {}

            for topic in similar_topics:
                cat = topic.get('category')
                if cat:
                    coherence = topic.get('coherence_score') or 1.0
                    weight = topic.get('total_weight') or 1.0
                    score = topic['similarity'] * coherence * weight
                    category_scores[cat] = category_scores.get(cat, 0.0) + score

            for node in similar_nodes:
                cat = node.get('category')
                if cat:
                    w = node.get('weight') or 1.0
                    score = node['similarity'] * w * 0.5
                    category_scores[cat] = category_scores.get(cat, 0.0) + score

            if not category_scores:
                return 'other', 0.0

            best_cat = max(category_scores, key=category_scores.get)
            max_score = category_scores[best_cat]
            total = sum(category_scores.values())
            confidence = max_score / total if total > 0 else 0.0

            if confidence < self.confidence_threshold:
                return 'other', confidence

            return best_cat, confidence

        except Exception as e:
            logger.error(f"Category prediction failed: {str(e)}")
            return 'other', 0.0

    def _predict_categories_multi(self, text: str) -> List[Dict[str, Any]]:
        """Multi-label keyword classification — mirrors SimpleRAGEngine logic."""
        text_lower = text.lower().strip()
        category_keywords = {
            'work': {
                'keywords': ['work', 'job', 'office', 'meeting', 'client', 'project', 'deadline',
                             'business', 'colleague', 'boss', 'schedule', 'conference', 'presentation'],
                'base_confidence': 0.8
            },
            'personal': {
                'keywords': ['personal', 'family', 'home', 'myself', 'friend', 'hobby', 'vacation',
                             'weekend', 'birthday', 'gift', 'celebration', 'party', 'relationship'],
                'base_confidence': 0.8
            },
            'shopping': {
                'keywords': ['shopping', 'store', 'purchase', 'retail', 'order', 'delivery',
                             'product', 'find', 'get', 'buy', 'cake', 'food', 'groceries',
                             'market', 'price'],
                'base_confidence': 0.7
            },
            'academic': {
                'keywords': ['study', 'school', 'learn', 'academic', 'research', 'university',
                             'exam', 'homework', 'class', 'education', 'course', 'assignment'],
                'base_confidence': 0.8
            },
            'health': {
                'keywords': ['health', 'doctor', 'medical', 'sick', 'hospital', 'medicine',
                             'exercise', 'diet', 'wellness', 'fitness', 'treatment'],
                'base_confidence': 0.8
            },
            'finance': {
                'keywords': ['money', 'buy', 'pay', 'finance', 'bank', 'budget', 'investment',
                             'expense', 'income', 'cost', 'payment', 'savings'],
                'base_confidence': 0.8
            },
            'technology': {
                'keywords': ['technology', 'computer', 'software', 'app', 'website', 'internet',
                             'digital', 'code', 'tech', 'online', 'system'],
                'base_confidence': 0.7
            },
            'entertainment': {
                'keywords': ['movie', 'music', 'game', 'entertainment', 'tv', 'show', 'concert',
                             'sports', 'fun', 'play', 'watch'],
                'base_confidence': 0.7
            },
            'travel': {
                'keywords': ['travel', 'trip', 'vacation', 'hotel', 'flight', 'destination',
                             'tourism', 'visit', 'journey'],
                'base_confidence': 0.7
            },
            'political': {
                'keywords': ['political', 'government', 'policy', 'vote', 'election', 'senator',
                             'congress', 'politics', 'law', 'city council', 'council', 'zoning',
                             'municipal', 'civic', 'public hearing', 'ordinance', 'regulation'],
                'base_confidence': 0.85
            },
            'legal': {
                'keywords': ['legal', 'law', 'court', 'judge', 'lawyer', 'attorney', 'lawsuit',
                             'contract', 'regulation', 'compliance', 'zoning', 'ordinance',
                             'municipal law', 'jurisdiction', 'statute'],
                'base_confidence': 0.85
            },
        }

        results = []
        for category, cfg in category_keywords.items():
            matches = sum(1 for kw in cfg['keywords'] if kw in text_lower)
            if matches > 0:
                confidence = min(0.9, cfg['base_confidence'] + (matches - 1) * 0.05)
                results.append({'category': category, 'confidence': confidence,
                                'keyword_matches': matches})

        results.sort(key=lambda x: x['confidence'], reverse=True)

        if not results:
            results.append({'category': 'other', 'confidence': 0.3, 'keyword_matches': 0})

        return results

    # ------------------------------------------------------------------
    # Node management
    # ------------------------------------------------------------------

    def _find_or_create_node(self, text: str, embedding: np.ndarray,
                             category: str, metadata: Dict = None) -> Node:
        """Find a near-duplicate node or create a fresh one."""
        try:
            similar = self._find_similar_nodes_db(embedding, limit=1)

            if similar and similar[0]['similarity'] > 0.95:
                node = self.db.session.get(Node, similar[0]['node_id'])
                if node:
                    node.frequency = (node.frequency or 0) + 1
                    node.weight = (node.weight or 1.0) * 0.9 + 0.1
                    if not node.category and category:
                        node.category = category
                    self.db.session.commit()
                    return node

            node = Node(
                content=text,
                embedding=json.dumps(embedding.tolist()),
                category=category,
                weight=1.0,
                frequency=1,
                meta_data=metadata or {}
            )
            self.db.session.add(node)
            self.db.session.commit()
            return node

        except Exception as e:
            logger.error(f"Node creation/update failed: {str(e)}")
            self.db.session.rollback()
            raise

    def _update_category_keywords(self, text: str, category: str):
        """Log newly learned keywords (informational — no DB writes needed)."""
        words = [w for w in text.lower().split() if len(w) > 3 and w.isalpha()]
        logger.info(f"Learned keywords for {category}: {words[:5]}")

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    @staticmethod
    def _cosine_similarity(v1: List[float], v2: List[float]) -> float:
        if not v1 or not v2 or len(v1) != len(v2):
            return 0.0
        dot = sum(a * b for a, b in zip(v1, v2))
        n1 = sum(a * a for a in v1) ** 0.5
        n2 = sum(b * b for b in v2) ** 0.5
        if n1 == 0.0 or n2 == 0.0:
            return 0.0
        return dot / (n1 * n2)
