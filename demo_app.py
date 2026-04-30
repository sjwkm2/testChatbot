
import os, requests, streamlit as st

st.set_page_config(page_title="🦙 Llama 3.1 Chatbot", page_icon="🦙")



# 📌 FastAPI 서버 주소
#    Colab 내부에서는 같은 VM이므로 localhost로 통신 가능
#    배포 시에는 환경 변수로 실제 서버 주소를 주입
API_URL = os.environ.get("API_URL", "http://localhost:8000")
# ============================================================
# FastAPI 서버 주소 설정
# ============================================================
#
# 📌 이 줄이 하는 일:
#    "FastAPI 서버가 어디에 있는지" 주소를 지정합니다.
#    Streamlit이 질문을 보낼 때 이 주소로 HTTP 요청을 보냅니다.
#
#
# 📌 "http://localhost:8000" 이 뭔가?
#
#    localhost = 지금 이 코드가 실행되고 있는 컴퓨터 자기 자신
#    8000      = 포트 번호 (FastAPI가 대기하고 있는 문 번호)
#
#    Colab에서는 FastAPI와 Streamlit이 같은 VM(컴퓨터)에서 돌아가므로
#    localhost로 서로 통신할 수 있습니다.
#
#    만약 FastAPI를 다른 서버에 배포하면 주소가 달라집니다:
#    - 로컬 (같은 컴퓨터):  http://localhost:8000
#    - 다른 서버에 배포:    https://my-api-server.com
#
#
# 📌 os.environ.get("API_URL", "http://localhost:8000") 분해:
#
#    os.environ        = 운영체제의 환경 변수 저장소 (dict처럼 동작)
#    .get("API_URL")   = "API_URL"이라는 이름의 환경 변수를 찾아라
#    , "http://..."    = 못 찾으면 이 기본값을 사용해라
#
#    즉:
#    - 환경 변수 API_URL이 설정되어 있으면 → 그 값 사용
#    - 설정 안 되어 있으면              → http://localhost:8000 사용
#
#
# 📌 환경 변수란?
#    코드 바깥에서 설정하는 값입니다.
#    코드를 수정하지 않고도 서버 주소를 바꿀 수 있습니다.
#
#    설정하는 방법:
#    - 터미널:   export API_URL="https://my-server.com"
#    - Python:   os.environ["API_URL"] = "https://my-server.com"
#    - Colab:    앞 셀에서 os.environ["API_URL"] = "http://localhost:8000"
#
#
# 📌 왜 코드에 직접 주소를 안 쓰고 환경 변수를 쓰는가?
#
#    API_URL = "http://localhost:8000"    ← 이렇게 써도 동작은 함
#
#    하지만 이러면 배포할 때 코드를 직접 수정해야 합니다.
#    환경 변수를 쓰면 코드는 그대로 두고,
#    실행 환경(로컬/서버)에 따라 주소만 바꿔 넣을 수 있습니다.
#
#    로컬 개발:  export API_URL="http://localhost:8000"     ← 내 컴퓨터
#    배포 환경:  export API_URL="https://prod-server.com"   ← 실제 서버
#    코드 변경:  없음
#
# ============================================================

API_URL = os.environ.get("API_URL", "http://localhost:8000")

# ============================================================
# Session State — 멀티턴 대화의 핵심
# ============================================================
# 📌 Streamlit은 사용자가 입력할 때마다 이 파일 전체를 재실행합니다.
#    일반 변수: messages = []  → 재실행마다 초기화 → 대화 날아감
#    session_state: 재실행해도 유지됨 → 대화 이력 보존
#
# 📌 "messages" not in 조건:
#    첫 방문 시에만 빈 리스트 생성, 이후에는 기존 데이터 유지
if "messages" not in st.session_state:
    st.session_state.messages = []


# ── 사이드바 ──
with st.sidebar:
    st.title("⚙️ 설정")
    show_debug = st.toggle("🔍 분석 정보 표시", value=True)
    if st.button("🗑️ 대화 초기화", use_container_width=True):
        st.session_state.messages = []
        st.rerun()  # 📌 스크립트를 처음부터 다시 실행 → 화면 갱신
    st.divider()
    st.caption(
        "📌 **라우팅 규칙**\n\n"
        "📄 논문 질문 → Paper QA\n\n"
        "💬 일반 대화 → General Chat\n\n"
        "🚫 관계없는 질문 → 안내 메시지"
    )


# ── 메인 화면 ──
st.title("🦙 Llama 3.1 논문 챗봇")
st.caption("의도 분석 → 동적 라우팅 → LLM 답변 생성")


# ============================================================
# 이전 대화 이력 렌더링
# ============================================================
# 📌 session_state.messages에 저장된 메시지를 순서대로 표시
#    스크립트가 재실행될 때마다 이 루프가 돌면서 과거 대화를 다시 그림
#    → 사용자 입장에서는 대화가 계속 유지되는 것처럼 보임
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        # 📌 role="user"면 사람 아이콘, "assistant"면 로봇 아이콘 자동 적용
        st.markdown(msg["content"])

        # 분석 정보 (assistant 메시지에만, meta가 있을 때만)
        if msg["role"] == "assistant" and show_debug and msg.get("meta"):
            m = msg["meta"]
            emoji = {"paper_qa": "📄", "general_chat": "💬", "off_topic": "🚫"}
            with st.expander(
                f"{emoji.get(m['intent'], '❓')} {m['intent']} → {m['pipeline']}",
                expanded=False,
            ):
                st.write(f"확신도: {m['confidence']:.0%}")
                st.write(f"이유: {m['reasoning']}")


# ============================================================
# 채팅 입력 처리 — 새 메시지가 들어왔을 때
# ============================================================
# 📌 st.chat_input(): 화면 하단에 고정된 입력창
#    Enter 누르면 → 스크립트 재실행 → prompt에 입력값 할당
#
# 📌 왈러스 연산자 (:=)
#    if prompt := st.chat_input(...)  는 아래 두 줄과 같음:
#    prompt = st.chat_input(...)
#    if prompt:

if prompt := st.chat_input("질문을 입력하세요..."):

    # ── 1) 사용자 메시지를 session_state에 저장 + 화면에 표시 ──
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # ── 2) FastAPI 호출 + 응답 처리 ──
    with st.chat_message("assistant"):
        with st.spinner("🔄 분석 중..."):
            try:
                # 📌 대화 이력 구성: session_state에서 role/content만 추출
                #    meta 같은 부가 정보는 FastAPI에 보낼 필요 없음
                #    [:-1]로 방금 추가한 user 메시지는 제외 (query로 별도 전송)
                history = [
                    {"role": m["role"], "content": m["content"]}
                    for m in st.session_state.messages[:-1]
                ]

                # 📌 FastAPI의 POST /chat 엔드포인트 호출
                #    query: 현재 질문
                #    chat_history: 이전 대화 (멀티턴 맥락 전달)
                resp = requests.post(
                    f"{API_URL}/chat",
                    json={"query": prompt, "chat_history": history},
                    timeout=60,
                )
                data = resp.json()
                # 📌 data 구조 (FastAPI가 반환한 JSON):
                #    {
                #        "answer": "Llama 3는...",
                #        "intent": "paper_qa",
                #        "confidence": 0.95,
                #        "reasoning": "논문 관련 질문",
                #        "pipeline": "Paper QA (LLM Expert)"
                #    }

                answer = data["answer"]
                st.markdown(answer)

                meta = {
                    "intent": data["intent"],
                    "confidence": data["confidence"],
                    "reasoning": data["reasoning"],
                    "pipeline": data["pipeline"],
                }

                if show_debug:
                    emoji = {"paper_qa": "📄", "general_chat": "💬", "off_topic": "🚫"}
                    with st.expander(
                        f"{emoji.get(meta['intent'], '❓')} {meta['intent']} → {meta['pipeline']}",
                        expanded=False,
                    ):
                        st.write(f"확신도: {meta['confidence']:.0%}")
                        st.write(f"이유: {meta['reasoning']}")

            except requests.exceptions.ConnectionError:
                answer = "❌ API 서버에 연결할 수 없습니다. FastAPI 셀을 먼저 실행해주세요!"
                meta = None
                st.error(answer)
            except Exception as e:
                answer = f"❌ 오류: {e}"
                meta = None
                st.error(answer)

    # ── 3) 어시스턴트 응답을 session_state에 저장 ──
    # 📌 여기서 저장해야 다음 재실행 시 위의 for 루프에서 다시 표시됨
    #    meta도 함께 저장하여 분석 정보를 나중에도 볼 수 있게 함
    st.session_state.messages.append(
        {"role": "assistant", "content": answer, "meta": meta}
    )
