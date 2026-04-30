#주피터 노트북(또는 코랩)에서 그 셀에 적힌 내용을 통째로 파일로 저장해라라는 매직 명령어

# ============================================================
# chatbot.py — LLM 기반 챗봇 핵심 로직
# ============================================================
# 📌 이 파일의 역할:
#    - 시스템 프롬프트 정의 (LLM에게 역할 부여)
#    - 의도 분류 함수 (LLM을 분류기로 활용)
#    - 답변 생성 함수 (의도별로 다른 프롬프트 사용)
#    - 메인 함수 (의도 분류 → 라우팅 → 답변)
#
# 📌 FastAPI(demo_api.py)가 이 파일을 import해서 사용합니다.
#    이렇게 분리하면 FastAPI 없이도 chatbot.py만으로 테스트 가능.
# ============================================================

import os
import json
from openai import OpenAI

# ── OpenAI 클라이언트 생성 ──
# 📌 환경 변수 OPENAI_API_KEY를 자동으로 읽습니다.
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))


# ============================================================
# 시스템 프롬프트 정의
# ============================================================
# 📌 시스템 프롬프트란?
#    LLM에게 "너는 어떤 역할이다"라고 알려주는 지시문.
#    같은 LLM이라도 프롬프트에 따라 완전히 다르게 동작합니다.
#
#    프롬프트 없이: "뭐든 대답하는 범용 AI"
#    프롬프트 있으면: "Llama 3.1 논문 전문가" / "의도 분류기" 등
# ============================================================

# ── 의도 분류용 프롬프트 ──
# 📌 LLM을 "분류기"로 사용하는 패턴 (Structured Output)
#    핵심: "JSON으로만 응답하라"고 강제하여 프로그래밍적으로 파싱 가능하게 함
INTENT_PROMPT = """You are an intent classifier for a Llama 3.1 paper chatbot.

Classify the user's query into EXACTLY ONE intent:

1. "paper_qa" — Questions about Llama 3 / 3.1 paper content
   (architecture, training, benchmarks, safety, RLHF, tokenizer, etc.)

2. "general_chat" — Greetings or broad AI/ML questions NOT about the paper
   ("hello", "what is deep learning?", etc.)

3. "off_topic" — Completely unrelated to AI/ML
   ("weather?", "cook pasta?", etc.)

Respond with ONLY JSON:
{"intent": "<intent>", "confidence": <0.0-1.0>, "reasoning": "<one-line>"}
"""

# ── 논문 전문가 프롬프트 (paper_qa용) ──
# 📌 "Llama 3.1 논문 전문가" 역할을 부여합니다.
#    실제 프로젝트에서는 여기에 RAG 검색 결과가 추가되지만,
#    이 데모에서는 LLM 자체 지식으로 답변합니다.
PAPER_QA_PROMPT = """You are an expert on the Llama 3.1 paper by Meta AI.
Answer questions about the paper's content: architecture, training data,
benchmark results, safety, RLHF, scaling laws, tokenizer, etc.

Be specific and include numbers/details when you know them.
If you're not sure about a specific detail, say so honestly.
Respond in the same language as the user's question."""

# ── 일반 대화 프롬프트 (general_chat용) ──
# 📌 친근한 AI 어시스턴트 역할.
#    논문 관련 질문이 오면 paper_qa로 안내합니다.
GENERAL_CHAT_PROMPT = """You are a friendly AI assistant that specializes in
the Llama 3.1 paper. You can discuss general AI/ML topics.
If the user asks about the Llama 3.1 paper specifically,
encourage them to ask detailed questions about the paper.
Respond in the same language as the user's question."""


# ============================================================
# 핵심 함수들
# ============================================================

def classify_intent(query: str) -> dict:
    """
    LLM으로 사용자 쿼리의 의도를 분류합니다.

    📌 동작 방식:
       1. INTENT_PROMPT(분류기 역할)를 시스템 프롬프트로 설정
       2. 사용자 쿼리를 전달
       3. LLM이 JSON으로 의도를 반환
       4. JSON 파싱 → dict 반환

    📌 temperature=0:
       분류는 항상 같은 결과가 나와야 하므로 창의성을 0으로 설정.

    Returns:
        {"intent": "paper_qa", "confidence": 0.95, "reasoning": "..."}
    """
    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": INTENT_PROMPT},
                {"role": "user", "content": query},
            ],
            temperature=0,      # 📌 분류는 결정적(deterministic)이어야 함
            max_tokens=150,     # 📌 JSON 한 줄이면 충분
        )
        text = resp.choices[0].message.content.strip()
        # 📌 방어적 파싱: LLM이 ```json```으로 감쌀 수 있음
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0]
        return json.loads(text)
    except Exception as e:
        # 📌 폴백: 파싱 실패 → paper_qa로 안전하게 분류
        return {"intent": "paper_qa", "confidence": 0.5, "reasoning": f"fallback: {e}"}


def paper_qa(query: str, chat_history: list = None) -> str:
    """
    논문 전문가 모드로 답변합니다.

    📌 chat_history를 함께 전달하여 멀티턴 대화를 지원합니다.
       이전 대화 맥락을 LLM이 기억하고 이어서 답변할 수 있습니다.

    📌 실제 프로젝트에서는 여기에 RAG 검색 결과를 주입하지만,
       이 데모에서는 LLM 자체 지식만으로 답변합니다.
    """
    messages = [{"role": "system", "content": PAPER_QA_PROMPT}]

    # 📌 이전 대화 이력 추가 (멀티턴)
    if chat_history:
        for msg in chat_history[-6:]:   # 최근 6개만 (토큰 절약)
            messages.append({"role": msg["role"], "content": msg["content"]})

    messages.append({"role": "user", "content": query})

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.3,     # 📌 논문 답변은 정확성 위주 → 낮은 temperature
        max_tokens=800,
    )
    return resp.choices[0].message.content


def general_chat(query: str, chat_history: list = None) -> str:
    """
    일반 대화 모드로 답변합니다.

    📌 paper_qa와의 차이:
       - 시스템 프롬프트가 다름 (친근한 어시스턴트 vs 논문 전문가)
       - temperature=0.7 (대화는 약간의 다양성 허용)
    """
    messages = [{"role": "system", "content": GENERAL_CHAT_PROMPT}]

    if chat_history:
        for msg in chat_history[-6:]:
            messages.append({"role": msg["role"], "content": msg["content"]})

    messages.append({"role": "user", "content": query})

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.7,     # 📌 대화는 약간의 창의성 허용
        max_tokens=500,
    )
    return resp.choices[0].message.content


def process_query(query: str, chat_history: list = None) -> dict:
    """
    ✨ 메인 함수 — 의도 분류 → 라우팅 → 답변 생성

    📌 이 함수 하나가 챗봇의 전체 흐름을 처리합니다:
       1) classify_intent()로 의도 파악
       2) 의도에 따라 적절한 함수 호출
       3) 통일된 형식으로 결과 반환

    📌 FastAPI의 /chat 엔드포인트가 이 함수를 호출합니다.
    """
    # ── Step 1: 의도 분류 ──
    intent_result = classify_intent(query)
    intent = intent_result.get("intent", "paper_qa")

    # ── Step 2: 의도별 라우팅 ──
    if intent == "paper_qa":
        answer = paper_qa(query, chat_history)
        pipeline = "Paper QA (LLM Expert)"

    elif intent == "general_chat":
        answer = general_chat(query, chat_history)
        pipeline = "General Chat (LLM)"

    elif intent == "off_topic":
        answer = (
            "죄송합니다, 저는 Llama 3.1 논문 전문 챗봇입니다. 🦙\n"
            "논문 내용이나 AI/ML 관련 질문을 해주세요!\n\n"
            "예시:\n"
            "- Llama 3의 파라미터 수는?\n"
            "- Transformer 아키텍처란?\n"
            "- RLHF가 뭔가요?"
        )
        pipeline = "Off-topic Handler"

    else:  # 폴백
        answer = paper_qa(query, chat_history)
        pipeline = "Paper QA (fallback)"

    return {
        "answer": answer,
        "intent": intent,
        "confidence": intent_result.get("confidence", 0.5),
        "reasoning": intent_result.get("reasoning", ""),
        "pipeline": pipeline,
    }
