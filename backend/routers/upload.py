"""
routers/upload.py — FastAPI routes for file upload and case ingestion.
"""

import shutil
import uuid
from pathlib import Path
from datetime import datetime

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Case, ChatMessage, CallRecord, Contact, MediaFile
from backend.parsers.ufdr_parser import UFDRParser
from backend.extractors.entity_extractor import EntityExtractor
from backend.config import settings

router = APIRouter(prefix="/upload", tags=["Upload"])

parser = UFDRParser()
extractor = EntityExtractor()


@router.post("/case")
async def upload_case(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    case_description: str = "",
    db: Session = Depends(get_db),
):
    allowed_extensions = {".json", ".zip", ".csv"}
    file_ext = Path(file.filename).suffix.lower()

    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{file_ext}'. Allowed: {allowed_extensions}",
        )

    case_id = str(uuid.uuid4())
    save_path = settings.UPLOAD_DIR / f"{case_id}{file_ext}"

    with open(save_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    db_case = Case(
        id=case_id,
        name=f"Case_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        description=case_description,
        file_path=str(save_path),
        file_name=file.filename,
        status="processing",
    )

    db.add(db_case)
    db.commit()

    background_tasks.add_task(
        process_case_file,
        case_id=case_id,
        file_path=str(save_path),
        original_filename=file.filename,
    )

    return {
        "success": True,
        "case_id": case_id,
        "message": "File uploaded. Processing started in background.",
        "status_url": f"/upload/case/{case_id}/status",
    }


@router.get("/case/{case_id}/status")
def get_case_status(case_id: str, db: Session = Depends(get_db)):
    case = db.query(Case).filter(Case.id == case_id).first()

    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    return {
        "case_id": case_id,
        "status": case.status,
        "case_name": case.name,
        "created_at": case.created_at.isoformat() if case.created_at else "",
    }


@router.get("/cases")
def list_all_cases(db: Session = Depends(get_db)):
    cases = db.query(Case).order_by(Case.created_at.desc()).all()

    result = []

    for case in cases:
        chat_count = db.query(ChatMessage).filter(ChatMessage.case_id == case.id).count()
        call_count = db.query(CallRecord).filter(CallRecord.case_id == case.id).count()
        contact_count = db.query(Contact).filter(Contact.case_id == case.id).count()

        result.append(
            {
                "case_id": case.id,
                "case_name": case.name,
                "status": case.status,
                "file_name": case.file_name,
                "created_at": case.created_at.isoformat() if case.created_at else "",
                "record_counts": {
                    "chats": chat_count,
                    "calls": call_count,
                    "contacts": contact_count,
                },
            }
        )

    return {"cases": result, "total": len(result)}


@router.delete("/case/{case_id}")
def delete_case(case_id: str, db: Session = Depends(get_db)):
    case = db.query(Case).filter(Case.id == case_id).first()

    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    db.delete(case)
    db.commit()

    try:
        Path(case.file_path).unlink(missing_ok=True)
    except Exception:
        pass

    return {"success": True, "message": f"Case {case_id} deleted."}


def process_case_file(case_id: str, file_path: str, original_filename: str):
    from backend.database import SessionLocal

    db = SessionLocal()

    try:
        print(f"⏳ Processing case {case_id}...")

        parsed = parser.parse_file(file_path, original_filename)

        case = db.query(Case).filter(Case.id == case_id).first()

        if not case:
            raise Exception(f"Case {case_id} not found in database")

        case.name = parsed.case_name
        case.device_info = parsed.device_info

        flagged_count = 0

        for chat in parsed.chats:
            entities = extractor.extract(chat.message_text)
            is_flagged = entities.risk_score >= 3.0

            db_chat = ChatMessage(
                case_id=case_id,
                platform=chat.platform,
                sender=chat.sender,
                receiver=chat.receiver,
                message_text=chat.message_text,
                timestamp=chat.timestamp,
                direction=chat.direction,
                risk_score=entities.risk_score,
                entities_json=entities.to_dict(),
                is_flagged=is_flagged,
                flag_reason="Auto-flagged: high risk score" if is_flagged else "",
            )

            db.add(db_chat)

            if is_flagged:
                flagged_count += 1

        for call in parsed.calls:
            all_numbers = [call.caller_number, call.receiver_number]

            is_foreign = any(
                num.startswith(tuple(EntityExtractor.FOREIGN_COUNTRY_CODES.keys()))
                for num in all_numbers
                if num
            )

            risk = 2.0 if is_foreign else 0.0

            if call.duration_seconds > 600:
                risk += 1.0

            db_call = CallRecord(
                case_id=case_id,
                caller_number=call.caller_number,
                receiver_number=call.receiver_number,
                timestamp=call.timestamp,
                duration_seconds=call.duration_seconds,
                call_type=call.call_type,
                platform=call.platform,
                is_foreign_number=is_foreign,
                risk_score=risk,
            )

            db.add(db_call)

        for contact in parsed.contacts:
            entities = extractor.extract(contact.notes + " " + contact.organization)

            db_contact = Contact(
                case_id=case_id,
                name=contact.name,
                phone_numbers=contact.phone_numbers,
                email_addresses=contact.email_addresses,
                organization=contact.organization,
                notes=contact.notes,
                risk_score=entities.risk_score,
                entities_json=entities.to_dict(),
            )

            db.add(db_contact)

        for media in parsed.media:
            risk = 0.0

            if media.gps_latitude and media.gps_longitude:
                if not (
                    8 <= media.gps_latitude <= 37
                    and 68 <= media.gps_longitude <= 98
                ):
                    risk = 2.0

            db_media = MediaFile(
                case_id=case_id,
                file_name=media.file_name,
                file_type=media.file_type,
                file_size_bytes=media.file_size_bytes,
                timestamp=media.timestamp,
                gps_latitude=media.gps_latitude,
                gps_longitude=media.gps_longitude,
                source_app=media.source_app,
                sha256_hash=media.sha256_hash,
                risk_score=risk,
            )

            db.add(db_media)

        db.commit()

        print("Indexing into ChromaDB...")
        index_case_into_chroma(case_id)

        case.status = "ready"
        db.commit()

        print(f"✅ Case {case_id} processed successfully.")
        print(
            f"   Chats: {len(parsed.chats)}, Calls: {len(parsed.calls)}, "
            f"Contacts: {len(parsed.contacts)}, Media: {len(parsed.media)}"
        )
        print(f"   Auto-flagged: {flagged_count} suspicious messages")

    except Exception as e:
        try:
            case = db.query(Case).filter(Case.id == case_id).first()
            if case:
                case.status = "error"
                db.commit()
        except Exception:
            pass

        print(f"❌ Case {case_id} processing FAILED: {e}")

        import traceback

        traceback.print_exc()

    finally:
        db.close()

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
