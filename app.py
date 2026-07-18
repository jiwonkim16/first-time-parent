"""부모는 처음이라 — Streamlit 채팅 UI (서비스급).

디자인 방향: 불안한 초보 부모를 '안심시키는 따뜻함'.
크림 배경 + 세이지 그린 액센트 + 위험도별 신호등 색상.
정체성 고지(진단 도구 아님)를 히어로에 명시하고, 위험도 배지로 판단을 투명하게.
"""

import streamlit as st

from agent import graph

st.set_page_config(page_title="부모는 처음이라", page_icon="🍼", layout="centered")

# ─────────────────────────────────────────────────────────
# 커스텀 CSS — Streamlit 기본 테마를 서비스급으로 오버라이드
#   폰트(Gowun Batang: 따뜻한 명조 / Pretendard 계열 본문), 색, 카드, 배지
# ─────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Gowun+Batang:wght@400;700&family=Gowun+Dodum&display=swap');

    :root {
        --cream: #FBF7F0;
        --sage: #7C9A80;
        --sage-deep: #5A7A5E;
        --ink: #3A3A38;
        --warn: #E0A458;
        --high: #D46A6A;
        --low: #7C9A80;
    }
    .stApp { background: var(--cream); }
    /* 테마 상속 방지: 앱 전역 텍스트를 잉크색으로 명시 */
    .stApp, .stApp p, .stApp li, .stApp span, [class*="css"] {
        font-family: 'Gowun Dodum', sans-serif; color: var(--ink);
    }
    h1, h2, h3 { font-family: 'Gowun Batang', serif !important; }

    /* 히어로 */
    .hero {
        text-align: center; padding: 1.2rem 0 0.4rem;
    }
    .hero-title { font-size: 2.1rem; font-weight: 700; margin: 0; color: var(--sage-deep); }
    .hero-sub { font-size: 0.95rem; color: #7A756C; margin-top: 0.3rem; }

    /* 정체성 고지 카드 */
    .identity {
        background: #FFFFFF; border: 1px solid #EAE3D6; border-left: 4px solid var(--sage);
        border-radius: 14px; padding: 1rem 1.2rem; margin: 1rem 0 1.4rem;
        font-size: 0.9rem; line-height: 1.65; box-shadow: 0 2px 12px rgba(124,154,128,0.08);
        color: var(--ink);   /* 다크 테마 상속 방지: 흰 배경 위 글자색을 명시 */
    }
    .identity b { color: var(--sage-deep); }
    .identity .no { color: var(--high); }
    .identity .yes { color: var(--sage-deep); }

    /* 위험도 배지 */
    .badge {
        display: inline-block; padding: 0.18rem 0.7rem; border-radius: 999px;
        font-size: 0.8rem; font-weight: 700; color: #fff;
    }
    .badge.high { background: var(--high); }
    .badge.warn { background: var(--warn); }
    .badge.low  { background: var(--low); }
    .badge.scope { background: #9A94A8; }

    /* 채팅 버블 톤 조정 */
    [data-testid="stChatMessage"] {
        background: #FFFFFF; border-radius: 16px; border: 1px solid #EFE8DA;
        box-shadow: 0 1px 6px rgba(0,0,0,0.03);
        padding: 1rem 1.4rem;   /* 좌우 대칭 패딩: 아바타로 인한 오른쪽 여백 부족 보정 */
    }
    /* 메시지 본문이 아바타 옆에서 오른쪽 끝까지 꽉 차도록 */
    [data-testid="stChatMessageContent"] { padding-right: 0.5rem; }
    /* 근거 expander */
    [data-testid="stExpander"] { border: none; }

    /* ── 다크모드에서도 사이드바·입력창을 밝게 고정 ──────────────
       config.toml에 더해 이중 안전장치. 시스템 테마와 무관하게
       사이드바/입력창 배경을 흰색·글씨를 잉크색으로 명시한다. */
    [data-testid="stSidebar"] {
        background: #FFFFFF; border-right: 1px solid #EAE3D6;
    }
    [data-testid="stSidebar"] * { color: var(--ink); }
    /* 채팅 입력창 — 배경 흰색, 입력 텍스트/placeholder 가독성 확보 */
    [data-testid="stChatInput"] { background: #FFFFFF; }
    [data-testid="stChatInput"] textarea {
        color: var(--ink) !important; -webkit-text-fill-color: var(--ink) !important;
    }
    [data-testid="stChatInput"] textarea::placeholder { color: #9A948A !important; }
    /* 사이드바 입력 위젯 (이름·개월수) 배경·글씨 */
    [data-testid="stSidebar"] input {
        background: #FBF7F0 !important; color: var(--ink) !important;
        -webkit-text-fill-color: var(--ink) !important;
    }
    /* 예시 질문 버튼 */
    .stButton button {
        background: #FFFFFF; color: var(--ink); border: 1px solid #EAE3D6;
        border-radius: 12px; font-size: 0.86rem; text-align: left;
    }
    .stButton button:hover { border-color: var(--sage); color: var(--sage-deep); }
    </style>
    """,
    unsafe_allow_html=True,
)

# ─────────────────────────────────────────────────────────
# 히어로 + 정체성 고지 (기획 §2: "나는 ~한 도구가 아니다"를 처음부터 명시)
# ─────────────────────────────────────────────────────────
st.markdown(
    """
    <div class="hero">
        <p class="hero-title">🍼 부모는 처음이라</p>
        <p class="hero-sub">초보 부모가 당황하지 않고 스스로 판단하도록 돕는 육아 교육 코치</p>
    </div>
    <div class="identity">
        저는 <b>진단하거나 처방하는 의료 도구가 아니에요.</b> 아이의 상태를 대신 진단하거나
        병원에 갈지를 대신 결정하지 않습니다. 대신 이렇게 도와드려요:<br><br>
        <span class="no">✕</span> 증상을 진단하는 AI &nbsp;→&nbsp; <span class="yes">✓</span> 어떻게 대처할지 교육하는 코치<br>
        <span class="no">✕</span> 병원 갈지 대신 결정 &nbsp;→&nbsp; <span class="yes">✓</span> 상담이 필요한 신호를 알려주기<br>
        <span class="no">✕</span> 육아 정답 제시 &nbsp;→&nbsp; <span class="yes">✓</span> 공식 근거로 선택지 정리하기<br><br>
        모든 답변 끝에는 <b>실제 상담 연락처</b>를 함께 안내해요. 급하면 먼저 <b>1339</b>로 연락하세요.<br><br>
        <span style="color:#9A948A;">※ 이 코치는 <b>생후 12개월 이하</b> 아기를 대상으로 해요.</span>
    </div>
    """,
    unsafe_allow_html=True,
)

# ─────────────────────────────────────────────────────────
# 위험도 배지 HTML 생성 헬퍼
# ─────────────────────────────────────────────────────────
_BADGE = {
    "high": ('badge high', '🚨 높음 · 즉시 상담'),
    "warn": ('badge warn', '⚠️ 주의 · 오늘 진료'),
    "low": ('badge low', '🌿 낮음 · 관찰 가능'),
}


def badge_html(out: dict) -> str:
    """에이전트 결과를 위험도 배지 + 판단 근거로 렌더링.

    clarify(되묻기)·out_of_scope는 위험도 판단을 하지 않으므로 risk 키가 없다.
    """
    if not out.get("in_scope", True):
        return '<span class="badge scope">🔍 역할 범위 밖</span>'
    if out.get("needs_clarification"):
        return '<span class="badge scope">💬 조금 더 여쭤볼게요</span>'
    if "risk" not in out:  # 방어: 예기치 못한 경로
        return ""
    cls, label = _BADGE[out["risk"]]
    src = out.get("source_status")
    src_note = " · 📎 공식 근거" if src == "found" else ""
    return (
        f'<span class="{cls}">{label}</span>'
        f'<span style="font-size:0.78rem;color:#9A948A;margin-left:0.6rem;">'
        f'LLM {out["llm_risk"]} · rule {out["rule_risk"]}{src_note}</span>'
    )


# ─────────────────────────────────────────────────────────
# 세션 프로필 (기획 §4) — 아이 이름·월령을 세션 메모리에만 보관.
#   DB·파일에 저장하지 않으므로 탭을 닫으면(세션 종료) 즉시 사라진다.
#   미성년자 민감정보를 영속 저장소에 남기지 않기 위한 설계.
# ─────────────────────────────────────────────────────────
if "history" not in st.session_state:
    st.session_state.history = []
if "profile" not in st.session_state:
    st.session_state.profile = None   # {"name":..., "month":...} 또는 None

with st.sidebar:
    st.markdown("### 👶 아이 정보")
    if st.session_state.profile:
        p = st.session_state.profile
        st.info(f"**{p['name']}** · 생후 {p['month']}개월")
        st.caption("이 정보는 이 세션에만 임시로 쓰이고, 탭을 닫으면 사라져요.")
        # 세션 종료(정보 삭제): 프로필과 대화를 모두 비운다
        if st.button("🗑 정보 지우고 새로 시작", use_container_width=True):
            st.session_state.profile = None
            st.session_state.history = []
            st.rerun()
    else:
        st.caption("상담을 시작하려면 아이 정보를 입력해 주세요.")
        with st.form("profile_form"):
            name = st.text_input("아이 이름(또는 애칭)", placeholder="예: 민준")
            month = st.number_input("생후 개월 수", min_value=0, max_value=12, value=2)
            if st.form_submit_button("시작하기", use_container_width=True):
                if name.strip():
                    st.session_state.profile = {"name": name.strip(), "month": int(month)}
                    st.rerun()
                else:
                    st.warning("이름(또는 애칭)을 입력해 주세요.")

# 프로필이 없으면 채팅을 막고 안내만 (사이드바에서 입력 유도)
if not st.session_state.profile:
    st.info("👈 왼쪽에서 아이 정보를 입력하면 상담을 시작할 수 있어요.")
    st.stop()

for msg in st.session_state.history:
    with st.chat_message(msg["role"], avatar="🍼" if msg["role"] == "assistant" else "🧑"):
        if msg.get("badge"):
            st.markdown(msg["badge"], unsafe_allow_html=True)
        st.markdown(msg["content"])

# 첫 화면 예시 질문 — 무엇을 물어볼 수 있는지 보여줘 첫 진입 장벽을 낮춘다.
# 클릭하면 그 문장이 그대로 입력으로 들어간다. (대화 시작 후엔 숨김)
EXAMPLES = [
    "밤에 자주 깨서 안아줘야 겨우 자요",
    "요즘 이유식을 자꾸 뱉어내요",
    "또래보다 뒤집기가 늦은 것 같아요",
    "열이 38도인데 평소보다 축 처져요",
]
chip_prompt = None
if not st.session_state.history:
    st.caption("이런 걸 물어볼 수 있어요")
    cols = st.columns(2)
    for i, ex in enumerate(EXAMPLES):
        if cols[i % 2].button(ex, key=f"ex_{i}", use_container_width=True):
            chip_prompt = ex

# ─────────────────────────────────────────────────────────
# 입력 → 그래프 실행 → 렌더
# ─────────────────────────────────────────────────────────
# st.chat_input은 조건 없이 '항상' 호출해야 매 rerun마다 화면에 그려진다.
# (or 단축평가로 건너뛰면 그 rerun에서 입력창이 사라진다.)
typed = st.chat_input("예: 우리 애 2개월인데 열이 39도예요")
if prompt := (typed or chip_prompt):
    st.session_state.history.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="🧑"):
        st.markdown(prompt)

    with st.chat_message("assistant", avatar="🍼"):
        with st.spinner("상황을 살펴보는 중이에요..."):
            # 세션 프로필(이름·월령)을 그래프 초기 State로 주입.
            # analyze가 월령을 추출하지 않으므로 여기서 넘겨줘야 한다.
            p = st.session_state.profile
            # 다중턴 맥락: 최근 대화 이력을 그래프에 함께 넘긴다 (체크포인터 대신
            # session_state 사용 — §11 비영속 원칙 준수). 직전 몇 턴만 요약해 전달.
            recent = st.session_state.history[-6:-1]  # 방금 넣은 user 메시지 제외
            history_text = "\n".join(
                f"{'부모' if m['role'] == 'user' else '코치'}: {m['content'][:300]}"
                for m in recent
            )
            try:
                out = graph.invoke(
                    {
                        "input": prompt,
                        "history": history_text,
                        "name": p["name"],
                        "month": p["month"],
                    }
                )
            except Exception as e:
                # 키 누락·네트워크·API 오류 등: 트레이스백 대신 친화적 안내 (체크리스트).
                # 급한 상황을 대비해 상담 연락처는 항상 노출한다.
                out = None
                st.error(
                    "⚠️ 지금 답변을 불러오지 못했어요. 잠시 후 다시 시도해 주세요.\n\n"
                    "**급한 상황이라면 지체 없이 아래로 연락하세요.**\n"
                    "- 야간·주말 응급 상담: **응급의료포털 1339**\n"
                    "- 육아 종합 상담: **육아종합지원센터 1577-0756**"
                )
                with st.expander("문제 원인 (개발자용)"):
                    st.caption(f"{type(e).__name__}: {e}")

        if out is not None:
            badge = badge_html(out)
            if badge:
                st.markdown(badge, unsafe_allow_html=True)
            st.markdown(out["answer"])

    if out is not None:
        st.session_state.history.append(
            {"role": "assistant", "content": out["answer"], "badge": badge}
        )
