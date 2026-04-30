# ============================================================
# demo_api.py — FastAPI 서버 (chatbot.py를 REST API로 감쌈)
# ============================================================

# ── 라이브러리 임포트 ──

from fastapi import FastAPI
# 📌 FastAPI: Python 웹 프레임워크
#    이 라이브러리가 제공하는 기능:
#    - HTTP 요청(GET, POST 등)을 Python 함수에 연결
#    - 요청/응답 데이터를 자동으로 검증
#    - /docs 경로에 API 문서(Swagger UI)를 자동 생성

from pydantic import BaseModel
# 📌 Pydantic: 데이터 검증 라이브러리
#    API가 주고받는 데이터의 "틀(스키마)"을 정의합니다.
#    예: query는 반드시 문자열이어야 한다 → str로 선언
#    틀에 맞지 않는 요청이 오면 422 에러를 자동 반환합니다.
#
#    BaseModel을 상속한 클래스 = 데이터 틀 정의

import chatbot
# 📌 같은 폴더의 chatbot.py를 import
#    chatbot.process_query() 함수를 사용하기 위함.
#    FastAPI는 "요청을 받아서 전달하는 통로" 역할만 하고,
#    실제 LLM 호출은 chatbot.py가 담당합니다.
#
#    이렇게 분리하면:
#    - chatbot.py만 단독으로 테스트 가능 (FastAPI 없이)
#    - chatbot.py를 다른 서버 프레임워크(Flask 등)에서도 재사용 가능


# ── FastAPI 앱 인스턴스 생성 ──

app = FastAPI(title="Llama 3.1 Chatbot API")
# 📌 FastAPI() 호출 = 웹 서버 객체 생성
#    이 한 줄로 서버의 뼈대가 만들어집니다.
#    title은 /docs 페이지 상단에 표시되는 이름입니다.
#
#    아직 서버가 "실행"되는 것은 아닙니다.
#    실행은 uvicorn이 담당: uvicorn demo_api:app --port 8000
#                                    ~~~~~~~~ ~~~
#                                    파일명    이 변수명


# ============================================================
# 요청/응답 스키마 정의
# ============================================================

class ChatRequest(BaseModel):
    # 📌 클라이언트(Streamlit)가 보내는 데이터의 구조
    #    POST /chat 요청의 body에 이 형태의 JSON이 들어와야 합니다.
    #
    #    실제로 Streamlit에서 보내는 JSON 예시:
    #    {
    #        "query": "Llama 3의 파라미터 수는?",
    #        "chat_history": [
    #            {"role": "user", "content": "안녕"},
    #            {"role": "assistant", "content": "안녕하세요!"}
    #        ]
    #    }

    query: str
    # 📌 필수 필드. 반드시 문자열이어야 함.
    #    빠지거나 타입이 다르면 → 422 Validation Error 자동 반환

    chat_history: list = []
    # 📌 선택 필드. 기본값이 빈 리스트이므로 안 보내도 됨.
    #    멀티턴 대화를 위해 이전 대화 이력을 받습니다.
    #    Streamlit의 st.session_state.messages가 여기로 전달됩니다.


class ChatResponse(BaseModel):
    # 📌 서버가 클라이언트에게 반환하는 데이터의 구조
    #    이 형태에 맞게 JSON이 만들어져서 Streamlit에 전달됩니다.
    #
    #    실제 반환 JSON 예시:
    #    {
    #        "answer": "Llama 3는 405B 파라미터...",
    #        "intent": "paper_qa",
    #        "confidence": 0.95,
    #        "reasoning": "Llama 3 파라미터 관련 질문",
    #        "pipeline": "Paper QA (LLM Expert)"
    #    }

    answer: str         # 챗봇의 최종 답변 텍스트
    intent: str         # 분류된 의도 (paper_qa / general_chat / off_topic)
    confidence: float   # 의도 분류 확신도 (0.0 ~ 1.0)
    reasoning: str      # 의도 분류 이유 (한 줄)
    pipeline: str       # 사용된 파이프라인 이름


# ============================================================
# API 엔드포인트 정의
# ============================================================

@app.get("/health")
# 📌 데코레이터: 이 함수를 GET /health 요청에 연결합니다.
#    GET = 데이터를 "조회"할 때 사용하는 HTTP 메서드
#    브라우저 주소창에 http://localhost:8000/health 입력하면 호출됨
def health():
    return {"status": "ok"}
    # 📌 dict를 반환하면 FastAPI가 자동으로 JSON으로 변환합니다.
    #    Streamlit 사이드바에서 서버 상태 확인용으로 사용합니다.



#/chat 주소로 POST 요청이 들어오면 바로 밑에 연결된 chat() 함수를 자동으로 실행
@app.post("/chat", response_model=ChatResponse)
# 📌 데코레이터: 이 함수를 POST /chat 요청에 연결합니다.
#    POST = 데이터를 "전송"할 때 사용하는 HTTP 메서드
#    GET과 달리 body에 JSON 데이터를 담아 보낼 수 있음
#
#    response_model=ChatResponse:
#    반환값이 ChatResponse 스키마에 맞는지 자동 검증합니다.
#    맞지 않으면 서버 에러가 발생합니다.

def chat(request: ChatRequest):
    # 📌 매개변수 타입이 ChatRequest(BaseModel)이면
    #    FastAPI가 자동으로:
    #    1) HTTP body에서 JSON을 꺼내고
    #    2) ChatRequest 스키마에 맞는지 검증하고
    #    3) 맞으면 request 객체로 변환하여 전달
    #    4) 안 맞으면 422 에러 반환
    #
    #    이 과정을 "역직렬화(deserialization)"라고 합니다.

    result = chatbot.process_query(
        query=request.query,
        # 📌 request.query: Streamlit에서 보낸 사용자 질문 텍스트

        chat_history=request.chat_history,
        # 📌 request.chat_history: 이전 대화 이력
        #    chatbot.py 내부에서 LLM에게 이전 대화를 함께 전달하여
        #    "그 모델" 같은 맥락 참조를 이해할 수 있게 합니다.
    )
    # 📌 chatbot.process_query()가 반환하는 dict 예시:
    #    {
    #        "answer": "Llama 3는...",
    #        "intent": "paper_qa",
    #        "confidence": 0.95,
    #        "reasoning": "논문 관련 질문",
    #        "pipeline": "Paper QA (LLM Expert)"
    #    }

    return ChatResponse(**result)
    # 📌 **result: dict를 언패킹하여 ChatResponse 생성자에 전달
    #    ChatResponse(answer="...", intent="...", confidence=0.95, ...)
    #    와 동일합니다.
    #
    #    FastAPI가 이 객체를 JSON으로 변환하여 HTTP 응답으로 보냅니다.
    #    Streamlit에서는 resp.json()으로 이 JSON을 받습니다.
