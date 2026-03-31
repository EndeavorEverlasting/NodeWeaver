"""Shared classification profile helpers for NodeWeaver integrations."""
import re
from typing import Any, Dict, List, Optional

from config import Config

AXTASK_PROFILE_NAME = 'axtask'
AXTASK_CATEGORY_ALIASES = {
    'development': 'Development',
    'dev': 'Development',
    'technology': 'Development',
    'tech': 'Development',
    'software': 'Development',
    'meeting': 'Meeting',
    'call': 'Meeting',
    'conference': 'Meeting',
    'standup': 'Meeting',
    'research': 'Research',
    'academic': 'Research',
    'study': 'Research',
    'analysis': 'Research',
    'maintenance': 'Maintenance',
    'ops': 'Maintenance',
    'support': 'Maintenance',
    'administrative': 'Administrative',
    'admin': 'Administrative',
    'documentation': 'Administrative',
    'legal': 'Administrative',
    'political': 'Administrative',
    'general': 'General',
    'work': 'General',
    'personal': 'General',
    'health': 'General',
    'finance': 'General',
    'shopping': 'General',
    'travel': 'General',
    'entertainment': 'General',
    'other': 'General',
}
DEFAULT_AXTASK_CATEGORY_MAPPING = dict(AXTASK_CATEGORY_ALIASES)

_AXTASK_KEYWORDS = {
    'Development': ['api', 'backend', 'bug', 'build', 'code', 'database', 'debug', 'deploy', 'development', 'feature', 'fix', 'frontend', 'implementation', 'programming', 'refactor', 'release', 'repo', 'software', 'test'],
    'Meeting': ['1:1', 'call', 'conference', 'demo', 'discuss', 'discussion', 'kickoff', 'meeting', 'presentation', 'present', 'retro', 'review meeting', 'standup', 'sync', 'workshop'],
    'Research': ['analyze', 'analysis', 'benchmark', 'compare', 'evaluate', 'explore', 'investigate', 'learn', 'prototype', 'research', 'study'],
    'Maintenance': ['backup', 'cleanup', 'configure', 'install', 'maintain', 'maintenance', 'migrate', 'monitor', 'patch', 'renew', 'restore', 'setup', 'update', 'upgrade'],
    'Administrative': ['admin', 'approve', 'compliance', 'confirm', 'contract', 'coordination', 'document', 'email', 'follow-up', 'followup', 'invoice', 'paperwork', 'report', 'sign', 'submit'],
}


def resolve_classification_profile(metadata: Optional[Dict[str, Any]] = None) -> str:
    """Resolve the classification profile from request metadata."""
    if not isinstance(metadata, dict):
        return 'default'

    markers = [
        metadata.get('classification_profile'),
        metadata.get('target_system'),
        metadata.get('source'),
    ]
    for marker in markers:
        value = str(marker or '').strip().lower().replace('-', '').replace('_', '')
        if value == AXTASK_PROFILE_NAME:
            return AXTASK_PROFILE_NAME
    return 'default'


def is_axtask_payload(payload: Optional[Dict[str, Any]]) -> bool:
    """Return True when a request payload looks like an AxTask task."""
    if not isinstance(payload, dict):
        return False
    return any(key in payload for key in ('activity', 'notes', 'prerequisites', 'classification'))


def build_axtask_metadata(metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Merge request metadata with AxTask profile markers."""
    combined = dict(metadata or {})
    combined.setdefault('source', 'axtask')
    combined.setdefault('target_system', 'axtask')
    combined.setdefault('classification_profile', 'axtask')
    return combined


def extract_task_text(payload: Optional[Dict[str, Any]]) -> str:
    """Extract classifier text from AxTask or generic task payloads."""
    if not isinstance(payload, dict):
        return ''

    if isinstance(payload.get('text'), str) and payload['text'].strip():
        return payload['text'].strip()

    text_parts = []
    for field in ('activity', 'notes', 'prerequisites', 'title', 'description'):
        value = payload.get(field)
        if isinstance(value, str) and value.strip():
            text_parts.append(value.strip())

    return ' | '.join(text_parts).strip()


def normalize_axtask_category(category: Optional[str], fallback: str = 'General') -> str:
    """Normalize a raw category into AxTask's canonical classification set."""
    key = str(category or '').strip().lower()
    if not key:
        return fallback
    if category in Config.AXTASK_CATEGORIES:
        return category
    return AXTASK_CATEGORY_ALIASES.get(key, fallback)


def predict_axtask_categories(text: str) -> List[Dict[str, Any]]:
    """Predict AxTask-compatible classifications from free-form task text."""
    text_lower = (text or '').lower().strip()
    if not text_lower:
        return [{'category': 'General', 'confidence': 0.35, 'keyword_matches': 0}]

    tokens = set(re.findall(r"[a-z0-9']+", text_lower))
    results = []
    for category, keywords in _AXTASK_KEYWORDS.items():
        matches = 0
        for keyword in keywords:
            if (' ' in keyword and keyword in text_lower) or keyword in tokens:
                matches += 1
        if matches:
            confidence = min(0.96, 0.62 + matches * 0.08)
            results.append({
                'category': category,
                'confidence': confidence,
                'keyword_matches': matches,
            })

    if not results:
        return [{'category': 'General', 'confidence': 0.45, 'keyword_matches': 0}]

    results.sort(key=lambda item: (item['confidence'], item['keyword_matches']), reverse=True)
    return results