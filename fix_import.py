content = open('backend/routers/upload.py', encoding='utf-8').read()

wrong_line = 'from backend.vector_store.chroma_store import index_case_into_chroma\n'

if wrong_line in content:
    content = content.replace(wrong_line, '')
    open('backend/routers/upload.py', 'w', encoding='utf-8').write(content)
    print('FIXED: Removed wrong import line')
else:
    print('Line not found, checking first 25 lines...')
    lines = content.split(chr(10))
    for i, line in enumerate(lines[:25], 1):
        print(f'{i}: {line}')
