"""Pure helpers for normalizing batch-classification request payloads."""
from copy import deepcopy
from typing import Any, Dict, List, Optional, Tuple

from utils.classification_profiles import (
    build_axtask_metadata,
    extract_task_text,
    is_axtask_payload,
)

BatchMetadata = Optional[List[Dict[str, Any]]]
BatchPayloads = Optional[List[Dict[str, Any]]]
BatchNormalization = Tuple[
    List[str],
    Dict[str, Any],
    BatchMetadata,
    BatchPayloads,
    Optional[str],
]


def normalize_batch_payload(data: Any) -> BatchNormalization:
    """Normalize generic ``texts`` and AxTask ``tasks`` batch requests.

    Returns ``texts``, shared metadata, per-item metadata, source payloads, and
    an optional validation error. This helper is intentionally Flask-free so
    the public request contract can be validated without booting models or a
    database.
    """
    if not isinstance(data, dict):
        return [], {}, None, None, 'No JSON data provided'

    raw_metadata = data.get('metadata', {})
    shared_metadata = (
        deepcopy(raw_metadata) if isinstance(raw_metadata, dict) else {}
    )
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
            raw_task_metadata = task.get('metadata', {})
            task_metadata = (
                deepcopy(raw_task_metadata)
                if isinstance(raw_task_metadata, dict)
                else {}
            )
            if is_axtask_payload(task):
                task_metadata = build_axtask_metadata(task_metadata)
            metadata_list.append(task_metadata)
            payload_list.append(task)
        shared_metadata = build_axtask_metadata(shared_metadata)
    else:
        return (
            [],
            shared_metadata,
            None,
            None,
            'No texts or tasks array provided',
        )

    if not isinstance(texts, list) or not texts:
        normalized_metadata = (
            metadata_list if isinstance(metadata_list, list) else None
        )
        return (
            [],
            shared_metadata,
            normalized_metadata,
            payload_list,
            'texts or tasks must be a non-empty array',
        )

    return (
        texts,
        shared_metadata,
        metadata_list if isinstance(metadata_list, list) else None,
        payload_list,
        None,
    )
