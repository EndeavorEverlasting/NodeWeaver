"""Pure helpers for normalizing batch-classification request payloads."""
from copy import deepcopy
from typing import Any, Dict, List, Optional, Tuple

from utils.classification_profiles import (
    build_axtask_metadata,
    extract_task_text,
    is_axtask_payload,
)


def normalize_batch_payload(
    data: Any,
) -> Tuple[List[str], Dict[str, Any], Optional[List[Dict[str, Any]]], Optional[List[Dict[str, Any]]], Optional[str]]:
    """Normalize generic ``texts`` and AxTask ``tasks`` batch requests.

    Returns ``texts``, shared metadata, per-item metadata, source payloads, and
    an optional validation error.  This helper is intentionally Flask-free so
    the public request contract can be validated without booting models or a
    database.
    """
    if not isinstance(data, dict):
        return [], {}, None, None, 'No JSON data provided'

    shared_metadata = deepcopy(data.get('metadata', {})) if isinstance(data.get('metadata'), dict) else {}
    metadata_list = data.get('metadata_list')
    payload_list = None

    if 'texts' in data:
        texts = data.get('texts')
    elif isinstance(data.get('tasks'), list):
        texts = []
        metadata_list = []
        payload_list = []
        for task in data['tasks']:
            if not isinstance(task, dict):
                continue
            task_text = extract_task_text(task)
            if not task_text:
                continue
            texts.append(task_text)
            task_metadata = deepcopy(task.get('metadata', {})) if isinstance(task.get('metadata'), dict) else {}
            if is_axtask_payload(task):
                task_metadata = build_axtask_metadata(task_metadata)
            metadata_list.append(task_metadata)
            payload_list.append(task)
        shared_metadata = build_axtask_metadata(shared_metadata)
    else:
        return [], shared_metadata, None, None, 'No texts or tasks array provided'

    if not isinstance(texts, list) or not texts:
        return [], shared_metadata, metadata_list if isinstance(metadata_list, list) else None, payload_list, 'texts or tasks must be a non-empty array'

    return (
        texts,
        shared_metadata,
        metadata_list if isinstance(metadata_list, list) else None,
        payload_list,
        None,
    )
