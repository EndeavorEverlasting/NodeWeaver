"""Input validation utilities for TopicSense API"""
from config import Config

def validate_classification_input(data):
    """Validate classification request input"""
    if not isinstance(data, dict):
        return "Input must be a JSON object"
    
    if 'text' not in data:
        return "Missing required field: text"
    
    text = data['text']
    if not isinstance(text, str):
        return "Field 'text' must be a string"
    
    if not text.strip():
        return "Field 'text' cannot be empty"
    
    if len(text) > Config.MAX_INPUT_LENGTH:
        return f"Text too long. Maximum length is {Config.MAX_INPUT_LENGTH} characters"
    
    # Validate metadata if provided
    if 'metadata' in data:
        if not isinstance(data['metadata'], dict):
            return "Field 'metadata' must be an object"
    
    return None  # No validation errors

def validate_topic_input(data):
    """Validate topic creation input"""
    if not isinstance(data, dict):
        return "Input must be a JSON object"
    
    if 'label' not in data:
        return "Missing required field: label"
    
    label = data['label']
    if not isinstance(label, str):
        return "Field 'label' must be a string"
    
    if not label.strip():
        return "Field 'label' cannot be empty"
    
    if len(label) > 200:
        return "Label too long. Maximum length is 200 characters"
    
    # Validate category if provided
    if 'category' in data:
        category = data['category']
        if not isinstance(category, str):
            return "Field 'category' must be a string"
        
        if category and category not in Config.DEFAULT_CATEGORIES:
            return f"Invalid category. Must be one of: {', '.join(Config.DEFAULT_CATEGORIES)}"
    
    return None  # No validation errors