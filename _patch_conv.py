import sys

path = sys.argv[1]
with open(path, 'r', newline='') as f:
    content = f.read()

old = """    if not intent_result.requires_llm:
        def _conversational():
            yield f"data: {_json({'type': 'token', 'content': intent_result.fast_response})}\\n\\n"
            yield f"data: {_json({'type': 'done', 'model': 'conversational', 'tier': 0, 'fallback_used': False, 'response_time': round(t_class, 3), 'intent': intent_result.intent.value, 'database_used': False, 'cache_used': False, 'pool': 'Conversation Pool'})}\\n\\n"
        return StreamingResponse(_conversational(), media_type="text/event-stream")"""

new = """    if not intent_result.requires_llm:
        def _conversational():
            yield f"data: {_json({'type': 'token', 'content': intent_result.fast_response})}\\n\\n"
            yield f"data: {_json({'type': 'metadata', 'model': 'conversational', 'provider': 'OpenRouter', 'time_to_first_token_ms': 0})}\\n\\n"
            yield f"data: {_json({'type': 'done', 'model': 'conversational', 'provider': 'OpenRouter', 'tier': 0, 'fallback_used': False, 'response_time': round(t_class, 3), 'intent': intent_result.intent.value, 'database_used': False, 'cache_used': False, 'pool': 'Conversation Pool'})}\\n\\n"
        return StreamingResponse(_conversational(), media_type="text/event-stream")"""

if old in content:
    content = content.replace(old, new)
    with open(path, 'w', newline='') as f:
        f.write(content)
    print('Successfully applied edit')
else:
    print('Could not find exact match')
    idx = content.find("if not intent_result.requires_llm:")
    if idx >= 0:
        print(repr(content[idx:idx+400]))

