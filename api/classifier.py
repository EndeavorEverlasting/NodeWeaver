from flask import Blueprint, request, jsonify, current_app
import time
import logging
from utils.validators import validate_classification_input
from models import ClassificationLog
from app import db

logger = logging.getLogger(__name__)

classifier_bp = Blueprint('classifier', __name__)

@classifier_bp.route('/classify', methods=['POST'])
def classify_text():
    """Classify input text and return category prediction"""
    try:
        start_time = time.time()
        
        # Validate input
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        validation_error = validate_classification_input(data)
        if validation_error:
            return jsonify({'error': validation_error}), 400
        
        text = data['text']
        metadata = data.get('metadata', {})
        
        # Get RAG engine from app context
        rag_engine = current_app.rag_engine
        
        # Perform classification
        result = rag_engine.classify_text(text, metadata)
        
        processing_time = time.time() - start_time
        
        # Log classification
        log_entry = ClassificationLog(
            input_text=text,
            predicted_category=result.get('predicted_category'),
            confidence_score=result.get('confidence_score'),
            similar_topics=result.get('similar_topics'),
            similar_nodes=result.get('similar_nodes'),
            processing_time=processing_time,
            meta_data=metadata
        )
        db.session.add(log_entry)
        db.session.commit()
        
        # Add processing time to result
        result['processing_time'] = processing_time
        result['log_id'] = log_entry.log_id
        
        logger.info(f"Classification completed in {processing_time:.3f}s for text: {text[:50]}...")
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Classification error: {str(e)}")
        return jsonify({'error': 'Classification failed', 'details': str(e)}), 500

@classifier_bp.route('/classify/batch', methods=['POST'])
def classify_batch():
    """Classify multiple texts in batch"""
    try:
        start_time = time.time()
        
        data = request.get_json()
        if not data or 'texts' not in data:
            return jsonify({'error': 'No texts array provided'}), 400
        
        texts = data['texts']
        if not isinstance(texts, list) or len(texts) == 0:
            return jsonify({'error': 'texts must be a non-empty array'}), 400
        
        if len(texts) > 100:  # Limit batch size
            return jsonify({'error': 'Batch size limited to 100 texts'}), 400
        
        rag_engine = current_app.rag_engine
        results = []
        
        for i, text in enumerate(texts):
            if not isinstance(text, str) or len(text.strip()) == 0:
                results.append({'error': f'Invalid text at index {i}'})
                continue
            
            try:
                result = rag_engine.classify_text(text)
                results.append(result)
            except Exception as e:
                logger.error(f"Error classifying text at index {i}: {str(e)}")
                results.append({'error': f'Classification failed: {str(e)}'})
        
        processing_time = time.time() - start_time
        
        return jsonify({
            'results': results,
            'batch_size': len(texts),
            'processing_time': processing_time
        })
        
    except Exception as e:
        logger.error(f"Batch classification error: {str(e)}")
        return jsonify({'error': 'Batch classification failed', 'details': str(e)}), 500

@classifier_bp.route('/categories', methods=['GET'])
def get_categories():
    """Get available classification categories"""
    from config import Config
    return jsonify({
        'categories': Config.DEFAULT_CATEGORIES,
        'total': len(Config.DEFAULT_CATEGORIES)
    })

@classifier_bp.route('/train', methods=['POST'])
def train_classifier():
    """Train classifier with new data"""
    try:
        data = request.get_json()
        if not data or 'training_data' not in data:
            return jsonify({'error': 'No training_data provided'}), 400
        
        training_data = data['training_data']
        if not isinstance(training_data, list):
            return jsonify({'error': 'training_data must be an array'}), 400
        
        rag_engine = current_app.rag_engine
        
        # Process training data
        for item in training_data:
            if 'text' not in item or 'category' not in item:
                continue
            
            rag_engine.add_training_data(item['text'], item['category'], item.get('metadata', {}))
        
        # Trigger topic detection after training
        emerging_topics = rag_engine.detect_emerging_topics()
        
        return jsonify({
            'message': 'Training completed successfully',
            'training_samples': len(training_data),
            'emerging_topics': len(emerging_topics)
        })
        
    except Exception as e:
        logger.error(f"Training error: {str(e)}")
        return jsonify({'error': 'Training failed', 'details': str(e)}), 500

@classifier_bp.route('/logs', methods=['GET'])
def get_classification_logs():
    """Get classification logs with pagination"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 100)  # Max 100 per page
        
        logs = ClassificationLog.query.order_by(ClassificationLog.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        return jsonify({
            'logs': [log.to_dict() for log in logs.items],
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': logs.total,
                'pages': logs.pages,
                'has_next': logs.has_next,
                'has_prev': logs.has_prev
            }
        })
        
    except Exception as e:
        logger.error(f"Error fetching logs: {str(e)}")
        return jsonify({'error': 'Failed to fetch logs', 'details': str(e)}), 500
