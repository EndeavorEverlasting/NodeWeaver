from flask import Blueprint, request, jsonify, current_app
import logging
import threading
import os
from models import Topic, Node
from app import db

logger = logging.getLogger(__name__)

topics_bp = Blueprint('topics', __name__)


def _fire_webhook(event_type: str, payload: dict):
    """Fire a background HTTP POST to AXTASK_WEBHOOK_URL if configured.
    Errors are swallowed so NodeWeaver never blocks on the callback.
    """
    webhook_url = os.environ.get('AXTASK_WEBHOOK_URL', '').strip()
    if not webhook_url:
        return

    def _post():
        try:
            import urllib.request
            import json as _json
            body = _json.dumps({
                'event': event_type,
                'source': 'nodeweaver',
                'data': payload,
            }).encode('utf-8')
            req = urllib.request.Request(
                webhook_url,
                data=body,
                headers={
                    'Content-Type': 'application/json',
                    'User-Agent': 'NodeWeaver-Webhook/1.0',
                },
                method='POST',
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                logger.debug(f"Webhook delivered to {webhook_url}: {resp.status}")
        except Exception as e:
            logger.warning(f"Webhook delivery to {webhook_url} failed (non-blocking): {e}")

    t = threading.Thread(target=_post, daemon=True)
    t.start()


@topics_bp.route('/topics', methods=['GET'])
def get_topics():
    """Get all topics with optional filtering"""
    try:
        category = request.args.get('category')
        min_weight = request.args.get('min_weight', type=float)
        min_coherence = request.args.get('min_coherence', type=float)
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 100)

        query = Topic.query

        if category:
            query = query.filter(Topic.category == category)
        if min_weight is not None:
            query = query.filter(Topic.total_weight >= min_weight)
        if min_coherence is not None:
            query = query.filter(Topic.coherence_score >= min_coherence)

        topics = query.order_by(Topic.total_weight.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )

        return jsonify({
            'topics': [topic.to_dict() for topic in topics.items],
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': topics.total,
                'pages': topics.pages,
                'has_next': topics.has_next,
                'has_prev': topics.has_prev
            }
        })

    except Exception as e:
        logger.error(f"Error fetching topics: {str(e)}")
        return jsonify({'error': 'Failed to fetch topics', 'details': str(e)}), 500


@topics_bp.route('/topics/<int:topic_id>', methods=['GET'])
def get_topic_details(topic_id):
    """Get detailed information about a specific topic"""
    try:
        topic = Topic.query.get_or_404(topic_id)

        related_nodes = []
        if topic.origin_node_ids:
            related_nodes = Node.query.filter(Node.node_id.in_(topic.origin_node_ids)).all()

        topic_data = topic.to_dict()
        topic_data['related_nodes'] = [node.to_dict() for node in related_nodes]

        return jsonify(topic_data)

    except Exception as e:
        logger.error(f"Error fetching topic {topic_id}: {str(e)}")
        return jsonify({'error': 'Failed to fetch topic details', 'details': str(e)}), 500


@topics_bp.route('/topics/detect', methods=['POST'])
def detect_topics():
    """Trigger topic detection algorithm"""
    try:
        rag_engine = current_app.extensions['rag_engine']

        emerging_topics = rag_engine.detect_emerging_topics()

        def _serialize(item):
            """Handle both model instances (have .to_dict()) and plain dicts."""
            if hasattr(item, 'to_dict'):
                return item.to_dict()
            return item

        serialized = [_serialize(t) for t in emerging_topics]

        if serialized:
            _fire_webhook('topic_emergence', {
                'count': len(serialized),
                'topics': serialized,
            })

        return jsonify({
            'message': 'Topic detection completed',
            'emerging_topics': len(serialized),
            'topics': serialized
        })

    except Exception as e:
        logger.error(f"Topic detection error: {str(e)}")
        return jsonify({'error': 'Topic detection failed', 'details': str(e)}), 500


@topics_bp.route('/topics/similar', methods=['POST'])
def find_similar_topics():
    """Find topics similar to input text"""
    try:
        data = request.get_json()
        if not data or 'text' not in data:
            return jsonify({'error': 'No text provided'}), 400

        text = data['text']
        limit = min(data.get('limit', 10), 50)
        threshold = data.get('threshold', 0.5)

        rag_engine = current_app.extensions['rag_engine']

        similar_topics = rag_engine.find_similar_topics(text, limit=limit, threshold=threshold)

        return jsonify({
            'input_text': text,
            'similar_topics': similar_topics,
            'count': len(similar_topics)
        })

    except Exception as e:
        logger.error(f"Error finding similar topics: {str(e)}")
        return jsonify({'error': 'Failed to find similar topics', 'details': str(e)}), 500


@topics_bp.route('/nodes', methods=['GET'])
def get_nodes():
    """Get nodes with optional filtering"""
    try:
        category = request.args.get('category')
        min_weight = request.args.get('min_weight', type=float)
        search = request.args.get('search')
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 100)

        query = Node.query

        if category:
            query = query.filter(Node.category == category)
        if min_weight is not None:
            query = query.filter(Node.weight >= min_weight)
        if search:
            query = query.filter(Node.content.ilike(f'%{search}%'))

        nodes = query.order_by(Node.weight.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )

        return jsonify({
            'nodes': [node.to_dict() for node in nodes.items],
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': nodes.total,
                'pages': nodes.pages,
                'has_next': nodes.has_next,
                'has_prev': nodes.has_prev
            }
        })

    except Exception as e:
        logger.error(f"Error fetching nodes: {str(e)}")
        return jsonify({'error': 'Failed to fetch nodes', 'details': str(e)}), 500


@topics_bp.route('/stats', methods=['GET'])
def get_stats():
    """Get system statistics"""
    try:
        total_topics = Topic.query.count()
        total_nodes = Node.query.count()

        category_stats = db.session.execute(
            db.text("""
                SELECT category, COUNT(*) as count
                FROM topics
                WHERE category IS NOT NULL
                GROUP BY category
                ORDER BY count DESC
            """)
        ).fetchall()

        node_category_stats = db.session.execute(
            db.text("""
                SELECT category, COUNT(*) as count
                FROM nodes
                WHERE category IS NOT NULL
                GROUP BY category
                ORDER BY count DESC
            """)
        ).fetchall()

        return jsonify({
            'total_topics': total_topics,
            'total_nodes': total_nodes,
            'topic_categories': [{'category': row[0], 'count': row[1]} for row in category_stats],
            'node_categories': [{'category': row[0], 'count': row[1]} for row in node_category_stats]
        })

    except Exception as e:
        logger.error(f"Error fetching stats: {str(e)}")
        return jsonify({'error': 'Failed to fetch statistics', 'details': str(e)}), 500
