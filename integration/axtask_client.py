"""
TopicSense AxTask Integration Client
Seamless integration between AxTask and TopicSense for automatic task categorization
"""

import requests
import logging
import time
from typing import Dict, List, Any, Optional, Union
import os
from dataclasses import dataclass
from functools import wraps
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class ClassificationResult:
    """Classification result data structure"""
    predicted_category: str
    confidence_score: float
    similar_topics: List[Dict[str, Any]]
    similar_nodes: List[Dict[str, Any]]
    processing_time: float
    document_id: Optional[int] = None

class TopicSenseAxTaskClient:
    """
    AxTask client for TopicSense integration
    Provides automatic task categorization capabilities
    """
    
    def __init__(self, api_url: str = None, api_key: str = None, timeout: int = 30):
        """
        Initialize the AxTask client
        
        Args:
            api_url: TopicSense API base URL
            api_key: API key for authentication (if required)
            timeout: Request timeout in seconds
        """
        self.api_url = api_url or os.getenv('TOPICSENSE_API_URL', 'http://localhost:5000/api/v1')
        self.api_key = api_key or os.getenv('TOPICSENSE_API_KEY')
        self.timeout = timeout
        self.session = requests.Session()
        
        # Set default headers
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'TopicSense-AxTask-Client/1.0'
        })
        
        if self.api_key:
            self.session.headers['Authorization'] = f'Bearer {self.api_key}'
        
        # Verify connection on initialization
        self._verify_connection()
        
        logger.info(f"TopicSense AxTask client initialized with URL: {self.api_url}")
    
    def _verify_connection(self):
        """Verify API connection and availability"""
        try:
            response = self._make_request('/categories', method='GET')
            logger.info("Successfully connected to TopicSense API")
            logger.info(f"Available categories: {', '.join(response.get('categories', []))}")
        except Exception as e:
            logger.warning(f"Failed to verify TopicSense connection: {e}")
    
    def _make_request(self, endpoint: str, method: str = 'GET', data: Dict = None, retries: int = 3) -> Dict:
        """
        Make HTTP request with retry logic
        
        Args:
            endpoint: API endpoint
            method: HTTP method
            data: Request payload
            retries: Number of retry attempts
            
        Returns:
            API response data
            
        Raises:
            requests.RequestException: If request fails after retries
        """
        url = f"{self.api_url.rstrip('/')}{endpoint}"
        
        for attempt in range(retries + 1):
            try:
                if method.upper() == 'GET':
                    response = self.session.get(url, timeout=self.timeout)
                elif method.upper() == 'POST':
                    response = self.session.post(url, json=data, timeout=self.timeout)
                else:
                    response = self.session.request(method, url, json=data, timeout=self.timeout)
                
                response.raise_for_status()
                return response.json()
                
            except requests.exceptions.RequestException as e:
                if attempt < retries:
                    wait_time = 2 ** attempt  # Exponential backoff
                    logger.warning(f"Request failed (attempt {attempt + 1}/{retries + 1}): {e}. Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"Request failed after {retries + 1} attempts: {e}")
                    raise
    
    def classify_task(self, task_text: str, metadata: Dict = None) -> ClassificationResult:
        """
        Classify a single task using TopicSense
        
        Args:
            task_text: The task text to classify
            metadata: Optional metadata to include
            
        Returns:
            ClassificationResult object
            
        Raises:
            ValueError: If task_text is empty
            requests.RequestException: If API request fails
        """
        if not task_text or not task_text.strip():
            raise ValueError("Task text cannot be empty")
        
        request_data = {
            'text': task_text.strip(),
            'metadata': metadata or {'source': 'axtask'}
        }
        
        logger.debug(f"Classifying task: {task_text[:50]}...")
        
        response = self._make_request('/classify', method='POST', data=request_data)
        
        result = ClassificationResult(
            predicted_category=response.get('predicted_category', 'other'),
            confidence_score=response.get('confidence_score', 0.0),
            similar_topics=response.get('similar_topics', []),
            similar_nodes=response.get('similar_nodes', []),
            processing_time=response.get('processing_time', 0.0),
            document_id=response.get('document_id')
        )
        
        logger.info(f"Task classified as '{result.predicted_category}' with {result.confidence_score:.2f} confidence")
        
        return result
    
    def classify_tasks_batch(self, tasks: List[str]) -> List[ClassificationResult]:
        """
        Classify multiple tasks in batch
        
        Args:
            tasks: List of task texts to classify
            
        Returns:
            List of ClassificationResult objects
            
        Raises:
            ValueError: If tasks list is empty or too large
            requests.RequestException: If API request fails
        """
        if not tasks:
            raise ValueError("Tasks list cannot be empty")
        
        if len(tasks) > 100:
            raise ValueError("Batch size limited to 100 tasks")
        
        # Filter out empty tasks
        valid_tasks = [task.strip() for task in tasks if task and task.strip()]
        
        if not valid_tasks:
            raise ValueError("No valid tasks found")
        
        logger.info(f"Classifying {len(valid_tasks)} tasks in batch...")
        
        response = self._make_request('/classify/batch', method='POST', data={'texts': valid_tasks})
        
        results = []
        for result_data in response.get('results', []):
            if 'error' in result_data:
                # Handle individual task errors
                result = ClassificationResult(
                    predicted_category='error',
                    confidence_score=0.0,
                    similar_topics=[],
                    similar_nodes=[],
                    processing_time=0.0
                )
            else:
                result = ClassificationResult(
                    predicted_category=result_data.get('predicted_category', 'other'),
                    confidence_score=result_data.get('confidence_score', 0.0),
                    similar_topics=result_data.get('similar_topics', []),
                    similar_nodes=result_data.get('similar_nodes', []),
                    processing_time=result_data.get('processing_time', 0.0),
                    document_id=result_data.get('document_id')
                )
            results.append(result)
        
        logger.info(f"Batch classification completed in {response.get('processing_time', 0):.3f}s")
        
        return results
    
    def get_categories(self) -> List[str]:
        """
        Get available classification categories
        
        Returns:
            List of available categories
        """
        response = self._make_request('/categories')
        return response.get('categories', ['other'])
    
    def train_with_tasks(self, training_data: List[Dict[str, str]]) -> Dict[str, Any]:
        """
        Train TopicSense with AxTask data
        
        Args:
            training_data: List of dicts with 'text' and 'category' fields
            
        Returns:
            Training result information
            
        Raises:
            ValueError: If training data is invalid
        """
        if not training_data:
            raise ValueError("Training data cannot be empty")
        
        # Validate training data format
        for i, item in enumerate(training_data):
            if not isinstance(item, dict) or 'text' not in item or 'category' not in item:
                raise ValueError(f"Training item {i} must have 'text' and 'category' fields")
        
        # Add AxTask metadata
        for item in training_data:
            if 'metadata' not in item:
                item['metadata'] = {}
            item['metadata']['source'] = 'axtask'
        
        logger.info(f"Training TopicSense with {len(training_data)} AxTask examples...")
        
        response = self._make_request('/train', method='POST', data={'training_data': training_data})
        
        logger.info(f"Training completed: {response.get('message', 'Success')}")
        
        return response
    
    def detect_emerging_topics(self) -> Dict[str, Any]:
        """
        Trigger topic detection to find new emerging topics
        
        Returns:
            Topic detection results
        """
        logger.info("Triggering topic detection...")
        
        response = self._make_request('/topics/detect', method='POST')
        
        logger.info(f"Topic detection completed: {response.get('emerging_topics', 0)} new topics found")
        
        return response
    
    def find_similar_topics(self, text: str, limit: int = 10, threshold: float = 0.5) -> List[Dict[str, Any]]:
        """
        Find topics similar to given text
        
        Args:
            text: Text to find similar topics for
            limit: Maximum number of topics to return
            threshold: Similarity threshold (0-1)
            
        Returns:
            List of similar topics
        """
        request_data = {
            'text': text,
            'limit': min(limit, 50),
            'threshold': max(0, min(1, threshold))
        }
        
        response = self._make_request('/topics/similar', method='POST', data=request_data)
        
        return response.get('similar_topics', [])
    
    def get_classification_stats(self) -> Dict[str, Any]:
        """
        Get classification statistics and system health
        
        Returns:
            System statistics
        """
        return self._make_request('/stats')

class AxTaskIntegration:
    """
    High-level AxTask integration class with convenience methods
    """
    
    def __init__(self, topicsense_client: TopicSenseAxTaskClient = None):
        """
        Initialize AxTask integration
        
        Args:
            topicsense_client: TopicSense client instance (optional)
        """
        self.client = topicsense_client or TopicSenseAxTaskClient()
        self.category_mapping = self._load_category_mapping()
    
    def _load_category_mapping(self) -> Dict[str, str]:
        """
        Load category mapping configuration for AxTask compatibility
        
        Returns:
            Category mapping dictionary
        """
        # Default mapping from TopicSense categories to AxTask categories
        default_mapping = {
            'personal': 'Personal',
            'work': 'Work',
            'academic': 'Study',
            'health': 'Health',
            'finance': 'Finance',
            'shopping': 'Shopping',
            'travel': 'Travel',
            'entertainment': 'Entertainment',
            'technology': 'Tech',
            'political': 'Politics',
            'other': 'Miscellaneous'
        }
        
        # Try to load custom mapping from environment or config file
        mapping_file = os.getenv('AXTASK_CATEGORY_MAPPING_FILE')
        if mapping_file and os.path.exists(mapping_file):
            try:
                with open(mapping_file, 'r') as f:
                    custom_mapping = json.load(f)
                    default_mapping.update(custom_mapping)
                    logger.info(f"Loaded custom category mapping from {mapping_file}")
            except Exception as e:
                logger.warning(f"Failed to load custom category mapping: {e}")
        
        return default_mapping
    
    def categorize_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Categorize an AxTask task object
        
        Args:
            task: AxTask task dictionary
            
        Returns:
            Updated task with category information
        """
        task_text = self._extract_task_text(task)
        
        if not task_text:
            logger.warning("No text found in task for classification")
            return task
        
        try:
            result = self.client.classify_task(
                task_text, 
                metadata={'axtask_id': task.get('id'), 'source': 'axtask'}
            )
            
            # Map TopicSense category to AxTask category
            axtask_category = self.category_mapping.get(
                result.predicted_category, 
                result.predicted_category.title()
            )
            
            # Update task with classification results
            task['category'] = axtask_category
            task['classification_confidence'] = result.confidence_score
            task['auto_categorized'] = True
            task['classification_metadata'] = {
                'topicsense_category': result.predicted_category,
                'confidence': result.confidence_score,
                'similar_topics_count': len(result.similar_topics),
                'processing_time': result.processing_time
            }
            
            logger.info(f"Task categorized as '{axtask_category}' (confidence: {result.confidence_score:.2f})")
            
        except Exception as e:
            logger.error(f"Failed to categorize task: {e}")
            task['classification_error'] = str(e)
        
        return task
    
    def _extract_task_text(self, task: Dict[str, Any]) -> str:
        """
        Extract meaningful text from AxTask task object
        
        Args:
            task: AxTask task dictionary
            
        Returns:
            Extracted text for classification
        """
        # Combine title, description, and notes for better classification
        text_parts = []
        
        if task.get('title'):
            text_parts.append(task['title'])
        
        if task.get('description'):
            text_parts.append(task['description'])
        
        if task.get('notes'):
            text_parts.append(task['notes'])
        
        return ' | '.join(text_parts).strip()
    
    def auto_categorize_project(self, project_tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Auto-categorize all tasks in an AxTask project
        
        Args:
            project_tasks: List of AxTask task dictionaries
            
        Returns:
            List of updated tasks with categories
        """
        logger.info(f"Auto-categorizing {len(project_tasks)} tasks...")
        
        # Extract texts for batch processing
        tasks_with_text = []
        task_texts = []
        
        for task in project_tasks:
            text = self._extract_task_text(task)
            if text:
                tasks_with_text.append(task)
                task_texts.append(text)
        
        if not task_texts:
            logger.warning("No tasks with text found for categorization")
            return project_tasks
        
        try:
            # Batch classify
            results = self.client.classify_tasks_batch(task_texts)
            
            # Update tasks with results
            for task, result in zip(tasks_with_text, results):
                if result.predicted_category != 'error':
                    axtask_category = self.category_mapping.get(
                        result.predicted_category,
                        result.predicted_category.title()
                    )
                    
                    task['category'] = axtask_category
                    task['classification_confidence'] = result.confidence_score
                    task['auto_categorized'] = True
                    task['classification_metadata'] = {
                        'topicsense_category': result.predicted_category,
                        'confidence': result.confidence_score,
                        'similar_topics_count': len(result.similar_topics),
                        'processing_time': result.processing_time
                    }
                else:
                    task['classification_error'] = 'Batch classification failed'
            
            categorized_count = sum(1 for task in tasks_with_text if 'category' in task)
            logger.info(f"Successfully categorized {categorized_count}/{len(tasks_with_text)} tasks")
            
        except Exception as e:
            logger.error(f"Batch categorization failed: {e}")
            
            # Fallback to individual classification
            for task in tasks_with_text:
                self.categorize_task(task)
        
        return project_tasks
    
    def setup_training_from_axtask(self, historical_tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Set up training data from historical AxTask tasks
        
        Args:
            historical_tasks: List of historical AxTask tasks with categories
            
        Returns:
            Training result
        """
        training_data = []
        
        for task in historical_tasks:
            text = self._extract_task_text(task)
            category = task.get('category')
            
            if text and category:
                # Map AxTask category back to TopicSense category
                topicsense_category = None
                for ts_cat, ax_cat in self.category_mapping.items():
                    if ax_cat.lower() == category.lower():
                        topicsense_category = ts_cat
                        break
                
                if not topicsense_category:
                    topicsense_category = category.lower()
                
                training_data.append({
                    'text': text,
                    'category': topicsense_category,
                    'metadata': {
                        'source': 'axtask_historical',
                        'axtask_id': task.get('id'),
                        'original_category': category
                    }
                })
        
        if not training_data:
            raise ValueError("No valid training data found in historical tasks")
        
        logger.info(f"Training TopicSense with {len(training_data)} historical AxTask examples...")
        
        return self.client.train_with_tasks(training_data)

# Utility functions for easy integration
def create_axtask_client(api_url: str = None, api_key: str = None) -> AxTaskIntegration:
    """
    Factory function to create AxTask integration client
    
    Args:
        api_url: TopicSense API URL
        api_key: API key for authentication
        
    Returns:
        AxTaskIntegration instance
    """
    client = TopicSenseAxTaskClient(api_url=api_url, api_key=api_key)
    return AxTaskIntegration(client)

def quick_categorize(task_text: str, api_url: str = None) -> str:
    """
    Quick function to categorize a single task text
    
    Args:
        task_text: Text to categorize
        api_url: TopicSense API URL (optional)
        
    Returns:
        Predicted category
    """
    client = TopicSenseAxTaskClient(api_url=api_url)
    result = client.classify_task(task_text)
    return result.predicted_category

# Example usage and testing
if __name__ == "__main__":
    # Example usage
    try:
        # Initialize integration
        integration = create_axtask_client()
        
        # Test single task categorization
        test_task = {
            'id': 'test-123',
            'title': 'Schedule dentist appointment',
            'description': 'Call Dr. Smith to book annual checkup',
            'notes': 'Prefer morning appointments'
        }
        
        categorized_task = integration.categorize_task(test_task)
        print(f"Task categorized as: {categorized_task.get('category')}")
        print(f"Confidence: {categorized_task.get('classification_confidence', 0):.2f}")
        
        # Test batch categorization
        test_tasks = [
            {'title': 'Buy groceries', 'description': 'Milk, bread, eggs'},
            {'title': 'Prepare presentation', 'description': 'For Monday board meeting'},
            {'title': 'Study chemistry', 'description': 'Chapter 5 for midterm exam'}
        ]
        
        categorized_tasks = integration.auto_categorize_project(test_tasks)
        for task in categorized_tasks:
            print(f"'{task['title']}' -> {task.get('category', 'Uncategorized')}")
        
    except Exception as e:
        logger.error(f"Example execution failed: {e}")
