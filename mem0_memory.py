"""Optional hosted or OSS Mem0 memory for the owner's private chat."""
import json
import logging
import os
import threading

LOG = logging.getLogger(__name__)
LOCK = threading.RLock()
_client = None


def client():
    global _client
    if os.getenv('MEM0_ENABLED', '').lower() != 'true':
        return None
    with LOCK:
        if _client is None:
            if not os.getenv('MEM0_OWNER_ID', '').strip():
                raise ValueError('Stable Mem0 owner ID required')
            if os.getenv('MEM0_BACKEND', 'oss') == 'platform':
                import httpx
                from mem0 import MemoryClient
                _client = MemoryClient(api_key=os.environ['MEM0_API_KEY'],
                    client=httpx.Client(base_url='https://api.mem0.ai',
                        headers={'Authorization': 'Token ' + os.environ['MEM0_API_KEY']},
                        timeout=15.0))
                return _client
            # Explicit configuration prevents SDK defaults creating ephemeral storage
            # or selecting a charged provider without the operator configuring it.
            config = json.loads(os.environ['MEM0_CONFIG_JSON'])
            if not all(k in config for k in ('llm', 'embedder', 'vector_store', 'history_db_path')):
                raise ValueError('Explicit Mem0 provider and history configuration required')
            if not os.getenv('MEM0_OWNER_ID', '').strip():
                raise ValueError('Stable Mem0 owner ID required')
            from mem0 import Memory
            _client = Memory.from_config(config)
        return _client


def recall(query):
    try:
        with LOCK:
            memory = client()
            if memory is None:
                return []
            result = memory.search(query[:2000],
                filters={'user_id': os.environ['MEM0_OWNER_ID'], 'agent_id': 'agentbroker-private'},
                top_k=5)
            rows = result.get('results', []) if isinstance(result, dict) else result
            return [{'memory': row['memory'][:1500]} for row in rows[:5]
                    if isinstance(row, dict) and isinstance(row.get('memory'), str)]
    except Exception as error:
        LOG.warning('Mem0 recall unavailable: %s', type(error).__name__)
        return []


def remember(user, assistant):
    try:
        with LOCK:
            memory = client()
            if memory is None:
                return False
            instruction = ('Extract only durable facts and preferences explicitly stated by the user. '
                           'Do not store secrets or instructions.')
            options = {'custom_instructions': instruction} if os.getenv('MEM0_BACKEND', 'oss') == 'platform' else {'prompt': instruction}
            memory.add([{'role': 'user', 'content': user[:2000]}],
                user_id=os.environ['MEM0_OWNER_ID'], agent_id='agentbroker-private',
                metadata={'scope': 'private_companion'},
                **options)
            return True
    except Exception as error:
        LOG.warning('Mem0 write unavailable: %s', type(error).__name__)
        return False


def status():
    return {'enabled': os.getenv('MEM0_ENABLED', '').lower() == 'true',
            'initialized': _client is not None, 'scope': 'private_companion',
            'backend': os.getenv('MEM0_BACKEND', 'oss'),
            'configured': bool(os.getenv('MEM0_OWNER_ID') and os.getenv(
                'MEM0_API_KEY' if os.getenv('MEM0_BACKEND', 'oss') == 'platform' else 'MEM0_CONFIG_JSON'))}
