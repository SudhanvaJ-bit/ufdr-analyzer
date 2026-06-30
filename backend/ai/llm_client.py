"""
llm_client.py — Wrapper around LLM providers (Gemini + OpenAI fallback).

WHY THIS FILE EXISTS:
  We don't call Gemini directly from the query engine.
  Instead, we have ONE wrapper class that:
  - Tries Gemini first (if API key is set)
  - Falls back to OpenAI (if key is set)
  - Falls back to keyword summarizer (always works, no API needed)

  This pattern is called the "Strategy Pattern" — swap implementations
  without changing the code that calls it.

THREE MODES:
  1. GEMINI MODE:   Real AI answers. Needs GEMINI_API_KEY in .env
  2. OPENAI MODE:   Fallback AI. Needs OPENAI_API_KEY in .env
  3. OFFLINE MODE:  No API key? Formats results as readable summary.
                    Still useful for investigators!

INTERVIEW CONCEPT — Why not call Gemini directly?
  Abstracting the LLM behind a wrapper means:
  - Easy to switch providers (Gemini → Claude → LLaMA)
  - Easy to test without spending API credits (use offline mode)
  - One place to add retry logic, rate limiting, logging
"""

import json
from backend.config import settings


class LLMClient:
    """
    Unified LLM client with automatic fallback chain:
    Gemini → OpenAI → Offline summarizer
    """

    def __init__(self):
        self.mode = self._detect_mode()
        print(f"🤖 LLM Mode: {self.mode}")

    def _detect_mode(self) -> str:
        """Detect which LLM is available based on API keys."""
        if settings.GEMINI_API_KEY and settings.GEMINI_API_KEY != "your_gemini_api_key_here":
            return "gemini"
        elif settings.OPENAI_API_KEY and settings.OPENAI_API_KEY != "your_openai_api_key_here":
            return "openai"
        else:
            return "offline"

    def ask(self, question: str, context: str, system_prompt: str = "", topic_count: int = 1) -> dict:
        """
        Ask a question with context retrieved from ChromaDB.
        """
        system_prompt = system_prompt or FORENSIC_SYSTEM_PROMPT

        if self.mode == "gemini":
            return self._ask_gemini(question, context, system_prompt, topic_count)
        elif self.mode == "openai":
            return self._ask_openai(question, context, system_prompt)
        else:
            return self._offline_summary(question, context)

    def _ask_gemini(self, question: str, context: str, system_prompt: str, topic_count: int = 1) -> dict:
        """Call Google Gemini API."""
        try:
            import google.generativeai as genai
            genai.configure(api_key=settings.GEMINI_API_KEY)
            model = genai.GenerativeModel(settings.GEMINI_MODEL)

            token_budget = settings.MAX_RESPONSE_TOKENS + (
                max(topic_count - 1, 0) * settings.MAX_RESPONSE_TOKENS_PER_SUBQUESTION
            )

            topic_instruction = (
                f"\nThis question covers {topic_count} distinct topics. "
                f"Give each topic its own clearly labeled section, with "
                f"roughly EQUAL depth for each — do not exhaust your "
                f"answer on the first topic and leave the rest brief or "
                f"missing. Cover every topic completely before adding "
                f"extra detail to any single one.\n"
                if topic_count > 1 else ""
            )

            full_prompt = f"""{system_prompt}

FORENSIC EVIDENCE CONTEXT:
{context}

INVESTIGATOR'S QUESTION:
{question}
{topic_instruction}
Provide a clear, structured answer based ONLY on the evidence above.

FORMAT RULES (important — keep the answer scannable, not exhaustive):
- Start with a 1-2 sentence direct answer to the question.
- Then group similar/repeated evidence together instead of listing every
  matching record individually — e.g. "5 messages across Telegram,
  WhatsApp, and SMS reference the same Bitcoin address [1][2][3][4][5]"
  rather than a separate numbered block per message.
- Reference evidence using its [N] index from the context above rather
  than quoting the full record each time.
- If there are more than ~5 matching records, summarize the pattern and
  cite a few representative examples rather than enumerating all of them.
- If the evidence doesn't contain enough information, say so clearly and
  briefly rather than padding the answer.
"""
            response = model.generate_content(
                full_prompt,
                generation_config=genai.types.GenerationConfig(
                    max_output_tokens=token_budget,
                    temperature=0.1,
                )
            )
            return {
                "answer": response.text,
                "mode": "gemini",
                "model": settings.GEMINI_MODEL,
                "error": None,
            }
        except Exception as e:
            print(f"⚠️  Gemini failed: {e}. Falling back to offline mode.")
            return self._offline_summary(question, context, error=str(e))

    def _ask_openai(self, question: str, context: str, system_prompt: str) -> dict:
        """Call OpenAI API."""
        try:
            from openai import OpenAI
            client = OpenAI(api_key=settings.OPENAI_API_KEY)

            messages = [
                {"role": "system", "content": system_prompt or FORENSIC_SYSTEM_PROMPT},
                {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"},
            ]
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=messages,
                max_tokens=settings.MAX_RESPONSE_TOKENS,
                temperature=0.1,
            )
            return {
                "answer": response.choices[0].message.content,
                "mode": "openai",
                "model": "gpt-3.5-turbo",
                "error": None,
            }
        except Exception as e:
            print(f"⚠️  OpenAI failed: {e}. Falling back to offline mode.")
            return self._offline_summary(question, context, error=str(e))

    def _offline_summary(self, question: str, context: str, error: str = None) -> dict:
        """
        Offline fallback: format retrieved evidence as a readable summary.
        No API key needed. Still very useful for investigators.

        Instead of an AI-written paragraph, this returns a clean
        structured list of the retrieved evidence.
        """
        lines = context.strip().split("\n") if context else []

        # Filter out empty lines and format nicely
        evidence_lines = [l.strip() for l in lines if l.strip()]

        if not evidence_lines:
            answer = f"No relevant evidence found for: '{question}'"
        else:
            answer = f"📋 Evidence found for: '{question}'\n\n"
            answer += "The following records were retrieved from the database:\n\n"
            for i, line in enumerate(evidence_lines[:15], 1):
                answer += f"{i}. {line}\n"
            answer += f"\n[{len(evidence_lines)} total records retrieved]"
            if error:
                answer += f"\n\n⚠️ Note: AI summarization unavailable ({error}). "
                answer += "Add GEMINI_API_KEY to .env for AI-powered answers."

        return {
            "answer": answer,
            "mode": "offline",
            "model": "keyword_summary",
            "error": error,
        }

    def is_ai_available(self) -> bool:
        """Check if real AI is available (not offline mode)."""
        return self.mode in ("gemini", "openai")


# ── System Prompt ─────────────────────────────────────────────
FORENSIC_SYSTEM_PROMPT = """You are a digital forensics analysis assistant helping law enforcement officers
analyze evidence from seized digital devices.

Your role:
- Analyze the provided forensic evidence carefully
- Answer questions about chats, calls, contacts, and patterns in the data
- Highlight suspicious activity, foreign communications, and cryptocurrency transactions
- Present findings in a clear, professional manner suitable for investigation reports
- Always cite specific evidence (phone numbers, message content, timestamps) in your answers
- If asked about something not in the provided evidence, clearly state that

Important guidelines:
- You assist trained forensic officers — be precise and factual
- Do NOT make assumptions beyond what the evidence shows
- Flag any potentially illegal activity mentioned in the evidence
- Maintain professional language appropriate for law enforcement

Disclaimer: This analysis assists human experts. All findings must be verified
by a qualified digital forensic examiner before use in legal proceedings."""