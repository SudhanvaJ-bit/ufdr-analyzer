content = open('backend/routers/upload.py', encoding='utf-8').read()

if 'def index_case_into_chroma' not in content:
    func = '''

def index_case_into_chroma(case_id: str):
    from backend.database import SessionLocal
    from backend.models import ChatMessage, CallRecord, Contact
    from backend.vector_store.chroma_store import get_vector_store

    db = SessionLocal()

    try:
        print(f"Indexing case {case_id} into ChromaDB...")

        vs = get_vector_store()

        chats = db.query(ChatMessage).filter(ChatMessage.case_id == case_id).all()
        calls = db.query(CallRecord).filter(CallRecord.case_id == case_id).all()
        contacts = db.query(Contact).filter(Contact.case_id == case_id).all()

        counts = vs.index_all(case_id, chats, calls, contacts)

        print(f"ChromaDB indexed: {counts}")

    except Exception as e:
        print(f"ChromaDB indexing failed (SQL search still works): {e}")
        import traceback
        traceback.print_exc()

    finally:
        db.close()
'''
    content = content + func

    open('backend/routers/upload.py', 'w', encoding='utf-8').write(content)

    print('ADDED: index_case_into_chroma function')
else:
    print('OK: function already exists')
