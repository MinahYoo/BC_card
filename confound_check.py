# -*- coding: utf-8 -*-
"""
BC카드 '연령 구성' 효과가 상권 유형(신도시/도심/농촌 등 시군구 수준 특성)의 대리 변수인지 점검한다.

배경: explain_cox.py에서 BC 연령 구성이 그룹(시군구x업종) 간 위험 격차를 가르는 1위 요인으로 나왔다. 그러나 이 블록 분산의 42%만 시군구 간 차이이고
      58%는 같은 시군구 안의 업종 간 차이라, 시군구 수준 변수 하나를 통제하는 것만으로는 대리 변수 가설을 검정할 수 없다.

검정 3종(모두 M3 = 사업장 변수 + 지역 최근 폐업률 + BC카드 기준)
  M3   : 기준 모형
  M3c  : M3 + 통제(행정구역 유형 구/군 더미 + 소진공 음식·편의 상가 수(로그))    — 거칠지만 투명한 통제
  M3s  : M3를 시군구별로 층화(시군구마다 기저위험을 따로) — 시군구 수준의 **모든** 교란(측정 여부와 무관)을 제거하고
         "같은 시군구 안에서 업종별 연령 구성이 다를 때 위험이 달라지는가"만 본다.

평가 지표(SHAP 비중은 변수가 겹치면 재분배돼 흔들리므로 쓰지 않는다)
  1) BC 연령 블록(5개 변수)의 결합 Wald 통계량 — **일반 분산이라 유의성이 부풀려지므로 p값은 쓰지 않고 모형 간 감쇠(상대 비교)로만 본다**
     (lifelines의 군집-강건 분산은 동률을 처리하지 못해 사용하지 않음). 추론은 2)의 시군구 cluster bootstrap으로 한다.
  2) 미학습 그룹 순위상관(Spearman)에서 연령 블록을 뺐을 때의 감소 = 연령 블록의 증분. 전체 그룹 기준과
     같은 시군구 안 편차(within-region) 기준을 모두 보고, 시군구 cluster bootstrap으로 신뢰구간을 낸다.
  * 층화 모형(M3s)은 시군구 간 차이를 일부러 제거하므로 within-region 기준만 의미가 있다.

해석 주의: 통제 후 연령 효과가 남아도 "고객 연령이 폐업을 만든다"는 인과가 아니다(측정되지 않은 다른 그룹 수준 요인이 남을 수 있음).
산출물: output/7_confound_wald.csv, output/7_confound_holdout.csv
"""
import numpy as np
import pandas as pd
from scipy.stats import chi2, spearmanr

from explain_common import fit_cox_cached, load_cohort, model_cols

B = 500
MIN_N = 100
print("코호트 로드...", flush=True)
ns, log = load_cohort()
full = ns["full"].reset_index(drop=True)
JOIN_KEY = ns["JOIN_KEY"]
TOP = ns["TOP"]

# ---- 통제 변수 ----
def rtype(ccg):
    last = ccg.split()[-1]
    return "군" if last.endswith("군") else ("구" if last.endswith("구") else "시")


dens = pd.read_csv("output/5_경쟁밀도_시군구x업종.csv", encoding="utf-8-sig")
dens = dens.groupby(["SIDO_NM", "CCG_NM"])["competitor_n"].sum().reset_index(name="sojin_n")
n0 = len(full)
full = full.merge(dens, on=["SIDO_NM", "CCG_NM"], how="left", validate="m:1")
assert len(full) == n0
miss = full["sojin_n"].isna().sum()
print(f"소진공 상가 수 미결합 행: {miss}", flush=True)
full["sojin_n"] = full["sojin_n"].fillna(full["sojin_n"].median())
full["log_sojin_n"] = np.log1p(full["sojin_n"])
types = full["CCG_NM"].map(rtype)
full["type_gu"] = (types == "구").astype(int)
full["type_gun"] = (types == "군").astype(int)
print("행정구역 유형 비중(%):", (types.value_counts(normalize=True) * 100).round(1).to_dict(), flush=True)

cols_M3 = model_cols(ns, TOP)
age_cols = [c for c in cols_M3 if "amt_share_age" in c]
controls = ["type_gu", "type_gun", "log_sojin_n"]
cols_M3c = cols_M3 + controls
noage = lambda cs: [c for c in cs if c not in age_cols]
STR = ["region_id"]

# ---- 1) 전체 코호트 적합 + 연령 블록 결합 Wald(시군구 군집-강건 분산) ----
fits = {
    "M3": dict(name=TOP, cols=cols_M3, strata=None),
    "M3c (+구/군 유형, 소진공 상가 수)": dict(name="M3c", cols=cols_M3c, strata=None),
    "M3s (시군구 층화)": dict(name="M3s", cols=cols_M3, strata=STR),
}
rows = []
keys = [full[k] for k in JOIN_KEY]
for label, f in fits.items():
    print(f"[적합] {label} ...", flush=True)
    # lifelines의 군집-강건 분산은 동률(ties)을 처리하지 못한다고 문서에 명시돼 있고(일 단위 기간이라 동률이 매우 많음) 이 데이터에서 오류도 났다.
    # 그래서 Wald는 일반 분산으로 계산하되 사업장을 독립 관측으로 세므로 유의성이 부풀려진다 -> 모형 간 '상대적 감쇠 지표'로만 쓰고,
    # 추론은 아래 미학습 그룹 검증의 시군구 cluster bootstrap 신뢰구간으로 한다.
    cph = fit_cox_cached(f["name"] + "|plain", f["cols"], full, strata=f["strata"])
    robust = False
    b = cph.params_.reindex(age_cols)
    V = cph.variance_matrix_.loc[age_cols, age_cols]
    wald = float(b.to_numpy() @ np.linalg.pinv(V.to_numpy()) @ b.to_numpy())
    X = full[f["cols"]].astype(float)
    c_age = ((X[age_cols] - X[age_cols].mean()) * b).sum(axis=1)
    grp = c_age.groupby(keys, observed=True).mean()
    n_grp = full.groupby(JOIN_KEY, observed=True).size()
    spread = float(grp[n_grp.reindex(grp.index) >= 300].std())
    rows.append({"모형": label, "분산": "일반(추론용 아님, 상대 비교용)", "연령블록 Wald": round(wald, 2), "df": len(age_cols),
                 "p": chi2.sf(wald, len(age_cols)), "그룹간 기여 표준편차(log HR)": round(spread, 4),
                 "연령 계수(5개)": " / ".join(f"{v:.2f}" for v in b)})
    print(f"  Wald={wald:.1f} (df={len(age_cols)}), 그룹 간 기여 SD={spread:.4f}", flush=True)
wald_tbl = pd.DataFrame(rows)
wald_tbl.to_csv("output/7_confound_wald.csv", index=False, encoding="utf-8-sig")
print("\n=== 연령 구성 블록의 결합 검정 ===")
print(wald_tbl.drop(columns="연령 계수(5개)").to_string(index=False), flush=True)

# ---- 2) 미학습 그룹 순위 검증: 연령 블록의 증분 ----
col, tr_ids, _ = ns["make_split"]("group", ns["RANDOM_STATE"])
is_tr = full[col].isin(tr_ids)   # 통제 변수를 붙인 full에서 나눈다(ns의 make_sets는 통제 변수가 없는 원본 full을 쓴다)
train, test = full[is_tr].reset_index(drop=True), full[~is_tr].reset_index(drop=True)
spec = {                                   # 표시 이름: (캐시 이름, 열, 층)
    "M3": (TOP + "|train", cols_M3, None),
    "M3 - 연령블록": ("M3-age|train", noage(cols_M3), None),
    "M3c": ("M3c|train", cols_M3c, None),
    "M3c - 연령블록": ("M3c-age|train", noage(cols_M3c), None),
    "M3s(층화)": ("M3s|train", cols_M3, STR),
    "M3s(층화) - 연령블록": ("M3s-age|train", noage(cols_M3), STR),
}
gm = {}
for label, (cname, cs, st) in spec.items():
    print(f"[학습 그룹 적합] {label} ...", flush=True)
    cph = fit_cox_cached(cname, cs, train, strata=st)
    lp = cph.predict_log_partial_hazard(test[cs]).to_numpy()
    g = test.assign(_lp=lp).groupby(JOIN_KEY, observed=True).agg(n=("event", "size"), rate=("event", "mean"), lp=("_lp", "mean"), region=("region_id", "first"))
    gm[label] = g[g["n"] >= MIN_N]
base = gm["M3"]
for lab in gm:
    assert gm[lab].index.equals(base.index)
print(f"미학습 그룹(사업장>={MIN_N}) {len(base)}개, 시군구 {base['region'].nunique()}개", flush=True)


def within(g, colname):
    m = g.groupby("region").apply(lambda d: np.average(d[colname], weights=d["n"]), include_groups=False)
    return g[colname] - g["region"].map(m)


rate_dev = within(base, "rate").to_numpy()
lp_all = {lab: g["lp"].to_numpy() for lab, g in gm.items()}
lp_dev = {lab: within(g, "lp").to_numpy() for lab, g in gm.items()}
reg = base["region"].to_numpy()
rate = base["rate"].to_numpy()
reg_ids = np.unique(reg)
idx_by_reg = {r: np.where(reg == r)[0] for r in reg_ids}
rng = np.random.default_rng(42)
boots = [np.concatenate([idx_by_reg[r] for r in rng.choice(reg_ids, size=len(reg_ids), replace=True)]) for _ in range(B)]


def rho(x, y, idx=None):
    if idx is not None:
        x, y = x[idx], y[idx]
    return float(spearmanr(x, y).statistic)


def ci(fn):
    v = np.array([fn(ix) for ix in boots])
    return np.percentile(v, [2.5, 97.5])


res = []
for kind, xs, y in (("전체 그룹", lp_all, rate), ("같은 시군구 내 편차", lp_dev, rate_dev)):
    for lab in gm:
        if kind == "전체 그룹" and "층화" in lab:
            continue                                       # 층화 모형은 시군구 간 차이를 제거하므로 전체 기준이 무의미
        lo, hi = ci(lambda ix, lab=lab: rho(xs[lab], y, ix))
        res.append({"기준": kind, "모형": lab, "Spearman": round(rho(xs[lab], y), 3), "95% CI": f"[{lo:.3f}, {hi:.3f}]"})
pair_res = []
for kind, xs, y in (("전체 그룹", lp_all, rate), ("같은 시군구 내 편차", lp_dev, rate_dev)):
    for full_lab, no_lab in (("M3", "M3 - 연령블록"), ("M3c", "M3c - 연령블록"), ("M3s(층화)", "M3s(층화) - 연령블록")):
        if kind == "전체 그룹" and "층화" in full_lab:
            continue
        d0 = rho(xs[full_lab], y) - rho(xs[no_lab], y)
        lo, hi = ci(lambda ix, a=full_lab, b=no_lab: rho(xs[a], y, ix) - rho(xs[b], y, ix))
        pair_res.append({"기준": kind, "비교": f"{full_lab} − ({no_lab})", "연령 블록의 증분(ΔSpearman)": round(d0, 3), "95% CI": f"[{lo:.3f}, {hi:.3f}]",
                         "CI가 0 제외": "예" if (lo > 0 or hi < 0) else "아니오"})
out = pd.DataFrame(res)
pairs = pd.DataFrame(pair_res)
out.to_csv("output/7_confound_holdout.csv", index=False, encoding="utf-8-sig")
pairs.to_csv("output/7_confound_holdout_increment.csv", index=False, encoding="utf-8-sig")
print("\n=== 미학습 그룹 순위상관(그룹 평균 위험점수 vs 관측 폐업률) ===")
print(out.to_string(index=False))
print("\n=== 연령 구성 블록의 증분(블록을 뺀 모형과의 차이, 시군구 cluster bootstrap) ===")
print(pairs.to_string(index=False), flush=True)
