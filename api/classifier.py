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
        
        # Get classification pipeline from app context
        pipeline = current_app.extensions.get('classification_pipeline')
        if pipeline is None:
            # Fallback: direct RAG engine (backwards-compatible)
            rag_engine = current_app.extensions['rag_engine']
            result = rag_engine.classify_text(text, metadata)
            result.setdefault('classification_source', 'nodeweaver_rag')
        else:
            result = pipeline.classify(text, metadata)
        
        processing_time = time.time() - start_time
        
        # Log classification (include pipeline source in meta_data)
        log_meta = dict(metadata)
        log_meta['classification_source'] = result.get('classification_source', 'nodeweaver_rag')
        log_meta['layer_debug'] = result.get('layer_debug', {})

        log_entry = ClassificationLog(
            input_text=text,
            predicted_category=result.get('predicted_category'),
            confidence_score=result.get('confidence_score'),
            similar_topics=result.get('similar_topics'),
            similar_nodes=result.get('similar_nodes'),
            processing_time=processing_time,
            meta_data=log_meta
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
        
        pipeline = current_app.extensions.get('classification_pipeline')
        rag_engine = current_app.extensions['rag_engine']
        results = []
        
        for i, text in enumerate(texts):
            if not isinstance(text, str) or len(text.strip()) == 0:
                results.append({'error': f'Invalid text at index {i}'})
                continue
            
            try:
                if pipeline is not None:
                    result = pipeline.classify(text)
                else:
                    result = rag_engine.classify_text(text)
                    result.setdefault('classification_source', 'nodeweaver_rag')
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

@classifier_bp.route('/train', methods=['POST'])
def add_training_data():
    """Add training data to improve classification accuracy"""
    try:
        data = request.get_json()
        if not data or 'text' not in data or 'category' not in data:
            return jsonify({'error': 'Missing text or category in request'}), 400
        
        text = data['text'].strip()
        category = data['category'].strip().lower()
        metadata = data.get('metadata', {})
        
        if not text:
            return jsonify({'error': 'Empty text provided'}), 400
        
        if not category:
            return jsonify({'error': 'Empty category provided'}), 400
        
        rag_engine = current_app.extensions['rag_engine']
        doc_id = rag_engine.add_training_data(text, category, metadata)
        
        logger.info(f"Training data added: {category} - {text[:50]}...")
        
        return jsonify({
            'success': True,
            'document_id': doc_id,
            'text': text,
            'category': category,
            'message': f'Training data added for category: {category}'
        })
        
    except Exception as e:
        logger.error(f"Training data error: {str(e)}")
        return jsonify({'error': 'Failed to add training data', 'details': str(e)}), 500

@classifier_bp.route('/correct', methods=['POST'])
def correct_classification():
    """Correct a misclassification and learn from it"""
    try:
        data = request.get_json()
        if not data or 'text' not in data or 'correct_category' not in data:
            return jsonify({'error': 'Missing text or correct_category in request'}), 400
        
        text = data['text'].strip()
        correct_category = data['correct_category'].strip().lower()
        metadata = data.get('metadata', {})
        
        if not text:
            return jsonify({'error': 'Empty text provided'}), 400
        
        if not correct_category:
            return jsonify({'error': 'Empty correct_category provided'}), 400
        
        rag_engine = current_app.extensions['rag_engine']
        success = rag_engine.correct_classification(text, correct_category, metadata)
        
        if success:
            logger.info(f"Classification corrected: '{text[:50]}...' -> {correct_category}")
            return jsonify({
                'success': True,
                'text': text,
                'correct_category': correct_category,
                'message': f'Classification corrected to: {correct_category}'
            })
        else:
            return jsonify({
                'success': False,
                'message': 'No original classification found for this text'
            }), 404
        
    except Exception as e:
        logger.error(f"Classification correction error: {str(e)}")
        return jsonify({'error': 'Failed to correct classification', 'details': str(e)}), 500

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
        
        rag_engine = current_app.extensions['rag_engine']
        
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
