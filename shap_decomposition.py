"""
shap_decomposition.py — Cox PH(M3)의 정확한 SHAP 분해를 시군구×업종 그룹으로 모아 "이 상권이 위험한 이유"를 만든다.

원리: Cox의 로그위험은 log h(x) = β·x + (기저)로 선형이다. 그래서 변수 j의 SHAP 값은 정확히
        φ_j(x) = β_j · (x_j − E[x_j])          (기준 = train 평균, interventional SHAP)
이고 Σ_j φ_j(x) = log h(x) − log h(평균 사업장)로 정확히 더해진다(근사 없음). 변수들을 의미 블록(영업연수·프랜차이즈·BC 연령 구성 …)으로
묶어 합산해도 그대로 정확하다. 사업장별 φ를 (시군구×업종) 그룹 안에서 평균내면 그 그룹의 위험이 어떤 블록 때문인지 나온다.

두 가지 기준선을 낸다:
  * overall   : 기준 = 전체 train 평균 사업장. '업종' 블록이 크게 나온다(업종 간 위험 차이).
  * withinbiz : 기준 = 같은 업종의 train 평균 사업장. 업종 효과가 0이 되어 '같은 업종 안에서 이 지역이 더 위험한 이유'만 남는다.
                상권을 비교할 때는 이쪽이 더 의미 있다.

주의(해석 한계, 리포트에 그대로 옮길 것):
  * 이 값은 '모형이 그렇게 예측하는 이유'이지 인과가 아니다. 특히 BC·지역 폐업률은 그룹 단위 변수다.
  * Cox는 비례위험 + 선형·가법 가정이다. 상호작용·비선형은 잡지 못한다(RSF 근사는 shap_rsf_approx.py).
  * '기여 비중(%)'은 위험을 올리는 블록끼리의 비중이다(내리는 블록은 별도 열, 서로 상쇄된다).
실행: python3 -u shap_decomposition.py
"""
import argparse
import time
import warnings

import matplotlib
matplotlib.use("Agg")
import matplotlib.font_manager
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from lifelines import CoxPHFitter
from lifelines.utils import concordance_index
from scipy.stats import spearmanr

from cohort_common import BLOCKS, BIZ_LIST, X_COLS, build_cohort, split_train_test

ap = argparse.ArgumentParser()
ap.add_argument("--end", default="2026-06-30")
ap.add_argument("--min-n", type=int, default=50, help="순위표에 넣는 그룹의 최소 사업장 수")
ap.add_argument("--top", type=int, default=30)
ap.add_argument("--seed", type=int, default=42)
args = ap.parse_args()
warnings.filterwarnings("ignore")
OUT = "output/"
T0 = time.time()


def log(m):
    print(f"[{(time.time() - T0) / 60:5.1f}분] {m}", flush=True)


log("코호트 생성")
d, horizon = build_cohort(args.end)
tr_idx, te_idx = split_train_test(d, args.seed)
is_train = np.zeros(len(d), bool)
is_train[tr_idx] = True
print(f"n={len(d):,}  폐업={int(d['event'].sum()):,}  train={is_train.sum():,}  test={(~is_train).sum():,}  그룹={d['group_id'].nunique():,}")

# 결측 대체는 train 중앙값만 사용(누수 방지). 값이 채워진 뒤에만 Cox가 돈다.
med = d.loc[is_train, X_COLS].median()
X = d[X_COLS].fillna(med).astype(float)
print("대체된 결측 열:", {c: int(d[c].isna().sum()) for c in X_COLS if d[c].isna().any()})

log("Cox PH(M3 = 사업장 + 지역 최근폐업률 + BC 구성비 + 업종) train 적합")
fit_df = X[is_train].assign(time=d.loc[is_train, "time"].to_numpy(), event=d.loc[is_train, "event"].astype(int).to_numpy())
cph = CoxPHFitter().fit(fit_df, duration_col="time", event_col="event")
coef = cph.summary[["coef", "exp(coef)", "se(coef)", "p"]].reindex(X_COLS)
coef.to_csv(OUT + "shap_cox_coef.csv", encoding="utf-8-sig")
log(f"적합 완료 (train 로그우도 {cph.log_likelihood_:.1f})")

# ------------------------------------------------------------------ 정확한 SHAP
beta = coef["coef"].to_numpy()
mu = X[is_train].mean().to_numpy()
phi = (X.to_numpy() - mu) * beta                       # n × p, φ_j = β_j (x_j − μ_j)

# 검증 1: 가법성 — Σφ가 lifelines의 로그위험(학습 평균 중심)과 같아야 한다.
lp = cph.predict_log_partial_hazard(X).to_numpy()
add_err = np.abs(phi.sum(axis=1) - lp).max()
print(f"[검증] 가법성 max|Σφ − log_partial_hazard| = {add_err:.2e}")
assert add_err < 1e-6, "SHAP 합이 모형 로그위험과 다르다"
# 검증 2: 모형 자체가 쓸 만한가(설명할 가치가 있는 모형인지) — test C-index
te = ~is_train
c_te = concordance_index(d.loc[te, "time"], -lp[te], d.loc[te, "event"])
print(f"[검증] Cox M3 test Harrell C = {c_te:.4f}  (rsf_eval RSF 0.6450과 비교용)")

col_pos = {c: i for i, c in enumerate(X_COLS)}
P = pd.DataFrame({b: phi[:, [col_pos[c] for c in cols]].sum(axis=1) for b, cols in BLOCKS.items()})   # 블록별 φ (overall)
biz_mean = P[is_train].groupby(d.loc[is_train, "bc_업종"].to_numpy()).mean()
Pw = P - biz_mean.reindex(d["bc_업종"]).to_numpy()                                                     # 같은 업종 train 평균 기준(withinbiz)
assert np.allclose(Pw["업종"], 0)                                                                       # 업종 블록은 기준선 안에서 0

# ------------------------------------------------------------------ 전역 중요도
glob = pd.DataFrame({"블록": P.columns,
                     "mean_abs_all": P.abs().mean().to_numpy(),
                     "mean_abs_test": P[te].abs().mean().to_numpy(),
                     "mean_abs_withinbiz": Pw.abs().mean().to_numpy()}).sort_values("mean_abs_all", ascending=False)
glob["비중_all_%"] = glob["mean_abs_all"] / glob["mean_abs_all"].sum() * 100
glob.round(4).to_csv(OUT + "shap_cox_global_importance.csv", index=False, encoding="utf-8-sig")
print("\n=== 전역 SHAP 중요도 (평균 |φ|, 로그위험 단위) ===")
print(glob.round(4).to_string(index=False))


# ------------------------------------------------------------------ 그룹 집계
def group_table(Pmat, name):
    gid = d["group_id"].to_numpy()
    agg = Pmat.groupby(gid).mean()
    meta = d.groupby("group_id").agg(시도=("SIDO_NM", "first"), 시군구=("CCG_NM", "first"), bc_업종=("bc_업종", "first"),
                                    사업장수=("event", "size"), 폐업수=("event", "sum"))
    meta["관찰_폐업률_%"] = meta["폐업수"] / meta["사업장수"] * 100
    meta["세트"] = np.where(pd.Series(is_train).groupby(gid).mean().to_numpy() > 0.5, "train", "test")   # 그룹은 한쪽에만 속한다
    t = meta.join(agg)
    t["총_로그위험"] = agg.sum(axis=1)
    t["위험배수"] = np.exp(t["총_로그위험"])
    pos = agg.clip(lower=0)
    neg = agg.clip(upper=0)
    t["양의_기여합"], t["음의_기여합"] = pos.sum(axis=1), neg.sum(axis=1)

    def reason(row):
        c = row[list(BLOCKS)]
        up = row["총_로그위험"] >= 0
        s = (c.clip(lower=0) if up else (-c).clip(lower=0))
        if s.sum() <= 1e-12:
            return ""
        s = (s / s.sum() * 100).sort_values(ascending=False)
        top = [f"{k} {v:.0f}%" for k, v in s.items() if v >= 1][:3]
        return ("위험↑ " if up else "위험↓ ") + " · ".join(top)

    t["이유_요약"] = t.apply(reason, axis=1)
    t.insert(0, "기준", name)
    return t.reset_index()


g_all, g_w = group_table(P, "overall"), group_table(Pw, "withinbiz")
g_all.round(5).to_csv(OUT + "shap_cox_group_overall.csv", index=False, encoding="utf-8-sig")
g_w.round(5).to_csv(OUT + "shap_cox_group_withinbiz.csv", index=False, encoding="utf-8-sig")

big = g_w[g_w["사업장수"] >= args.min_n].sort_values("총_로그위험", ascending=False)
show = ["시도", "시군구", "bc_업종", "사업장수", "관찰_폐업률_%", "위험배수", "이유_요약", "세트"]
top_tbl = pd.concat([big.head(args.top).assign(구분="위험 상위"), big.tail(args.top).assign(구분="위험 하위")])
top_tbl[["구분"] + show + list(BLOCKS)].round(4).to_csv(OUT + "shap_cox_top_groups.csv", index=False, encoding="utf-8-sig")
print(f"\n=== 같은 업종 평균 대비 위험 상위 (사업장 {args.min_n}개 이상 그룹 {len(big):,}개 중) ===")
print(big.head(12)[show].round(3).to_string(index=False))
print("\n=== 위험 하위 ===")
print(big.tail(5)[show].round(3).to_string(index=False))

# 검증 3: 그룹 평균 예측 위험이 실제 폐업률과 같은 방향인지(설명할 대상이 실제 위험과 무관하면 분해도 무의미).
print("\n[검증] 그룹 평균 로그위험 vs 관찰 폐업률 Spearman (사업장 %d개 이상 그룹)" % args.min_n)
for name, g in (("overall", g_all), ("withinbiz", g_w)):
    gg = g[g["사업장수"] >= args.min_n]
    r_all = spearmanr(gg["총_로그위험"], gg["관찰_폐업률_%"])[0]
    gt = gg[gg["세트"] == "test"]
    r_te = spearmanr(gt["총_로그위험"], gt["관찰_폐업률_%"])[0]
    print(f"  {name:9s} 전체 {len(gg):,}그룹 ρ={r_all:.3f} / test 그룹 {len(gt):,}개 ρ={r_te:.3f}")

# ------------------------------------------------------------------ 그림
for fam in ("AppleGothic", "Malgun Gothic", "NanumGothic"):
    if any(fam == f.name for f in matplotlib.font_manager.fontManager.ttflist):
        plt.rcParams["font.family"] = fam
        break
plt.rcParams["axes.unicode_minus"] = False
cols10 = plt.cm.tab10(np.arange(10))
fig, axes = plt.subplots(1, 2, figsize=(17, 6.5), gridspec_kw={"width_ratios": [1, 1.6]})
gs = glob.sort_values("mean_abs_all")
axes[0].barh(gs["블록"], gs["mean_abs_all"], color="#4C78A8")
axes[0].set(title="전역 SHAP 중요도 (평균 |φ|, 로그위험)", xlabel="평균 |φ|")
top12 = big.head(12).iloc[::-1]
ypos = np.arange(len(top12))
left_p, left_n = np.zeros(len(top12)), np.zeros(len(top12))
for i, b in enumerate(BLOCKS):
    if b == "업종":
        continue
    v = top12[b].to_numpy()
    axes[1].barh(ypos, np.where(v > 0, v, 0), left=left_p, color=cols10[i], label=b)
    axes[1].barh(ypos, np.where(v < 0, v, 0), left=left_n, color=cols10[i])
    left_p += np.where(v > 0, v, 0)
    left_n += np.where(v < 0, v, 0)
axes[1].set_yticks(ypos)
axes[1].set_yticklabels([f"{r.시군구} {r.bc_업종} (n={r.사업장수:,})" for r in top12.itertuples()], fontsize=8)
axes[1].axvline(0, color="k", lw=0.8)
axes[1].set(title=f"같은 업종 평균 대비 위험 상위 12개 상권의 블록별 기여 (사업장 {args.min_n}+)", xlabel="로그위험 기여(오른쪽=위험↑)")
axes[1].legend(fontsize=8, loc="lower right")
fig.suptitle("Cox M3 정확 SHAP 분해 (train 적합, 그룹 평균) — 모형 설명이지 인과가 아니다", fontsize=11)
fig.tight_layout()
fig.savefig(OUT + "shap_cox_decomposition.png", dpi=130)
log("완료")
