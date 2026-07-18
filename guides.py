"""
공식 근거 레지스트리 — 월령 × 주제 → 기관 자료 URL.

agent.py의 search_national_guide(tool)와 search_node가 소비한다.
순수 데이터 + 순수 함수만 두어 테스트·유지보수를 쉽게 한다.

주제(topic)는 '수면·수유·발달·안전·건강' 5개로 고정(Extracted.topic Literal과 일치).
아이사랑 세부 카테고리(관계와소통·행동·놀이와학습·배설 등)는 이 5개로 매핑해 넣는다 —
5개 밖의 키를 넣으면 lookup에서 절대 조회되지 않는 죽은 엔트리가 된다.
"""


def _band(month: int) -> str:
    """월령을 레지스트리 밴드로 정규화."""
    if month <= 3:
        return "1~3"
    if month <= 6:
        return "4~6"
    if month <= 9:
        return "7~9"
    return "10~12"


# (밴드, 주제) → "기관 - 제목 (URL)"
GUIDE_REGISTRY = {
    (
        "1~3",
        "수면",
    ): "아이사랑 - 1~3개월 수면 (https://www.childcare.go.kr/?menuno=431)",
    (
        "1~3",
        "건강",
    ): "아이사랑 - 1~3개월 건강과 일상 (https://www.childcare.go.kr/?menuno=432)",
    (
        "1~3",
        "수유",
    ): "아이사랑 - 1~3개월 수유 (https://www.childcare.go.kr/?menuno=429)",
    (
        "1~3",
        "발달",
    ): "아이사랑 - 1~3개월 성장발달 (https://www.childcare.go.kr/?menuno=425)",
    (
        "1~3",
        "안전",
    ): "아이사랑 - 1~3개월 안전 (https://www.childcare.go.kr/?menuno=428)",
    (
        "4~6",
        "발달",
    ): "아이사랑 - 4~6개월 발달 (https://www.childcare.go.kr/?menuno=290)",
    (
        "4~6",
        "안전",
    ): "아이사랑 - 4~6개월 안전 (https://www.childcare.go.kr/?menuno=436)",
    (
        "4~6",
        "수유",
    ): "아이사랑 - 4~6개월 수유·이유식 (https://www.childcare.go.kr/?menuno=437)",
    (
        "4~6",
        "수면",
    ): "아이사랑 - 4~6개월 배설·수면 (https://www.childcare.go.kr/?menuno=438)",
    (
        "4~6",
        "건강",
    ): "아이사랑 - 4~6개월 건강과 일상 (https://www.childcare.go.kr/?menuno=439)",
    (
        "7~9",
        "발달",
    ): "아이사랑 - 7~9개월 발달 (https://www.childcare.go.kr/?menuno=291)",
    (
        "7~9",
        "수유",
    ): "아이사랑 - 7~9개월 수유·영양 (https://www.childcare.go.kr/?menuno=443)",
    (
        "7~9",
        "수면",
    ): "아이사랑 - 7~9개월 배설·수면 (https://www.childcare.go.kr/?menuno=444)",
    (
        "7~9",
        "건강",
    ): "아이사랑 - 7~9개월 건강과 일상 (https://www.childcare.go.kr/?menuno=445)",
    (
        "7~9",
        "안전",
    ): "아이사랑 - 7~9개월 안전 (https://www.childcare.go.kr/?menuno=442)",
    (
        "10~12",
        "발달",
    ): "아이사랑 - 10~12개월 발달 (https://www.childcare.go.kr/?menuno=292)",
    (
        "10~12",
        "안전",
    ): "아이사랑 - 10~12개월 행동·안전 (https://www.childcare.go.kr/?menuno=448)",
    (
        "10~12",
        "수유",
    ): "아이사랑 - 10~12개월 수유·영양 (https://www.childcare.go.kr/?menuno=449)",
    (
        "10~12",
        "건강",
    ): "아이사랑 - 10~12개월 건강과 일상 (https://www.childcare.go.kr/?menuno=451)",
}

# 밴드에 없는 (주제) 보완용 — 전월령 공통 공식 페이지
GUIDE_FALLBACK = {
    "수면": "CDC - 안전 수면(SUID) (https://www.cdc.gov/sudden-infant-death/sleep-safely/)",
    "발달": "CDC - 발달 이정표 (https://www.cdc.gov/milestones)",
    "건강": "질병관리청 - 영유아 식이·탈수 (https://health.kdca.go.kr/healthinfo/)",
}


def lookup_guide(month: int, topic: str) -> str:
    """월령·주제로 §8 레지스트리에서 공식 근거를 찾는다. 없으면 'NOT_FOUND'.

    순수 함수(테스트 가능). tool과 노드가 공유한다.
    """
    hit = GUIDE_REGISTRY.get((_band(month), topic))
    if hit:
        return hit
    fb = GUIDE_FALLBACK.get(topic)
    return fb if fb else "NOT_FOUND"
