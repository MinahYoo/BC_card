"""
rsf_eval.py — Random Survival Forest(scikit-survival) 구현·튜닝·평가.  cox_rsf.py의 주 설계(단순 코호트)와 같은 모집단을 쓴다.

[먼저 밝히는 데이터 특성: 경쟁위험 / 시간가변 공변량]  (체크 1-6)
  * 경쟁위험: 사건은 '폐업' 하나다. 휴업·취소/말소는 종결 상태가 아니라 censored로 두었고(CHANGELOG ⑨), 양도양수·업종변경 같은
    다른 종결 사건은 LOCALDATA에 없어 관측할 수 없다. 따라서 sksurv RSF(단일 사건)로 충분하다. 다만 '폐업 외 사유로 사라진 사업장'이
    censored로 섞여 있을 가능성은 한계로 남는다(관측 불가).
  * 시간가변 공변량: 사업장 변수(영업연수·프랜차이즈·크기 등)와 g_closure_rate_1y(시작 시점 이전 정보)는 시작 시점 고정값이다.
    BC카드 성별·연령 구성비는 원래 월별 값이지만 2026-01~06 전체를 한 번에 집계한 '정적 그룹 변수'로 썼다(= 추적 기간 중 값을 baseline에
    붙인 것이라 미래정보/역인과 가능성이 남는다 — 결과 해석의 한계). sksurv RSF는 시간가변 공변량을 못 다루므로 월별을 그대로 쓰는 대신
    이렇게 정적으로 요약했고, 진짜 시간가변 모형이 필요하면 (사업장×월) 계수과정 형태의 Cox(lifelines CoxTimeVaryingFitter)가 필요하다.
  * 시간 원점은 2026-01-01(모두 같은 날 시작)이라 left truncation은 필요 없다. 영업연수는 공변량(log_age)으로 넣는다.

실행: python3 -u rsf_eval.py                      (본 실행)
      python3 -u rsf_eval.py --quick              (동작 확인용 소규모)
"""
import argparse
import json
import math
import time
import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.font_manager
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from lifelines.utils import concordance_index as fast_cindex          # 부트스트랩용 O(n log n) Harrell C
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.model_selection import RandomizedSearchCV, StratifiedGroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from sksurv.ensemble import RandomSurvivalForest
from sksurv.metrics import (brier_score, concordance_index_censored, concordance_index_ipcw,
                            cumulative_dynamic_auc, integrated_brier_score)
from sksurv.nonparametric import kaplan_meier_estimator
from sksurv.util import Surv

ap = argparse.ArgumentParser()
ap.add_argument("--end", default="2026-06-30", help="추적 종료일(민감도: 2026-09-16)")
ap.add_argument("--trees", type=int, default=500, help="최종 모형 트리 수(체크 2: 500 이상)")
ap.add_argument("--tune-trees", type=int, default=500, help="튜닝 fit의 트리 수")
ap.add_argument("--tune-n", type=int, default=40_000, help="튜닝에 쓰는 train 부분표본 행 수")
ap.add_argument("--fit-n", type=int, default=150_000, help="최종 모형 학습 행 수(train에서 무작위 추출, 0이면 전부)")
ap.add_argument("--n-iter", type=int, default=12, help="RandomizedSearchCV 후보 조합 수")
ap.add_argument("--cv", type=int, default=3)
ap.add_argument("--n-repeats", type=int, default=10, help="permutation importance 반복 수")
ap.add_argument("--imp-n", type=int, default=20_000, help="permutation importance에 쓰는 test 부분표본 행 수")
ap.add_argument("--n-boot", type=int, default=100, help="test C-index 그룹 부트스트랩 횟수")
ap.add_argument("--seed", type=int, default=42)
ap.add_argument("--quick", action="store_true")
ap.add_argument("--tag", default="")
args = ap.parse_args()
if args.quick:
    args.trees, args.tune_trees, args.tune_n, args.fit_n = 50, 20, 8_000, 20_000
    args.n_iter, args.cv, args.n_repeats, args.imp_n, args.n_boot = 3, 2, 2, 5_000, 10

SEED = args.seed
DATA_DIR, OUT_DIR = Path("data"), Path("output")
OUT_DIR.mkdir(exist_ok=True)
TAG = ("_quick" if args.quick else "") + args.tag
BIZ_LIST = ["한식계열", "일식회집", "중국음식", "서양음식", "스넥", "제과점", "편의점"]
JOIN_KEY = ["SIDO_NM", "CCG_NM", "bc_업종"]
LM, END = pd.Timestamp("2026-01-01"), pd.Timestamp(args.end)
HORIZON = (END - LM).days                       # 추적 일수(6/30이면 180)
BC_MONTHS = [202601, 202602, 202603, 202604, 202605, 202606]
T0 = time.time()
warnings.filterwarnings("ignore", category=FutureWarning)


def log(msg):
    print(f"[{(time.time() - T0) / 60:6.1f}분] {msg}", flush=True)


# =====================================================================================================
# 1. 데이터 준비
# =====================================================================================================
log("데이터 로드")
df = pd.read_csv(DATA_DIR / "final_joined.csv", encoding="utf-8-sig", parse_dates=["인허가일자", "폐업일자"], low_memory=False,
                 usecols=["관리번호", "인허가일자", "폐업일자", "bc_업종", "SIDO_NM", "CCG_NM", "is_franchise",
                          "dist_to_region_centroid_m", "is_multiuse", "log시설총규모_업종내z", "시설총규모_결측여부",
                          "좌표결측", "전화번호_기재"])
df = df[df["bc_업종"].isin(BIZ_LIST)].copy()

# [체크 1-4] 결측치·누수: 여기서는 '값이 정해진' 도메인 규칙만 적용하고(통계량을 학습하지 않는다), 통계량이 필요한 결측 대체(중앙값)는
# 아래 Pipeline의 SimpleImputer가 train에서만 fit한다.
#  - 크기(size_z)는 업종 내 z-score라 결측 = 업종 평균(0)이고 결측 표시(size_missing)를 함께 둔다(팀 규칙, CHANGELOG ⑩).
#  - 거리(log_dist_to_centroid), is_multiuse는 NaN 그대로 두어 Pipeline이 train 중앙값으로 채운다(좌표결측 표시는 별도 변수).
df["log_dist_to_centroid"] = np.log1p(df["dist_to_region_centroid_m"])
df["coord_missing"] = df["좌표결측"].astype(int)
df["size_z"] = df["log시설총규모_업종내z"].fillna(0)
df["size_missing"] = df["시설총규모_결측여부"].astype(int)
df["phone_recorded"] = df["전화번호_기재"].astype(int)

# BC카드: cox_rsf.py와 동일하게 제물포구(중구+동구 합성)를 만들고 2026-01~06 성별·연령 구성비를 그룹 단위로 집계한다.
bc = pd.read_csv(DATA_DIR / "bc_clean.csv", encoding="utf-8-sig", dtype={"GENDER_CD": str, "AGE_CD": str})
jemulpo = bc[(bc["SIDO_NM"] == "인천광역시") & (bc["CCG_NM"].isin(["중구", "동구"]))].copy()
jemulpo["CCG_NM"] = "제물포구"
bc = pd.concat([bc, jemulpo], ignore_index=True)
bc = bc[bc["bc_업종"].isin(BIZ_LIST) & bc["STRD_YYMM"].isin(BC_MONTHS)]
cov = pd.DataFrame(index=bc.groupby(JOIN_KEY).size().index)
for col, prefix in [("GENDER_CD", "amt_share_gender_"), ("AGE_CD", "amt_share_age_")]:
    amt = bc[bc[col] != "x"].groupby(JOIN_KEY + [col])["amt"].sum().unstack(col, fill_value=0)   # 마스킹('x') 행 제외
    cov = cov.join(amt.div(amt.sum(axis=1), axis=0).add_prefix(prefix))
cov = cov.reset_index()
GROUP_BC = ["amt_share_gender_1", "amt_share_gender_2",                                   # 준거범주: 성별 3(법인), 연령 1
            "amt_share_age_2", "amt_share_age_3", "amt_share_age_4", "amt_share_age_5", "amt_share_age_6"]

# 모집단: 2026-01-01에 영업 중인 사업장. 사건 = 폐업일자가 (1/1, END]. 그 외는 END에서 censored(행정적 종결).
d = df[(df["인허가일자"] <= LM) & (df["폐업일자"].isna() | (df["폐업일자"] > LM))].copy()
closed = d["폐업일자"].notna() & (d["폐업일자"] <= END)
d["event"] = closed.to_numpy()
d["time"] = np.where(closed, (d["폐업일자"] - LM).dt.days, HORIZON).astype(float)     # 단위: 일
d["log_age"] = np.log1p((LM - d["인허가일자"]).dt.days / 365.25)

y_ = pd.Timedelta(days=365)                                                            # g_closure_rate_1y: 1/1 이전 정보만 사용
alive = lambda t: (df["인허가일자"] <= t) & (df["폐업일자"].isna() | (df["폐업일자"] > t))
g = pd.concat([df[alive(LM - y_)].groupby(JOIN_KEY).size().rename("n_ago"),
               df[(df["폐업일자"] > LM - y_) & (df["폐업일자"] <= LM)].groupby(JOIN_KEY).size().rename("closed_1y")], axis=1).fillna(0)
g["g_closure_rate_1y"] = g["closed_1y"] / g["n_ago"].clip(lower=1)
n0 = len(d)
d = d.merge(cov, on=JOIN_KEY, how="left", validate="m:1").merge(g[["g_closure_rate_1y"]].reset_index(), on=JOIN_KEY,
                                                                how="left", validate="m:1")
d["g_closure_rate_1y"] = d["g_closure_rate_1y"].fillna(0)
assert len(d) == n0
d["group_id"] = d.groupby(JOIN_KEY).ngroup()                                           # 시군구×업종 그룹(분할·부트스트랩 단위)
d = d.reset_index(drop=True)

# [체크 1-1] 전체 n뿐 아니라 관측된 이벤트 수·검열 비율을 먼저 출력하고, 이벤트가 적으면 경고한다.
NUM = ["log_age", "is_franchise", "log_dist_to_centroid", "is_multiuse", "size_z", "size_missing", "coord_missing",
       "phone_recorded", "g_closure_rate_1y"] + GROUP_BC
CAT = ["bc_업종"]
FEATS = NUM + CAT
n_ev, n_all = int(d["event"].sum()), len(d)
print(f"\n=== 데이터 요약 ===\nn = {n_all:,}   관측된 이벤트(폐업) = {n_ev:,}   검열 비율 = {(1 - n_ev / n_all) * 100:.2f}%   "
      f"시간 단위 = 일(0~{HORIZON})   그룹(시군구×업종) = {d['group_id'].nunique():,}개   변수 = {len(NUM)}개 수치 + 업종 범주")
print("시간 변수: time / 이벤트 변수: event(bool) / 공변량: 사업장(영업연수·프랜차이즈·거리·다중이용·크기·좌표결측·전화) + 지역 최근폐업률 + BC 성별·연령 구성비 + 업종")
if args.end == "2026-06-30" and not args.quick:
    print(f"[검증] ⑯ 기준값 at-risk 635,567 / 폐업 25,330 → {'일치' if (n_all, n_ev) == (635_567, 25_330) else '불일치(원본·코드 확인 필요)'}")
EV_MIN = 10 * len(FEATS)
if n_ev < max(EV_MIN, 200):
    print(f"⚠ 이벤트 수 {n_ev}건이 적다(경고 기준 max(10×변수 {len(FEATS)}, 200) = {max(EV_MIN, 200)}). 리프·트리 안정성이 낮다.")
else:
    print(f"이벤트 수 충분(경고 기준 {max(EV_MIN, 200)}건, 변수당 {n_ev / len(FEATS):,.0f}건).")

# [체크 1-2] 타깃: Surv.from_arrays(event, time), event는 bool 확인.
assert d["event"].dtype == bool and set(d["event"].unique()) <= {True, False}
assert d["time"].min() > 0 and d["time"].max() <= HORIZON
y_all = Surv.from_arrays(event=d["event"].to_numpy(), time=d["time"].to_numpy())
assert y_all.dtype["event"] == np.bool_

# [체크 1-3] 분할: event로 stratify하되 같은 (시군구×업종) 그룹은 통째로 한쪽에만 둔다(StratifiedGroupKFold).
# 같은 그룹 사업장은 BC·지역 변수를 공유하므로 행 단위 stratified split은 그룹 정보가 새 (평가가 낙관적) — 프로젝트 원칙(그룹 분할)을 지키면서
# event 비율 stratify를 함께 만족시키는 방법이다. 외부 5-fold 중 하나를 test(20%)로 쓴다.
sgkf = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=SEED)
tr_idx, te_idx = next(sgkf.split(d, d["event"], d["group_id"]))
train, test = d.iloc[tr_idx].reset_index(drop=True), d.iloc[te_idx].reset_index(drop=True)
assert not (set(train["group_id"]) & set(test["group_id"])), "그룹이 train/test에 걸쳐 있다(누수)"
assert not (set(train["관리번호"]) & set(test["관리번호"]))
y_tr = Surv.from_arrays(train["event"].to_numpy(), train["time"].to_numpy())
y_te = Surv.from_arrays(test["event"].to_numpy(), test["time"].to_numpy())
print(f"\ntrain {len(train):,}행 (이벤트 {int(train['event'].sum()):,}, {train['event'].mean() * 100:.2f}%, 그룹 {train['group_id'].nunique():,}) / "
      f"test {len(test):,}행 (이벤트 {int(test['event'].sum()):,}, {test['event'].mean() * 100:.2f}%, 그룹 {test['group_id'].nunique():,})")

# 학습·튜닝에 쓰는 부분표본: 전체 train(약 50만 행)은 500트리 RSF에 너무 커서 무작위 행 추출을 쓴다(그룹은 유지, 이벤트 비율은 그대로).
fit_df = train if args.fit_n in (0, len(train)) else train.sample(n=min(args.fit_n, len(train)), random_state=SEED)
tune_df = fit_df.sample(n=min(args.tune_n, len(fit_df)), random_state=SEED + 1)
y_fit = Surv.from_arrays(fit_df["event"].to_numpy(), fit_df["time"].to_numpy())
y_tune = Surv.from_arrays(tune_df["event"].to_numpy(), tune_df["time"].to_numpy())
EVENT_RATE = float(fit_df["event"].mean())
print(f"최종 학습 {len(fit_df):,}행(이벤트 {int(fit_df['event'].sum()):,}) / 튜닝 {len(tune_df):,}행(이벤트 {int(tune_df['event'].sum()):,})")

# [체크 1-4] 전처리는 Pipeline 안에서 train(폴드의 학습부분)에만 fit한다: 수치 = 중앙값 대체(+결측 표시), 범주 = one-hot.
# RSF는 변수 척도에 불변이라 표준화는 하지 않는다.
pre = ColumnTransformer([("num", SimpleImputer(strategy="median", add_indicator=True), NUM),
                         ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CAT)], remainder="drop")


def make_pipe(**rsf_kw):
    # [체크 2-1] n_estimators ≥ 500, oob_score=True(bootstrap 필요), random_state 고정, n_jobs=-1.
    kw = dict(n_estimators=args.trees, oob_score=True, bootstrap=True, random_state=SEED, n_jobs=-1)
    kw.update(rsf_kw)
    return Pipeline([("pre", pre), ("rsf", RandomSurvivalForest(**kw))])


# =====================================================================================================
# 2. 튜닝: RandomizedSearchCV + StratifiedGroupKFold, 기준 = C-index(RSF.score = Harrell C, 높을수록 좋음)
# =====================================================================================================
# [체크 2-2] min_samples_leaf는 '리프 안 기대 이벤트 수'로 정한다. 이벤트 비율이 약 4%이므로 리프당 이벤트 15/30/60건이 되도록
# 표본 수 = 목표 이벤트 / 이벤트 비율로 환산한다(분류/회귀 기본값 3은 리프에 이벤트가 0~1건이라 로그순위 분할이 불안정).
leaf_grid = sorted({int(math.ceil(k / EVENT_RATE)) for k in (15, 30, 60)})
# [체크 2-3] max_features, min_samples_split, max_depth도 튜닝 대상. min_samples_split이 2×leaf보다 작으면 leaf 제약이 우선한다.
param_dist = {"rsf__min_samples_leaf": leaf_grid,
              "rsf__min_samples_split": [2 * l for l in leaf_grid] + [4 * leaf_grid[-1]],
              "rsf__max_features": ["sqrt", 0.5, 1.0],
              "rsf__max_depth": [4, 6, 8, 12, None]}
print(f"\n=== 튜닝 === 리프 후보(이벤트 15/30/60건 기준) {leaf_grid}  event 비율 {EVENT_RATE * 100:.2f}%")
# [체크 1-3] CV fold도 event 기준 stratify + 그룹 유지. GridSearchCV는 구조화 y를 splitter에 넘기면 깨지므로 분할 목록을 직접 만들어 준다.
cv_splits = list(StratifiedGroupKFold(n_splits=args.cv, shuffle=True, random_state=SEED)
                 .split(tune_df, tune_df["event"], tune_df["group_id"]))
# [체크 2-4] 튜닝 기준은 정확도가 아니라 C-index(scoring=None → 추정기 기본 score). IBS는 최종 평가에서 함께 본다.
# 튜닝 fit은 oob_score=False(속도) — 최종 모형에는 oob_score=True를 켠다.
search = RandomizedSearchCV(make_pipe(n_estimators=args.tune_trees, oob_score=False), param_dist, n_iter=args.n_iter, cv=cv_splits,
                            scoring=None, n_jobs=1, refit=False, random_state=SEED, verbose=3, return_train_score=False)
search.fit(tune_df[FEATS], y_tune)
cvres = pd.DataFrame(search.cv_results_).sort_values("rank_test_score")
cvres.to_csv(OUT_DIR / f"rsf_eval_cv_results{TAG}.csv", index=False, encoding="utf-8-sig")
print(cvres[["rank_test_score", "mean_test_score", "std_test_score", "mean_fit_time"] + [c for c in cvres if c.startswith("param_")]]
      .head(8).round(4).to_string(index=False))
best = {k.replace("rsf__", ""): v for k, v in cvres.iloc[0]["params"].items()}     # refit=False라 순위 1위 행에서 직접 꺼낸다
print("최적 하이퍼파라미터:", best, f"(CV Harrell C {cvres.iloc[0]['mean_test_score']:.4f})")
best_json = {k: (None if v is None else (int(v) if isinstance(v, (np.integer,)) else v)) for k, v in best.items()}
json.dump(best_json, open(OUT_DIR / f"rsf_eval_best_params{TAG}.json", "w"), ensure_ascii=False, indent=1)

# =====================================================================================================
# 3. 최종 학습 + OOB
# =====================================================================================================
log(f"최종 모형 학습: 트리 {args.trees}개, {len(fit_df):,}행")
pipe = make_pipe(**best)
pipe.fit(fit_df[FEATS], y_fit)
rsf, prep = pipe.named_steps["rsf"], pipe[:-1]
# [체크 3-4] oob_score_는 오차가 아니라 OOB 예측의 Harrell C-index다(높을수록 좋음, 0.5 = 무작위). 행 단위 bootstrap의 OOB라
# 같은 그룹의 다른 사업장이 in-bag에 있어 그룹 hold-out인 test보다 낙관적일 수 있다.
print(f"OOB C-index (oob_score_, 높을수록 좋음) = {rsf.oob_score_:.4f}   [주의: 오차가 아니라 C-index이며 행 단위 OOB]")
X_te = test[FEATS]


def chunked(fn, X, size=20_000):
    return np.concatenate([fn(X.iloc[i:i + size]) for i in range(0, len(X), size)])


# =====================================================================================================
# 4. 평가 (test)
# =====================================================================================================
# [체크 5-1] predict()는 위험 점수(risk score)다. 값이 클수록 폐업이 빠르다는 순위 정보일 뿐 확률이 아니다(단위·범위 무의미).
log("test 위험 점수 예측")
risk_te = chunked(lambda x: rsf.predict(prep.transform(x)), X_te)

# [체크 3-1] Harrell C와 Uno C를 함께 보고한다.
# [체크 3-3] 시간 grid는 test의 관측 사건 시간 범위(5~95백분위) 안에서만 잡고, IPCW 계열은 train 시간 범위 밖으로 벗어나지 않게 한다.
#  * 이 데이터는 검열이 전부 추적 종료일(=HORIZON일)에 몰린 행정적 검열이라 censoring 분포 G(t)가 HORIZON에서 0이 된다.
#    따라서 IPCW 계열(Uno C, AUC(t), Brier)은 t < train 최대 시간인 구간에서만 정의된다 → 상한을 사건 시간 95백분위로 자른다.
ev_t = test.loc[test["event"], "time"]
lo, hi = np.percentile(ev_t, [5, 95])
t_grid = np.unique(np.linspace(lo, hi, 20).round())
t_auc = t_grid[::3]
TAU = float(t_grid.max())
# cumulative_dynamic_auc·brier_score·integrated_brier_score는 test의 모든 사건에 1/G(t)를 계산하는데, 마지막 날(HORIZON일)의 사건은
# G(HORIZON)=0이라 오류가 난다(6/30 폐업이 HORIZON일). 그래서 이 세 지표는 test를 CAP일에서 행정적으로 절단한 사본(CAP 이후 사건은 CAP에서
# censored)으로 계산한다. grid의 모든 t ≤ TAU < CAP이라 t 시점 지표는 절단의 영향을 받지 않는다. (Uno C는 tau 인자가 같은 역할을 한다.)
CAP = float(min(np.ceil(TAU) + 3, HORIZON - 1))
y_te_cap = Surv.from_arrays(event=y_te["event"] & (y_te["time"] <= CAP), time=np.minimum(y_te["time"], CAP))
assert t_grid.min() >= y_tr["time"].min() and t_grid.max() < y_tr["time"].max(), "grid가 train 시간 범위를 벗어남"
assert t_grid.min() >= y_te_cap["time"].min() and t_grid.max() < y_te_cap["time"].max(), "grid가 test 시간 범위를 벗어남"
print(f"\n평가 시점 grid(일): {t_grid.astype(int).tolist()}   Uno tau = {TAU:.0f}일, 절단 CAP = {CAP:.0f}일 (train 최대 시간 {y_tr['time'].max():.0f}일 미만)")

harrell = concordance_index_censored(y_te["event"], y_te["time"], risk_te)
uno = concordance_index_ipcw(y_tr, y_te, risk_te, tau=TAU)
auc_t, auc_mean = cumulative_dynamic_auc(y_tr, y_te_cap, risk_te, t_auc)


# [체크 5-2] 확률이 필요하면 predict_survival_function(생존확률 S(t))이나 predict_cumulative_hazard_function(누적위험 H(t))을 쓴다.
#  - S(t)  : 트리별 리프의 Kaplan-Meier 생존함수를 앙상블 평균한 값(확률, 0~1). Brier·calibration은 이것을 쓴다.
#  - H(t)  : 트리별 Nelson-Aalen 누적위험을 앙상블 평균한 값(확률 아님, 0 이상). S(t) ≠ exp(-H(t))이다(평균 순서가 다름).
#  - predict()의 위험 점수 = H(t)를 모든 사건 시점에서 합한 값(순위용).
def surv_at(x, times):
    Xt = prep.transform(x)
    idx = np.searchsorted(rsf.unique_times_, times, side="right") - 1     # 계단함수: t 이하 마지막 사건 시점의 값
    return rsf.predict_survival_function(Xt, return_array=True)[:, idx]


log("test 생존확률 예측")
S_te = chunked(lambda x: surv_at(x, t_grid), X_te)
S_te = S_te.reshape(len(X_te), -1)
# KM 기준선(공변량 없는 모형): 모든 사업장에 train KM 생존확률을 준다.
km_t, km_s = kaplan_meier_estimator(y_tr["event"], y_tr["time"])
S_km = np.tile(km_s[np.searchsorted(km_t, t_grid, side="right") - 1], (len(X_te), 1))
bs_t, bs = brier_score(y_tr, y_te_cap, S_te, t_grid)
_, bs_km = brier_score(y_tr, y_te_cap, S_km, t_grid)
ibs = integrated_brier_score(y_tr, y_te_cap, S_te, t_grid)
ibs_km = integrated_brier_score(y_tr, y_te_cap, S_km, t_grid)

# 업종 내 C(사건수 가중): 업종 더미가 순위의 대부분을 만들 수 있어 업종 안에서의 변별력을 따로 본다(lifelines의 빠른 구현 사용).
def within_biz_c(risk):
    per, w = [], []
    for b, gdf in test.assign(_r=risk).groupby("bc_업종"):
        if gdf["event"].sum() >= 20:
            per.append(fast_cindex(gdf["time"], -gdf["_r"], gdf["event"]))
            w.append(gdf["event"].sum())
    return float(np.average(per, weights=w))


# test C-index의 그룹 부트스트랩 CI(같은 그룹 사업장이 상관되어 행 단위 CI는 너무 좁다). lifelines Harrell 구현으로 계산.
log(f"그룹 부트스트랩 {args.n_boot}회")
rng = np.random.default_rng(SEED)
rows_by_g = test.groupby("group_id").indices
gids = np.array(list(rows_by_g))
boot = []
for _ in range(args.n_boot):
    ii = np.concatenate([rows_by_g[k] for k in rng.choice(gids, len(gids), replace=True)])
    boot.append(fast_cindex(test["time"].to_numpy()[ii], -risk_te[ii], test["event"].to_numpy()[ii]))
ci_lo, ci_hi = np.percentile(boot, [2.5, 97.5])

metrics = pd.DataFrame([
    ("OOB C-index (oob_score_, 행 단위·높을수록 좋음)", rsf.oob_score_, "train 내부"),
    ("Harrell C (concordance_index_censored)", harrell[0], f"test, 그룹 부트스트랩 95% CI [{ci_lo:.4f}, {ci_hi:.4f}]"),
    (f"Uno C (concordance_index_ipcw, tau={TAU:.0f}일)", uno[0], "test, IPCW"),
    ("업종 내 Harrell C (사건수 가중)", within_biz_c(risk_te), "test"),
    (f"평균 시간가변 AUC (cumulative_dynamic_auc, {int(t_auc.min())}~{int(t_auc.max())}일)", auc_mean, "test, IPCW"),
    (f"IBS (integrated_brier_score, {int(t_grid.min())}~{int(t_grid.max())}일) — 낮을수록 좋음", ibs, "test"),
    ("IBS — KM 기준선(공변량 없음)", ibs_km, "test"),
    ("IBS 개선율 = 1 − IBS/IBS_KM", 1 - ibs / ibs_km, "test, 0보다 커야 KM보다 낫다")], columns=["지표", "값", "비고"])
metrics["값"] = metrics["값"].round(4)
td = pd.DataFrame({"time_day": t_grid.astype(int), "brier_rsf": bs, "brier_km": bs_km, "brier_skill": 1 - bs / bs_km})
td = td.merge(pd.DataFrame({"time_day": t_auc.astype(int), "auc_t": auc_t}), on="time_day", how="left")
metrics.to_csv(OUT_DIR / f"rsf_eval_metrics{TAG}.csv", index=False, encoding="utf-8-sig")
td.round(4).to_csv(OUT_DIR / f"rsf_eval_time_dependent{TAG}.csv", index=False, encoding="utf-8-sig")
print("\n=== 성능 지표 (test, 그룹 hold-out) ===")
print(metrics.to_string(index=False))
print("\n시점별 Brier / AUC(t):")
print(td.round(4).to_string(index=False))

# S(t)와 exp(-H(t))가 다르다는 것을 표본으로 확인(체크 5-2 설명용)
smp = X_te.iloc[:3000]
Xs = prep.transform(smp)
i90 = np.searchsorted(rsf.unique_times_, 90, side="right") - 1
S90 = rsf.predict_survival_function(Xs, return_array=True)[:, i90]
H90 = rsf.predict_cumulative_hazard_function(Xs, return_array=True)[:, i90]
print(f"\n[확인] 90일 시점 평균 S(t)={S90.mean():.4f}  exp(-H(t))={np.exp(-H90).mean():.4f}  (개별 사업장 기준 최대 차이 {np.abs(S90 - np.exp(-H90)).max():.4f})  평균 H(t)={H90.mean():.4f}  "
      f"위험점수 평균={risk_te[:3000].mean():.2f}(H를 전 시점 합한 값이라 확률 아님)")

# =====================================================================================================
# 5. Calibration plot: 예측 사건확률(1−S(t)) 십분위 vs 실제 Kaplan-Meier
# =====================================================================================================
# [체크 3-6] 추적이 180일이라 1년·3년은 정의되지 않는다 → 90일과 마지막 grid 시점(≈171일)에서 본다.
for fam in ("AppleGothic", "Malgun Gothic", "NanumGothic"):
    if any(fam == f.name for f in matplotlib.font_manager.fontManager.ttflist):
        plt.rcParams["font.family"] = fam
        break
plt.rcParams["axes.unicode_minus"] = False
cal_times = [float(t_grid[np.argmin(np.abs(t_grid - 90))]), float(t_grid.max())]
fig, axes = plt.subplots(1, 3, figsize=(16, 5))
cal_rows = []
for ax, tt in zip(axes[:2], cal_times):
    j = int(np.where(t_grid == tt)[0][0])
    p = 1 - S_te[:, j]                                                     # 예측 t일 폐업확률
    dec = pd.qcut(pd.Series(p).rank(method="first"), 10, labels=False)
    xs, ys, lo_, hi_ = [], [], [], []
    for k in range(10):
        m = (dec == k).to_numpy()
        tk, sk, ci = kaplan_meier_estimator(y_te["event"][m], y_te["time"][m], conf_type="log-log")
        q = np.searchsorted(tk, tt, side="right") - 1
        xs.append(p[m].mean()); ys.append(1 - sk[q]); lo_.append(1 - ci[1][q]); hi_.append(1 - ci[0][q])
        cal_rows.append({"time_day": int(tt), "decile": k + 1, "rows": int(m.sum()), "mean_pred_cuminc": p[m].mean(),
                         "km_cuminc": 1 - sk[q], "km_lo": 1 - ci[1][q], "km_hi": 1 - ci[0][q]})
    xs, ys, lo_, hi_ = map(np.array, (xs, ys, lo_, hi_))
    ax.errorbar(xs, ys, yerr=[ys - lo_, hi_ - ys], fmt="o-", capsize=3, label="십분위(KM, 95% CI)")
    mx = max(xs.max(), hi_.max()) * 1.05
    ax.plot([0, mx], [0, mx], "k--", lw=1, label="완벽한 보정")
    ax.set(xlabel=f"예측 {int(tt)}일 폐업확률 1-S(t) (십분위 평균)", ylabel="실제 KM 폐업확률", title=f"{int(tt)}일 calibration")
    ax.legend()
mean_S = S_te.mean(axis=0)
tk, sk = kaplan_meier_estimator(y_te["event"], y_te["time"])
ax = axes[2]
ax.step(tk, sk, where="post", label="실제 KM (test)")
ax.plot(t_grid, mean_S, "o-", ms=3, label="예측 평균 S(t)")
ax.set(xlabel="일", ylabel="생존확률", title="전체 평균: 예측 vs KM", xlim=(0, HORIZON))
ax.legend()
fig.suptitle("RSF calibration (test, 그룹 hold-out) — 같은 그룹 사업장이 상관되어 CI는 낙관적", fontsize=11)
fig.tight_layout()
fig.savefig(OUT_DIR / f"rsf_eval_calibration{TAG}.png", dpi=130)
pd.DataFrame(cal_rows).round(5).to_csv(OUT_DIR / f"rsf_eval_calibration_deciles{TAG}.csv", index=False, encoding="utf-8-sig")
print("\ncalibration 십분위(90일·마지막 grid):")
print(pd.DataFrame(cal_rows).assign(mean_pred_cuminc=lambda x: (x.mean_pred_cuminc * 100).round(2),
                                    km_cuminc=lambda x: (x.km_cuminc * 100).round(2))[["time_day", "decile", "rows", "mean_pred_cuminc", "km_cuminc"]]
      .to_string(index=False))

# =====================================================================================================
# 6. 변수 중요도: permutation importance (test 부분표본, Harrell C 감소량)
# =====================================================================================================
# [체크 4-1] sksurv RSF에는 feature_importances_가 없어 sklearn.inspection.permutation_importance를 test 표본에 쓴다.
# 원본 열(범주형은 통째로) 단위로 섞으므로 one-hot 더미가 따로 놀지 않는다. 기본 scoring = Pipeline.score = Harrell C.
log(f"permutation importance (test {args.imp_n:,}행, {args.n_repeats}회 반복)")
imp_df = test.sample(n=min(args.imp_n, len(test)), random_state=SEED).reset_index(drop=True)
y_imp = Surv.from_arrays(imp_df["event"].to_numpy(), imp_df["time"].to_numpy())
pi = permutation_importance(pipe, imp_df[FEATS], y_imp, n_repeats=args.n_repeats, random_state=SEED, n_jobs=1)
imp = pd.DataFrame({"feature": FEATS, "importance_mean": pi.importances_mean, "importance_sd": pi.importances_std}) \
    .sort_values("importance_mean", ascending=False)
base_c = pipe.score(imp_df[FEATS], y_imp)

# [체크 4-2] 상관 높은 변수는 개별로 섞으면 중요도가 서로 나뉘거나(대체 변수가 정보를 보충) 현실에 없는 조합이 생겨 왜곡된다.
# BC 성별·연령 구성비(같은 그룹 내 합=1, 서로 강한 종속)와 그룹 단위 변수는 '블록 전체를 함께' 섞은 중요도를 추가로 낸다.
# 그룹 단위 변수는 그룹을 통째로 다른 그룹 값과 맞바꾼다(행별 섞기는 한 그룹 안에서 값이 흔들려 비현실적).
BLOCKS = {"BC 성별 비중(2)": ("group", ["amt_share_gender_1", "amt_share_gender_2"]),
          "BC 연령 비중(5)": ("group", GROUP_BC[2:]),
          "BC 전체(7)": ("group", GROUP_BC),
          "지역 최근폐업률": ("group", ["g_closure_rate_1y"]),
          "사업장 크기(size_z+결측표시)": ("row", ["size_z", "size_missing"]),
          "좌표(거리+좌표결측)": ("row", ["log_dist_to_centroid", "coord_missing"])}
gt = imp_df.drop_duplicates("group_id").set_index("group_id")
brng = np.random.default_rng(SEED)
blk_rows = []
for name, (kind, cols) in BLOCKS.items():
    drops = []
    for _ in range(args.n_repeats):
        x = imp_df[FEATS].copy()
        if kind == "row":
            x[cols] = imp_df[cols].to_numpy()[brng.permutation(len(imp_df))]
        else:
            swap = dict(zip(gt.index, brng.permutation(gt.index.to_numpy())))
            x[cols] = gt.loc[imp_df["group_id"].map(swap), cols].to_numpy()
        drops.append(base_c - pipe.score(x, y_imp))
    blk_rows.append({"feature": "[블록] " + name, "importance_mean": np.mean(drops), "importance_sd": np.std(drops, ddof=1)})
imp_all = pd.concat([imp, pd.DataFrame(blk_rows)], ignore_index=True)
imp_all.to_csv(OUT_DIR / f"rsf_eval_perm_importance{TAG}.csv", index=False, encoding="utf-8-sig")
print(f"\n=== permutation importance (기준 Harrell C {base_c:.4f}, 단위 = C-index 감소량, {args.n_repeats}회 평균) ===")
print(imp_all.assign(importance_mean=lambda x: x.importance_mean.round(4), importance_sd=lambda x: x.importance_sd.round(4)).to_string(index=False))
log("완료")
