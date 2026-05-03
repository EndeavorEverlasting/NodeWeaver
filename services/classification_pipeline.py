"""Layered classification pipeline for NodeWeaver.

Layer 1 — NodeWeaver Internal (SimpleRAGEngine keyword scoring)
Layer 2 — RAG Augmentation (DB node/topic retrieval + re-scoring)
Layer 3 — Universal Zero-Shot Fallback (HuggingFace zero-shot)
"""
import json
import logging
import time
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)

_CATEGORY_CACHE_TTL = 60  # seconds


class ClassificationPipeline:
    """Orchestrates the three-layer classification sequence."""

    def __init__(self, rag_engine, db, l1_threshold: float = 0.7, l2_threshold: float = 0.55):
        self.rag_engine = rag_engine
        self.db = db
        self.l1_threshold = l1_threshold
        self.l2_threshold = l2_threshold

        self._zs_pipeline = None
        self._zs_loaded = False
        self._zs_available = True

        self._category_cache: List[str] = []
        self._category_cache_ts: float = 0.0

        logger.info(
            "ClassificationPipeline initialized — L1 threshold=%.2f, L2 threshold=%.2f",
            l1_threshold, l2_threshold,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def classify(self, text: str, metadata: Dict = None) -> Dict[str, Any]:
        """Run layered classification and return an enriched result dict."""
        metadata = metadata or {}
        layer_debug: Dict[str, Any] = {}

        # ------ Layer 1 — internal RAG engine ------
        l1_result = self.rag_engine.classify_text(text, metadata)
        l1_category = l1_result.get('predicted_category', 'other')
        l1_confidence = l1_result.get('confidence_score', 0.0)
        layer_debug['layer1'] = {'category': l1_category, 'confidence': l1_confidence}

        if l1_confidence >= self.l1_threshold and l1_category != 'other':
            return self._build_response(l1_result, 'nodeweaver_rag', l1_confidence, layer_debug)

        # ------ Layer 2 — RAG-augmented re-scoring ------
        l2_category, l2_confidence = self._rag_augmented_classify(text, l1_result)
        layer_debug['layer2'] = {'category': l2_category, 'confidence': l2_confidence}

        if l2_confidence >= self.l2_threshold and l2_category != 'other':
            result = dict(l1_result)
            result['predicted_category'] = l2_category
            result['confidence_score'] = l2_confidence
            return self._build_response(result, 'rag_augmented', l2_confidence, layer_debug)

        # ------ Layer 3 — universal zero-shot fallback ------
        l3_category, l3_confidence = self._universal_classify(text)
        layer_debug['layer3'] = {'category': l3_category, 'confidence': l3_confidence}

        # If zero-shot produced a real (non-other) category, always accept it —
        # it is the final fallback and is not compared against lower-layer scores.
        if l3_category != 'other' and l3_confidence > 0:
            result = dict(l1_result)
            result['predicted_category'] = l3_category
            result['confidence_score'] = l3_confidence
            return self._build_response(result, 'universal_classifier', l3_confidence, layer_debug)

        # Zero-shot was unavailable or also returned 'other'.
        # Pick the best non-other result from L1/L2; only fall back to 'other' if
        # every layer genuinely could not find a match.
        best_category, best_confidence, source = self._pick_best(
            l1_category, l1_confidence,
            l2_category, l2_confidence,
        )
        result = dict(l1_result)
        result['predicted_category'] = best_category
        result['confidence_score'] = best_confidence
        return self._build_response(result, source, best_confidence, layer_debug)

    # ------------------------------------------------------------------
    # Layer 2 — RAG Augmentation
    # ------------------------------------------------------------------

    def _rag_augmented_classify(self, text: str, l1_result: Dict) -> Tuple[str, float]:
        """Re-score categories using an augmented context built from DB nodes/topics."""
        try:
            # Retrieve semantically similar nodes from the database
            similar_nodes = self._fetch_similar_nodes_db(text, limit=5)

            # Also use similar_topics already returned by Layer 1
            similar_topics = l1_result.get('similar_topics', [])

            context_parts: List[str] = []

            # Add node content (primary augmentation signal)
            for node in similar_nodes:
                content = (node.get('content') or '').strip()
                if content:
                    context_parts.append(content)

            # Add topic labels as secondary signal
            for topic in similar_topics[:3]:
                label = (topic.get('label') or '').strip()
                category = (topic.get('category') or '').strip()
                if label:
                    context_parts.append(f"[{category}] {label}" if category else label)

            if not context_parts:
                return 'other', 0.0

            # Build augmented context window and re-score using whichever scoring
            # API the underlying engine exposes.
            augmented_text = text + " | " + " | ".join(context_parts)

            # SimpleRAGEngine exposes _predict_categories_multi (multi-label list)
            if hasattr(self.rag_engine, '_predict_categories_multi'):
                augmented_results = self.rag_engine._predict_categories_multi(augmented_text)
                if not augmented_results:
                    return 'other', 0.0
                for r in augmented_results:
                    if r.get('category', 'other') != 'other':
                        return r['category'], r.get('confidence', 0.0)
                return 'other', 0.0

            # Full RAGEngine exposes _predict_category(similar_topics, similar_nodes)
            if hasattr(self.rag_engine, '_predict_category'):
                aug_embedding = self.rag_engine.embedding_service.encode(augmented_text)
                aug_topics = self.rag_engine._find_similar_topics_db(aug_embedding)
                aug_nodes = self.rag_engine._find_similar_nodes_db(aug_embedding)
                category, confidence = self.rag_engine._predict_category(aug_topics, aug_nodes)
                return category, confidence

            return 'other', 0.0

        except Exception as e:
            logger.warning("Layer 2 RAG augmentation failed: %s", e)
            return 'other', 0.0

    def _fetch_similar_nodes_db(self, text: str, limit: int = 5) -> List[Dict]:
        """Retrieve top-N nodes from the DB ranked by embedding similarity to text.

        Falls back to keyword overlap if embedding comparison fails.
        """
        try:
            from models import Node

            # Compute query embedding
            query_vec = self.rag_engine.embedding_service.encode(text)

            # Load all nodes (bounded query; in production this would be pgvector)
            nodes = self.db.session.query(Node).filter(Node.embedding.isnot(None)).limit(200).all()

            scored: List[Tuple[float, Dict]] = []
            for node in nodes:
                try:
                    node_vec = json.loads(node.embedding)
                    sim = self._cosine_similarity(query_vec, node_vec)
                    scored.append((sim, {
                        'node_id': node.node_id,
                        'content': node.content,
                        'category': node.category,
                        'similarity': sim,
                    }))
                except Exception:
                    continue

            # Sort descending by similarity
            scored.sort(key=lambda x: x[0], reverse=True)
            return [entry for _, entry in scored[:limit]]

        except Exception as e:
            logger.warning("DB node retrieval for Layer 2 failed: %s", e)
            return []

    @staticmethod
    def _cosine_similarity(v1: List[float], v2: List[float]) -> float:
        """Compute cosine similarity between two vectors."""
        if not v1 or not v2 or len(v1) != len(v2):
            return 0.0
        dot = sum(a * b for a, b in zip(v1, v2))
        norm1 = sum(a * a for a in v1) ** 0.5
        norm2 = sum(b * b for b in v2) ** 0.5
        if norm1 == 0.0 or norm2 == 0.0:
            return 0.0
        return dot / (norm1 * norm2)

    # ------------------------------------------------------------------
    # Layer 3 — Universal Zero-Shot Classifier
    # ------------------------------------------------------------------

    def _load_zero_shot_pipeline(self) -> bool:
        """Lazily load the HuggingFace zero-shot pipeline. Returns True on success."""
        if self._zs_loaded:
            return self._zs_pipeline is not None

        self._zs_loaded = True
        if not self._zs_available:
            return False

        try:
            import os
            from transformers import pipeline as hf_pipeline
            model_name = os.environ.get('NW_ZS_MODEL', 'cross-encoder/nli-deberta-v3-small')
            logger.info("Loading zero-shot model: %s", model_name)
            self._zs_pipeline = hf_pipeline(
                'zero-shot-classification',
                model=model_name,
                device=-1,
            )
            logger.info("Zero-shot model loaded successfully")
            return True
        except Exception as e:
            logger.warning(
                "Zero-shot model could not be loaded — Layer 3 will be skipped: %s", e
            )
            self._zs_pipeline = None
            self._zs_available = False
            return False

    def _universal_classify(self, text: str) -> Tuple[str, float]:
        """Classify text using the HuggingFace zero-shot pipeline."""
        try:
            if not self._load_zero_shot_pipeline():
                return 'other', 0.0

            categories = self._get_known_categories()
            if not categories:
                return 'other', 0.0

            output = self._zs_pipeline(text, candidate_labels=categories, multi_label=False)
            if not output or not output.get('labels'):
                return 'other', 0.0

            top_label = output['labels'][0]
            top_score = float(output['scores'][0])
            return top_label, top_score

        except Exception as e:
            logger.warning("Layer 3 universal classify failed: %s", e)
            return 'other', 0.0

    # ------------------------------------------------------------------
    # Dynamic category list (cached)
    # ------------------------------------------------------------------

    def _get_known_categories(self) -> List[str]:
        """Return known categories from the Topic table, with short-lived cache."""
        now = time.time()
        if self._category_cache and (now - self._category_cache_ts) < _CATEGORY_CACHE_TTL:
            return self._category_cache

        try:
            from models import Topic
            rows = self.db.session.query(Topic.category).distinct().all()
            db_categories = [r[0] for r in rows if r[0]]
        except Exception as e:
            logger.warning("Could not query Topic categories: %s", e)
            db_categories = []

        from config import Config
        combined = list({*Config.DEFAULT_CATEGORIES, *db_categories})
        combined = [c for c in combined if c and c != 'other']

        self._category_cache = combined or Config.DEFAULT_CATEGORIES
        self._category_cache_ts = now
        return self._category_cache

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _pick_best(
        c1: str, s1: float,
        c2: str, s2: float,
    ) -> Tuple[str, float, str]:
        """Choose the best result from L1 and L2, preferring any non-other category.

        Only returns 'other' if every layer genuinely returned 'other'.
        """
        candidates = [
            (c2, s2, 'rag_augmented'),
            (c1, s1, 'nodeweaver_rag'),
        ]

        # Prefer non-other with highest confidence
        non_other = [(c, s, src) for c, s, src in candidates if c != 'other' and s > 0]
        if non_other:
            return max(non_other, key=lambda x: x[1])

        # Every layer returned 'other' — pick the most confident 'other'
        return max(candidates, key=lambda x: x[1])

    @staticmethod
    def _build_response(
        base: Dict[str, Any],
        source: str,
        confidence: float,
        layer_debug: Dict,
    ) -> Dict[str, Any]:
        result = dict(base)
        result['classification_source'] = source
        result['confidence_score'] = confidence
        result['layer_debug'] = layer_debug
        return result
