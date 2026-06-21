"""
generate_sample_data.py — Creates realistic synthetic UFDR-like forensic data.

WHY THIS FILE EXISTS:
  Real UFDR files are classified and can't be shared. For development and
  demo purposes, we generate synthetic data that LOOKS like real forensic
  exports. This data includes:
  - Realistic criminal investigation scenarios
  - Actual crypto address formats
  - Realistic phone number formats
  - Coded language drug dealers use
  - International number patterns

IMPORTANT ETHICS NOTE:
  This is SYNTHETIC data. No real people, no real crimes, no real numbers.
  It's designed to test the tool's ability to detect patterns, not to
  represent any real investigation.

RUN THIS SCRIPT ONCE:
  python data/sample_ufdr/generate_sample_data.py
  It creates: data/sample_ufdr/sample_case_001.json
"""

import json
import random
from datetime import datetime, timedelta
from pathlib import Path

# ── Seed for reproducibility ──────────────────────────────────
random.seed(42)

# ── Fake identities for our synthetic case ────────────────────
SUSPECTS = {
    "suspect_a": {
        "name": "Rahul Sharma",
        "numbers": ["+919876543210", "+919812345678"],
        "whatsapp": "+919876543210",
    },
    "suspect_b": {
        "name": "Amir Khan",
        "numbers": ["+919988776655", "+971501234567"],  # UAE number
        "whatsapp": "+919988776655",
    },
    "suspect_c": {
        "name": "Unknown",
        "numbers": ["+447911123456", "+919123456789"],  # UK number
        "whatsapp": "+447911123456",
    },
    "victim": {
        "name": "Priya Mehta",
        "numbers": ["+919090909090"],
        "whatsapp": "+919090909090",
    }
}

# ── Realistic crypto addresses (format-valid, not real) ───────
CRYPTO_ADDRESSES = [
    "1A1zP1eP5QGefi2DMPTfTL5SLmv7Divf",      # Bitcoin (starts with 1)
    "3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy",     # Bitcoin (starts with 3)
    "bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq",  # Bitcoin bech32
    "0x71C7656EC7ab88b098defB751B7401B5f6d8976F",   # Ethereum
    "TQn9Y2khEsLJW1ChVWFMSMeRDow5KcbLSE",    # TRON USDT
]

# ── Suspicious conversation templates ─────────────────────────
SUSPICIOUS_CHATS = [
    ("hey bhai, aaj raat ka kya plan hai? same place?", "haan bhai, 11 baje mil. same package."),
    ("wallet address bhej mujhe", "yaar send kar 0.5 BTC is address pe: 1A1zP1eP5QGefi2DMPTfTL5SLmv7Divf"),
    ("delivery ho gayi?", "haan bhai, 3 packet safe the. cash mil gaya."),
    ("police ka koi movement hai kya?", "nahi bhai, sab clear hai. aaj hi move karo."),
    ("wo Dubai wala account confirm hua?", "haan bhai, transfer ho gaya. 2 lakh USDT."),
    ("naya phone le lena, ye trace ho sakta hai", "ok bhai, kal new SIM lunga."),
    ("maal kab aayega?", "agle hafte shipment aayega. 5 kg."),
    ("boss ne bola hawala se bhej", "kal tak ho jaayega, 10 lakh ka."),
    ("BC1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq is address pe bhej", "done, 0.3 ETH bheja."),
    ("yeh fake documents ready hain?", "haan, 2 din mein deliver hoga."),
    ("bomb ka material kahan se milega?", "bhai yeh sab chhod, abhi sirf cash deal karo"),
    ("TQn9Y2khEsLJW1ChVWFMSMeRDow5KcbLSE pe USDT send karo", "ok 500 USDT bhej raha hoon"),
    ("Dubai se parcel aaya hai", "warehouse mein rakh. kal utha lena."),
    ("passports ready hain?", "2 are done. 3rd wala kal tak."),
    ("wo stranger se mat milo", "ok boss, samjha."),
]

# ── Normal conversations (to avoid all data being suspicious) ─
NORMAL_CHATS = [
    ("bhai kab aa raha hai?", "kal subah aaunga."),
    ("movie dekhne chalein?", "haan bhai, 7 baje chalte hain."),
    ("khana kha liya?", "haan abhi abhi."),
    ("exam kab hai tera?", "next Monday."),
    ("Happy birthday bhai!", "Thanks yaar!"),
    ("office mein aaj kuch nahi tha", "acha, boring tha kya?"),
    ("ghar kab aayega?", "thodi der mein."),
    ("match dekhna hai aaj?", "haan India ka game hai, zaroor."),
]


def random_timestamp(start_days_ago: int = 90, end_days_ago: int = 0) -> str:
    """Generate a random timestamp within a date range."""
    now = datetime.now()
    delta_days = random.randint(end_days_ago, start_days_ago)
    delta_hours = random.randint(0, 23)
    delta_minutes = random.randint(0, 59)
    ts = now - timedelta(days=delta_days, hours=delta_hours, minutes=delta_minutes)
    return ts.isoformat()


def generate_chats(num_suspicious=40, num_normal=60) -> list:
    """Generate a list of chat messages mixing suspicious and normal content."""
    chats = []
    msg_id = 1

    platforms = ["WhatsApp", "Telegram", "SMS", "Instagram"]

    # Generate suspicious chats
    for i in range(num_suspicious):
        sender_key = random.choice(["suspect_a", "suspect_b", "suspect_c"])
        receiver_key = random.choice([k for k in SUSPECTS.keys() if k != sender_key])
        sender = SUSPECTS[sender_key]
        receiver = SUSPECTS[receiver_key]

        convo = random.choice(SUSPICIOUS_CHATS)
        # Alternate between the two sides of conversation
        text = convo[i % 2]

        chats.append({
            "id": f"MSG_{msg_id:04d}",
            "platform": random.choice(platforms),
            "sender_number": random.choice(sender["numbers"]),
            "sender_name": sender["name"],
            "receiver_number": random.choice(receiver["numbers"]),
            "receiver_name": receiver["name"],
            "message": text,
            "timestamp": random_timestamp(90, 1),
            "direction": random.choice(["sent", "received"]),
            "thread_id": f"THREAD_{random.randint(1, 10):02d}",
        })
        msg_id += 1

    # Generate normal chats
    for i in range(num_normal):
        convo = random.choice(NORMAL_CHATS)
        sender_key = random.choice(list(SUSPECTS.keys()))
        receiver_key = random.choice([k for k in SUSPECTS.keys() if k != sender_key])

        chats.append({
            "id": f"MSG_{msg_id:04d}",
            "platform": random.choice(platforms),
            "sender_number": random.choice(SUSPECTS[sender_key]["numbers"]),
            "sender_name": SUSPECTS[sender_key]["name"],
            "receiver_number": random.choice(SUSPECTS[receiver_key]["numbers"]),
            "receiver_name": SUSPECTS[receiver_key]["name"],
            "message": convo[i % 2],
            "timestamp": random_timestamp(90, 1),
            "direction": random.choice(["sent", "received"]),
            "thread_id": f"THREAD_{random.randint(1, 10):02d}",
        })
        msg_id += 1

    # Shuffle so suspicious and normal are mixed
    random.shuffle(chats)
    return chats


def generate_calls(num_calls=50) -> list:
    """Generate call records including some to foreign numbers."""
    calls = []
    call_types = ["incoming", "outgoing", "missed"]
    platforms = ["GSM", "WhatsApp", "Telegram"]

    for i in range(num_calls):
        caller_key = random.choice(list(SUSPECTS.keys()))
        receiver_key = random.choice([k for k in SUSPECTS.keys() if k != caller_key])

        caller_num = random.choice(SUSPECTS[caller_key]["numbers"])
        receiver_num = random.choice(SUSPECTS[receiver_key]["numbers"])

        # Duration: 0 for missed calls, else 30s to 30min
        call_type = random.choice(call_types)
        duration = 0 if call_type == "missed" else random.randint(30, 1800)

        calls.append({
            "id": f"CALL_{i+1:04d}",
            "caller_number": caller_num,
            "caller_name": SUSPECTS[caller_key]["name"],
            "receiver_number": receiver_num,
            "receiver_name": SUSPECTS[receiver_key]["name"],
            "timestamp": random_timestamp(90, 1),
            "duration_seconds": duration,
            "call_type": call_type,
            "platform": random.choice(platforms),
        })

    return calls


def generate_contacts() -> list:
    """Generate address book contacts."""
    contacts = []
    for key, info in SUSPECTS.items():
        contacts.append({
            "id": f"CONTACT_{key.upper()}",
            "name": info["name"],
            "phone_numbers": info["numbers"],
            "email": f"{info['name'].lower().replace(' ', '.')}@gmail.com",
            "organization": random.choice(["", "Self Employed", "Trader", "Unknown"]),
            "notes": "",
        })

    # Add some extra contacts
    extra_contacts = [
        {"name": "Supplier Dubai", "numbers": ["+971521234567"], "email": ""},
        {"name": "Bhai London", "numbers": ["+447700900123"], "email": ""},
        {"name": "Cash Agent", "numbers": ["+919999888877"], "email": ""},
        {"name": "Lawyer Sahab", "numbers": ["+919111222333"], "email": "advocate@law.in"},
        {"name": "Raju Transport", "numbers": ["+919000111222"], "email": ""},
    ]

    for i, c in enumerate(extra_contacts):
        contacts.append({
            "id": f"CONTACT_EXTRA_{i+1:02d}",
            "name": c["name"],
            "phone_numbers": c["numbers"],
            "email": c["email"],
            "organization": "",
            "notes": "",
        })

    return contacts


def generate_media_metadata(num_files=30) -> list:
    """Generate metadata for photos/videos (NOT the actual files)."""
    media = []
    file_types = ["image/jpeg", "image/png", "video/mp4", "application/pdf", "audio/mpeg"]
    apps = ["WhatsApp", "Camera", "Telegram", "Downloads", "Screenshots"]

    # Add some files with suspicious GPS coordinates (known drug areas - fictional)
    gps_data = [
        (19.0760, 72.8777, "Mumbai"),       # Mumbai
        (28.7041, 77.1025, "Delhi"),
        (25.2048, 55.2708, "Dubai"),        # Foreign GPS!
        (51.5074, -0.1278, "London"),       # Foreign GPS!
        (None, None, "No GPS"),
    ]

    for i in range(num_files):
        gps = random.choice(gps_data)
        file_type = random.choice(file_types)
        ext = {"image/jpeg": "jpg", "image/png": "png", "video/mp4": "mp4",
               "application/pdf": "pdf", "audio/mpeg": "mp3"}.get(file_type, "bin")

        media.append({
            "id": f"MEDIA_{i+1:04d}",
            "file_name": f"IMG_{random.randint(1000,9999)}.{ext}",
            "file_type": file_type,
            "file_size_bytes": random.randint(50000, 5000000),
            "timestamp": random_timestamp(90, 1),
            "gps_latitude": gps[0],
            "gps_longitude": gps[1],
            "gps_location_name": gps[2],
            "source_app": random.choice(apps),
            "sha256_hash": f"{''.join(random.choices('0123456789abcdef', k=64))}",
        })

    return media


def generate_full_case() -> dict:
    """Assemble the complete synthetic UFDR case."""
    return {
        "case_metadata": {
            "case_id": "CASE_2024_MUMBAI_001",
            "device_info": {
                "manufacturer": "Samsung",
                "model": "Galaxy S21",
                "os": "Android 13",
                "imei": "352093001761481",  # fictional IMEI
                "phone_number": "+919876543210",
                "extraction_tool": "Cellebrite UFED 7.58",
                "extraction_date": datetime.now().isoformat(),
                "examiner": "Digital Forensics Lab",
            },
            "report_version": "1.0",
            "description": "Synthetic UFDR data for demonstration. All persons/numbers/transactions are fictional.",
        },
        "chat_messages": generate_chats(40, 60),
        "call_records": generate_calls(50),
        "contacts": generate_contacts(),
        "media_metadata": generate_media_metadata(30),
    }


if __name__ == "__main__":
    output_dir = Path(__file__).parent
    output_file = output_dir / "sample_case_001.json"

    print("⏳ Generating synthetic UFDR case data...")
    case_data = generate_full_case()

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(case_data, f, indent=2, ensure_ascii=False)

    # Print summary
    print(f"✅ Generated: {output_file}")
    print(f"   📱 Chat messages: {len(case_data['chat_messages'])}")
    print(f"   📞 Call records:  {len(case_data['call_records'])}")
    print(f"   👤 Contacts:      {len(case_data['contacts'])}")
    print(f"   🖼️  Media files:   {len(case_data['media_metadata'])}")
    print(f"\n   Total records: {sum([len(v) for v in case_data.values() if isinstance(v, list)])}")
