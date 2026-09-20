# -*- coding: utf-8 -*-
"""
Cox 기준 "SHAP" 분해 — 지역×업종이 왜 위험/안전한가를 요인 블록별로 나눈다.

[설명 대상 — 정확한 정의]
  설명하는 것은 Cox의 **선형예측자(log partial hazard)** 이다. 시점과 무관한 위험도 점수이며, 특정 시점의 생존확률이 아니다.
  Cox는 선형이라 사업장 i의 변수 j 기여는 정확히  shap_ij = beta_j * (x_ij - mean_j)  이고,
  sum_j shap_ij = (사업장 i의 선형예측자) - (평균 사업장의 선형예측자)  가 성립한다(실행 시 lifelines 예측값과 대조해 검증한다).
  기준(baseline)은 코호트 평균 사업장이다. exp(기여)는 "평균 사업장 대비 상대위험 배수"로 읽는다(예: 프랜차이즈 x0.93).

[읽을 때 주의]
  - 연관의 분해이지 인과가 아니다(프랜차이즈여서 덜 폐업한다고 단정할 수 없음).
  - BC카드 변수는 사업장별이 아니라 시군구x업종 그룹 단위 값이라 생태학적 해석이다.
  - 변수 간 상관(예: 성별·연령 구성비, 크기와 다중이용업소)이 있어 변수 하나하나가 아니라 **블록 단위**로 읽는다.
  - "X% 기여"는 부호가 섞여 오해하기 쉬우므로 곱셈 배수를 주된 표현으로 하고 절대값 비중은 참고용으로만 낸다.

[기본 대상 모형] M3(사업장 변수 + 지역 최근 폐업률 + BC카드), 코호트 전체에 적합. (경쟁밀도 M4가 확정되면 --model로 바꿔 같은 방식으로 돌린다)

산출물: output/6_explain_cox_coef.csv, 6_explain_block_importance.csv, 6_explain_group_blocks.csv
"""
import argparse

import numpy as np
import pandas as pd

from explain_common import fit_cox_cached, load_cohort, model_cols

ap = argparse.ArgumentParser()
ap.add_argument("--model", default=None, help="explain 대상 모형 이름(기본: cox_rsf.py의 TOP = 'M3 +BC카드')")
ap.add_argument("--min-n", type=int, default=300, help="그룹별 표에 넣을 최소 사업장 수")
ap.add_argument("--no-cache", action="store_true")
ap.add_argument("--holdout", action="store_true", help="학습 그룹으로 적합한 모형이 미학습 그룹의 위험 순위를 얼마나 맞히는지(그룹 단위) 확인")
args = ap.parse_args()

ns, log = load_cohort()
full = ns["full"].reset_index(drop=True)
JOIN_KEY = ns["JOIN_KEY"]
model = args.model or ns["TOP"]
cols = model_cols(ns, model)
print(f"코호트: {len(full):,}행, 폐업 {int(full['event'].sum()):,}건 / 설명 대상 모형: {model} ({len(cols)}개 변수)")

cph = fit_cox_cached(model, cols, full, use_cache=not args.no_cache)
beta = cph.params_.reindex(cols)

# ---- 1) 정확한 분해 + 검증 ----
X = full[cols].astype(float)
mu = X.mean()
contrib = (X - mu) * beta                        # shap_ij
lp_model = cph.predict_log_partial_hazard(full[cols]).to_numpy()
err = float(np.abs(contrib.sum(axis=1).to_numpy() - lp_model).max())
print(f"[검증] max |sum_j shap_ij - lifelines 선형예측자| = {err:.2e}  (0에 가까워야 정확한 분해)")
assert err < 1e-6, "SHAP 합이 모형의 선형예측자와 다르다 — 정의를 재검토하라"

# ---- 2) 블록 ----
share = ns["COV_SHARE"]
BLOCKS = {
    "영업연수": ["log_age"],
    "프랜차이즈": ["is_franchise"],
    "입지(중심점 거리)": ["log_dist_to_centroid"],
    "사업장 확장(다중이용·크기·좌표결측·전화)": list(ns["STORE_EXT"]),
    "지역 최근 폐업률": list(ns["COV_HIST"]),
    "BC 성별 구성": [c for c in share if "gender" in c],
    "BC 연령 구성": [c for c in share if "age" in c],
    "업종": list(ns["BIZ_DUMMY"]),
}
BLOCKS = {k: [c for c in v if c in cols] for k, v in BLOCKS.items()}
BLOCKS = {k: v for k, v in BLOCKS.items() if v}
assigned = sorted(c for v in BLOCKS.values() for c in v)
assert assigned == sorted(cols), f"블록에 배정되지 않은 변수: {sorted(set(cols) - set(assigned))}"
blk = pd.DataFrame({k: contrib[v].sum(axis=1) for k, v in BLOCKS.items()})

# ---- 3) 계수표 ----
coef = pd.DataFrame({"coef": beta, "HR": np.exp(beta), "평균": mu, "표준편차": X.std()})
coef["1SD당_HR"] = np.exp(beta * X.std())
coef["블록"] = [next(k for k, v in BLOCKS.items() if c in v) for c in coef.index]
coef.round(4).to_csv("output/6_explain_cox_coef.csv", encoding="utf-8-sig")

# ---- 4) 전체 중요도(블록별) ----
imp = pd.DataFrame({"평균_절대기여(log HR)": blk.abs().mean(), "기여의_표준편차(log HR)": blk.std()})
imp["전형적_배수(exp 평균절대)"] = np.exp(imp["평균_절대기여(log HR)"])
imp["절대기여_비중(%)"] = imp["평균_절대기여(log HR)"] / imp["평균_절대기여(log HR)"].sum() * 100
imp = imp.sort_values("평균_절대기여(log HR)", ascending=False)
imp.round(4).to_csv("output/6_explain_block_importance.csv", encoding="utf-8-sig")
print("\n=== 블록별 중요도(사업장 단위 SHAP의 평균 절대값) ===")
print(imp.round(3).to_string())

# ---- 5) 지역x업종 그룹별 분해 ----
keys = [full[k] for k in JOIN_KEY]
g_blk = blk.groupby(keys, observed=True).mean()
g_info = full.groupby(JOIN_KEY, observed=True).agg(n=("event", "size"), events=("event", "sum"), obs_rate=("event", "mean"))
g_lp = pd.Series(lp_model, index=full.index).groupby(keys, observed=True).mean().rename("mean_LP")
grp = g_info.join(g_lp).join(g_blk)
grp["상대위험_배수"] = np.exp(grp["mean_LP"])
for c in blk.columns:
    grp[f"x_{c}"] = np.exp(grp[c])
grp = grp.reset_index()
grp.round(4).to_csv("output/6_explain_group_blocks.csv", index=False, encoding="utf-8-sig")
print(f"\n그룹(시군구x업종) {len(grp):,}개 저장 -> output/6_explain_group_blocks.csv")

big = grp[grp["n"] >= args.min_n].sort_values("mean_LP")
show = ["SIDO_NM", "CCG_NM", "bc_업종", "n", "obs_rate", "상대위험_배수"] + [f"x_{c}" for c in blk.columns]
print(f"\n=== 가장 위험한 그룹 8개 (사업장>={args.min_n}) — 각 열은 평균 사업장 대비 상대위험 배수 ===")
print(big.tail(8).iloc[::-1][show].round(3).to_string(index=False))
print(f"\n=== 가장 안전한 그룹 8개 ===")
print(big.head(8)[show].round(3).to_string(index=False))

# ---- 6) 해석 보조: 그룹 위험 격차를 어느 블록이 설명하나 ----
spread = big[list(blk.columns)].std().sort_values(ascending=False)
print("\n=== 그룹 간 위험 격차에 대한 블록별 기여의 표준편차(log HR) — 클수록 그룹을 가르는 요인 ===")
print(spread.round(4).to_string())
pd.DataFrame({"그룹간_표준편차(log HR)": spread}).round(4).to_csv("output/6_explain_group_spread.csv", encoding="utf-8-sig")

# ---- 7) (선택) 분해가 미학습 그룹에서도 통하는가 ----
# 위 분해는 코호트 전체에 적합한 모형의 내부 구조다. BC카드 변수는 그룹 단위 값이라, 그룹 수(약 1,800)에 비해 계수가 크면 같은 그룹들의 차이를
# 과하게 맞춰(in-sample) 새 그룹에서는 통하지 않을 수 있다. 그룹 단위로 학습/평가를 나눠 "그룹 평균 위험점수 vs 관측 그룹 폐업률"의 순위상관(Spearman)을 본다.
if args.holdout:
    from scipy.stats import spearmanr
    col, tr_ids, _ = ns["make_split"]("group", ns["RANDOM_STATE"])
    sets = ns["make_sets"](col, tr_ids)
    train, test = sets["train"].reset_index(drop=True), sets[ns["TEST_KEY"]].reset_index(drop=True)
    rows = []
    for m in (ns["BASE"], ns["REF"], ns["TOP"]):
        cm = model_cols(ns, m)
        cph_tr = fit_cox_cached(m + "|train", cm, train, use_cache=not args.no_cache)
        for label, d in (("학습 그룹(in-sample)", train), ("미학습 그룹(hold-out)", test)):
            lp = cph_tr.predict_log_partial_hazard(d[cm]).to_numpy()
            g = d.assign(_lp=lp).groupby(JOIN_KEY, observed=True).agg(n=("event", "size"), rate=("event", "mean"), lp=("_lp", "mean"))
            g = g[g["n"] >= 100]
            rows.append({"모형": m, "평가 대상": label, "그룹 수": len(g), "Spearman(그룹 평균 위험점수, 관측 폐업률)": round(float(spearmanr(g["lp"], g["rate"]).statistic), 3)})
    res = pd.DataFrame(rows)
    res.to_csv("output/6_explain_holdout.csv", index=False, encoding="utf-8-sig")
    print("\n=== 그룹 단위 순위 검증: 학습 그룹 vs 미학습 그룹 (사업장>=100인 그룹) ===")
    print(res.to_string(index=False))
