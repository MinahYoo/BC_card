# -*- coding: utf-8 -*-
"""
분석 1) 그룹(시군구x업종) 위험이 어디서 오는가 — 분산 분해
분석 3) "소비는 있는데 왜 못 버티는가" — 사업장·지역 요인을 다 반영한 뒤에도 폐업이 많은 그룹과 BC 소비 수준의 관계

[분석 1]
  (a) M3 선형예측자(LP)의 그룹 평균 분산을 요인 블록별 공분산 몫으로 쪼갠다: Var(LP_g) = sum_k Cov(블록k_g, LP_g)  ->  몫_k = Cov/Var (합이 1, 부호가 섞여도 정의됨).
      시군구 간(between-region) 분산과 시군구 내(within-region) 분산으로 나눠 블록 몫을 따로 본다.
  (b) 시군구 효과 vs 업종 효과: 그룹 평균 LP와 관측 폐업률을 시군구 더미·업종 더미로 회귀한 조정 R^2.
      관측 폐업률은 사업장 수가 적으면 우연 변동이 커서, 이항 잡음이 분산의 몇 %인지도 함께 낸다.
[분석 3]
  기준 모형 M2h(사업장 변수 + 지역 최근 폐업률, BC 변수 없음)로 그룹의 기대 폐업 수를 계산한다(Cox 기저 누적위험 x exp(LP), 180일).
  초과 폐업률 = 관측 - 기대. z = 초과 / sqrt(sum p(1-p)).  BC 소비(점포당 소비, 객단가)가 이 초과분과 관련 있는지 본다.
  * 소비 변수는 8_group_features.csv(bc_scale_check.py 산출)를 쓴다. 1월 소비는 코호트 시작 직후 값, 6개월 값(M5D 방식)은 관측창과 겹쳐 역인과 가능성이 있다.
  * 연관 분석이다. 인과가 아니다.
산출물: output/9_*.csv
"""
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from explain_common import fit_cox_cached, load_cohort, model_cols

MIN_N = 100
B = 500
print("코호트 로드...", flush=True)
ns, log = load_cohort()
full = ns["full"].reset_index(drop=True)
JOIN_KEY, REGION_KEY, TOP, REF = ns["JOIN_KEY"], ns["REGION_KEY"], ns["TOP"], ns["REF"]
feat = pd.read_csv("output/8_group_features.csv", encoding="utf-8-sig")
n0 = len(full)
full = full.merge(feat, on=JOIN_KEY, how="left", validate="m:1")
assert len(full) == n0
gid = full["group_id"].to_numpy()
G = int(gid.max()) + 1
n_g = np.bincount(gid, minlength=G).astype(float)
reg_g = np.zeros(G, dtype=int)
reg_g[gid] = full["region_id"].to_numpy()
biz_g = np.empty(G, dtype=object)
biz_g[gid] = full["bc_업종"].to_numpy()
keep = n_g >= MIN_N
print(f"평가 그룹(사업장>={MIN_N}) {int(keep.sum())}개", flush=True)


def gmean(v):
    return np.bincount(gid, weights=np.asarray(v, float), minlength=G) / np.maximum(n_g, 1)


# ============================================
# 분석 1-(a): M3 LP 분산의 블록별 몫
# ============================================
cols = model_cols(ns, TOP)
cph3 = fit_cox_cached(TOP, cols, full)
beta = cph3.params_.reindex(cols)
X = full[cols].astype(float)
contrib = (X - X.mean()) * beta
share = ns["COV_SHARE"]
BLOCKS = {
    "영업연수": ["log_age"], "프랜차이즈": ["is_franchise"], "입지(중심점 거리)": ["log_dist_to_centroid"],
    "사업장 확장": list(ns["STORE_EXT"]), "지역 최근 폐업률": list(ns["COV_HIST"]),
    "BC 성별 구성": [c for c in share if "gender" in c], "BC 연령 구성": [c for c in share if "age" in c], "업종": list(ns["BIZ_DUMMY"]),
}
BLOCKS = {k: [c for c in v if c in cols] for k, v in BLOCKS.items()}
BLOCKS = {k: v for k, v in BLOCKS.items() if v}
gb = pd.DataFrame({k: gmean(contrib[v].sum(axis=1)) for k, v in BLOCKS.items()})[keep].reset_index(drop=True)
glp = gb.sum(axis=1)
rg = reg_g[keep]


def region_split(s):
    """그룹 값 s를 시군구 평균(between)과 편차(within)로 나눈다(그룹 단위 단순평균)."""
    m = s.groupby(rg).transform("mean")
    return m, s - m


tot_b, tot_w = region_split(glp)
rows = []
for k in gb:
    b_, w_ = region_split(gb[k])
    rows.append({"요인 블록": k,
                 "그룹 간 위험 분산 몫(%)": 100 * np.cov(gb[k], glp)[0, 1] / glp.var(),
                 "시군구 간 분산 몫(%)": 100 * np.cov(b_, tot_b)[0, 1] / tot_b.var(),
                 "시군구 내 분산 몫(%)": 100 * np.cov(w_, tot_w)[0, 1] / tot_w.var()})
dec = pd.DataFrame(rows).set_index("요인 블록")
dec.loc["합계"] = dec.sum()
share_between = 100 * tot_b.var() / glp.var()
print(f"\n=== 분석 1-a: M3 위험점수의 그룹 간 분산을 요인 블록으로 나눈 몫(%) === (그룹 간 분산의 {share_between:.0f}%가 시군구 간, {100 - share_between:.0f}%가 시군구 내)")
print(dec.round(1).to_string(), flush=True)
dec.round(2).to_csv("output/9_variance_decomp_blocks.csv", encoding="utf-8-sig")

# ============================================
# 분석 1-(b): 시군구 효과 vs 업종 효과(조정 R^2)
# ============================================
# 기대 확률(분석 3에서도 씀): p_i = 1 - exp(-H0(T) * exp(LP_i))
cph2 = fit_cox_cached(REF, model_cols(ns, REF), full)
H0 = float(cph2.baseline_cumulative_hazard_.iloc[-1, 0])
lp2 = cph2.predict_log_partial_hazard(full[model_cols(ns, REF)]).to_numpy()
p = 1 - np.exp(-H0 * np.exp(lp2))
print(f"\n[교정 확인] M2h 평균 기대 폐업률 {p.mean() * 100:.2f}% vs 관측 {full['event'].mean() * 100:.2f}%", flush=True)
n_ev = np.bincount(gid, weights=full["event"].to_numpy(float), minlength=G)
exp_g = np.bincount(gid, weights=p, minlength=G)
var_g = np.bincount(gid, weights=p * (1 - p), minlength=G)
rate = n_ev / np.maximum(n_g, 1)


def adj_r2(y, w, *dummy_sets):
    cols_ = [np.ones(len(y))]
    for lab in dummy_sets:
        d = pd.get_dummies(lab, drop_first=True).to_numpy(float)
        cols_.append(d)
    Xd = np.column_stack(cols_)
    sw = np.sqrt(w)
    coef, *_ = np.linalg.lstsq(Xd * sw[:, None], y * sw, rcond=None)
    res = y - Xd @ coef
    ybar = np.average(y, weights=w)
    r2 = 1 - np.sum(w * res ** 2) / np.sum(w * (y - ybar) ** 2)
    k = Xd.shape[1] - 1
    return 1 - (1 - r2) * (len(y) - 1) / max(len(y) - k - 1, 1)


w = n_g[keep]
reg_lab, biz_lab = rg, biz_g[keep]
rows = []
for name, y in (("M3 위험점수(그룹 평균 LP)", glp.to_numpy()), ("관측 폐업률", rate[keep])):
    rows.append({"대상": name, "업종만": adj_r2(y, w, biz_lab), "시군구만": adj_r2(y, w, reg_lab), "업종+시군구": adj_r2(y, w, biz_lab, reg_lab)})
r2t = pd.DataFrame(rows).set_index("대상")
noise = float(np.average(var_g[keep] / n_g[keep] ** 2, weights=w))          # 그룹 폐업률의 이항 잡음 분산(기대확률 기준)
obs_var = float(np.cov(rate[keep], aweights=w))
print("\n=== 분석 1-b: 업종·시군구 더미로 설명되는 분산(조정 R^2, 사업장 수 가중) ===")
print(r2t.round(3).to_string())
print(f"관측 폐업률의 그룹 간 분산 중 이항 우연변동(잡음) 비중: {100 * noise / obs_var:.0f}%  -> 관측 폐업률 R^2의 이론적 상한은 약 {100 - 100 * noise / obs_var:.0f}%", flush=True)
r2t.round(4).to_csv("output/9_region_vs_biz_r2.csv", encoding="utf-8-sig")

# ============================================
# 분석 3: 사업장·지역 요인을 반영한 뒤의 초과 폐업 vs 소비
# ============================================
g = pd.DataFrame({"n": n_g, "obs_rate": rate, "exp_rate": exp_g / np.maximum(n_g, 1),
                  "excess": (n_ev - exp_g) / np.maximum(n_g, 1),
                  "z": (n_ev - exp_g) / np.sqrt(np.maximum(var_g, 1e-9)), "region_id": reg_g, "biz": biz_g})
grp_tbl = full.drop_duplicates("group_id").set_index("group_id").sort_index()
for c in JOIN_KEY + ["spend_jan", "spend_6d", "unit_z_jan", "log_n_grp", "g_closure_rate_1y"]:
    g[c] = grp_tbl[c].to_numpy() if c in grp_tbl else np.nan
g["평균 영업연수(년)"] = np.expm1(gmean(full["log_age"]))
g["프랜차이즈(%)"] = 100 * gmean(full["is_franchise"])
g["다중이용업소(%)"] = 100 * gmean(full["is_multiuse"])
g = g[keep].reset_index(drop=True)
for c in ("spend_jan", "spend_6d", "unit_z_jan"):
    g[c + "_pct"] = g.groupby("biz")[c].rank(pct=True)                       # 업종 내 백분위(업종마다 소비 수준이 달라 업종 안에서 비교)
    g[c + "_tier"] = pd.cut(g[c + "_pct"], [0, 1 / 3, 2 / 3, 1.0], labels=["하", "중", "상"], include_lowest=True)

print("\n=== 분석 3-a: 점포당 소비(1월, 업종 내 3분위)별 폐업 — 원자료 vs 사업장·지역 요인 반영 후 ===")
rows = []
for c, lab in (("spend_jan", "점포당 소비(1월)"), ("spend_6d", "점포당 소비(6개월, 월별 분모)"), ("unit_z_jan", "객단가(1월, 업종 내 z)")):
    for t in ("하", "중", "상"):
        s = g[g[c + "_tier"] == t]
        wt = s["n"]
        rows.append({"소비 변수": lab, "분위": t, "그룹 수": len(s),
                     "관측 폐업률(%)": np.average(s["obs_rate"], weights=wt) * 100, "M2h 기대 폐업률(%)": np.average(s["exp_rate"], weights=wt) * 100,
                     "초과 폐업률(%p)": np.average(s["excess"], weights=wt) * 100, "초과 z 평균": s["z"].mean(),
                     "z>1.96 비중(%)": 100 * (s["z"] > 1.96).mean(), "z<-1.96 비중(%)": 100 * (s["z"] < -1.96).mean()})
t3a = pd.DataFrame(rows)
print(t3a.round(2).to_string(index=False), flush=True)
t3a.round(3).to_csv("output/9_excess_by_spend_tier.csv", index=False, encoding="utf-8-sig")


def within_dev(x):
    m = pd.Series(x).groupby(g["region_id"].to_numpy()).transform("mean").to_numpy()
    return x - m


rng = np.random.default_rng(42)
reg_ids = np.unique(g["region_id"])
by = {r: np.where(g["region_id"].to_numpy() == r)[0] for r in reg_ids}
boots = [np.concatenate([by[r] for r in rng.choice(reg_ids, size=len(reg_ids), replace=True)]) for _ in range(B)]
rows = []
for c, lab in (("spend_jan_pct", "점포당 소비(1월) 업종 내 백분위"), ("spend_6d_pct", "점포당 소비(6개월) 업종 내 백분위"), ("unit_z_jan_pct", "객단가(1월) 업종 내 백분위")):
    x = g[c].to_numpy()
    for tgt, nm in (("obs_rate", "관측 폐업률"), ("excess", "초과 폐업률(M2h 기준)")):
        y = g[tgt].to_numpy()
        for kind, xx, yy in (("전체", x, y), ("같은 시군구 내 편차", within_dev(x), within_dev(y))):
            v = np.array([spearmanr(xx[b_], yy[b_]).statistic for b_ in boots])
            rows.append({"소비 변수": lab, "대상": nm, "기준": kind, "Spearman": round(float(spearmanr(xx, yy).statistic), 3),
                         "95% CI": f"[{np.percentile(v, 2.5):.3f}, {np.percentile(v, 97.5):.3f}]"})
t3b = pd.DataFrame(rows)
print("\n=== 분석 3-b: 소비 백분위와 폐업의 순위상관(시군구 cluster bootstrap) ===")
print(t3b.to_string(index=False), flush=True)
t3b.to_csv("output/9_excess_spend_spearman.csv", index=False, encoding="utf-8-sig")

# 3-c: 소비 상위 3분위이면서 초과 폐업이 큰 그룹
hi = g[(g["spend_jan_tier"] == "상")]
show = ["SIDO_NM", "CCG_NM", "bc_업종", "n", "obs_rate", "exp_rate", "z", "spend_jan_pct", "g_closure_rate_1y", "평균 영업연수(년)", "프랜차이즈(%)", "log_n_grp"]
top = hi.sort_values("z", ascending=False).head(25)[show]
print("\n=== 분석 3-c: 점포당 소비 상위 3분위인데 기대보다 폐업이 많은 그룹 상위 25 (z 순) ===")
print(top.round(3).to_string(index=False), flush=True)
top.round(4).to_csv("output/9_high_spend_high_excess.csv", index=False, encoding="utf-8-sig")

# 3-d: 소비 상위 그룹 안에서 초과 폐업 그룹(z>1.96) vs 정상 그룹의 특성 비교
hi = hi.assign(유형=np.where(hi["z"] > 1.96, "고소비·초과폐업(z>1.96)", "고소비·그 외"))
comp_cols = ["n", "obs_rate", "exp_rate", "g_closure_rate_1y", "평균 영업연수(년)", "프랜차이즈(%)", "다중이용업소(%)", "log_n_grp", "spend_jan", "unit_z_jan"]
comp = hi.groupby("유형")[comp_cols].mean().T
comp["그룹 수"] = np.nan
print("\n=== 분석 3-d: 고소비 그룹 안에서 초과 폐업 그룹과 그 외의 평균 특성 ===")
print(hi["유형"].value_counts().to_string())
print(comp.drop(columns="그룹 수").round(3).to_string(), flush=True)
comp.drop(columns="그룹 수").round(4).to_csv("output/9_high_spend_composition.csv", encoding="utf-8-sig")
print("\n완료", flush=True)
