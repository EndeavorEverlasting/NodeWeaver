"""Shared classification profile helpers for NodeWeaver integrations."""
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from config import Config

AXTASK_PROFILE_NAME = 'axtask'
AXTASK_CATEGORY_ALIASES = {
    'crisis': 'Crisis',
    'emergency': 'Crisis',
    'urgent': 'Crisis',
    'incident': 'Crisis',
    'safety': 'Crisis',
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
    'Crisis': {
        'keywords': ['accident', 'alarm', 'ambulance', 'bleeding', 'choking', 'collapse', 'critical', 'danger', 'dead', 'death', 'dying', 'emergency', 'evacuate', 'evacuation', 'fatal', 'fire', 'flood', 'hazard', 'help', 'hospital', 'hurt', 'incident', 'injured', 'injury', 'inspection', 'medical', 'osha', 'overdose', 'panic', 'poison', 'rescue', 'safety', 'seizure', 'severe', 'sos', 'stroke', 'suicide', 'threat', 'trapped', 'unconscious', 'unsafe', 'urgent', 'violation'],
        'base_confidence': 0.97,
        'priority': 100,
    },
    'Development': {
        'keywords': ['api', 'backend', 'bug', 'bugfix', 'build', 'code', 'database', 'debug', 'deploy', 'development', 'feature', 'fix', 'frontend', 'implementation', 'integration', 'programming', 'refactor', 'release', 'repo', 'ship', 'software', 'test', 'webhook'],
        'base_confidence': 0.72,
        'priority': 80,
    },
    'Meeting': {
        'keywords': ['1:1', 'briefing', 'call', 'conference', 'demo', 'discuss', 'discussion', 'kickoff', 'meeting', 'presentation', 'present', 'retro', 'review meeting', 'standup', 'sync', 'workshop'],
        'base_confidence': 0.7,
        'priority': 70,
    },
    'Research': {
        'keywords': ['analyze', 'analysis', 'benchmark', 'compare', 'evaluate', 'explore', 'investigate', 'learn', 'prototype', 'research', 'study'],
        'base_confidence': 0.68,
        'priority': 60,
    },
    'Maintenance': {
        'keywords': ['backup', 'cleanup', 'configure', 'install', 'maintain', 'maintenance', 'migrate', 'monitor', 'patch', 'renew', 'restore', 'setup', 'support', 'update', 'upgrade'],
        'base_confidence': 0.66,
        'priority': 50,
    },
    'Administrative': {
        'keywords': ['admin', 'approve', 'compliance', 'confirm', 'contract', 'coord', 'coordination', 'deadline', 'document', 'email', 'follow', 'follow-up', 'followup', 'invoice', 'license', 'paperwork', 'report', 'share', 'sign', 'submit'],
        'base_confidence': 0.64,
        'priority': 40,
    },
}

_AXTASK_TIME_KEYWORDS = ['today', 'tomorrow', 'asap', 'immediately', 'now']
_AXTASK_PROBLEM_KEYWORDS = ['error', 'issue', 'problem', 'broken', 'failed', "won't", "can't", "doesn't"]
_AXTASK_TAG_BOOSTS = {
    'Crisis': ['@urgent', '#urgent', '@critical', '#critical', '@emergency', '#emergency', '@safety', '#safety'],
    'Development': ['@blocker', '#blocker'],
    'Administrative': ['@followup', '#followup'],
}
_AXTASK_DATE_PATTERN = re.compile(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{4}\b")


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


def build_axtask_metadata(
    metadata: Optional[Dict[str, Any]] = None,
    payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Merge request metadata with AxTask profile markers."""
    combined = dict(metadata or {})
    if isinstance(payload, dict):
        payload_mapping = {
            'id': 'axtask_id',
            'status': 'status',
            'date': 'date',
            'time': 'time',
            'urgency': 'urgency',
            'impact': 'impact',
            'effort': 'effort',
            'priority': 'priority',
            'priorityScore': 'priorityScore',
            'priority_score': 'priorityScore',
            'isRepeated': 'isRepeated',
            'is_repeated': 'isRepeated',
        }
        for source_field, target_field in payload_mapping.items():
            value = payload.get(source_field)
            if value not in (None, '') and target_field not in combined:
                combined[target_field] = value
        if payload.get('prerequisites'):
            combined.setdefault('has_prerequisites', True)
    combined.setdefault('source', 'axtask')
    combined.setdefault('target_system', 'axtask')
    combined.setdefault('classification_profile', 'axtask')
    return combined


def normalize_profile_category(
    category: Optional[str],
    metadata: Optional[Dict[str, Any]] = None,
    fallback: str = 'other',
) -> str:
    """Normalize a category for the active classification profile."""
    if resolve_classification_profile(metadata) == AXTASK_PROFILE_NAME:
        return normalize_axtask_category(category)

    normalized = str(category or '').strip().lower()
    return normalized or fallback


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


def normalize_profile_result(
    result: Optional[Dict[str, Any]],
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Normalize result categories for the active classification profile."""
    normalized_result = dict(result or {})
    if resolve_classification_profile(metadata) != AXTASK_PROFILE_NAME:
        return normalized_result

    normalized_result['predicted_category'] = normalize_axtask_category(
        normalized_result.get('predicted_category')
    )
    normalized_result['classification_profile'] = AXTASK_PROFILE_NAME

    deduped_categories: Dict[str, Dict[str, Any]] = {}
    for item in normalized_result.get('all_categories', []):
        if not isinstance(item, dict):
            continue

        category = normalize_axtask_category(item.get('category'))
        candidate = dict(item)
        candidate['category'] = category

        existing = deduped_categories.get(category)
        if not existing or float(candidate.get('confidence', 0.0)) > float(existing.get('confidence', 0.0)):
            deduped_categories[category] = candidate

    if deduped_categories:
        normalized_result['all_categories'] = sorted(
            deduped_categories.values(),
            key=lambda item: (
                float(item.get('confidence', 0.0)),
                int(item.get('keyword_matches', 0)),
            ),
            reverse=True,
        )

    return normalized_result


def _count_keyword_matches(text_lower: str, tokens: Set[str], keywords: List[str]) -> Tuple[int, List[str]]:
    """Count whole-word and phrase keyword matches for AxTask category scoring."""
    matches: List[str] = []
    for keyword in keywords:
        matched = (' ' in keyword and keyword in text_lower) or keyword in tokens
        if matched and keyword not in matches:
            matches.append(keyword)
    return len(matches), matches


def _coerce_int(value: Any) -> Optional[int]:
    """Best-effort coercion of metadata scores into integers."""
    try:
        if value in (None, ''):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _build_signal_boosts(text_lower: str, metadata: Optional[Dict[str, Any]]) -> Dict[str, int]:
    """Build category boosts from AxTask priority-engine signals."""
    boosts = {category: 0 for category in _AXTASK_KEYWORDS}

    for category, tags in _AXTASK_TAG_BOOSTS.items():
        if any(tag in text_lower for tag in tags):
            boosts[category] += 2 if category == 'Crisis' else 1

    if any(keyword in text_lower for keyword in _AXTASK_TIME_KEYWORDS):
        boosts['Administrative'] += 1
        boosts['Meeting'] += 1
    if _AXTASK_DATE_PATTERN.search(text_lower):
        boosts['Administrative'] += 1
        boosts['Meeting'] += 1

    if any(keyword in text_lower for keyword in _AXTASK_PROBLEM_KEYWORDS):
        boosts['Development'] += 2
        boosts['Maintenance'] += 1

    urgency = _coerce_int((metadata or {}).get('urgency'))
    impact = _coerce_int((metadata or {}).get('impact'))
    effort = _coerce_int((metadata or {}).get('effort'))

    if urgency and urgency >= 4:
        boosts['Crisis'] += 1
        boosts['Administrative'] += 1
    if urgency and impact and urgency >= 4 and impact >= 4:
        boosts['Crisis'] += 2
    if urgency and impact and urgency >= 4 and impact >= 3:
        boosts['Development'] += 1
        boosts['Maintenance'] += 1
    if effort and effort <= 2:
        boosts['Development'] += 1
        boosts['Administrative'] += 1

    return boosts


def predict_axtask_categories(
    text: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Predict AxTask-compatible classifications from free-form task text."""
    text_lower = (text or '').lower().strip()
    if not text_lower:
        return [{'category': 'General', 'confidence': 0.35, 'keyword_matches': 0}]

    tokens = set(re.findall(r"[a-z0-9']+", text_lower))
    signal_boosts = _build_signal_boosts(text_lower, metadata)
    results = []
    for category, config in _AXTASK_KEYWORDS.items():
        match_count, matched_keywords = _count_keyword_matches(text_lower, tokens, config['keywords'])
        signal_boost = signal_boosts.get(category, 0)
        weighted_matches = match_count + signal_boost
        if weighted_matches:
            confidence = min(
                0.99,
                config['base_confidence']
                + (min(match_count, 4) * 0.05)
                + (min(signal_boost, 3) * 0.03),
            )
            results.append({
                'category': category,
                'confidence': confidence,
                'keyword_matches': weighted_matches,
                'matched_keywords': matched_keywords,
                'signal_boost': signal_boost,
                'priority': config['priority'],
            })

    if not results:
        return [{'category': 'General', 'confidence': 0.45, 'keyword_matches': 0}]

    results.sort(
        key=lambda item: (item['confidence'], item['keyword_matches'], item['priority']),
        reverse=True,
    )
    for item in results:
        item.pop('priority', None)
    return results