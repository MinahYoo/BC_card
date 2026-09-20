# -*- coding: utf-8 -*-
"""
5단계: 2026년 영업 중인 사업장의 폐업 위험 예측 (Cox PH / Random Survival Forest).

설계(--design)
  cohort   (기본, 주 설계): 2026-01-01에 영업 중인 사업장 전체를 --end(기본 2026-06-30)까지 추적한다. 시간 분할 없이 그룹 단위 분할만 쓴다.
           BC카드는 추적 기간과 같은 2026-01~06 집계(룩백 없음)를 그룹 공변량으로 붙이고, 트렌드 변수는 성능 기여가 0이라 뺀다.
  landmark (강건성 확인): 아래 L1/L2 원안. 결정 근거는 CHANGELOG ⑪⑫.
  산출 파일 이름에 설계명이 붙는다(기존 landmark 결과를 덮어쓰지 않는다).

[이하 설명은 landmark 설계 기준 — 원안 그대로]
5단계(원안): 2026년 landmark 시점에 영업 중인 사업장의 '78일 단기 폐업 위험 순위' 예측.

질문 범위(주의): 개업 후 전체 생존시간을 설명하는 모형이 아니다. 각 landmark 시점까지 살아남은 사업장이
이후 78일 안에 폐업하는지의 위험 순위/확률을 얼마나 맞히는가를 본다.

분할
  - 그룹 분할(기본): (시도,시군구,업종) 그룹을 통째로 train/test. BC카드 공변량이 그룹 단위 값이라 필요.
    같은 시군구의 다른 업종은 train에 있을 수 있으므로 '처음 보는 지역'이 아니라 '처음 보는 지역x업종'이다.
  - 시군구 hold-out(엄격): 시군구 자체를 통째로 train/test. 지역 외삽은 이쪽을 본다.
시간 (동일 horizon 78일, 공변량 lookback 3개월)
  L1 = 2026-03-31 (BC카드 1~3월), 사건 관측 3/31 ~ 6/17  -> 학습
  L2 = 2026-06-30 (BC카드 4~6월), 사건 관측 6/30 ~ 9/16  -> 평가
  학습 라벨은 6/17에서 잘려(censoring) 평가 기간 정보가 섞이지 않는다.
  두 window는 계절이 다르므로 시간 일반화 결과에는 계절 효과가 섞여 있다(분리 불가).

누수 관련 결정
  - 소진공 경쟁밀도는 2026-06-30 스냅샷 하나라 L1(3/31 기준) 학습에 미래 정보가 들어간다.
    그래서 주모형에서는 경쟁밀도를 제외하고, 민감도 분석(S1, S2)으로만 넣는다.

모형 (업종 더미는 모든 모형에 공통 포함)
  M0 업종만 / M1 +영업연수 / M2 +프랜차이즈·입지 / M3 +BC카드 9개 변수
"""
import argparse
import warnings
import numpy as np
import pandas as pd
from pathlib import Path
from joblib import Parallel, delayed
from lifelines import CoxPHFitter
from lifelines.statistics import proportional_hazard_test
from lifelines.utils import concordance_index
from scipy.stats import norm, chi2
# RandomSurvivalForest는 --skip-rsf가 아닐 때만 아래에서 import한다(scikit-survival 없이도 Cox 부분을 돌릴 수 있게).
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split

warnings.filterwarnings("ignore")

ap = argparse.ArgumentParser()
ap.add_argument("--biz", nargs="*", help="특정 bc_업종만 실행(안전판용, 예: --biz 편의점)")
ap.add_argument("--rsf-n", type=int, default=100_000)
ap.add_argument("--rsf-trees", type=int, default=100)
ap.add_argument("--n-boot", type=int, default=500, help="Cox 계수 시군구 cluster bootstrap 횟수")
ap.add_argument("--n-diff-boot", type=int, default=300, help="C-index 차이 paired bootstrap 횟수")
ap.add_argument("--n-repeat", type=int, default=10, help="반복 분할 횟수")
ap.add_argument("--n-perm", type=int, default=10, help="RSF permutation 반복 횟수")
ap.add_argument("--n-jobs", type=int, default=4)
ap.add_argument("--skip-rsf", action="store_true")
ap.add_argument("--tag", default="", help="출력 파일명 뒤에 붙일 접미사(기존 결과를 덮어쓰지 않으려고 사용)")
ap.add_argument("--design", choices=["cohort", "landmark"], default="cohort",
                help="cohort: 1/1 단순 코호트(주 설계) / landmark: L1·L2 원안(강건성 확인)")
ap.add_argument("--end", default="2026-06-30", help="cohort 설계의 추적 종료일(민감도: 2026-09-16)")
args = ap.parse_args()

DATA_DIR = Path("data")
OUT_DIR = Path("output")
TAG = ("_" + "_".join(args.biz) if args.biz else "") + f"_{args.design}" + args.tag   # 팀원의 기존 산출물을 덮어쓰지 않도록 설계명을 접미사로 붙인다
RANDOM_STATE = 42
MAIN_BIZ = ["한식계열", "일식회집", "중국음식", "서양음식", "스넥", "제과점", "편의점"]
BIZ_LIST = args.biz or MAIN_BIZ
JOIN_KEY = ["SIDO_NM", "CCG_NM", "bc_업종"]
REGION_KEY = ["SIDO_NM", "CCG_NM"]

# LOCALDATA 폐업일자는 2026-09-16까지만 실제로 쌓여 있음(이후 4건).
DATA_END = pd.Timestamp("2026-09-16")
if args.design == "cohort":
    # 단일 코호트: 2026-01-01에 영업 중인 사업장을 --end까지 추적한다. BC는 추적 기간과 겹치는 2026-01~06 전체 집계(룩백 없음).
    LANDMARKS = {"C": dict(landmark=pd.Timestamp("2026-01-01"), months=[202601, 202602, 202603, 202604, 202605, 202606],
                           end=pd.Timestamp(args.end))}
    assert LANDMARKS["C"]["end"] <= DATA_END, "LOCALDATA 폐업기록이 있는 2026-09-16까지만 추적할 수 있다"
else:
    # landmark(팀원 원안): 두 시점 모두 관측창 78일. L2 종료 = 6/30 + 78일 = 9/16
    LANDMARKS = {
        "L1": dict(landmark=pd.Timestamp("2026-03-31"), months=[202601, 202602, 202603]),
        "L2": dict(landmark=pd.Timestamp("2026-06-30"), months=[202604, 202605, 202606]),
    }
    for cfg in LANDMARKS.values():
        cfg["end"] = cfg["landmark"] + pd.Timedelta(days=78)
    assert LANDMARKS["L2"]["end"] == DATA_END
for cfg in LANDMARKS.values():
    cfg["horizon"] = (cfg["end"] - cfg["landmark"]).days
HORIZON_DAYS = next(iter(LANDMARKS.values()))["horizon"]
assert all(c["horizon"] == HORIZON_DAYS for c in LANDMARKS.values())
H_YEARS = HORIZON_DAYS / 365.25
TEST_KEY = "test_group" if args.design == "cohort" else "test_both"   # 학습에 없는 그룹의 평가 세트
LAST_TAG = list(LANDMARKS)[-1]

# ============================================
# 1. 로드 + 사건 정의 검증
# ============================================
print("=== 로드 ===")
USECOLS = ["관리번호", "인허가일자", "폐업일자", "bc_업종", "SIDO_NM", "CCG_NM",
           "is_franchise", "dist_to_region_centroid_m",
           "is_multiuse", "log시설총규모_업종내z", "시설총규모_결측여부", "좌표결측", "전화번호_기재"]
df = pd.read_csv(DATA_DIR / "final_joined.csv", encoding="utf-8-sig", usecols=USECOLS,
                  parse_dates=["인허가일자", "폐업일자"], low_memory=False)
df = df[df["bc_업종"].isin(BIZ_LIST)].copy()

n_df = len(df)
SPATIAL_PATH = OUT_DIR / "5b_spatial_competitor.csv"
if SPATIAL_PATH.exists():
    spatial = pd.read_csv(SPATIAL_PATH, encoding="utf-8-sig")
    df = df.merge(spatial, on="관리번호", how="left", validate="1:1")
else:
    print("⚠ 5b_spatial_competitor.csv 없음 -> 경쟁밀도 민감도(S1, S2) 생략")
    df["spatial_competitor_500m"] = np.nan
assert len(df) == n_df
HAS_SPATIAL = bool(df["spatial_competitor_500m"].notna().any())
df["log_spatial_competitor"] = np.log1p(df["spatial_competitor_500m"])   # 자기 점포가 포함됐을 수 있음(민감도 분석에서만 사용)
df["log_dist_to_centroid"] = np.log1p(df["dist_to_region_centroid_m"])

# 좌표가 없는 사업장(약 3%)은 같은 나이·업종 대비 폐업률이 낮다(O/E 0.77, CHANGELOG ⑩). 통째로 제외하면 이 집단이 사라지므로
# 거리·경쟁밀도는 중앙값으로 채우고 좌표결측 표시를 모형에 넣는다.
df["coord_missing"] = df["좌표결측"].astype(int)
for _c in ["log_dist_to_centroid", "log_spatial_competitor"]:
    df[_c] = df[_c].fillna(df[_c].median())
# 사업장 확장 후보. 결측/무효 시설총규모는 업종 평균(0)으로 두고 결측 표시를 함께 넣는다.
df["is_multiuse"] = df["is_multiuse"].fillna(0)
df["size_z"] = df["log시설총규모_업종내z"].fillna(0)
df["size_missing"] = df["시설총규모_결측여부"].astype(int)
df["phone_recorded"] = df["전화번호_기재"].astype(int)

bc = pd.read_csv(DATA_DIR / "bc_clean.csv", encoding="utf-8-sig", dtype={"GENDER_CD": str, "AGE_CD": str})
# join_datasets.py와 동일: 제물포구는 (구)중구+(구)동구 합성
jemulpo = bc[(bc["SIDO_NM"] == "인천광역시") & (bc["CCG_NM"].isin(["중구", "동구"]))].copy()
jemulpo["CCG_NM"] = "제물포구"
bc = pd.concat([bc, jemulpo], ignore_index=True)
bc = bc[bc["bc_업종"].isin(BIZ_LIST)]


# ============================================
# 2. landmark별 BC카드 그룹 공변량 (원자료 구성비, 최근 3개월)
# ============================================
def bc_window_covariates(months):
    w = bc[bc["STRD_YYMM"].isin(months)]
    cov = w.groupby(JOIN_KEY).agg(bc_amt_total=("amt", "sum"), bc_cnt_total=("cnt", "sum"))
    # 성별/연령의 소규모셀 마스킹('x')은 항상 같은 행에서 함께 나타난다(13,161행 모두 성별x=연령x). 그 행을 제외하고 구성비를 만들고, x 금액 비중은 별도 변수로 남긴다.
    for col, prefix, short in [("GENDER_CD", "amt_share_gender_", "gender"), ("AGE_CD", "amt_share_age_", "age")]:
        d = w[w[col] != "x"]
        amt = d.groupby(JOIN_KEY + [col])["amt"].sum().unstack(col, fill_value=0)
        share = amt.div(amt.sum(axis=1), axis=0)
        cov = cov.join(share.add_prefix(prefix))
        cov[f"{short}_n"] = d.groupby(JOIN_KEY)["cnt"].sum().reindex(cov.index)     # 표본 크기(EB 민감도용)
        cov[f"{short}_x_share"] = (w[w[col] == "x"].groupby(JOIN_KEY)["amt"].sum().reindex(cov.index).fillna(0)
                                    / cov["bc_amt_total"])

    monthly = w.groupby(JOIN_KEY + ["STRD_YYMM"])["amt"].sum().reset_index()

    def trend(g):
        y = g.sort_values("STRD_YYMM")["amt"].to_numpy(dtype=float)
        if len(y) < 2 or y.mean() == 0:
            return pd.Series({"bc_amt_trend_slope": 0.0, "bc_amt_cv": 0.0})
        return pd.Series({"bc_amt_trend_slope": np.polyfit(np.arange(len(y)), y, 1)[0] / y.mean(), "bc_amt_cv": y.std() / y.mean()})

    return cov.join(monthly.groupby(JOIN_KEY).apply(trend, include_groups=False)).reset_index()


# ============================================
# 3. landmark별 at-risk 모집단 + 라벨
# ============================================
GROUP_COV = {}


def group_history(lm):
    """시군구x업종 그룹의 lm 이전 1년 폐업률 = 직전 1년 폐업 수 / 1년 전 영업 중 점포 수. lm 이전 정보만 쓴다."""
    y = pd.Timedelta(days=365)

    def alive(t):
        return (df["인허가일자"] <= t) & (df["폐업일자"].isna() | (df["폐업일자"] > t))

    n_ago = df[alive(lm - y)].groupby(JOIN_KEY).size().rename("n_ago")
    closed = df[(df["폐업일자"] > lm - y) & (df["폐업일자"] <= lm)].groupby(JOIN_KEY).size().rename("closed_1y")
    g = pd.concat([n_ago, closed], axis=1).fillna(0)
    g["g_closure_rate_1y"] = g["closed_1y"] / g["n_ago"].clip(lower=1)
    return g[["g_closure_rate_1y"]].reset_index()


def build_landmark(tag, cfg):
    lm, end, hz = cfg["landmark"], cfg["end"], cfg["horizon"]
    d = df[(df["인허가일자"] <= lm) & (df["폐업일자"].isna() | (df["폐업일자"] > lm))].copy()
    closed = d["폐업일자"].notna() & (d["폐업일자"] <= end)
    d["event"] = closed.astype(int)
    d["duration"] = np.where(closed, (d["폐업일자"] - lm).dt.days, hz) / 365.25
    d["log_age"] = np.log1p((lm - d["인허가일자"]).dt.days / 365.25)   # log(1+영업연수(년))
    cov = bc_window_covariates(cfg["months"])
    assert not cov.duplicated(JOIN_KEY).any()
    GROUP_COV[tag] = cov.assign(landmark=tag)
    n0 = len(d)
    d = d.merge(cov, on=JOIN_KEY, how="left", validate="m:1")
    d = d.merge(group_history(lm), on=JOIN_KEY, how="left", validate="m:1")
    d["g_closure_rate_1y"] = d["g_closure_rate_1y"].fillna(0)   # 1년 전 점포도 폐업도 없는 그룹
    assert len(d) == n0, "그룹 공변량 조인으로 행이 증식됨"
    d["landmark"] = tag
    print(f"[{tag}] 시작 {lm.date()} at-risk {len(d):,}행 / 관측창 {hz}일({lm.date()}~{end.date()}) "
          f"/ 폐업 {int(d['event'].sum()):,}건 ({d['event'].mean()*100:.2f}%)")
    return d


print("\n=== landmark 모집단 구성 ===")
full = pd.concat([build_landmark(t, c) for t, c in LANDMARKS.items()], ignore_index=True)
for b in BIZ_LIST[1:]:
    full[f"biz_{b}"] = (full["bc_업종"] == b).astype(int)
BIZ_DUMMY = [f"biz_{b}" for b in BIZ_LIST[1:]]

COV_SHARE = ["amt_share_gender_1", "amt_share_gender_2",           # 성별 준거범주: 3(법인)
             "amt_share_age_2", "amt_share_age_3", "amt_share_age_4", "amt_share_age_5", "amt_share_age_6"]  # 연령 준거범주: 1
COV_TREND = ["bc_amt_trend_slope", "bc_amt_cv"] if args.design == "landmark" else []   # 주 설계(cohort)에서는 성능 기여가 0이라 제외(CHANGELOG ⑪)
COV_GROUP = COV_SHARE + COV_TREND
STORE_CORE = ["log_age", "is_franchise", "log_dist_to_centroid"]
STORE_EXT = ["is_multiuse", "size_z", "size_missing", "coord_missing", "phone_recorded"]   # EDA 후보(CHANGELOG ⑩)
COV_HIST = ["g_closure_rate_1y"]   # 그룹의 직전 1년 폐업률(시작 시점 이전 정보만)

# 좌표 결측(좌표가 없으면 중심점 거리도 못 구함) 제외 전후 비교: complete-case 선택편향 확인
miss = full["dist_to_region_centroid_m"].isna()
cmp_tbl = full[full["landmark"] == LAST_TAG].assign(좌표결측=miss).groupby("좌표결측").agg(
    사업장수=("event", "size"), 폐업률_pct=("event", lambda s: s.mean() * 100), 평균_log_age=("log_age", "mean"),
    프랜차이즈_pct=("is_franchise", lambda s: s.mean() * 100)).round(3)
biz_mix = pd.crosstab(full[full["landmark"] == LAST_TAG]["bc_업종"], miss[full["landmark"] == LAST_TAG], normalize="columns").mul(100).round(1)
biz_mix.columns = [f"업종비중_pct_좌표{'결측' if c else '있음'}" for c in biz_mix.columns]
print(f"\n=== 좌표 결측 vs 비결측 ({LAST_TAG}) ===")
print(cmp_tbl.to_string())
print(biz_mix.to_string())
cmp_tbl.reset_index().to_csv(OUT_DIR / f"5_좌표결측비교{TAG}.csv", index=False, encoding="utf-8-sig")
biz_mix.reset_index().to_csv(OUT_DIR / f"5_좌표결측_업종비중{TAG}.csv", index=False, encoding="utf-8-sig")

n0 = len(full)
full = full.dropna(subset=COV_GROUP + STORE_CORE)
print(f"\n공변량 결측(BC 마스킹/BC 조인 실패) 제거: {n0:,} -> {len(full):,}행 (좌표 없는 사업장은 제거하지 않고 표시 변수로 처리)")
# 상수가 되는 열(예: 업종 하나만 돌릴 때 편의점의 크기 표준화값)은 Cox를 특이하게 만들므로 후보에서 뺀다
_pruned = [c for c in STORE_EXT + COV_HIST if full[c].nunique() <= 1]
if _pruned:
    print("상수 열 제외:", _pruned)
STORE_EXT = [c for c in STORE_EXT if c not in _pruned]
COV_HIST = [c for c in COV_HIST if c not in _pruned]

# 그룹/시군구 식별자
groups = full[JOIN_KEY].drop_duplicates().reset_index(drop=True)
groups["group_id"] = np.arange(len(groups))
regions = full[REGION_KEY].drop_duplicates().reset_index(drop=True)
regions["region_id"] = np.arange(len(regions))
full = full.merge(groups, on=JOIN_KEY, validate="m:1").merge(regions, on=REGION_KEY, validate="m:1")
print(f"그룹(시군구x업종) {len(groups):,}개, 시군구 {len(regions):,}개")


def make_split(level, seed):
    """level='group': 시군구x업종 그룹 단위, 'region': 시군구 통째로 hold-out."""
    if level == "group":
        units, col, strat = groups, "group_id", groups["bc_업종"]
    else:
        units, col, strat = regions, "region_id", None
    tr_u, te_u = train_test_split(units, test_size=0.2, random_state=seed, stratify=strat)
    return col, set(tr_u[col]), set(te_u[col])


def make_sets(col, tr_ids):
    is_tr = full[col].isin(tr_ids)
    if args.design == "cohort":   # 단일 코호트: 시간 분할 없이 그룹 분할만
        return {"train": full[is_tr], "test_group": full[~is_tr]}
    return {"train": full[is_tr & (full["landmark"] == "L1")],
            "valid_time": full[is_tr & (full["landmark"] == "L2")],
            "test_group": full[~is_tr & (full["landmark"] == "L1")],
            "test_both": full[~is_tr & (full["landmark"] == "L2")]}


# ============================================
# 4. 주분할: 그룹 단위 80:20 (+ 누수 방어 검증)
# ============================================
col, tr_ids, te_ids = make_split("group", RANDOM_STATE)
sets = make_sets(col, tr_ids)
train, test = sets["train"], sets[TEST_KEY]
assert not (tr_ids & te_ids)
for _k in ("test_group", "test_both"):   # valid_time은 학습과 같은 사업장의 다른 시점이라 겹치는 게 정상
    if _k in sets:
        assert not (set(train["관리번호"]) & set(sets[_k]["관리번호"]))
assert train["duration"].max() <= H_YEARS + 1e-9

split_summary = pd.DataFrame([
    {"set": k, "landmark": v["landmark"].iloc[0], "groups": v["group_id"].nunique(), "regions": v["region_id"].nunique(),
     "rows": len(v), "events": int(v["event"].sum()), "event_rate_pct": round(v["event"].mean() * 100, 2)}
    for k, v in sets.items()])
print("\n=== 분할 요약 (그룹 분할) ===")
print(split_summary.to_string(index=False))
split_summary.to_csv(OUT_DIR / f"5_split_요약{TAG}.csv", index=False, encoding="utf-8-sig")
te_regions = set(sets[TEST_KEY]["region_id"])
tr_regions = set(train["region_id"])
print(f"test 그룹이 속한 시군구 중 train에도 나오는 시군구: {len(te_regions & tr_regions)}/{len(te_regions)}"
      " (시군구 단위로는 겹침 -> 지역 외삽은 시군구 hold-out으로 따로 평가)")

# EB 부분 풀링은 주모형에서 제외하고 민감도(S3)로만 본다. prior(업종 평균, 그룹간 분산)는 train 그룹에서만 추정한다.
train_group_keys = pd.MultiIndex.from_frame(groups.loc[groups["group_id"].isin(tr_ids), JOIN_KEY])


def eb_table(cov):
    """구성비를 업종 평균 쪽으로 축소하는 근사 empirical Bayes(민감도용). 금액 가중 구성비에 이항분산을 쓰는 근사라 엄밀한 posterior가 아니다."""
    cov = cov.reset_index(drop=True)
    is_train = pd.MultiIndex.from_frame(cov[JOIN_KEY]).isin(train_group_keys)
    all_cols = [c for c in cov.columns if c.startswith(("amt_share_gender_", "amt_share_age_"))]
    res = pd.DataFrame(np.nan, index=cov.index, columns=["eb_" + c for c in all_cols])
    for prefix, ncol in [("amt_share_gender_", "gender_n"), ("amt_share_age_", "age_n")]:
        cols = [c for c in all_cols if c.startswith(prefix)]
        for b, idx in cov.groupby("bc_업종").groups.items():
            idx = np.asarray(idx)
            g = cov.loc[idx]
            tr = g[is_train[idx] & g[cols].notna().all(axis=1).to_numpy()]
            if len(tr) < 3:
                continue
            nn = tr[ncol].clip(lower=1).to_numpy()
            mu = (tr[cols].mul(nn, axis=0).sum() / nn.sum()).to_numpy()
            base = mu * (1 - mu)
            tau2 = np.clip(((tr[cols].to_numpy() - mu) ** 2).sum(axis=0) / (len(tr) - 1) - np.outer(1 / nn, base).mean(axis=0), 0, None)
            w = tau2 / (tau2 + np.outer(1 / g[ncol].clip(lower=1).to_numpy(), base))
            res.loc[idx, ["eb_" + c for c in cols]] = mu + w * (g[cols].to_numpy() - mu)
    return cov[JOIN_KEY + ["landmark"]].join(res)


eb_all = pd.concat([eb_table(c) for c in GROUP_COV.values()], ignore_index=True)
full = full.merge(eb_all, on=JOIN_KEY + ["landmark"], how="left", validate="m:1")
EB_COLS = ["eb_" + c for c in COV_SHARE]
for c in COV_SHARE:
    full["eb_" + c] = full["eb_" + c].fillna(full[c])   # prior를 못 만든 소수 그룹은 원자료 사용
sets = make_sets(col, tr_ids)
train, test = sets["train"], sets[TEST_KEY]

BASE, REF, TOP = "M2 +프랜차이즈·입지", "M2h +지역 최근폐업률", "M3 +BC카드"
MODELS = {"M0 업종만": [], "M1 +영업연수": ["log_age"], BASE: STORE_CORE,
          "M2x +사업장 확장변수": STORE_CORE + STORE_EXT,
          REF: STORE_CORE + STORE_EXT + COV_HIST,
          TOP: STORE_CORE + STORE_EXT + COV_HIST + COV_GROUP}
# BC카드 블록의 추가 기여는 REF(사업장 변수 + 지역 최근 폐업률을 모두 통제한 모형) 대비로 본다. BASE(M2) 대비는 참고용.
SNAP_NOTE = "추적 이후 스냅샷 누수" if args.design == "cohort" else "L1 미래정보 누수"
SENS = {}
if HAS_SPATIAL:
    SENS[f"S1 M2h+경쟁밀도({SNAP_NOTE})"] = MODELS[REF] + ["log_spatial_competitor"]
    SENS[f"S2 M3+경쟁밀도({SNAP_NOTE})"] = MODELS[TOP] + ["log_spatial_competitor"]
SENS["S3 M3 구성비 EB축소(prior=train그룹)"] = [c for c in MODELS[TOP] if c not in COV_SHARE] + EB_COLS
SENS["S4 M3 + 마스킹(x) 금액비중"] = MODELS[TOP] + ["age_x_share"]   # 성별x와 연령x는 항상 같은 행이라 값이 같아 하나만 사용
if COV_TREND:
    SENS["S5 M3 추세·CV 제외"] = [c for c in MODELS[TOP] if c not in COV_TREND]
ALL_MODELS = {**MODELS, **SENS}


# ============================================
# 5. 평가 도구
# ============================================
def cindex(d, risk):
    """전체 + 업종 내(사건수 가중) concordance. risk가 클수록 폐업 위험 큼."""
    if d["event"].sum() == 0:
        return np.nan, np.nan
    overall = concordance_index(d["duration"], -risk, d["event"])
    per, wts = [], []
    for b, g in d.assign(_r=risk).groupby("bc_업종"):
        if g["event"].sum() >= 20:
            per.append(concordance_index(g["duration"], -g["_r"], g["event"]))
            wts.append(g["event"].sum())
    return overall, (np.average(per, weights=wts) if per else np.nan)


def fit_cox(d, cols):
    X = cols + BIZ_DUMMY
    if not X:
        return None
    return CoxPHFitter().fit(d[X + ["duration", "event"]], duration_col="duration", event_col="event")


def cox_risk(cph, cols, d):
    if cph is None:
        return np.zeros(len(d))
    return cph.predict_log_partial_hazard(d[cols + BIZ_DUMMY]).to_numpy()


def cox_prob(cph, cols, d):
    """H일 안에 폐업할 확률 = 1 - S(H | x). 관측 종료가 모두 horizon과 같아 이항 결과가 완전 관측이다."""
    if cph is None:
        return None
    return 1 - cph.predict_survival_function(d[cols + BIZ_DUMMY], times=[H_YEARS]).iloc[0].to_numpy()


perf_rows, hz_rows = [], []
p0 = train["event"].mean()                                   # 무정보 기준 확률(학습 폐업률)


def horizon_metrics(model, d_name, d, p):
    y = d["event"].to_numpy()
    brier = np.mean((p - y) ** 2)
    brier0 = np.mean((p0 - y) ** 2)
    hz_rows.append({"model": model, "set": d_name, "mean_pred_pct": round(p.mean() * 100, 3), "obs_pct": round(y.mean() * 100, 3),
                    "brier": round(brier, 5), "brier_null": round(brier0, 5), "brier_skill": round(1 - brier / brier0, 4),
                    "auc_horizon": round(roc_auc_score(y, p), 4)})


print("\n=== Cox PH (주분할: 그룹) ===")
cox_fits = {}
for name, cols in ALL_MODELS.items():
    try:
        cph = fit_cox(train, cols)
    except Exception as e:
        if name in MODELS:
            raise
        print(f"[민감도 모형 적합 실패] {name}: {type(e).__name__} (공선성/상수 열 가능성) -> 건너뜀")
        cph = None
    cox_fits[name] = cph
    if cph is None:
        continue
    for sname, d in sets.items():
        ov, wb = cindex(d, cox_risk(cph, cols, d))
        perf_rows.append({"model": name, "set": sname, "c_index": round(ov, 4), "c_index_within_biz": round(wb, 4)})
    if name in (BASE, REF, TOP):
        for sname, d in sets.items():
            horizon_metrics(name, sname, d, cox_prob(cph, cols, d))
print(pd.DataFrame(perf_rows).pivot(index="model", columns="set", values="c_index")[list(sets)].to_string())
print("\n업종 내 C-index:")
print(pd.DataFrame(perf_rows).pivot(index="model", columns="set", values="c_index_within_biz")[list(sets)].to_string())

# ============================================
# 6. M3 vs M2: C-index 차이의 paired 시군구 cluster bootstrap
# ============================================
c2, c3 = MODELS[BASE], MODELS[TOP]
risk_by = {n: cox_risk(cox_fits[n], MODELS[n], test) for n in (BASE, REF, TOP)}
te_dur, te_ev = test["duration"].to_numpy(), test["event"].to_numpy()
te_rows_by_region = test.reset_index(drop=True).groupby("region_id").indices
te_region_ids = np.array(list(te_rows_by_region))


def _diff_boot(seed, dur, ev, r2, r3, rows_by_region, region_ids):
    rng = np.random.default_rng(seed)
    rows = np.concatenate([rows_by_region[g] for g in rng.choice(region_ids, size=len(region_ids), replace=True)])
    return concordance_index(dur[rows], -r3[rows], ev[rows]) - concordance_index(dur[rows], -r2[rows], ev[rows])


print(f"\n=== [{TEST_KEY}] BC카드 블록의 추가 기여(C-index 차이): 시군구 cluster bootstrap B={args.n_diff_boot} ===")
diff_rows = []
for ref_name in (REF, BASE):
    r_ref, r_top = risk_by[ref_name], risk_by[TOP]
    diffs = np.array(Parallel(n_jobs=args.n_jobs)(delayed(_diff_boot)(3000 + i, te_dur, te_ev, r_ref, r_top, te_rows_by_region, te_region_ids)
                                      for i in range(args.n_diff_boot)))
    d_pt = concordance_index(te_dur, -r_top, te_ev) - concordance_index(te_dur, -r_ref, te_ev)
    d_lo, d_hi = np.percentile(diffs, [2.5, 97.5])
    print(f"{TOP} - {ref_name}: 차이 {d_pt:+.4f}  95% CI [{d_lo:+.4f}, {d_hi:+.4f}]  (CI가 0을 포함하면 유의한 개선이라 할 수 없음)")
    diff_rows.append({"reference": ref_name, "top": TOP, "diff": d_pt, "ci_lo": d_lo, "ci_hi": d_hi, "B": args.n_diff_boot})
pd.DataFrame(diff_rows).to_csv(OUT_DIR / f"5_C-index차이_CI{TAG}.csv", index=False, encoding="utf-8-sig")

# ============================================
# 7. M3 계수: 시군구 cluster bootstrap(B=500) + BC 블록 joint 검정
# ============================================
cph3 = cox_fits[TOP]
X_cols = c3 + BIZ_DUMMY
tr_r = train.reset_index(drop=True)
Xm, dur_m, ev_m = tr_r[X_cols].to_numpy(dtype=float), tr_r["duration"].to_numpy(), tr_r["event"].to_numpy()
tr_rows_by_region = tr_r.groupby("region_id").indices
tr_region_ids = np.array(list(tr_rows_by_region))


def _boot_fit(seed, X, dur, ev, x_cols, rows_by_region, region_ids):
    rng = np.random.default_rng(seed)
    rows = np.concatenate([rows_by_region[g] for g in rng.choice(region_ids, size=len(region_ids), replace=True)])
    d_ = pd.DataFrame(X[rows], columns=x_cols)
    d_["duration"], d_["event"] = dur[rows], ev[rows]
    try:
        return CoxPHFitter().fit(d_, duration_col="duration", event_col="event").params_.reindex(x_cols).to_numpy()
    except Exception:
        return np.full(len(x_cols), np.nan)


print(f"\n=== Cox M3 계수: 시군구 cluster bootstrap B={args.n_boot} ===")
reps = np.array(Parallel(n_jobs=args.n_jobs)(delayed(_boot_fit)(2000 + i, Xm, dur_m, ev_m, X_cols, tr_rows_by_region, tr_region_ids)
                                 for i in range(args.n_boot)))
reps = reps[~np.isnan(reps).any(axis=1)]
coef = cph3.params_.reindex(X_cols)
se = pd.Series(reps.std(axis=0, ddof=1), index=X_cols)
lo, hi = np.percentile(reps, [2.5, 97.5], axis=0)
out = pd.DataFrame({"coef": coef, "boot_se": se, "coef_lo95": lo, "coef_hi95": hi})
out["HR"] = np.exp(out["coef"])
out["HR_lo95"], out["HR_hi95"] = np.exp(out["coef_lo95"]), np.exp(out["coef_hi95"])
out["z"] = out["coef"] / out["boot_se"]
out["p_normal_approx"] = 2 * (1 - norm.cdf(out["z"].abs()))
out["HR_per_10pp"] = np.where(out.index.isin(COV_SHARE), np.exp(out["coef"] * 0.1), np.nan)   # 구성비 10%p 변화당 HR
print(f"성공한 bootstrap 표본: {len(reps)}/{args.n_boot}")
print(out.round(4).to_string())
out.to_csv(OUT_DIR / f"5_CoxPH_계수{TAG}.csv", encoding="utf-8-sig")

# BC 블록 joint 검정 (구성비 변수끼리 상관이 커서 개별 p값만으로는 블록 전체 효과를 판단할 수 없다)
bc_idx = [X_cols.index(c) for c in COV_GROUP]
b_vec = coef.to_numpy()[bc_idx]
sigma = np.cov(reps[:, bc_idx], rowvar=False)
wald = float(b_vec @ np.linalg.pinv(sigma) @ b_vec)
df_bc = len(bc_idx)
#  BC 블록만 추가된 모형(REF=M2h)과 M3의 로그우도 차이(둘은 COV_GROUP만큼만 다르다)
lr = 2 * (cph3.log_likelihood_ - cox_fits[REF].log_likelihood_)
joint = pd.DataFrame([{"test": "Wald (시군구 cluster bootstrap 공분산)", "stat": wald, "df": df_bc, "p": chi2.sf(wald, df_bc)},
                      {"test": "LR (사업장 독립 가정, 참고용·반보수적)", "stat": lr, "df": df_bc, "p": chi2.sf(lr, df_bc)}])
print("\nBC카드 9개 변수 블록 joint 검정:")
print(joint.to_string(index=False))
joint.to_csv(OUT_DIR / f"5_BC블록_joint검정{TAG}.csv", index=False, encoding="utf-8-sig")

# ============================================
# 8. 비례위험(PH) 가정 검정 (Schoenfeld, 10만 행 표본 — 표본이 커서 작은 이탈도 유의하게 나올 수 있음)
# ============================================
print("\n=== PH 가정 검정 (M3, 표본 10만) ===")
try:
    sub = train.sample(n=min(100_000, len(train)), random_state=RANDOM_STATE)
    c_sub = CoxPHFitter().fit(sub[X_cols + ["duration", "event"]], duration_col="duration", event_col="event")
    ph = proportional_hazard_test(c_sub, sub[X_cols + ["duration", "event"]], time_transform="rank").summary
    print(ph.round(4).to_string())
    ph.to_csv(OUT_DIR / f"5_PH검정{TAG}.csv", encoding="utf-8-sig")
except Exception as e:
    print("PH 검정 실패:", repr(e))

# ============================================
# 9. 반복 분할 (그룹 분할 / 시군구 hold-out) — Cox 모형들의 평가 세트 C-index
# ============================================
print(f"\n=== 반복 분할 {args.n_repeat}회 x (그룹, 시군구 hold-out) ===")
rep_rows = []
for level in ["group", "region"]:
    for r in range(args.n_repeat):
        col_r, tr_r_ids, _ = make_split(level, 1000 + r)
        s = make_sets(col_r, tr_r_ids)
        tr_d, te_d = s["train"], s[TEST_KEY]
        row = {"split": level, "seed": 1000 + r, "test_events": int(te_d["event"].sum())}
        for name, cols in MODELS.items():
            cph = fit_cox(tr_d, cols)
            ov, wb = cindex(te_d, cox_risk(cph, cols, te_d))
            row[f"{name}|overall"], row[f"{name}|within_biz"] = ov, wb
        row["diff_M3-M2h"] = row[f"{TOP}|overall"] - row[f"{REF}|overall"]
        row["diff_M3-M2"] = row[f"{TOP}|overall"] - row[f"{BASE}|overall"]
        rep_rows.append(row)
    print(f"  {level} 완료")
rep = pd.DataFrame(rep_rows)
rep.to_csv(OUT_DIR / f"5_반복분할{TAG}.csv", index=False, encoding="utf-8-sig")
num = [c for c in rep.columns if "|" in c or c.startswith("diff")]
rep_sum = rep.groupby("split")[num].agg(["mean", "std"]).round(4)
print(rep_sum.T.to_string())
rep_sum.to_csv(OUT_DIR / f"5_반복분할_요약{TAG}.csv", encoding="utf-8-sig")

# ============================================
# 10. Random Survival Forest (M3 변수, 주분할) + 블록 permutation 중요도
# ============================================
if not args.skip_rsf:
    from sksurv.ensemble import RandomSurvivalForest
    print("\n=== Random Survival Forest ===")
    RSF_COLS = c3 + BIZ_DUMMY
    rsf_tr = train.sample(n=min(args.rsf_n, len(train)), random_state=RANDOM_STATE)
    y_tr = np.array(list(zip(rsf_tr["event"].astype(bool), rsf_tr["duration"])), dtype=[("event", bool), ("time", float)])
    print(f"RSF 학습표본: {len(rsf_tr):,}행 (폐업 {int(rsf_tr['event'].sum()):,}건), 트리 {args.rsf_trees}개")
    rsf = RandomSurvivalForest(n_estimators=args.rsf_trees, max_depth=8, min_samples_leaf=200,
                                n_jobs=args.n_jobs, random_state=RANDOM_STATE)
    rsf.fit(rsf_tr[RSF_COLS], y_tr)
    h_idx = np.searchsorted(rsf.unique_times_, H_YEARS, side="right") - 1

    def rsf_prob(d):
        out_ = []
        for i in range(0, len(d), 20_000):
            surv = rsf.predict_survival_function(d[RSF_COLS].iloc[i:i + 20_000], return_array=True)
            out_.append(1 - surv[:, h_idx])
        return np.concatenate(out_)

    for sname, d in sets.items():
        ov, wb = cindex(d, rsf.predict(d[RSF_COLS]))
        perf_rows.append({"model": "RSF (M3 변수)", "set": sname, "c_index": round(ov, 4), "c_index_within_biz": round(wb, 4)})
        horizon_metrics("RSF (M3 변수)", sname, d, rsf_prob(d))

    # 블록 permutation: 그룹 단위 변수는 그룹 통째로 다른 그룹 값과 맞바꾸고, 구성비/업종은 블록 전체를 함께 바꾼다.
    BLOCKS = {"영업연수": ("store", ["log_age"]), "프랜차이즈 여부": ("store", ["is_franchise"]),
              "중심지까지 거리": ("store", ["log_dist_to_centroid"]),
              "사업장 확장변수(다중이용·크기·좌표결측·전화)": ("store", STORE_EXT),
              "지역 최근 폐업률": ("group", COV_HIST),
              "BC 성별 비중(2개)": ("group", ["amt_share_gender_1", "amt_share_gender_2"]),
              "BC 연령 비중(5개)": ("group", ["amt_share_age_2", "amt_share_age_3", "amt_share_age_4", "amt_share_age_5", "amt_share_age_6"]),
              "BC 추세·변동성(2개)": ("group", COV_TREND),
              "업종 더미": ("group", BIZ_DUMMY)}
    te_s = test.sample(n=min(40_000, len(test)), random_state=RANDOM_STATE).reset_index(drop=True)
    base_ci = concordance_index(te_s["duration"], -rsf.predict(te_s[RSF_COLS]), te_s["event"])
    gtab = te_s.drop_duplicates("group_id").set_index("group_id")
    gids = gtab.index.to_numpy()
    rng = np.random.default_rng(RANDOM_STATE)
    imp_rows = []
    for bname, (kind, cols_) in BLOCKS.items():
        if not cols_:
            continue
        drops = []
        for _ in range(args.n_perm):
            x = te_s[RSF_COLS].copy()
            if kind == "store":
                x[cols_] = te_s[cols_].to_numpy()[rng.permutation(len(te_s))]
            else:
                swap = dict(zip(gids, rng.permutation(gids)))
                x[cols_] = gtab.loc[te_s["group_id"].map(swap), cols_].to_numpy()
            drops.append(base_ci - concordance_index(te_s["duration"], -rsf.predict(x), te_s["event"]))
        imp_rows.append({"block": bname, "kind": kind, "importance_mean": np.mean(drops), "importance_sd": np.std(drops, ddof=1),
                         "importance_min": np.min(drops), "importance_max": np.max(drops)})
    imp = pd.DataFrame(imp_rows).sort_values("importance_mean", ascending=False)
    print(f"\nRSF 블록 permutation 중요도 ({TEST_KEY} 표본 {len(te_s):,}행, 기준 C-index {base_ci:.4f}, {args.n_perm}회 반복):")
    print(imp.round(4).to_string(index=False))
    imp.to_csv(OUT_DIR / f"5_RSF_블록중요도{TAG}.csv", index=False, encoding="utf-8-sig")

# ============================================
# 11. 결과 저장/요약
# ============================================
perf = pd.DataFrame(perf_rows)
perf.to_csv(OUT_DIR / f"5_모델성능{TAG}.csv", index=False, encoding="utf-8-sig")
hz = pd.DataFrame(hz_rows)
hz.to_csv(OUT_DIR / f"5_고정기간_지표{TAG}.csv", index=False, encoding="utf-8-sig")

# 예측 확률(1 - S(H)) 기준 calibration: 예측 확률 십분위별 평균 예측 vs 실제 폐업률 (test_both)
cal_rows = []
cal_models = [("Cox M3 +BC카드", lambda d: cox_prob(cox_fits["M3 +BC카드"], c3, d))]
if not args.skip_rsf:
    cal_models.append(("RSF (M3 변수)", rsf_prob))
for mname, pfn in cal_models:
    p = pfn(test)
    t = pd.DataFrame({"p": p, "y": test["event"].to_numpy()})
    t["decile"] = pd.qcut(t["p"].rank(method="first"), 10, labels=range(1, 11))
    g = t.groupby("decile", observed=True).agg(rows=("y", "size"), mean_pred_pct=("p", lambda s: s.mean() * 100),
                                                obs_pct=("y", lambda s: s.mean() * 100)).round(3).reset_index()
    cal_rows.append(g.assign(model=mname))
cal = pd.concat(cal_rows)
cal.to_csv(OUT_DIR / f"5_calibration{TAG}.csv", index=False, encoding="utf-8-sig")

print("\n=== 최종 요약 ===")
print("전체 C-index (0.5=무작위):")
print(perf.pivot(index="model", columns="set", values="c_index")[list(sets)].to_string())
print("\n업종 내 C-index:")
print(perf.pivot(index="model", columns="set", values="c_index_within_biz")[list(sets)].to_string())
print(f"\n{HORIZON_DAYS}일 고정기간 지표 (Brier skill > 0이면 학습 폐업률 상수 예측보다 낫다):")
print(hz.to_string(index=False))
print(f"\n[{TEST_KEY}] 예측확률 십분위별 예측 vs 실제 폐업률(%):")
print(cal.to_string(index=False))
