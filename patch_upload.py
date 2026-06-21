content = open('backend/routers/upload.py', encoding='utf-8').read()

old = '''        # Step 6: Update case status to ready
        case.status = "ready"
        db.commit()

        print(f"Case {case_id} processed successfully.")'''

new = '''        # Step 6: Index into ChromaDB for semantic search
        print(f"Indexing into ChromaDB...")
        index_case_into_chroma(case_id)

        # Step 7: Update case status to ready
        case.status = "ready"
        db.commit()

        print(f"Case {case_id} processed successfully.")'''

if old in content:
    content = content.replace(old, new)
    open('backend/routers/upload.py', 'w', encoding='utf-8').write(content)
    print('PATCHED: ChromaDB indexing now called after SQLite storage')
else:
    print('Pattern not found - checking what is near status=ready...')
    idx = content.find('case.status = "ready"')
    if idx > 0:
        print(repr(content[idx-200:idx+100]))
