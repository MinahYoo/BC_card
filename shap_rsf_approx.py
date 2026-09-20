"""
shap_rsf_approx.py — RSF의 블록 단위 SHAP 근사(표본 기반)와 Cox 정확 SHAP과의 비교.

RSF는 선형이 아니라 정확한 SHAP 공식이 없다. 그래서 Štrumbelj–Kononenko의 permutation-sampling Shapley를 쓴다:
  · 플레이어 = 설명 블록 10개(영업연수·프랜차이즈·BC 연령 구성 …; cohort_common.BLOCKS). 변수 17개가 아니라 블록 단위라서
    상관이 높은 BC 구성비(합=1)가 서로 쪼개지는 문제가 없고 계산도 훨씬 싸다.
  · 값 함수 f(x) = log(RSF 위험점수). 위험점수 = 누적위험함수의 전 시점 합(양수)이며 로그를 취하면 Cox의 로그위험과 비슷한 가법 척도가 된다.
  · 한 번의 반복 = 블록 순서 π 하나 + 배경 사업장 z 하나: z에서 시작해 π 순서대로 블록을 x의 값으로 바꿔 가며 f의 증가분을 그 블록에 귀속.
    M번 평균하면 φ_b(x)의 불편추정치가 된다. 반복마다 f(x) − f(z)가 정확히 나눠지므로 Σ_b φ_b(x) = f(x) − mean_z f(z)가 (수치 오차 내에서) 항상 성립한다 — 근사 오차는
    '블록 간 배분'에만 있고 이 표준오차를 함께 낸다.
  · 배경 분포 = train 사업장 표본(interventional). Cox의 정확 SHAP(기준 = train 평균)과 같은 개념이라 블록별로 직접 비교할 수 있다.
  · 비용 때문에 사업장 전부가 아니라 선택한 그룹(Cox 기준 위험 상위·하위 + 무작위)에서 그룹당 일정 수만 설명한다.

Cox 정확 SHAP 분해 자체는 팀원의 explain_cox.py(CHANGELOG ⑰)가 이미 제공한다. 이 스크립트는 RSF와 비교하고 설명 대상 그룹을 고르는 데
필요한 만큼만 Cox M3를 직접 적합한다(train, 수 초). 다른 스크립트의 산출물에 의존하지 않는다.
주의: RSF는 rsf_eval.py 최종 모형(500트리·15만 행)을 저장해 두지 않아 더 작은 모형(기본 200트리·10만 행)을 같은 최적 하이퍼파라미터로 다시 학습한다.
      업종은 rsf_eval.py의 one-hot 범주 대신 이미 만들어 둔 더미 6개를 그대로 쓴다(같은 정보).
실행: python3 -u shap_rsf_approx.py           (--quick 은 동작 확인용)
"""
import argparse
import json
import time
import warnings

import numpy as np
import pandas as pd
from lifelines import CoxPHFitter
from lifelines.utils import concordance_index
from sksurv.ensemble import RandomSurvivalForest
from sksurv.util import Surv

from cohort_common import BLOCKS, X_COLS, build_cohort, split_train_test

ap = argparse.ArgumentParser()
ap.add_argument("--end", default="2026-06-30")
ap.add_argument("--rsf-n", type=int, default=100_000)
ap.add_argument("--rsf-trees", type=int, default=200)
ap.add_argument("--n-perm", type=int, default=40, help="Shapley 반복 수 M")
ap.add_argument("--per-group", type=int, default=25, help="그룹당 설명할 사업장 수")
ap.add_argument("--n-top", type=int, default=20)
ap.add_argument("--n-bottom", type=int, default=10)
ap.add_argument("--n-random", type=int, default=30)
ap.add_argument("--seed", type=int, default=42)
ap.add_argument("--quick", action="store_true")
args = ap.parse_args()
if args.quick:
    args.rsf_n, args.rsf_trees, args.n_perm, args.per_group, args.n_top, args.n_bottom, args.n_random = 20_000, 30, 6, 5, 3, 2, 3
warnings.filterwarnings("ignore")
OUT = "output/"
T0 = time.time()
rng = np.random.default_rng(args.seed)


def log(m):
    print(f"[{(time.time() - T0) / 60:5.1f}분] {m}", flush=True)


log("코호트 생성")
d, horizon = build_cohort(args.end)
tr_idx, te_idx = split_train_test(d, args.seed)
is_train = np.zeros(len(d), bool)
is_train[tr_idx] = True
med = d.loc[is_train, X_COLS].median()                      # 결측 대체는 train 중앙값만(누수 방지)
X = d[X_COLS].fillna(med).astype(float)

# ------------------------------------------------------------------ Cox M3 적합 (정확 SHAP 비교 + 설명 대상 그룹 선택)
names = list(BLOCKS)
col_idx = {b: [X_COLS.index(c) for c in cols] for b, cols in BLOCKS.items()}
fit_df = X[is_train].assign(time=d.loc[is_train, "time"].to_numpy(), event=d.loc[is_train, "event"].astype(int).to_numpy())
cph = CoxPHFitter().fit(fit_df, duration_col="time", event_col="event")
coef = cph.params_.reindex(X_COLS).to_numpy()
mu = X[is_train].mean().to_numpy()
phi_cox_all = (X.to_numpy() - mu) * coef                 # Cox 정확 SHAP: β_j (x_j − train 평균)
assert np.abs(phi_cox_all.sum(axis=1) - cph.predict_log_partial_hazard(X).to_numpy()).max() < 1e-6
P = pd.DataFrame({b: phi_cox_all[:, col_idx[b]].sum(axis=1) for b in names})
biz_mean = P[is_train].groupby(d.loc[is_train, "bc_업종"].to_numpy()).mean()
Pw = P - biz_mean.reindex(d["bc_업종"]).to_numpy()       # 같은 업종 train 평균 기준(업종 효과 제거): 설명 대상 그룹의 위험 순위용

# ------------------------------------------------------------------ RSF 학습 (rsf_eval.py의 최적 하이퍼파라미터)
try:
    best = json.load(open(OUT + "rsf_eval_best_params.json"))
except FileNotFoundError:
    best = dict(min_samples_leaf=370, min_samples_split=1480, max_features="sqrt", max_depth=None)
print("RSF 하이퍼파라미터(rsf_eval 튜닝 결과):", best)
fit_rows = rng.choice(np.where(is_train)[0], size=min(args.rsf_n, is_train.sum()), replace=False)
y_fit = Surv.from_arrays(d["event"].to_numpy()[fit_rows], d["time"].to_numpy()[fit_rows])
log(f"RSF 학습: 트리 {args.rsf_trees}개, {len(fit_rows):,}행")
rsf = RandomSurvivalForest(n_estimators=args.rsf_trees, n_jobs=-1, random_state=args.seed, **best)
rsf.fit(X.iloc[fit_rows], y_fit)
te_sample = rng.choice(np.where(~is_train)[0], size=min(40_000, (~is_train).sum()), replace=False)
c_te = concordance_index(d["time"].to_numpy()[te_sample], -rsf.predict(X.iloc[te_sample]), d["event"].to_numpy()[te_sample])
print(f"[검증] 이 RSF의 test 표본(4만 행) Harrell C = {c_te:.4f}  (rsf_eval 500트리·15만 행 모형 0.6450과 비교)")


def f(M):
    """값 함수: log(RSF 위험점수). 배열 M(n×p, X_COLS 순서)을 받는다."""
    out = []
    for i in range(0, len(M), 20_000):
        out.append(rsf.predict(pd.DataFrame(M[i:i + 20_000], columns=X_COLS)))
    return np.log(np.clip(np.concatenate(out), 1e-9, None))


# ------------------------------------------------------------------ 설명 대상 선택 (Cox 위험 순위 기반)
gtab = d.groupby("group_id").agg(시도=("SIDO_NM", "first"), 시군구=("CCG_NM", "first"), bc_업종=("bc_업종", "first"),
                                 사업장수=("event", "size"), 폐업수=("event", "sum"))
gtab["관찰_폐업률_%"] = gtab["폐업수"] / gtab["사업장수"] * 100
gtab["총_로그위험"] = Pw.sum(axis=1).groupby(d["group_id"]).mean()     # 같은 업종 평균 대비 그룹 평균 Cox 로그위험
big = gtab[gtab["사업장수"] >= 50].sort_values("총_로그위험", ascending=False).reset_index()
sel = pd.concat([big.head(args.n_top), big.tail(args.n_bottom),
                 big.iloc[args.n_top:-args.n_bottom].sample(args.n_random, random_state=args.seed)])
sel_gids = sel["group_id"].tolist()
rows = np.concatenate([rng.choice(np.where(d["group_id"].to_numpy() == g)[0],
                                  size=min(args.per_group, int((d["group_id"] == g).sum())), replace=False) for g in sel_gids])
Xe = X.to_numpy()[rows]
gid_e = d["group_id"].to_numpy()[rows]
print(f"설명 대상: 그룹 {len(sel_gids)}개(위험 상위 {args.n_top} + 하위 {args.n_bottom} + 무작위 {args.n_random}), 사업장 {len(rows):,}개")

# ------------------------------------------------------------------ 블록 permutation-sampling Shapley
bg_pool = np.where(is_train)[0]
N, B, M = len(rows), len(names), args.n_perm
phi_all = np.zeros((M, N, B))                       # 반복별 값을 남겨 표준오차를 계산한다
base_f = np.zeros((M, N))
log(f"Shapley 근사: 사업장 {N:,} × 반복 {M} × 평가 {B + 1} = {N * M * (B + 1):,}회 RSF 예측")
fx = f(Xe)
for m in range(M):
    order = rng.permutation(B)
    Z = X.to_numpy()[rng.choice(bg_pool, size=N)]   # 사업장마다 다른 배경 사업장
    cur = Z.copy()
    f_prev = f(cur)
    base_f[m] = f_prev
    for b in order:
        cur[:, col_idx[names[b]]] = Xe[:, col_idx[names[b]]]
        f_new = f(cur)
        phi_all[m, :, b] = f_new - f_prev
        f_prev = f_new
    if (m + 1) % max(1, M // 5) == 0:
        log(f"  반복 {m + 1}/{M}")
phi = phi_all.mean(axis=0)                          # N × B
se = phi_all.std(axis=0, ddof=1) / np.sqrt(M)
add_err = np.abs(phi.sum(axis=1) - (fx - base_f.mean(axis=0))).max()
print(f"[검증] 가법성 max|Σφ − (f(x) − mean_z f(z))| = {add_err:.2e}   블록 φ의 평균 표준오차 = {se.mean():.4f}")

# ------------------------------------------------------------------ Cox 정확 SHAP과 비교 (같은 사업장·같은 기준)
phi_cox = P.to_numpy()[rows]                       # 같은 사업장의 Cox 정확 SHAP(블록별)

cmp_rows = []
for j, b in enumerate(names):
    cmp_rows.append({"블록": b, "mean|φ|_RSF": np.abs(phi[:, j]).mean(), "mean|φ|_Cox": np.abs(phi_cox[:, j]).mean(),
                     "상관(사업장)": np.corrcoef(phi[:, j], phi_cox[:, j])[0, 1] if phi[:, j].std() > 0 and phi_cox[:, j].std() > 0 else np.nan})
gm_r = pd.DataFrame(phi, columns=names).groupby(gid_e).mean()
gm_c = pd.DataFrame(phi_cox, columns=names).groupby(gid_e).mean()
for r in cmp_rows:
    b = r["블록"]
    r["상관(그룹평균)"] = np.corrcoef(gm_r[b], gm_c[b])[0, 1] if gm_r[b].std() > 0 and gm_c[b].std() > 0 else np.nan
cmp = pd.DataFrame(cmp_rows).sort_values("mean|φ|_RSF", ascending=False)
cmp["순위_RSF"] = cmp["mean|φ|_RSF"].rank(ascending=False).astype(int)
cmp["순위_Cox"] = cmp["mean|φ|_Cox"].rank(ascending=False).astype(int)
cmp.round(4).to_csv(OUT + "shap_rsf_vs_cox.csv", index=False, encoding="utf-8-sig")
print("\n=== 블록별 평균 |φ| 와 Cox 정확 SHAP과의 일치도 (같은 사업장 %d개) ===" % N)
print(cmp.round(3).to_string(index=False))
tot_r, tot_c = phi.sum(axis=1), phi_cox.sum(axis=1)
print(f"\n사업장 총 기여(Σφ) RSF vs Cox 상관 = {np.corrcoef(tot_r, tot_c)[0, 1]:.3f}")

grp = pd.concat([gm_r.add_prefix("RSF_"), gm_c.add_prefix("Cox_")], axis=1).reset_index().rename(columns={"index": "group_id"})
grp = sel[["group_id", "시도", "시군구", "bc_업종", "사업장수", "관찰_폐업률_%"]].merge(grp, on="group_id")
grp.round(4).to_csv(OUT + "shap_rsf_group_blocks.csv", index=False, encoding="utf-8-sig")
log("완료")
