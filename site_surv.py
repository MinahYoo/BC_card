# -*- coding: utf-8 -*-
"""
사이트 "생존 분석" 탭 본문(build_report.py가 만든 HTML 조각)을 화면용으로 다듬는다.

- 숫자·통계 로직은 건드리지 않는다: 원문에 있는 값(막대 길이·신뢰구간·표 셀)을 그대로 읽어 표시 방식만 바꾼다.
- 바꿀 문구가 원문에 없으면 AssertionError로 멈춘다(리포트가 바뀌었는데 조용히 어긋나는 일을 막는다).
- build_site.py(분석 산출물이 있을 때)와 build_site_offline.py(site_parts/ 조각만 있을 때)가 함께 쓴다.
"""
import re


def _rep(h, old, new, n=1):
    assert h.count(old) == n, f"원문 불일치({h.count(old)}≠{n}): {old[:50]!r}"
    return h.replace(old, new)


def _rep_any(h, old, new):
    assert old in h, f"원문 없음: {old[:50]!r}"
    return h.replace(old, new)


def tip(term, text, pre=""):
    """용어 뒤에 붙는 (?) 도움말. 화면의 .q 스타일과 공통 클릭 핸들러를 쓴다."""
    t = text.replace('"', "'")
    return f'<span class="hasq">{pre}{term}<button type="button" class="q" data-tip="{t}" aria-label="설명: {t}">?</button></span>'


# ---------------------------------------------------------------- Step 1: 용어 통일 ----------
def unify_terms(h):
    # 표·차트 라벨(원문 라벨 → 화면 라벨). 앱의 요인 라벨과 같은 말을 쓴다.
    for old, new in [("사업장 확장", "점포 규모·운영 특성"), ("자기·이웃 이력", "지역 폐업 흐름"), ("BC 연령", "BC카드 고객 연령대"),
                     ("BC 성별", "BC카드 고객 성별"), ("그룹 직전 폐업률", "지역·업종 직전 폐업률")]:
        h = _rep_any(h, f">{old}<", f">{new}<")
    h = _rep(h, "<th>전체 배수</th>", "<th>폐업 위험도(배수)</th>", 2)

    # 본문 문구(개별)
    pairs = [
        ("영업연수·점포 성격·프랜차이즈가 만든다", "영업연수·점포 규모·운영 특성·프랜차이즈가 만든다"),
        ("영업연수·사업장 성격·프랜차이즈가 점포 수준의 판별을 만듭니다.", "영업연수·점포 규모·운영 특성·프랜차이즈가 점포 수준의 판별을 만듭니다."),
        ("자기·이웃 지역 폐업 이력과 BC 연령 구성이", "지역 폐업 흐름과 BC카드 고객 연령대가"),
        ("BC 성별 구성은 빼는 편이 오히려 낫습니다(주황).", "BC카드 고객 성별은 빼는 편이 오히려 낫습니다."),
        ("고객 연령 구성은 “지역 유형”의 신호일 뿐", "BC카드 고객 연령대는 “지역 유형”의 신호일 뿐"),
        ("연령 구성은 시군구 간 순위에는", "연령대 구성은 시군구 간 순위에는"),
        ("남은 공간 구조는 “이웃 지역의 최근 폐업 흐름” 하나로 설명된다", "남은 공간 구조는 “지역 폐업 흐름” 하나로 설명된다"),
        ("이웃 시군구의 폐업 이력이라는 해석 가능한 변수만으로", "이웃 시군구까지 포함한 지역 폐업 흐름이라는 해석 가능한 변수만으로"),
        ("5. 남은 공간 구조와 이웃 폐업 이력", "5. 남은 공간 구조와 지역 폐업 흐름"),
        ("이웃 시군구의 1/1 이전 1년 폐업률을 더하면", "이웃 시군구의 2026-01-01 기준 직전 1년 폐업률을 더하면"),
        ("이웃 폐업 이력은 지역 국면의 대리 변수입니다.", "지역 폐업 흐름은 지역 국면의 대리 변수입니다."),
        ("(같은 시군구·업종의 1/1 영업 점포 수)", "(같은 시군구·업종에서 2026-01-01에 영업 중인 점포 수)"),
        ("사업장 성격·이웃 폐업 이력이 높으며", "점포 규모·운영 특성·지역 폐업 흐름이 높으며"),
        ("점포 성격과 지역 폐업 흐름 위에", "점포 규모·운영 특성과 지역 폐업 흐름 위에"),
        ("점포 성격(영업연수·프랜차이즈·규모)", "점포 특성(영업연수·프랜차이즈·규모)"),
        ("배수는 인과가 아니라 연관입니다.", "폐업 위험도는 인과가 아니라 연관입니다."),
        ("배수와 순위 개선은 관측된 연관이며", "폐업 위험도(배수)와 순위 개선은 관측된 연관이며"),
        ("예측에 기여가 없는 입지·그룹 직전 폐업률 열은 뺐습니다.", "예측에 기여가 없는 입지·지역·업종 직전 폐업률 열은 뺐습니다."),
        ("시군구 더미 255개를 그룹 1,090개에 적합한 값이라", "시군구 더미 255개를 지역·업종 조합 1,090개에 맞춘 값이라"),
        ("미학습 시군구 외삽", "학습에 쓰지 않은 시군구 예측(외삽)"),
        ("예상보다 폐업이 많은 군집 (M3 잔차 기준)", "예상보다 폐업이 많은 군집 (이웃 폐업 흐름을 넣기 전 모형의 잔차 기준)"),
        ("모형에 더해 본 것과 결과 (M3 또는 M4 대비 미학습 그룹 순위 변화, ΔSpearman)", "모형에 더해 본 것과 결과 (기본 모형 대비, 학습에 쓰지 않은 지역·업종 조합의 순위 변화 · ΔSpearman)"),
        ("(M3L, p=0.23)", "(최종 모형, p=0.23)"),
        ("최종 모형(M3L)에서", "최종 모형에서"),
        ("“어느 지역인가”를 가릅니다. 파랑 = 신뢰구간이 0을 제외.", "“어느 지역인가”를 가릅니다. 다만 BC카드 고객 연령대는 같은 시군구 안에서는 도움이 되지 않아(아래 차트), 원인이 아니라 지역 유형의 신호로 읽어야 합니다."),
        ("지역의 최근 폐업 흐름을 결합해야 합니다.", "지역 폐업 흐름을 결합해야 합니다."),
    ]
    for old, new in pairs:
        h = _rep(h, old, new)

    # Moran 차트의 모형 단계 라벨: 모델 코드(M2·M3…) 대신 무엇을 넣었는지로 표기(코드 대응은 통계 상세에)
    for old, new in [("모형 없음(원자료)", "① 모형 없음(원자료)"), ("M2 사업장", "② 점포 특성만"), ("M2h + 그룹 폐업률", "③ + 지역·업종 직전 폐업률"),
                     ("M3 + BC 성별·연령", "④ + BC카드 고객 성별·연령대"), ("M3L + 이웃 폐업 이력", "⑤ + 지역 폐업 흐름(최종 모형)")]:
        h = _rep(h, f">{old}<", f">{new}<")

    # 스넥 → 스낵(표시만; 데이터 키는 그대로)
    h = _rep_any(h, "스넥 · 점포", "스낵 · 점포")
    # 블록 → 요인 묶음, 그룹 → 지역·업종 조합 (일괄)
    h = h.replace("블록", "요인 묶음").replace("그룹", "지역·업종 조합")
    # 장 표기(결론 A~E와 겹치지 않게)
    for n in "12345":
        h = re.sub(rf"<h2>{n}\. ", f"<h2>{n}장. ", h)
    h = _rep(h, "<h2>6. BC카드", "<h2>6장. BC카드")
    for i, ch in enumerate("ABCDE", 1):
        h = _rep(h, f'<div class="n">{i}</div>', f'<div class="n">{ch}</div>')
    return h


# ---------------------------------------------------------------- Step 1: 용어 (?) 풀이 ----------
GLOSS = [
    # (원문 안의 위치 문맥, 용어, 도움말) — 처음 나오는 곳 한 번만 단다
    ("(5-fold 교차검증)", "교차검증", "데이터를 5개로 나눠 한 조각씩 빼 두고, 그 조각에서 예측이 맞는지 확인하는 방법이에요. 이미 본 데이터가 아니라 처음 보는 데이터에서의 성능을 재요."),
    ("학습에 쓰지 않은 지역·업종 조합(5-fold", "학습에 쓰지 않은 지역·업종 조합", "모형을 만들 때 쓰지 않고 따로 빼 둔 조합이에요. 처음 보는 곳에서도 맞히는지 확인하려고 써요."),
    ("(조정 R² 0.44)", "조정 R²", "설명력을 0~1로 나타낸 값이에요. 클수록 그 정보만으로 폐업률 차이를 잘 설명해요."),
    ("(순위상관 +0.02)", "순위상관", "두 값의 순위가 얼마나 비슷한지를 -1~+1로 나타낸 값이에요. 0이면 관계가 없어요."),
    ("신뢰구간이 0을 포함)", "신뢰구간", "결과가 우연으로 흔들릴 수 있는 범위(95%)예요. 이 범위가 0을 포함하면 차이가 확실하지 않다는 뜻이에요."),
    ("판별력(C-index)", "C-index", "폐업할 점포와 남을 점포를 얼마나 잘 가려내는지를 나타낸 값이에요(0.5는 무작위, 1은 완벽)."),
    ("잔차의 공간 자기상관", "잔차", "모형이 설명하지 못하고 남은 부분(실제 − 예측)이에요."),
    ("(Moran’s I)이", "Moran’s I", "이웃한 지역끼리 값이 비슷한 정도(공간 자기상관)예요. 0에 가까울수록 이웃끼리 닮은 패턴이 남아 있지 않다는 뜻이에요."),
    ("시군구 단위 부트스트랩", "부트스트랩", "데이터를 여러 번 다시 뽑아 결과가 얼마나 흔들리는지 재는 방법이에요."),
    ("더미 변수로 설명한 정도", "더미 변수", "시군구나 업종을 ‘해당/아님’(1/0)으로 구분해 넣은 변수예요."),
    ("(1월, 업종 내 3분위)별 폐업률", "3분위", "값을 낮음·중간·높음 세 구간으로 나눈 것이에요."),
    ("한 요인 묶음을 빼고", "요인 묶음", "모형에 넣은 변수들을 성격별로 묶은 것이에요(예: 영업연수, 프랜차이즈, BC카드 변수). 한 묶음을 통째로 빼 봐요."),
    ("“지역 폐업 흐름” 하나로", "지역 폐업 흐름", "이 시군구와 이웃 시군구에서 2026-01-01 기준 직전 1년 동안 폐업한 점포의 비율이에요."),
]


def add_glossary(h):
    for ctx, term, text in GLOSS:
        assert h.count(ctx) >= 1, f"용어 문맥 없음: {ctx}"
        i = h.index(ctx)
        j = i + ctx.index(term) + len(term)
        # 문맥 안에서 용어 끝까지를 <span>으로 감싼다
        start = i + ctx.index(term)
        h = h[:start] + tip(term, text) + h[j:]
    return h


# ---------------------------------------------------------------- Step 1: SVG 막대 차트 → HTML 막대 ----------
_ROW = re.compile(
    r'<text x="([\d.]+)" y="[\d.]+" text-anchor="end" class="lbl">(.*?)</text>'
    r'<rect x="(-?[\d.]+)" y="[\d.]+" width="([\d.]+)" height="[\d.]+" rx="3" class="bar (\w+)"/>'
    r'((?:<line [^>]*class="whisk"/>)*)'
    r'<text [^>]*class="val">(.*?)</text>')
_SVG = re.compile(r'<svg viewBox="0 0 (\d+) (\d+)" role="img" class="chart">(.*?)</svg>', re.S)


KINDS = [("점포 단위 판별력 하락(ΔC-index)", "c"), ("지역 간 순위 하락(ΔSpearman, 95% CI)", "s"), ("같은 시군구 안 순위 하락(ΔSpearman, 95% CI)", "w"),
         ("폐업률 차이를 설명하는 정도(조정 R²)", ""), ("점포당 소비 구간별 폐업률", ""), ("객단가 구간별 폐업률", ""), ("모형 단계별 Moran’s I", "")]
_SW = lambda c, t: f'<span class="lgi"><span class="sw {c}"></span>{t}</span>'
LEGEND = {
    "c": _SW("pos", "★ 뚜렷한 기여(ΔC-index 0.003 초과)") + _SW("muted", "기여 미약"),
    "s": _SW("pos", "★ 유의: 95% 신뢰구간이 0을 제외") + _SW("muted", "구간이 0을 포함(뚜렷한 차이 없음)"),
    "w": _SW("pos", "★ 유의: 95% 신뢰구간이 0을 제외") + _SW("muted", "구간이 0을 포함") + _SW("neg", "▼ 구간이 0 미만: 빼는 편이 오히려 나음"),
}


def _hbars(m, idx=0):
    """build_report.hbar()가 그린 SVG를 같은 좌표 그대로 % 위치의 HTML 막대로 옮긴다(값·CI 계산을 새로 하지 않는다)."""
    W, body = int(m.group(1)), m.group(3)
    rows = _ROW.findall(body)
    assert rows, "hbar 행을 못 읽음"
    x0, x1 = float(rows[0][0]) + 8, W - 70.0            # build_report.hbar: 라벨 x = label_w-8, 막대 영역 끝 = width-70
    ax = re.search(r'<line x1="([\d.]+)" x2="\1" y1="6" y2="[\d.]+" class="axis"/>', body)
    pct = lambda x: max(0.0, min(100.0, (x - x0) / (x1 - x0) * 100))
    zero = pct(float(ax.group(1))) if ax else 0.0
    title, kind = KINDS[idx]
    star = {"pos": "★ ", "neg": "▼ "} if kind else {}
    aria = title + ": " + ", ".join(f"{re.sub('<[^>]+>', '', r[1])} {r[6]}" for r in rows)
    out = [f'<p class="lgd">{LEGEND[kind]}</p>' if kind else "", f'<div class="hb" role="group" aria-label="{aria}">']
    for lx, lab, rx, rw, cls, whisk, val in rows:
        l, w = pct(float(rx)), float(rw) / (x1 - x0) * 100
        trk = f'<i class="zero" style="left:{zero:.2f}%"></i><i class="hbar {cls}" style="left:{l:.2f}%;width:{w:.2f}%"></i>'
        xs = [(float(a), float(b)) for a, b in re.findall(r'<line x1="([\d.]+)" x2="([\d.]+)" y1="[\d.]+" y2="[\d.]+" class="whisk"/>', whisk)]
        if xs:                                            # 첫 선 = 가로 신뢰구간, 나머지 둘 = 양 끝 마디
            lo, hi = pct(xs[0][0]), pct(xs[0][1])
            trk += f'<i class="wk" style="left:{lo:.2f}%;width:{hi - lo:.2f}%"></i><i class="wkc" style="left:{lo:.2f}%"></i><i class="wkc" style="left:{hi:.2f}%"></i>'
        out.append(f'<div class="hbrow" data-cls="{cls}"><div class="nm">{star.get(cls, "")}{lab}</div><div class="trk">{trk}</div><div class="val">{val}</div></div>')
    out.append("</div>")
    return "".join(out)


def bars_to_html(h):
    it = iter(range(len(KINDS)))
    h, n = _SVG.subn(lambda m: _hbars(m, next(it)), h)
    assert n == len(KINDS), f"막대 차트 수가 달라짐: {n}"
    return h


def transform_step1(h):
    h = unify_terms(h)
    h = add_glossary(h)
    h = bars_to_html(h)
    return h


# ---------------------------------------------------------------- Step 2: 정보 구조 ----------
TIP_MIN = ("지역·업종 조합 표는 점포 300개 이상, 시군구 전체 Top 10은 2,000개 이상, 소비 산점도는 100개 이상만 넣어요. "
           "다루는 단위마다 점포 수가 달라서 기준을 다르게 뒀어요. 점포가 적으면 폐업률이 우연으로 크게 흔들려요.")


def how(text):
    return f'<p class="how"><b>읽는 법</b> {text}</p>'


def _after(h, anchor, add, n=1):
    assert h.count(anchor) == n, f"앵커 불일치({h.count(anchor)}≠{n}): {anchor[:60]!r}"
    return h.replace(anchor, anchor + add)


def _split_sections(h):
    idx = [m.start() for m in re.finditer(r"<h2>", h)]
    assert idx and idx[0] == 0
    parts = [h[a:b] for a, b in zip(idx, idx[1:] + [len(h)])]
    return {re.match(r"<h2>(.*?)</h2>", x).group(1): x for x in parts}


def _find(secs, prefix):
    ks = [k for k in secs if k.startswith(prefix)]
    assert len(ks) == 1, f"섹션 못 찾음: {prefix}"
    return ks[0]


def _fold(sec, plain, summary="통계 상세 (심사·연구자용)"):
    """제목 바로 아래에 일반인용 한 줄을 두고, 나머지(통계 전문 내용)는 기본 닫힘 접이식에 넣는다. 내용은 지우지 않는다."""
    m = re.match(r"(<h2>.*?</h2>)(.*)", sec, re.S)
    return f'{m.group(1)}<p class="plain">{plain}</p><details class="stat"><summary>{summary}</summary><div class="statbody">{m.group(2)}</div></details>'


SUMMARY = (
    '<div class="sumbox"><h2 style="margin:0 0 4px">이 서비스는 무엇이고, 결론은 무엇인가요?</h2>'
    '<p class="plain" style="margin:0 0 8px">전국 시군구의 7개 업종 점포가 2026년 상반기 180일 동안 실제로 문을 닫은 기록을 바탕으로, 어느 지역·업종이 평균 점포보다 폐업 위험이 높은지, 그리고 왜 그런지를 지도로 보여 줘요.</p>'
    '<ol class="sumlist"><li><b>위험은 업종보다 지역에서 더 크게 갈려요.</b> 시군구만으로 설명한 정도가 업종만의 약 4배예요.</li>'
    '<li><b>소비가 많다고 버티지는 않아요.</b> BC카드 소비 지표를 더해도 폐업 예측은 좋아지지 않았어요.</li>'
    '<li><b>점포는 영업연수·점포 규모·운영 특성·프랜차이즈가, 지역은 지역 폐업 흐름이 위험을 가장 잘 설명해요.</b></li></ol>'
    '<p class="hint" style="margin:6px 0 10px">모두 연관이며 인과가 아니에요. 아래에서 BC카드에 주는 시사점과 근거를 볼 수 있어요.</p>'
    '<div class="sumcta"><button type="button" class="chip-b pri" data-go-tab="map">지도에서 확인하기 →</button>'
    '<a class="chip-b" href="#implications" data-jump="implications">BC카드에 주는 시사점 보기</a></div></div>')

# 시사점 4개: 원문 문장은 그대로 두고 “누가 · 무엇을 · 어떤 데이터로”로 구조화한다(누가는 적용 주체를 정리한 표현)
IMPS = [
    ("소비 지표 단독으로 폐업 위험을 진단하지 않는다.", "BC카드 상권 분석·가맹점 대상 서비스 담당", "소비 규모만으로 “안전한 상권”이라고 안내하지 않는다", "시군구×업종 소비 금액·건수(BC카드 ABP) — 이번 분석에서 예측을 개선하지 못한 지표"),
    ("위험 진단은 점포 특성(영업연수·프랜차이즈·규모)과 지역 폐업 흐름을 결합해야 합니다.", "폐업 위험 진단 상품을 기획하는 BC카드 상품팀", "점포 특성과 지역 폐업 흐름을 결합한 폐업 위험도 지표를 만든다", "인허가 데이터(LOCALDATA)의 영업연수·프랜차이즈·규모 + 이웃 시군구를 포함한 직전 1년 폐업률"),
    ("조기 경보 후보:", "가맹점 대상 상권 모니터링 서비스 담당", "신생 점포 비중이 높고 이웃 지역 폐업이 늘고 있는 지역·업종 조합을 우선 관찰 대상으로 삼는다", "영업연수 분포(인허가) + 이웃 시군구 폐업 추이"),
    ("더 나아가려면 점포 단위 매출 데이터가 필요합니다.", "BC카드 가맹점 데이터 담당", "이번 지역·업종 조합 수준의 진단을 점포 단위로 넓힌다", "가맹점별 월 매출 추이(“소비는 있는데 못 버티는” 점포를 직접 확인)"),
]


def implications(sec):
    items = re.findall(r"<li><b>(.*?)</b>(.*?)</li>", sec, re.S)
    assert len(items) == 4, "시사점 개수가 달라짐"
    out = ['<h2 id="implications">BC카드에 주는 시사점</h2><p class="sec-sub">누가 · 무엇을 · 어떤 데이터로 할 수 있는지로 정리했어요(분석 결과를 활용처 관점으로 다시 쓴 것이며, 사실 내용은 그대로예요).</p><div class="imps">']
    for (head, body), (h0, who, what, data) in zip(items, IMPS):
        assert head == h0, f"시사점 문구가 달라짐: {head}"
        out.append(f'<div class="imp"><h4>{head}</h4><dl><dt>누가</dt><dd>{who}</dd><dt>무엇을</dt><dd>{what}</dd><dt>어떤 데이터로</dt><dd>{data}</dd></dl><p class="cap" style="margin:6px 0 0">{body.strip()}</p></div>')
    out.append("</div>")
    return "".join(out)


def step2(h):
    # 차트·표 제목의 용어 풀이 + “읽는 법”
    dc = tip("ΔC-index", "Δ(델타)는 ‘변화량’이에요. 어떤 요인 묶음을 뺐을 때 점포 단위 판별력(C-index)이 얼마나 떨어지는지예요. 클수록 그 묶음이 중요해요.")
    ds = tip("ΔSpearman", "요인 묶음을 뺐을 때 순위 예측(Spearman 순위상관)이 얼마나 나빠지는지예요. 클수록 그 묶음이 중요해요.")
    h = _rep(h, "점포 단위 판별력 하락 (ΔC-index)</h3>", f"점포 단위 판별력 하락 ({dc})</h3>" + how("막대가 길수록, 그 요인 묶음을 빼면 점포 단위 예측(폐업할 점포 가려내기)이 많이 나빠져요."))
    h = _rep(h, "지역 간 순위 하락 (ΔSpearman, 95% CI)</h3>", f"지역 간 순위 하락 ({ds}, 95% CI)</h3>" + how("막대가 길수록, 그 요인 묶음을 빼면 ‘지역끼리의 위험 순위’가 많이 틀어져요. 막대 위 가로선은 95% 신뢰구간이에요."))
    h = _rep(h, "같은 시군구 안 순위 하락 (ΔSpearman, 95% CI)</h3>", "같은 시군구 안 순위 하락 (ΔSpearman, 95% CI)</h3>" + how("같은 시군구 안에서 지역·업종 조합의 순위를 가르는 데 그 요인 묶음이 얼마나 필요한지예요. 왼쪽(음수)이면 빼는 편이 오히려 나은 요인이에요."))
    for aria_start, title, hw in [("폐업률 차이를 설명하는 정도", "폐업률 차이를 설명하는 정도 (조정 R²)", how("막대가 길수록 그 정보(업종 또는 시군구)만으로 지역·업종 조합 간 폐업률 차이를 잘 설명해요. 이론상 상한은 약 0.72예요.")),
                                  ("모형 단계별 Moran’s I", "이웃끼리 닮은 패턴이 남은 정도 (Moran’s I)", how("막대가 짧을수록(0에 가까울수록) 모형이 놓친 ‘이웃끼리 닮은 패턴’이 적어요."))]:
        h = _rep(h, f'<div class="card"><div class="hb" role="group" aria-label="{aria_start}', f'<div class="card"><h3 style="margin-top:0">{title}</h3>{hw}<div class="hb" role="group" aria-label="{aria_start}')
    h, n = re.subn(r'(<h3 style="margin-top:0">(?:점포당 소비|객단가)\(1월.*?</h3>)', lambda m: m.group(1) + how("막대는 0%부터 시작해요. 길수록 그 구간의 폐업률이 높아요."), h)
    assert n == 2
    h = _after(h, "순위 변화 · ΔSpearman)</h3>", how("각 칸은 변수를 더했을 때 순위 예측이 얼마나 좋아졌는지(ΔSpearman)와 [95% 신뢰구간]이에요. 구간이 0을 포함하면 개선이 확실하지 않다는 뜻이에요."))
    h = _after(h, "<h3>가장 위험한 8개 지역·업종 조합</h3>", how("숫자는 그 요인이 평균 점포 대비 폐업 위험을 몇 배로 만드는지예요(×1.0 = 평균). 붉을수록 위험을 높이고 푸를수록 낮춰요. 회색은 ±3% 이내라 영향이 작아요."))
    h, n = re.subn(r'(<h3 style="margin-top:0">예상보다 폐업이 (?:많은|적은) 군집.*?</h3>)', lambda m: m.group(1) + how("관측 = 실제 폐업 건수, 예상 = 모형이 예측한 건수예요."), h)
    assert n == 2

    # 4장: 해석 문장을 표 위로, 안전 표 바로 위에 “연관이며 인과 아님” 한 번 더
    m = re.search(r'<p class="cap">(위험 지역·업종 조합은 영업연수가 짧고.*?)</p>', h, re.S)
    assert m, "4장 해석 문장 없음"
    cap = m.group(1)
    h = h.replace(m.group(0), "")
    h = _rep(h, "열은 뺐습니다.</p>", f'열은 뺐습니다.</p><div class="note"><b>해석.</b> {cap}</div>')
    h = _rep(h, "<h3>가장 안전한 8개 지역·업종 조합</h3>", '<div class="note"><b>주의: 연관이며 인과가 아니에요.</b> 안전한 조합에 지방 한식계열이 많다고 해서 “지방 한식은 무조건 안전하다”는 뜻은 아니에요. 평균 점포와 비교한 통계적 연관일 뿐, 원인이나 정책 효과가 아니에요.</div><h3>가장 안전한 8개 지역·업종 조합</h3>' + how("위 표와 같은 방식으로 읽어요. 푸를수록 그 요인이 위험을 낮추고, 회색(±3% 이내)은 영향이 작아요."))
    h = _rep(h, "점포 300개 이상인 지역·업종 조합만 표시하며", "점포 300개 이상인 지역·업종 조합만 표시하며" + tip("", TIP_MIN))
    # 성별 주석(모순처럼 보이는 지점)
    h = _rep(h, "BC카드 고객 성별은 빼는 편이 오히려 낫습니다.</p></div>",
             'BC카드 고객 성별은 빼는 편이 오히려 낫습니다.</p>'
             '<div class="note" style="margin:10px 0 0"><b>지도의 결과 카드에는 왜 “BC카드 고객 성별” 막대가 나오나요?</b> 최종 모형에는 성별 구성이 들어 있어 값이 표시돼요. 다만 같은 시군구 안에서 조합을 가르는 데는 빼는 편이 오히려 나았어요(위 ▼ 표시 막대). 그래서 참고용으로 봐 주세요.</div></div>')
    h = _rep(h, "3장 표에 그대로 실었습니다", "3장의 통계 상세 표에 그대로 실었습니다")

    secs = _split_sections(h)
    k_find = _find(secs, "한눈에"); k1, k2, k3 = _find(secs, "1장."), _find(secs, "2장."), _find(secs, "3장.")
    k4, k5, k6, kl = _find(secs, "4장."), _find(secs, "5장."), _find(secs, "6장."), _find(secs, "데이터와 한계")
    find = secs[k_find].replace("<h2>한눈에 보는 결론</h2>", "<h2>핵심 결론 (A~E)</h2>")
    s1 = _fold(secs[k1], "점포 하나를 가려낼 땐 영업연수·점포 규모·운영 특성·프랜차이즈가, 지역끼리 비교할 땐 지역 폐업 흐름과 영업연수가 중요했어요. BC카드 고객 연령대는 ‘어떤 유형의 지역인가’를 알려 주는 신호일 뿐 같은 지역 안의 원인은 아니었고, 같은 시군구 안에서 조합을 가르는 건 업종뿐이었어요.")
    s2 = _fold(secs[k2], "위험은 업종보다 지역에서 더 크게 갈려요. 시군구만으로 설명한 정도가 업종만의 약 4배예요.")
    # 3장: 소비 3분위 차트는 그대로 두고, 통계 표만 접는다
    s3 = secs[k3]
    m3 = re.search(r"(<h3>모형에 더해 본 것과 결과.*?</h3>.*?</p>)\s*(<div class=\"scroll\">.*?</div>)", s3, re.S)
    assert m3, "3장 표 구조가 달라짐"
    s3 = s3.replace(m3.group(0), '<p class="plain">소비·객단가·경쟁밀도 등을 더해 봐도 예측이 좋아지지 않았어요(아래 표의 판정은 모두 “개선 없음”).</p>'
                    f'<details class="stat"><summary>통계 상세 (심사·연구자용)</summary><div class="statbody">{m3.group(1)}{m3.group(2)}</div></details>')
    # 5장: 설명·Moran 차트를 접고, 군집 목록은 그대로
    s5 = secs[k5]
    m5 = re.search(r'(<h2>.*?</h2>)\s*(<p class="sec-sub">.*?</p>.*?)(?=\s*<div class="cols")', s5, re.S)
    assert m5, "5장 구조가 달라짐"
    s5 = (m5.group(1) + '<p class="plain">이웃 지역의 폐업 흐름을 모형에 넣으니, 모형이 놓치던 ‘이웃끼리 닮은 패턴’이 사라졌어요.</p>'
          f'<details class="stat"><summary>통계 상세 (심사·연구자용)</summary><div class="statbody">{m5.group(2)}</div></details>' + s5[m5.end():])
    lim = secs[kl] + CODE_TABLE
    return SUMMARY + implications(secs[k6]) + find + s1 + s2 + s3 + secs[k4] + s5 + lim


CODE_TABLE = (
    '<details class="stat"><summary>모형 이름 대응표 (연구자용)</summary><div class="statbody"><p class="cap" style="margin:0 0 8px">리포트의 모형 코드가 무엇을 넣은 모형인지 정리했어요. 최종 모형(M3L)은 Cox 비례위험 모형이에요.</p>'
    '<div class="scroll"><table><thead><tr><th>코드</th><th>넣은 것</th></tr></thead><tbody>'
    '<tr><td>M2</td><td>점포(사업장) 변수: 영업연수·프랜차이즈·입지·점포 규모·운영 특성 등</td></tr>'
    '<tr><td>M2h</td><td>M2 + 지역·업종 조합의 직전 1년 폐업률</td></tr>'
    '<tr><td>M3</td><td>M2h + BC카드 고객 성별·연령대 구성</td></tr>'
    '<tr><td>M3L</td><td>M3 + 지역 폐업 흐름(이 시군구와 이웃 시군구의 이전 폐업 이력) — <b>최종 모형</b></td></tr>'
    '<tr><td>M4</td><td>M3 + 경쟁밀도</td></tr>'
    '<tr><td>M5J · M5D</td><td>M4 + 점포당 BC 소비·객단가 (각각 1월 · 6개월 기준)</td></tr>'
    '<tr><td>M6</td><td>M4 + 추가 BC 특성 7개</td></tr>'
    '<tr><td>M7</td><td>M4 + 지역·업종 조합 구성(프랜차이즈 비중·평균 영업연수·다중이용 비중)</td></tr>'
    '</tbody></table></div></div></details>')


COLTIPS = {
    "영업연수": "문을 연 지 몇 년 됐는지예요. 오래 영업한 점포가 많을수록 위험이 낮게 나와요.",
    "프랜차이즈": "프랜차이즈(가맹) 점포의 비중이에요. 이 모형에서는 비중이 높은 곳이 위험이 낮게 나와요.",
    "점포 규모·운영 특성": "점포 규모, 다중이용시설 여부처럼 점포 자체의 특성이에요.",
    "지역 폐업 흐름": "이 시군구와 이웃 시군구에서 2026-01-01 기준 직전 1년 동안 폐업한 점포의 비율이에요. 높을수록 위험이 높아요.",
    "BC카드 고객 성별": "BC카드 결제 고객의 남성·여성·법인 비중이에요. 최종 모형에는 들어 있지만 같은 시군구 안에서는 빼는 편이 예측이 조금 더 나았어요. 참고용으로 봐 주세요.",
    "BC카드 고객 연령대": "BC카드 결제 고객의 연령대 구성이에요. 같은 시군구 안에서는 위험을 가르지 못하고 어떤 유형의 지역인지 알려 주는 신호일 뿐이에요.",
    "업종": "업종마다 평균적으로 폐업이 잦은 정도가 달라요. 그 업종 자체가 가진 기본 위험이에요.",
    "폐업 위험도(배수)": "평균 점포를 ×1.0으로 놓고 비교한 폐업 위험도예요. 오른쪽 요인 배수들(표에서 뺀 입지·직전 폐업률 요인 포함)을 곱한 값이에요. 연관일 뿐 원인은 아니에요.",
}


def _qbtn(t):
    t = t.replace('"', "'")
    return f'<button type="button" class="q" data-tip="{t}" aria-label="설명: {t}">?</button>'


def step3(h):
    # 요인 배수 셀: ±3%(0.97~1.03)는 회색, 나머지는 원문 색(1.0 중심 발산) + ▲/▼ 표기
    def cell(m):
        v = float(m.group(2))
        if 0.97 <= v <= 1.03:
            return f'<td class="chip flat">{m.group(2)}</td>'
        return f'<td class="chip" style="{m.group(1)}"><span class="ar">{"▲" if v >= 1 else "▼"}</span>{m.group(2)}</td>'
    h, n = re.subn(r'<td class="chip" style="([^"]*)">([\d.]+)</td>', cell, h)
    assert n == 112, f"표 셀 수가 달라짐: {n}"
    for col, text in COLTIPS.items():
        h = _rep(h, f"<th>{col}</th>", f'<th class="hasq">{col}{_qbtn(text)}</th>', 2)
    return h


def transform(h):
    return step3(step2(transform_step1(h)))
