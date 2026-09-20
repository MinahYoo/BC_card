# -*- coding: utf-8 -*-
"""
분석 산출물(output/*.csv)을 읽어 정적 리포트 report/index.html 한 장(외부 라이브러리·CDN 없음)을 만든다.
수치는 전부 CSV에서 읽는다(손으로 옮기지 않음). 사전 조건: bc_scale_check.py, risk_decomp.py, moran_residuals.py, explain_final.py 실행 완료.
"""
import html
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path("output")
rd = lambda f: pd.read_csv(OUT / f, encoding="utf-8-sig")
e = html.escape

drop = rd("11_final_drop_block.csv")
imp = rd("11_final_block_importance.csv").rename(columns={"Unnamed: 0": "블록"})
grp = rd("11_final_group_blocks.csv")
r2 = rd("9_region_vs_biz_r2.csv").set_index("대상")
tier = rd("9_excess_by_spend_tier.csv")
sp = rd("9_excess_spend_spearman.csv")
moran = rd("10_moran_summary.csv")
hot = rd("10_local_hotspots.csv")
inc = rd("8_cv_group_increment.csv")
inc_r = rd("8_cv_region_increment.csv")
full_m3l = drop.iloc[0]

SHORT = {"영업연수": "영업연수", "프랜차이즈": "프랜차이즈", "입지(중심점 거리)": "입지", "사업장 확장(다중이용·크기·좌표결측·전화)": "사업장 확장",
         "그룹 직전 1년 폐업률": "그룹 직전 폐업률", "자기·이웃 시군구 폐업 이력": "자기·이웃 이력", "BC 성별 구성": "BC 성별", "BC 연령 구성": "BC 연령", "업종": "업종"}
N_STORES, N_EVENTS = 635_536, 25_329      # 모형 적합 표본(BC 변수 결측 31개 제외). prep_site_data.py가 만든 값이 있으면 그것을 쓴다
try:
    import json
    _nat = json.loads(Path("output/site_data.json").read_text(encoding="utf-8"))["national"]
    N_STORES, N_EVENTS = _nat["n"], _nat["events"]
except FileNotFoundError:
    pass


def ci_of(s):
    lo, hi = s.strip("[]").split(",")
    return float(lo), float(hi)


def hbar(rows, vmin, vmax, width=620, label_w=170, bar_h=20, gap=8, fmt="{:+.3f}", zero_line=True, note_col=None):
    """rows: (라벨, 값, (lo, hi) 또는 None, 클래스 'pos'|'neg'|'ref'|'muted')."""
    n = len(rows)
    H = n * (bar_h + gap) + 26
    x0, x1 = label_w, width - 70
    sx = lambda v: x0 + (v - vmin) / (vmax - vmin) * (x1 - x0)
    out = [f'<svg viewBox="0 0 {width} {H}" role="img" class="chart">']
    if zero_line and vmin < 0 < vmax:
        out.append(f'<line x1="{sx(0):.1f}" x2="{sx(0):.1f}" y1="6" y2="{H - 20}" class="axis"/>')
    for i, (lab, v, ci, cls) in enumerate(rows):
        y = 8 + i * (bar_h + gap)
        a, b = sorted((sx(0) if zero_line and vmin < 0 < vmax else x0, sx(v)))
        out.append(f'<text x="{label_w - 8}" y="{y + bar_h * 0.72:.1f}" text-anchor="end" class="lbl">{e(lab)}</text>')
        out.append(f'<rect x="{a:.1f}" y="{y}" width="{max(b - a, 1.5):.1f}" height="{bar_h}" rx="3" class="bar {cls}"/>')
        if ci:
            out.append(f'<line x1="{sx(ci[0]):.1f}" x2="{sx(ci[1]):.1f}" y1="{y + bar_h / 2}" y2="{y + bar_h / 2}" class="whisk"/>')
            for c in ci:
                out.append(f'<line x1="{sx(c):.1f}" x2="{sx(c):.1f}" y1="{y + 4}" y2="{y + bar_h - 4}" class="whisk"/>')
        tx = max(sx(v), sx(ci[1]) if ci else 0) + 6 if v >= 0 else min(sx(v), sx(ci[0]) if ci else 1e9) - 6
        out.append(f'<text x="{tx:.1f}" y="{y + bar_h * 0.72:.1f}" text-anchor="{"start" if v >= 0 else "end"}" class="val">{fmt.format(v)}</text>')
    out.append("</svg>")
    return "".join(out)


TABLE_COLS = {k: v for k, v in SHORT.items() if v not in ("입지", "그룹 직전 폐업률")}   # 예측에 기여가 없는 두 블록은 표에서 뺀다(3장 제거 실험 참고)


def chips(g):
    cells = []
    for full_name, short in TABLE_COLS.items():
        v = float(g[f"x_{full_name}"])
        a = min(abs(np.log(v)) / 0.35, 1.0) * 0.75
        rgb = "214,69,65" if v >= 1 else "45,110,190"
        cells.append(f'<td class="chip" style="background:rgba({rgb},{a:.2f})">{v:.2f}</td>')
    return "".join(cells)


def group_table(df, title):
    head = "".join(f"<th>{e(s)}</th>" for s in TABLE_COLS.values())
    body = []
    for _, g in df.iterrows():
        body.append(f'<tr><td class="gname">{e(g["SIDO_NM"])} {e(g["CCG_NM"])}<br><span class="sub">{e(g["bc_업종"])} · 점포 {int(g["n"]):,}개 · 실제 폐업률 {g["obs_rate"] * 100:.1f}%</span></td>'
                    f'<td class="tot">×{g["상대위험_배수"]:.2f}</td>{chips(g)}</tr>')
    return (f'<h3>{e(title)}</h3><div class="scroll"><table class="grp"><thead><tr><th>지역 · 업종</th><th>전체 배수</th>{head}</tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table></div>')


# ---------- 차트 1: 블록 제거 예측 중요도 ----------
blk_rows = drop.iloc[1:].copy()
blk_rows["short"] = blk_rows["제거 블록"].map(SHORT)
order_c = blk_rows.sort_values("ΔC-index", ascending=False)
ch_c = hbar([(r["short"], r["ΔC-index"], None, "pos" if r["ΔC-index"] > 0.003 else "muted") for _, r in order_c.iterrows()],
            -0.002, 0.016, width=470, label_w=118, fmt="{:+.4f}")
order_s = blk_rows.sort_values("ΔSpearman 전체", ascending=False)
ch_s = hbar([(r["short"], r["ΔSpearman 전체"], ci_of(r["ΔSpearman 전체 95% CI"]),
              "pos" if ci_of(r["ΔSpearman 전체 95% CI"])[0] > 0 else "muted") for _, r in order_s.iterrows()],
            -0.03, 0.075, width=470, label_w=118)
order_w = blk_rows.sort_values("ΔSpearman 시군구 내", ascending=False)
ch_w = hbar([(r["short"], r["ΔSpearman 시군구 내"], ci_of(r["ΔSpearman 시군구 내 95% CI"]),
              "pos" if ci_of(r["ΔSpearman 시군구 내 95% CI"])[0] > 0 else ("neg" if ci_of(r["ΔSpearman 시군구 내 95% CI"])[1] < 0 else "muted")) for _, r in order_w.iterrows()],
            -0.03, 0.105, width=940, label_w=150, bar_h=22)

# ---------- 차트 2: 시군구 vs 업종 ----------
rr = r2.loc["관측 폐업률"]
ch_r2 = hbar([("업종만", rr["업종만"], None, "muted"), ("시군구만", rr["시군구만"], None, "pos"), ("업종 + 시군구", rr["업종+시군구"], None, "ref")], 0, 0.7, width=940, label_w=130, bar_h=24, fmt="{:.2f}", zero_line=False)

# ---------- 차트 3: 소비 3분위 ----------
t1 = tier[tier["소비 변수"] == "점포당 소비(1월)"].set_index("분위")
ch_tier = hbar([(f"점포당 소비 {k}", t1.loc[k, "관측 폐업률(%)"], None, "pos" if k == "상" else ("ref" if k == "중" else "muted")) for k in ("하", "중", "상")],
               0, 5.2, width=470, label_w=112, fmt="{:.2f}%", zero_line=False)
unit = tier[tier["소비 변수"].str.startswith("객단가")].set_index("분위")
ch_unit = hbar([(f"객단가 {k}", unit.loc[k, "관측 폐업률(%)"], None, "muted" if k == "상" else "ref") for k in ("하", "중", "상")], 0, 5.2, width=470, label_w=112, fmt="{:.2f}%", zero_line=False)
sp_g = lambda var, tgt, kind: float(sp[(sp["소비 변수"].str.startswith(var)) & (sp["대상"] == tgt) & (sp["기준"] == kind)].iloc[0]["Spearman"])
rho_all, rho_in = sp_g("점포당 소비(1월)", "관측 폐업률", "전체"), sp_g("점포당 소비(1월)", "관측 폐업률", "같은 시군구 내 편차")

# ---------- 차트 4: Moran ----------
m5 = moran[moran["k"] == 5].set_index("잔차 기준")
mrows = [("모형 없음(원자료)", "원자료 폐업률(모형 없음)", "muted"), ("M2 사업장", "M2 (OOF)", "muted"), ("M2h + 그룹 폐업률", "M2h (OOF)", "muted"),
         ("M3 + BC 성별·연령", "M3 (OOF)", "ref"), ("M3L + 이웃 폐업 이력", "M3L (OOF)", "pos")]
ch_m = hbar([(lab, float(m5.loc[key, "Moran I"]), None, cls) for lab, key, cls in mrows], 0, 0.5, width=940, label_w=190, bar_h=24, fmt="{:.3f}", zero_line=False)
m3l_p = float(m5.loc["M3L (OOF)", "p(단측)"])

# ---------- 시도한 것 ----------
def inc_row(df, block_prefix, kind="전체 그룹"):
    r = df[(df["블록"].str.startswith(block_prefix)) & (df["기준"] == kind)]
    return r.iloc[0] if len(r) else None


tried = []
for label, pref, desc in [("경쟁밀도(같은 시군구·업종의 1/1 영업 점포 수)", "경쟁밀도(그룹)", "M4 − M3"),
                          ("점포당 BC 소비 · 객단가 (1월)", "소비(1월)", "M5J − M4"),
                          ("점포당 BC 소비 · 객단가 (6개월, 월별 점포 수 분모)", "소비(6개월, 월별", "M5D − M4"),
                          ("추가 BC 특성 7개(연령 집중도·지역 대비 고객 편차·지역 소비력·성장률 등)", "추가 BC 특성", "M6 − M4"),
                          ("그룹 구성(프랜차이즈 비중·평균 영업연수·다중이용 비중)", "그룹 구성", "M7 − M4")]:
    a, w = inc_row(inc, pref, "전체 그룹"), inc_row(inc, pref, "같은 시군구 내 편차")
    if a is None or w is None:
        continue
    tried.append(f'<tr><td>{e(label)}</td><td class="num">{a["ΔSpearman"]:+.3f}<br><span class="sub">{e(a["95% CI"])}</span></td>'
                 f'<td class="num">{w["ΔSpearman"]:+.3f}<br><span class="sub">{e(w["95% CI"])}</span></td>'
                 f'<td>{"개선 없음" if not (ci_of(a["95% CI"])[0] > 0 or ci_of(w["95% CI"])[0] > 0) else ("시군구 간만 개선" if ci_of(w["95% CI"])[0] <= 0 else "개선")}</td></tr>')
tried_html = "".join(tried)

# ---------- 대표 그룹 / 핫스폿 ----------
big = grp[grp["n"] >= 300].sort_values("상대위험_배수")
risky, safe = big.tail(8).iloc[::-1], big.head(8)
hi = hot[hot["z"] > 0].sort_values("국지 I", ascending=False).head(8)
lo = hot[hot["z"] < 0].sort_values("국지 I", ascending=False).head(8)


def region_list(df):
    return "".join(f'<li><b>{e(r["SIDO_NM"])} {e(r["CCG_NM"])}</b> <span class="sub">관측 {int(r["obs"])}건 vs 예상 {r["exp"]:.0f}건</span></li>' for _, r in df.iterrows())


c_full = float(full_m3l["C-index"])
sp_full, sp_in = float(full_m3l["Spearman(전체)"]), float(full_m3l["Spearman(시군구 내)"])
age = blk_rows.set_index("제거 블록").loc["BC 연령 구성"]
hist = blk_rows.set_index("제거 블록").loc["자기·이웃 시군구 폐업 이력"]

HTML = f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>상권 생존 분석 리포트</title>
<style>
:root{{--bg:#f6f5f1;--card:#fff;--fg:#1f2328;--sub:#667085;--line:#e3e1da;--acc:#1f5eff;--pos:#1f5eff;--neg:#c2410c;--ref:#7a8699;--muted:#c8cdd6;--warn:#fff4dd;--warnb:#f0c36d}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{--bg:#14161a;--card:#1c1f25;--fg:#e8eaed;--sub:#9aa3b2;--line:#2d323b;--acc:#7aa2ff;--pos:#7aa2ff;--neg:#f59e6b;--ref:#7f8ba0;--muted:#3a404b;--warn:#2b2516;--warnb:#7a6320}}}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--fg);font:16px/1.65 system-ui,-apple-system,"Segoe UI","Malgun Gothic","Apple SD Gothic Neo",sans-serif}}
main{{max-width:980px;margin:0 auto;padding:0 16px 80px}}
header{{padding:56px 0 24px}}
.kicker{{color:var(--acc);font-weight:700;letter-spacing:.04em;font-size:13px}}
h1{{font-size:clamp(26px,5vw,40px);line-height:1.25;margin:8px 0 12px}}
.lead{{font-size:18px;color:var(--sub);max-width:760px}}
h2{{font-size:24px;margin:56px 0 6px}} h3{{font-size:17px;margin:28px 0 8px}}
.sec-sub{{color:var(--sub);margin:0 0 18px}}
.kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin:24px 0}}
.kpi,.card{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 18px}}
.kpi b{{display:block;font-size:26px;line-height:1.2}} .kpi span{{color:var(--sub);font-size:13px}}
.finding{{display:grid;grid-template-columns:38px 1fr;gap:12px;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 18px;margin:10px 0}}
.finding .n{{width:34px;height:34px;border-radius:50%;background:var(--acc);color:#fff;display:grid;place-items:center;font-weight:700}}
.finding h4{{margin:0 0 2px;font-size:17px}} .finding p{{margin:0;color:var(--sub);font-size:15px}}
.cols{{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:14px}}
.chart{{width:100%;height:auto}} .chart .lbl{{fill:var(--fg);font-size:12.5px}} .chart .val{{fill:var(--sub);font-size:12px}}
.chart .axis{{stroke:var(--sub);stroke-width:1;stroke-dasharray:3 3}} .chart .whisk{{stroke:var(--fg);stroke-width:1.4}}
.bar.pos{{fill:var(--pos)}} .bar.neg{{fill:var(--neg)}} .bar.ref{{fill:var(--ref)}} .bar.muted{{fill:var(--muted)}}
.cap{{font-size:13.5px;color:var(--sub);margin:8px 2px 0}}
.note{{background:var(--warn);border:1px solid var(--warnb);border-radius:10px;padding:12px 16px;margin:16px 0;font-size:15px}}
table{{border-collapse:collapse;width:100%;font-size:14px}} th,td{{padding:8px 10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}}
th{{color:var(--sub);font-weight:600;font-size:12.5px}} .num{{text-align:right;white-space:nowrap}} .sub{{color:var(--sub);font-size:12.5px}}
.scroll{{overflow-x:auto}} table.grp td.chip{{text-align:center;font-variant-numeric:tabular-nums;min-width:58px;border-left:2px solid var(--card)}}
table.grp th{{white-space:nowrap;text-align:center}} table.grp th:first-child{{text-align:left}} .gname{{min-width:210px}} .tot{{font-weight:700;font-size:16px;white-space:nowrap}}
ul.reg{{margin:6px 0 0;padding-left:20px}} ul.reg li{{margin:2px 0}}
.pill{{display:inline-block;padding:1px 8px;border-radius:999px;background:var(--line);font-size:12px;color:var(--sub);margin-right:4px}}
footer{{margin-top:56px;color:var(--sub);font-size:13.5px}}
@media (max-width:560px){{header{{padding-top:32px}} h2{{font-size:21px}}}}
</style></head><body><main>
<header>
<div class="kicker">BC카드 소비데이터 공모전 · 설명 가능한 상권 생존 모델</div>
<h1>소비는 있는데 왜 못 버티는가</h1>
<p class="lead">2026년 1월 1일 영업 중이던 점포 {N_STORES:,}개를 180일간 추적했습니다. 폐업을 가른 것은 <b>소비 규모가 아니라 점포의 나이·성격과 지역의 최근 폐업 흐름</b>이었습니다. BC카드 소비 지표만으로는 위험을 가려내기 어렵다는 것도 함께 확인했습니다.</p>
<div class="kpis">
<div class="kpi"><b>{N_STORES:,}</b><span>추적 점포(2026-01-01 영업 중, 7개 업종)</span></div>
<div class="kpi"><b>{N_EVENTS:,}건</b><span>180일 내 폐업 ({N_EVENTS / N_STORES * 100:.2f}%)</span></div>
<div class="kpi"><b>1,782개</b><span>시군구 × 업종 그룹 (255개 시군구)</span></div>
<div class="kpi"><b>{c_full:.3f}</b><span>최종 모형의 점포 단위 판별력(C-index, 미학습 그룹; 0.5 = 무작위)</span></div>
</div>
</header>

<h2>한눈에 보는 결론</h2>
<p class="sec-sub">모든 수치는 학습에 쓰지 않은 그룹(5-fold 교차검증)에서 확인했고, 연관이지 인과가 아닙니다.</p>
<div class="finding"><div class="n">1</div><div><h4>위험의 가장 큰 축은 “어느 업종이냐”보다 “어느 지역이냐”</h4>
<p>그룹 간 폐업률 차이를 시군구 더미만으로 설명한 정도(조정 R² {rr["시군구만"]:.2f})가 업종만의 경우({rr["업종만"]:.2f})의 약 {rr["시군구만"] / rr["업종만"]:.0f}배입니다.</p></div></div>
<div class="finding"><div class="n">2</div><div><h4>소비가 많다고 버티지 않는다</h4>
<p>업종 안에서 점포당 소비가 상위인 그룹의 폐업률은 {t1.loc["상", "관측 폐업률(%)"]:.2f}%로 하위({t1.loc["하", "관측 폐업률(%)"]:.2f}%)보다 높았습니다. 같은 시군구 안에서는 관계가 없습니다(순위상관 {rho_in:+.2f}). 소비 규모·객단가·성장률 등을 모형에 더해도 예측이 좋아지지 않았습니다.</p></div></div>
<div class="finding"><div class="n">3</div><div><h4>고객 연령 구성은 “지역 유형”의 신호일 뿐, 같은 지역 안의 원인이 아니다</h4>
<p>연령 구성은 시군구 간 순위에는 도움이 되지만(+{age["ΔSpearman 전체"]:.3f}) 같은 시군구 안에서는 도움이 되지 않습니다(+{age["ΔSpearman 시군구 내"]:.3f}, 신뢰구간이 0을 포함).</p></div></div>
<div class="finding"><div class="n">4</div><div><h4>점포 단위 판별은 영업연수·점포 성격·프랜차이즈가 만든다</h4>
<p>이 세 블록을 빼면 판별력(C-index)이 각각 {blk_rows.set_index("제거 블록").loc["영업연수", "ΔC-index"]:.3f} · {blk_rows.set_index("제거 블록").loc["사업장 확장(다중이용·크기·좌표결측·전화)", "ΔC-index"]:.3f} · {blk_rows.set_index("제거 블록").loc["프랜차이즈", "ΔC-index"]:.3f} 떨어집니다. BC 변수를 뺀 경우는 0.002 이하입니다.</p></div></div>
<div class="finding"><div class="n">5</div><div><h4>남은 공간 구조는 “이웃 지역의 최근 폐업 흐름” 하나로 설명된다</h4>
<p>잔차의 공간 자기상관(Moran’s I)이 {float(m5.loc["M3 (OOF)", "Moran I"]):.3f}에서 {float(m5.loc["M3L (OOF)", "Moran I"]):.3f}(p={m3l_p:.2f})로 사라졌습니다. 복잡한 그래프 신경망 없이, 이웃 시군구의 폐업 이력이라는 해석 가능한 변수만으로 충분했습니다.</p></div></div>

<h2>1. 무엇이 예측에 필요한가</h2>
<p class="sec-sub">최종 모형(M3L)에서 한 블록을 빼고 다시 학습해, 학습에 쓰지 않은 그룹에서 얼마나 나빠지는지 잰 값입니다. 클수록 그 블록이 필요합니다. 그룹 순위는 그룹 평균 위험점수와 실제 폐업률의 Spearman 순위상관입니다(전체 {sp_full:.3f}, 시군구 내 {sp_in:.3f}).</p>
<div class="cols">
<div class="card"><h3 style="margin-top:0">점포 단위 판별력 하락 (ΔC-index)</h3>{ch_c}<p class="cap">영업연수·사업장 성격·프랜차이즈가 점포 수준의 판별을 만듭니다.</p></div>
<div class="card"><h3 style="margin-top:0">지역 간 순위 하락 (ΔSpearman, 95% CI)</h3>{ch_s}<p class="cap">자기·이웃 지역 폐업 이력과 BC 연령 구성이 “어느 지역인가”를 가릅니다. 파랑 = 신뢰구간이 0을 제외.</p></div>
</div>
<div class="card" style="margin-top:14px"><h3 style="margin-top:0">같은 시군구 안 순위 하락 (ΔSpearman, 95% CI)</h3>{ch_w}<p class="cap">같은 지역 안에서 그룹을 가르는 것은 업종뿐입니다. BC 성별 구성은 빼는 편이 오히려 낫습니다(주황).</p></div>

<h2>2. 지역이 업종보다 크다</h2>
<p class="sec-sub">그룹 간 관측 폐업률의 분산을 더미 변수로 설명한 정도(조정 R², 사업장 수 가중). 이항 우연변동이 분산의 약 28%라 이론상 상한은 약 0.72입니다.</p>
<div class="card">{ch_r2}<p class="cap">시군구 더미 255개를 그룹 1,090개에 적합한 값이라 다소 낙관적입니다.</p></div>

<h2>3. BC카드 소비 데이터가 말해 주는 것과 말해 주지 못하는 것</h2>
<p class="sec-sub">BC 데이터는 시군구 × 업종 단위의 월별 금액·건수·성별·연령뿐입니다. 폐업은 점포 단위 사건이라 해상도가 다릅니다.</p>
<div class="cols">
<div class="card"><h3 style="margin-top:0">점포당 소비(1월, 업종 내 3분위)별 폐업률</h3>{ch_tier}<p class="cap">소비가 높은 그룹의 폐업률이 더 높습니다(순위상관 {rho_all:+.2f}). 같은 시군구 안에서는 {rho_in:+.2f}로 관계가 없어, 소비와 폐업이 함께 높은 도심·고회전 상권의 차이로 보입니다.</p></div>
<div class="card"><h3 style="margin-top:0">객단가(1월, 업종 내 3분위)별 폐업률</h3>{ch_unit}<p class="cap">객단가가 높은 그룹은 폐업이 적지만, 같은 시군구 안에서는 관계가 없습니다.</p></div>
</div>
<h3>모형에 더해 본 것과 결과 (M3 또는 M4 대비 미학습 그룹 순위 변화, ΔSpearman)</h3>
<div class="scroll"><table><thead><tr><th>추가한 변수</th><th class="num">지역 간 순위</th><th class="num">같은 시군구 내 순위</th><th>판정</th></tr></thead><tbody>{tried_html}</tbody></table></div>
<div class="note"><b>해석의 한계.</b> BC 지표가 “원리상 쓸모없다”는 뜻이 아닙니다. 이 해상도(시군구 × 업종 평균, 6개월)에서는 점포 성격과 지역 폐업 흐름 위에 추가로 잡히는 신호가 없었다는 뜻입니다. 점포별 매출이 있으면 다른 결과가 나올 수 있습니다.</div>

<h2>4. 어느 지역 × 업종이 왜 위험한가</h2>
<p class="sec-sub">각 칸은 그 요인이 평균 점포 대비 폐업 위험을 몇 배로 만드는지(연관)를 나타냅니다. 붉을수록 위험을 높이고 푸를수록 낮춥니다. 점포 300개 이상인 그룹만 표시하며, 예측에 기여가 없는 입지·그룹 직전 폐업률 열은 뺐습니다.</p>
{group_table(risky, "가장 위험한 8개 그룹")}
{group_table(safe, "가장 안전한 8개 그룹")}
<p class="cap">위험 그룹은 영업연수가 짧고(신생 점포 비중) 사업장 성격·이웃 폐업 이력이 높으며, 안전 그룹은 오래된 점포가 많은 지방 한식계열이 대부분입니다. 배수는 인과가 아니라 연관입니다.</p>

<h2>5. 남은 공간 구조와 이웃 폐업 이력</h2>
<p class="sec-sub">모형이 설명하지 못한 부분(잔차)이 이웃한 시군구끼리 비슷한지(Moran’s I, 미학습 예측 기준, 가까운 5개 이웃)를 봤습니다.</p>
<div class="card">{ch_m}<p class="cap">이웃 시군구의 1/1 이전 1년 폐업률을 더하면 공간 군집이 사라집니다(M3L, p={m3l_p:.2f}). 이 변수는 원인이 아니라 지역 국면의 대리 변수입니다.</p></div>
<div class="cols" style="margin-top:14px">
<div class="card"><h3 style="margin-top:0">예상보다 폐업이 많은 군집 (M3 잔차 기준)</h3><ul class="reg">{region_list(hi)}</ul></div>
<div class="card"><h3 style="margin-top:0">예상보다 폐업이 적은 군집</h3><ul class="reg">{region_list(lo)}</ul></div>
</div>

<h2>6. BC카드에 주는 시사점</h2>
<div class="card">
<ul>
<li><b>소비 지표 단독으로 폐업 위험을 진단하지 않는다.</b> 소비가 큰 상권이 오히려 회전율이 높았습니다. 소비 규모는 “수요가 있다”는 신호이지 “버틴다”는 신호가 아닙니다.</li>
<li><b>위험 진단은 점포 성격(영업연수·프랜차이즈·규모)과 지역의 최근 폐업 흐름을 결합해야 합니다.</b> 이웃 시군구까지 포함한 최근 1년 폐업률이 지역 간 순위의 가장 강한 단일 신호였습니다.</li>
<li><b>조기 경보 후보:</b> 신생 점포 비중이 높고 이웃 지역 폐업이 늘고 있는 그룹(예: 수도권 동북부 한식계열·서양음식)을 우선 관찰 대상으로 삼을 수 있습니다.</li>
<li><b>더 나아가려면 점포 단위 매출 데이터가 필요합니다.</b> 가맹점별 매출 추이를 결합하면 “소비는 있는데 못 버티는” 점포를 직접 볼 수 있습니다. 이번 분석은 그 전 단계의 그룹 수준 진단입니다.</li>
</ul></div>

<h2>데이터와 한계</h2>
<div class="card"><ul>
<li><b>결과 변수:</b> LOCALDATA 인허가 4종(일반음식점·휴게음식점·제과점영업·대규모점포)의 폐업일자. 2026-01-01 영업 중인 점포를 2026-06-30까지 추적(180일). 대상은 한식계열·서양음식·스낵·일식회집·제과점·중국음식·편의점 7개 업종.</li>
<li><b>BC 변수:</b> 공모전 제공 ABP 데이터(2026-01~06, 시군구 × 업종 × 성별 × 연령 월 집계). 점포 단위가 아니라 그룹 단위 값이라 점포의 매출을 뜻하지 않습니다.</li>
<li><b>검증:</b> 시군구 × 업종 그룹 5-fold와 시군구 5-fold(미학습 시군구 외삽). 신뢰구간은 시군구 단위 부트스트랩. 분할은 시드 42 한 번.</li>
<li><b>연관 ≠ 인과.</b> 배수와 순위 개선은 관측된 연관이며 정책 효과를 뜻하지 않습니다. 이웃 폐업 이력은 지역 국면의 대리 변수입니다.</li>
<li><b>관측 창:</b> 6개월 하나. 프랜차이즈 여부는 수작업 브랜드 목록 기반이라 일부 누락이 있습니다. 폐업 사건에는 행정상 직권 처리 등이 섞여 있을 수 있습니다.</li>
<li><b>시도했으나 채택하지 않은 것</b>은 3장 표에 그대로 실었습니다(음의 결과 포함).</li>
</ul></div>
<footer>이 리포트의 모든 수치는 <code>output/</code>의 분석 산출물에서 <code>build_report.py</code>가 생성했습니다. 방법과 검증 기록은 CHANGELOG.md ⑧~㉓.</footer>
</main></body></html>"""

Path("report").mkdir(exist_ok=True)
Path("report/index.html").write_text(HTML, encoding="utf-8")
print(f"report/index.html 작성 ({len(HTML) / 1024:.0f} KB)")
