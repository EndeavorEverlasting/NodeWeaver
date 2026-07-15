from utils.batch_payloads import normalize_batch_payload


def test_normalize_generic_text_batch_preserves_shared_metadata():
    texts, shared, metadata_list, payload_list, error = normalize_batch_payload({
        'texts': ['alpha', 'beta'],
        'metadata': {'source': 'test'},
    })

    assert error is None
    assert texts == ['alpha', 'beta']
    assert shared == {'source': 'test'}
    assert metadata_list is None
    assert payload_list is None


def test_normalize_axtask_task_batch_extracts_text_and_profile_metadata():
    first_task = {
        'activity': 'Fix the batch classifier',
        'notes': 'AxTask sends tasks rather than texts',
        'metadata': {'axtask_id': 'task-1'},
    }
    second_task = {
        'activity': 'Write regression coverage',
        'metadata': {'axtask_id': 'task-2'},
    }

    texts, shared, metadata_list, payload_list, error = normalize_batch_payload({
        'tasks': [first_task, second_task],
        'metadata': {'request_id': 'batch-1'},
    })

    assert error is None
    assert texts == [
        'Fix the batch classifier | AxTask sends tasks rather than texts',
        'Write regression coverage',
    ]
    assert shared == {
        'request_id': 'batch-1',
        'source': 'axtask',
        'target_system': 'axtask',
        'classification_profile': 'axtask',
    }
    assert metadata_list == [
        {
            'axtask_id': 'task-1',
            'source': 'axtask',
            'target_system': 'axtask',
            'classification_profile': 'axtask',
        },
        {
            'axtask_id': 'task-2',
            'source': 'axtask',
            'target_system': 'axtask',
            'classification_profile': 'axtask',
        },
    ]
    assert payload_list == [first_task, second_task]


def test_normalize_batch_rejects_missing_or_empty_arrays():
    assert normalize_batch_payload({})[-1] == 'No texts or tasks array provided'
    assert normalize_batch_payload({'texts': []})[-1] == 'texts or tasks must be a non-empty array'
    assert normalize_batch_payload({'tasks': []})[-1] == 'texts or tasks must be a non-empty array'


def test_normalize_axtask_batch_skips_unclassifiable_items():
    texts, _, metadata_list, payload_list, error = normalize_batch_payload({
        'tasks': [None, {}, {'activity': 'Valid task'}],
    })

    assert error is None
    assert texts == ['Valid task']
    assert len(metadata_list) == 1
    assert payload_list == [{'activity': 'Valid task'}]
