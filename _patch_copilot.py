import sys

path = sys.argv[1]
with open(path, 'r', newline='') as f:
    content = f.read()

old = """                if meta is not None:
                    if meta.get("type") == "warning":
                        logger.info("[SSE DIAGNOSTIC] Emitting warning event: %s", meta.get("message"))
                        yield f"data: {_json(meta)}\\n\\n"
                        continue

                    metadata_emitted = True"""

new = """                if meta is not None:
                    # Handle dedicated metadata event (type: "metadata")
                    if meta.get("type") == "metadata":
                        logger.info("[SSE] Emitting metadata event: model=%s, ttft=%s", meta.get("model"), meta.get("time_to_first_token_ms"))
                        yield f"data: {_json(meta)}\\n\\n"
                        continue

                    if meta.get("type") == "warning":
                        logger.info("[SSE DIAGNOSTIC] Emitting warning event: %s", meta.get("message"))
                        yield f"data: {_json(meta)}\\n\\n"
                        continue

                    metadata_emitted = True"""

if old in content:
    content = content.replace(old, new)
    with open(path, 'w', newline='') as f:
        f.write(content)
    print('Successfully applied edit')
else:
    print('Could not find exact match')
    idx = content.find('if meta is not None:')
    if idx >= 0:
        print(repr(content[idx:idx+600]))

