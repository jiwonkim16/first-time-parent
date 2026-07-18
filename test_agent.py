"""결정론적 안전 로직 테스트 (노트3: LLM 없는 부분은 == 단정 유지).

LLM 호출 노드(analyze/llm_risk/coach)는 비결정적이라 여기서 테스트하지 않는다.
여기서는 rule guardrail·aggregate·§9 정책 분기·라우팅·근거 레지스트리처럼
입력이 같으면 출력이 같은 부분만 검증한다.

실행: uv run pytest test_agent.py -vv
"""

import pytest

from agent import (
    aggregate_node,
    decide_node,
    lookup_guide,
    route_after_analyze,
    route_clarify,
    route_scope,
    rule_risk_node,
)


# ── rule guardrail (§7) ────────────────────────────────────
@pytest.mark.parametrize(
    "month, temp, red_flags, expected",
    [
        (2, 39.0, [], "high"),        # ≤90일 + 38.0℃↑
        (5, 38.5, [], "warn"),        # 90일~6개월 + 38.3℃↑
        (12, 36.0, [], "low"),        # 발열 없음
        (12, 40.5, [], "high"),       # 전월령 40.0℃↑
        (8, 39.5, [], "warn"),        # >6개월 + 39.4℃↑
        # red_flags: 발열이 없어도 응급 신호 하나로 high 강제 상향
        (10, 36.5, ["seizure"], "high"),
        (10, 36.5, ["unconscious"], "high"),
        (10, 36.5, ["no_urine_8h"], "high"),
        (10, 36.5, ["bilious_or_bloody_vomit"], "high"),
        (10, 36.5, ["vomiting_over_24h"], "high"),
        (10, 36.5, ["head_injury_followup"], "high"),
    ],
)
def test_rule_risk(month, temp, red_flags, expected):
    out = rule_risk_node({"month": month, "temp": temp, "red_flags": red_flags})
    assert out["rule_risk"] == expected


# ── aggregate 안전 바닥 (§7: finalRisk = max) ──────────────
def test_aggregate_takes_higher():
    # LLM이 low여도 rule이 high면 최종 high여야 안전
    assert aggregate_node({"llm_risk": "low", "rule_risk": "high"})["risk"] == "high"
    assert aggregate_node({"llm_risk": "warn", "rule_risk": "low"})["risk"] == "warn"
    assert aggregate_node({"llm_risk": "low", "rule_risk": "low"})["risk"] == "low"


# ── §9 소스×위험도 매트릭스 ────────────────────────────────
def test_decide_high_ignores_source():
    # high는 근거 유무 무관하게 즉시 병원 안내
    out = decide_node(
        {"risk": "high", "source_status": "not_found", "symptoms": "경련", "name": "민준"}
    )
    assert "응급" in out["answer"] or "소아청소년과" in out["answer"]


def test_decide_low_not_found_discloses():
    # low + 근거없음 → "공식 문서엔 특정 기준이 없지만 일반적으로…" 고지
    out = decide_node(
        {
            "risk": "low",
            "source_status": "not_found",
            "answer": "일반적인 안내 본문",
            "symptoms": "밤에 뒤척임",
            "name": "민준",
        }
    )
    assert "공식 문서" in out["answer"]


def test_decide_warn_not_found_recommends_hospital():
    # warn + 근거없음 → 확인된 자료 없음 고지 + 병원권고
    out = decide_node(
        {
            "risk": "warn",
            "source_status": "not_found",
            "answer": "코치 본문",
            "symptoms": "발진",
            "name": "민준",
        }
    )
    assert "확인" in out["answer"]  # "확인된 공식 자료를 찾지 못" 류 문구


# ── 라우팅 (노트1 조건부 edge) ─────────────────────────────
def test_route_clarify():
    assert route_clarify({"needs_clarification": True}) == "clarify"
    assert route_clarify({"needs_clarification": False}) == "proceed"


def test_route_after_analyze_safety_overrides_clarify():
    # 안전 우선: 되묻기가 필요하다 판정돼도 rule이 위험을 잡으면 되묻지 않는다
    # 2개월 39℃ = rule high → clarify로 새지 않고 위험판단으로 진행해야 함
    danger = {
        "needs_clarification": True,
        "in_scope": True,
        "month": 2,
        "temp": 39.0,
        "red_flags": [],
    }
    assert route_after_analyze(danger) == ["llm_risk", "rule_risk"]

    # 반대로 rule이 low이고 정보 부족이면 되묻는다
    unclear = {
        "needs_clarification": True,
        "in_scope": True,
        "month": 7,
        "temp": 0.0,
        "red_flags": [],
    }
    assert route_after_analyze(unclear) == "clarify"


def test_route_scope():
    assert route_scope({"in_scope": True}) == ["llm_risk", "rule_risk"]
    assert route_scope({"in_scope": False}) == "out_of_scope"


# ── §8 근거 레지스트리 조회 ────────────────────────────────
def test_lookup_guide_found():
    # 2개월 수면 → 1~3개월 밴드의 수면 URL을 찾아야 한다
    result = lookup_guide(2, "수면")
    assert "childcare.go.kr" in result

def test_lookup_guide_not_found():
    # 존재하지 않는 조합은 NOT_FOUND
    assert lookup_guide(2, "존재하지않는주제") == "NOT_FOUND"
