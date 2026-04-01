from flask import Blueprint, request, jsonify, current_app
import time
import logging
from copy import deepcopy
from utils.validators import validate_classification_input
from models import ClassificationLog
from app import db
from config import Config
from utils.classification_profiles import (
    build_axtask_metadata,
    extract_task_text,
    is_axtask_payload,
    normalize_profile_category,
    normalize_profile_result,
    resolve_classification_profile,
)

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
        
        text = extract_task_text(data)
        metadata = deepcopy(data.get('metadata', {})) if isinstance(data.get('metadata'), dict) else {}
        if is_axtask_payload(data) or resolve_classification_profile(metadata) == 'axtask':
            metadata = build_axtask_metadata(metadata, payload=data)
        
        # Get RAG engine from app context
        rag_engine = current_app.extensions['rag_engine']
        
        # Perform classification
        result = rag_engine.classify_text(text, metadata)
        result = normalize_profile_result(result, metadata)
        
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
        if not data or ('texts' not in data and 'tasks' not in data):
            return jsonify({'error': 'Provide either a texts array or a tasks array'}), 400
        
        texts = data.get('texts')
        shared_metadata = deepcopy(data.get('metadata', {})) if isinstance(data.get('metadata'), dict) else {}
        metadata_list = data.get('metadata_list')

        if texts is None and isinstance(data.get('tasks'), list):
            texts = []
            metadata_list = []
            for task in data['tasks']:
                task_text = extract_task_text(task)
                if task_text:
                    texts.append(task_text)
                    task_metadata = deepcopy(task.get('metadata', {})) if isinstance(task.get('metadata'), dict) else {}
                    if is_axtask_payload(task):
                        task_metadata = build_axtask_metadata(task_metadata, payload=task)
                    metadata_list.append(task_metadata)

        if not isinstance(texts, list) or len(texts) == 0:
            return jsonify({'error': 'texts or tasks must be a non-empty array'}), 400

        if resolve_classification_profile(shared_metadata) == 'axtask':
            shared_metadata = build_axtask_metadata(shared_metadata, payload=data)
        elif isinstance(data, dict) and 'tasks' in data:
            shared_metadata = build_axtask_metadata(shared_metadata)
        
        if len(texts) > 100:  # Limit batch size
            return jsonify({'error': 'Batch size limited to 100 texts'}), 400
        
        rag_engine = current_app.extensions['rag_engine']
        results = []
        
        for i, text in enumerate(texts):
            if not isinstance(text, str) or len(text.strip()) == 0:
                results.append({'error': f'Invalid text at index {i}'})
                continue
            
            try:
                item_metadata = {}
                if isinstance(metadata_list, list) and i < len(metadata_list) and isinstance(metadata_list[i], dict):
                    item_metadata = metadata_list[i]
                elif isinstance(shared_metadata, dict):
                    item_metadata = shared_metadata
                if resolve_classification_profile(item_metadata) == 'axtask':
                    item_metadata = build_axtask_metadata(item_metadata)
                result = rag_engine.classify_text(text, item_metadata)
                result = normalize_profile_result(result, item_metadata)
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

@classifier_bp.route('/correct', methods=['POST'])
def correct_classification():
    """Correct a misclassification and learn from it"""
    try:
        data = request.get_json()
        if not data or 'text' not in data or 'correct_category' not in data:
            return jsonify({'error': 'Missing text or correct_category in request'}), 400
        
        text = data['text'].strip()
        metadata = deepcopy(data.get('metadata', {})) if isinstance(data.get('metadata'), dict) else {}
        if is_axtask_payload(data) or resolve_classification_profile(metadata) == 'axtask':
            metadata = build_axtask_metadata(metadata, payload=data)
        correct_category = normalize_profile_category(data['correct_category'], metadata)
        
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
    requested_profile = request.args.get('profile')
    profile = resolve_classification_profile({'classification_profile': requested_profile})
    categories = Config.get_categories(profile)
    return jsonify({
        'categories': categories,
        'total': len(categories),
        'profile': profile or 'default'
    })

@classifier_bp.route('/train', methods=['POST'])
def train_classifier():
    """Train classifier with one sample or a batch of samples."""
    try:
        data = request.get_json()
        rag_engine = current_app.extensions['rag_engine']

        if data and 'training_data' in data:
            training_data = data['training_data']
            if not isinstance(training_data, list):
                return jsonify({'error': 'training_data must be an array'}), 400

            processed = 0
            for item in training_data:
                if 'text' not in item or 'category' not in item:
                    continue
                item_metadata = item.get('metadata', {}) if isinstance(item.get('metadata'), dict) else {}
                if resolve_classification_profile(item_metadata) == 'axtask':
                    item_metadata = build_axtask_metadata(item_metadata, payload=item)
                rag_engine.add_training_data(
                    item['text'].strip(),
                    normalize_profile_category(item['category'], item_metadata),
                    item_metadata,
                )
                processed += 1

            emerging_topics = rag_engine.detect_emerging_topics()
            return jsonify({
                'message': 'Training completed successfully',
                'training_samples': processed,
                'emerging_topics': len(emerging_topics)
            })

        if not data or 'text' not in data or 'category' not in data:
            return jsonify({'error': 'Missing text or category in request'}), 400

        text = data['text'].strip()
        metadata = deepcopy(data.get('metadata', {})) if isinstance(data.get('metadata'), dict) else {}
        if is_axtask_payload(data) or resolve_classification_profile(metadata) == 'axtask':
            metadata = build_axtask_metadata(metadata, payload=data)
        category = normalize_profile_category(data['category'], metadata)

        if not text:
            return jsonify({'error': 'Empty text provided'}), 400

        if not category:
            return jsonify({'error': 'Empty category provided'}), 400

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
