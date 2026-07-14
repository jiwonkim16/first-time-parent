"""부모는 처음이라 — 교육형 육아 코치 (LangGraph 병렬 워크플로우).

이 에이전트의 정체성 (기획문서 §2):
    ❌ 아기 증상을 진단하는 AI          ✅ 부모의 의사결정을 돕는 교육 코치
    ❌ 병원 갈지 대신 결정하는 AI        ✅ 병원 상담이 필요한 신호를 교육하는 AI
    ❌ 육아 정답을 알려주는 AI           ✅ 공식 근거로 선택지를 정리해주는 AI

즉 의료 진단/판단은 하지 않는다. "어떻게 대처할지"를 교육하고,
응답마다 실제 상담 자원으로 연결한다.

── 그래프 흐름 (기획 §5) ──────────────────────────────────
    START
      ↓
    analyze  ── 자연어→구조화. 육아 무관이면 out_of_scope로 조기 종료
      ↓ (육아 질문일 때만)
    ┌── llm_risk  ‖  rule_risk ──┐   ← 병렬 처리(Parallelization)
    └──────── aggregate ─────────┘   ← finalRisk = max(llm, rule) 보수적 채택
      ↓
    route_by_risk (3-way 조건부 분기)
      ├ high  → decide                    (교육 생략, 즉시 병원 안내)
      ├ warn  → search → decide           (근거 조회 후 병원 권고 + 교육)
      └ low   → coach → search → decide   (주제별 관점 코칭 + 7단 교육)
      ↓
    END
────────────────────────────────────────────────────────
"""

from typing import Literal, Optional

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_core.tools import tool
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field
from typing_extensions import TypedDict

load_dotenv()

# temperature=0: 위험도 판단은 재현 가능해야 하므로 무작위성을 제거한다.
llm = init_chat_model("openai:gpt-4o-mini", temperature=0)

Risk = Literal["high", "warn", "low"]
# 위험도를 정수로 매핑해 max() 비교가 가능하게 한다. (문자열 비교로는 순서가 틀림)
_RISK_RANK = {"low": 0, "warn": 1, "high": 2}

# 응답마다 붙는 실제 상담 자원 연락처 (기획 §4). 진단 도구가 아니므로
# 최종 판단은 항상 사람(의료진/상담센터)에게 연결한다.
CONTACT_FOOTER = (
    "\n\n---\n"
    "📞 **바로 상담할 수 있는 곳**\n"
    "- 야간·주말 응급 상담: **응급의료포털 1339**\n"
    "- 육아 종합 상담: **육아종합지원센터 1577-0756**\n"
    "- 가까운 소아청소년과\n\n"
    "※ 저는 진단·처방을 하지 않는 **교육용 도구**입니다. "
    "실제 판단과 처치는 반드시 의료진과 확인하세요."
)


# ─────────────────────────────────────────────────────────
# 1. State — 노드 사이를 흐르는 공유 데이터
#    병렬 노드(llm_risk, rule_risk)는 서로 다른 필드에 써야 충돌하지 않는다.
# ─────────────────────────────────────────────────────────
class State(TypedDict):
    input: str
    name: str                  # 세션 프로필: 아이 이름 (UI에서 주입, 그래프 밖에서 관리)
    month: int                 # 세션 프로필: 월령 (UI에서 주입 — analyze가 덮어쓰지 않음)
    in_scope: bool             # analyze가 판정: 육아 질문인가?
    temp: float
    symptoms: str
    topic: str
    llm_risk: Risk             # LLM 판단 (병렬 branch 1)
    rule_risk: Risk            # 결정론적 rule 판단 (병렬 branch 2)
    risk: Risk                 # aggregate가 max()로 합친 최종값
    source: str
    answer: str


# ─────────────────────────────────────────────────────────
# 2. 구조화 추출/판단 스키마 — LLM이 자유 텍스트 대신 이 형태로만 답하게 강제
# ─────────────────────────────────────────────────────────
class Extracted(BaseModel):
    """analyze 노드가 자연어에서 뽑아낼 구조. 월령은 세션 프로필에서 오므로 추출하지 않는다."""

    in_scope: bool = Field(description="육아/아기 건강 관련 질문이면 true, 아니면 false")
    temp: float = Field(description="체온(섭씨). 언급 없으면 0")
    symptoms: str = Field(description="부모가 호소한 주요 상황/증상 요약")
    topic: Literal["수면", "수유", "발달", "안전", "건강"] = Field(
        description="가장 관련 있는 주제(코칭 관점)"
    )


class RiskVerdict(BaseModel):
    """llm_risk 노드의 판단 결과."""

    risk: Risk = Field(description="위험도: high / warn / low 중 하나")
    reason: str = Field(description="판단 근거 한 문장")


# ─────────────────────────────────────────────────────────
# 3. 근거 검색 도구 (기획 §8의 "조준" 방식 stub)
#    ponytail: 실제 라이브 검색/RAG는 defer. 월령×주제 라우팅의 뼈대만 dict로.
#    add when 공식 사이트 크롤링/allowed_domains 라이브 검색이 필요해질 때.
# ─────────────────────────────────────────────────────────
GUIDE_TABLE = {
    "수면": "아이사랑 - 안전 수면 원칙 (childcare.go.kr)",
    "수유": "아이사랑 - 월령별 수유량 가이드 (childcare.go.kr)",
    "발달": "아이사랑 - 월령별 발달 이정표 (childcare.go.kr)",
    "안전": "아이사랑 - 영유아 생활안전 가이드 (childcare.go.kr)",
    "건강": "질병관리청 - 영유아 발열/증상 대응 (health.kdca.go.kr)",
}


@tool
def search_official_guide(month: int, topic: str) -> str:
    """월령과 주제로 공신력 있는 기관의 근거 페이지를 조회한다."""
    return GUIDE_TABLE.get(topic, "확인된 공식 자료를 찾지 못했습니다.")


# ─────────────────────────────────────────────────────────
# 4. 노드 정의
# ─────────────────────────────────────────────────────────
def analyze_node(state: State):
    """자연어 입력 → 구조화. 육아 무관 질문은 in_scope=False로 걸러낸다 (기획 §8).

    월령(month)은 세션 프로필에서 이미 State에 들어와 있으므로 여기서 추출하지 않는다.
    → 부모가 매번 개월수를 말할 필요가 없고, §7 '되묻기' 월령 문제도 사라진다.
    """
    result = llm.with_structured_output(Extracted).invoke(
        "다음은 부모가 아이에 대해 한 말이다. 정보를 추출하라. "
        "육아·아기 건강과 무관한 질문(제품 추천, 일반 상식 등)이면 in_scope=false로 판정하라.\n"
        f"입력: {state['input']}"
    )
    return {
        "in_scope": result.in_scope,
        "temp": result.temp,
        "symptoms": result.symptoms,
        "topic": result.topic,
    }


def llm_risk_node(state: State):
    """LLM이 맥락을 읽어 위험도를 판단 (병렬 branch 1).

    정체성: '트리아지 보조'가 아니라 교육 코치의 관점. 진단이 아니라
    '병원 상담이 필요한 신호인지'를 보수적으로 가늠한다 (기획 §7).
    """
    verdict = llm.with_structured_output(RiskVerdict).invoke(
        "너는 초보 부모를 돕는 육아 교육 코치다. 진단은 하지 않는다. "
        "부모의 서술에서 '지금 병원 상담이 필요한 신호'가 있는지를 보수적으로 가늠하라. "
        "과잉경고(양치기소년)와 위험누락을 모두 피하라. 애매하면 한 단계 높게 보되, "
        "다음은 특별한 동반 신호가 없으면 low로 보라: 수면 패턴 변화(자주 깸·낮잠 거부), "
        "평소보다 조금 덜 먹음, 월령별 발달 걱정(뒤집기·앉기 등), 이유식 거부, "
        "힘들어하지 않는 변비. "
        "반대로 축 처짐·수유 거부·호흡 이상·경련 같은 동반 신호가 있으면 위험도를 올려라. "
        "위험도를 high/warn/low 중 하나로 답하라.\n"
        f"개월수: {state['month']}, 체온: {state['temp']}℃, 상황: {state['symptoms']}"
    )
    return {"llm_risk": verdict.risk}


def rule_risk_node(state: State):
    """근거 확정된 결정론적 rule (병렬 branch 2). 안전측 최소 위험도 강제 상향.

    ponytail: 기획 §7의 전체 rule 테이블(경련/의식소실/구토 담즙 등) 중 대표 subset만.
    발열 월령 밴드(AAP 기준)를 구현. add when 나머지 OR 신호까지 코드화할 때.
    체온 기준은 직장 체온 가정(측정부위 정규화는 defer).
    """
    month, temp = state["month"], state["temp"]
    # 신호는 OR 결합: 하나라도 참이면 발동 (기획 §7 "신호 결합 규칙")
    if 0 <= month <= 3 and temp >= 38.0:        # AAP: 3개월 이하 38℃↑ 즉시 진료
        risk: Risk = "high"
    elif temp >= 40.0:                          # CDC: 전월령 40℃↑
        risk = "high"
    elif 3 < month <= 6 and temp >= 38.3:       # AAP: 3~6개월 38.3℃↑
        risk = "warn"
    elif month > 6 and temp >= 39.4:            # AAP: 6개월↑ 39.4℃↑
        risk = "warn"
    else:
        risk = "low"
    return {"rule_risk": risk}


def aggregate_node(state: State):
    """두 판단 중 더 높은 위험도를 채택 (기획 §7: finalRisk = max(llm, rule)).

    핵심 안전 설계: 교육형으로 톤은 부드러워져도 이 안전 바닥은 절대 낮추지 않는다.
    LLM이 실수로 낮게 봐도 rule이 강제한 최소선이 max()로 살아남는다.
    """
    final = max(state["llm_risk"], state["rule_risk"], key=_RISK_RANK.get)
    return {"risk": final}


def search_node(state: State):
    """공식 근거를 조회 (warn/low 경로). 못 찾으면 '근거 없음'으로 진행 (기획 §9)."""
    result = search_official_guide.invoke(
        {"month": state["month"], "topic": state["topic"]}
    )
    return {"source": result}


def coach_node(state: State):
    """주제(topic)를 관점(lens)으로 쓰는 단일 코칭 노드 (근거 있는 low/warn, 기획 §6·§10).

    독립된 5개 노드가 아니라, 프롬프트에 topic을 주입해 관점만 바꾼다.
    search 뒤에 실행되므로 state['source']에 실제 근거가 채워져 있고,
    이를 5번 섹션에 인용한다. 위험도(risk)를 넘겨 warn/low 톤을 구분한다.
    """
    tone = (
        "위험도는 '주의'다. 오늘 중 소아과 방문을 권하는 톤으로, 2번 위험도 판단에서 이를 명확히 하라."
        if state["risk"] == "warn"
        else "위험도는 '낮음'이다. 집에서 관찰 가능하다는 안심되는 톤으로 답하라."
    )
    # 세션 프로필의 이름으로 개인화 (없으면 '아이'). 그래프 밖 UI에서 주입된 값.
    child = state.get("name") or "아이"
    answer = llm.invoke(
        "너는 초보 부모를 돕는 육아 교육 코치다. 진단·처방은 하지 않고, "
        "부모가 스스로 판단하도록 교육한다. 아래 상황을 다음 7단 구조로 한국어로 답하라. "
        "각 단계에 이모지 제목을 붙여라:\n"
        "1) 📋 지금 상황  2) 🔎 위험도 판단  3) ⚡ 지금 당장 할 일  "
        "4) 🚫 하지 말아야 할 일  5) 📖 왜 그런지 (근거 포함)  "
        "6) 👁 앞으로 관찰할 기준  7) 🏥 병원 상담이 필요한 신호\n"
        f"{tone}\n"
        "5번 섹션에는 아래 '참고 근거'의 출처를 반드시 명시하라.\n"
        f"아이 이름: {child} (자연스럽게 이름을 불러 개인화하라)\n"
        f"관점(주제): {state['topic']}\n"
        f"개월수: {state['month']}, 상황: {state['symptoms']}\n"
        f"참고 근거: {state.get('source', '확인된 자료 없음')}"
    ).content
    return {"answer": answer}


def decide_node(state: State):
    """최종 응답 확정 (기획 §5의 합류점). 연락처를 항상 덧붙인다.

    - high: 교육 생략, 즉시 병원/응급 안내 (기획 §9)
    - warn/low: coach_node가 이미 7단 answer를 채웠으므로 그대로 사용
    """
    if state["risk"] == "high":
        child = state.get("name") or "아이"
        answer = (
            f"🚨 **지금 바로 소아청소년과 또는 응급 상담에 연락하세요.**\n\n"
            f"{child}의 '{state['symptoms']}' 상황은 즉시 전문가 확인이 필요한 신호로 보입니다. "
            f"저는 진단을 하지 않으며, 지체 없이 아래 연락처로 상담하시길 권합니다."
        )
    else:  # warn/low — coach가 생성한 7단 교육 답변을 사용
        answer = state["answer"]

    return {"answer": answer + CONTACT_FOOTER}


def out_of_scope_node(state: State):
    """육아 무관 질문 거절 (기획 §8, 시나리오 5). 정체성을 재확인한다."""
    answer = (
        "🍼 저는 **초보 부모를 위한 육아 교육 코치**예요.\n\n"
        "아기의 수면·수유·발달·안전·건강 신호처럼 육아와 관련된 고민을 도와드릴 수 있어요. "
        "그 외 주제(제품 추천, 일반 상식 등)는 제 역할 범위 밖이라 도와드리기 어려워요.\n\n"
        "예: \"우리 애 2개월인데 열이 나요\", \"7개월인데 밤에 자주 깨요\" 처럼 물어봐 주세요!"
    )
    return {"answer": answer + CONTACT_FOOTER}


# ─────────────────────────────────────────────────────────
# 5. 라우팅 함수 (조건부 edge)
# ─────────────────────────────────────────────────────────
def route_scope(state: State):
    """analyze 직후: 육아 질문이면 두 위험판단으로 fan-out, 아니면 거절 노드로.

    리스트를 반환하면 LangGraph가 그 노드들을 동시에(병렬) 실행한다.
    무조건 edge로 rule_risk를 걸면 out_of_scope에도 실행돼 fan-in이 깨지므로,
    병렬 fan-out은 반드시 이 조건부 안에서 함께 관리한다.
    """
    return ["llm_risk", "rule_risk"] if state["in_scope"] else "out_of_scope"


def route_by_risk(state: State):
    """aggregate 직후: 위험도별 분기 (기획 §5).

    high는 검색을 기다리지 않고 즉시 안내. warn/low는 모두 근거 검색 후
    7단 코칭으로 합류한다(coach가 source를 인용하려면 search가 먼저여야 함).
    """
    return "decide" if state["risk"] == "high" else "search"


# ─────────────────────────────────────────────────────────
# 6. 그래프 조립
# ─────────────────────────────────────────────────────────
def build_graph():
    builder = StateGraph(State)
    builder.add_node("analyze", analyze_node)
    builder.add_node("out_of_scope", out_of_scope_node)
    builder.add_node("llm_risk", llm_risk_node)
    builder.add_node("rule_risk", rule_risk_node)
    builder.add_node("aggregate", aggregate_node)
    builder.add_node("coach", coach_node)
    builder.add_node("search", search_node)
    builder.add_node("decide", decide_node)

    builder.add_edge(START, "analyze")

    # 범위 판정 + 병렬 fan-out: in_scope면 [llm_risk, rule_risk] 동시 실행,
    # 아니면 out_of_scope로. (route_scope가 리스트를 반환해 병렬을 표현)
    builder.add_conditional_edges(
        "analyze",
        route_scope,
        ["llm_risk", "rule_risk", "out_of_scope"],
    )
    builder.add_edge("out_of_scope", END)

    # fan-in: 두 위험판단이 모두 끝나면 aggregate
    builder.add_edge("llm_risk", "aggregate")
    builder.add_edge("rule_risk", "aggregate")

    # 위험도 분기: high는 즉시 decide, warn/low는 search로
    builder.add_conditional_edges(
        "aggregate",
        route_by_risk,
        {"decide": "decide", "search": "search"},
    )
    builder.add_edge("search", "coach")        # warn/low: 근거 조회 후 7단 코칭
    builder.add_edge("coach", "decide")        # 코칭 답변을 decide가 마무리(연락처 첨부)
    builder.add_edge("decide", END)
    return builder.compile()


graph = build_graph()


# ─────────────────────────────────────────────────────────
# 7. self-check — 핵심 안전 로직이 깨지면 실패하는 최소 검증
# ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    # max() 안전 바닥: LLM이 low여도 rule이 high면 최종 high여야 한다
    assert aggregate_node({"llm_risk": "low", "rule_risk": "high"})["risk"] == "high"
    # rule 발열 밴드
    assert rule_risk_node({"month": 2, "temp": 39})["rule_risk"] == "high"
    assert rule_risk_node({"month": 5, "temp": 38.5})["rule_risk"] == "warn"
    assert rule_risk_node({"month": 12, "temp": 36})["rule_risk"] == "low"
    print("self-check OK")

    # end-to-end: 세션 프로필(name, month)을 주입하는 실사용 형태로 호출
    out = graph.invoke(
        {"input": "열이 39도에요. 어떻게 하면 좋을까요?", "name": "민준", "month": 2}
    )
    print(f"\n[high 케이스] risk={out['risk']} (llm={out['llm_risk']}, rule={out['rule_risk']})")
    print(out["answer"][:120], "...")

    out2 = graph.invoke({"input": "에어팟 추천해줘", "name": "민준", "month": 2})
    print(f"\n[out_of_scope] in_scope={out2['in_scope']}")
    print(out2["answer"][:80], "...")
