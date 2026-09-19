# -*- coding: utf-8 -*-
"""
5단계: Cox PH / Random Survival Forest — 그룹(시군구x업종) 분할 + 시간(landmark) 분할.

왜 이렇게 나누나:
  같은 (SIDO_NM,CCG_NM,bc_업종) 안의 사업장은 BC카드/경쟁밀도 공변량이 완전히 동일하다.
  사업장 단위로 랜덤 분할하면 같은 그룹이 train/test에 갈라져 들어가 누수가 생기므로
  (1) 그룹 단위로 통째로 train/test 분할하고, (2) 시간도 분리한다.

시간 분할 (landmark 2개, 공변량 lookback 3개월 / 사건 관측창 각각 별도):
  L1 = 2026-03-31: 공변량 = BC카드 1~3월, 사건 = 4/1~6/30 폐업   -> train 그룹만 학습에 사용
  L2 = 2026-06-30: 공변량 = BC카드 4~6월, 사건 = 7/1~9/16 폐업   -> 평가(미학습 그룹, 미래 시점)
  학습 라벨은 6/30에서 censoring되므로 L2 이후 정보가 학습에 섞이지 않는다.

평가 세트 4종(같은 모델, 같은 지표):
  train       : 학습그룹 @L1
  valid_time  : 학습그룹 @L2   (본 그룹 + 미래)   -> 시간 일반화만 본 것
  test_group  : 미학습그룹 @L1 (못 본 그룹 + 같은 기간) -> 그룹 일반화만 본 것
  test_both   : 미학습그룹 @L2 (못 본 그룹 + 미래)   -> 가장 엄격한 평가(헤드라인)
"""
import argparse
import numpy as np
import pandas as pd
from pathlib import Path
from lifelines import CoxPHFitter
from lifelines.utils import concordance_index
from scipy.stats import norm
from sksurv.ensemble import RandomSurvivalForest
from sklearn.model_selection import train_test_split

ap = argparse.ArgumentParser()
ap.add_argument("--biz", nargs="*", help="특정 bc_업종만 실행(3단계 안전판용, 예: --biz 편의점)")
ap.add_argument("--rsf-n", type=int, default=100_000, help="RSF 학습 표본 행수")
ap.add_argument("--rsf-trees", type=int, default=100)
args = ap.parse_args()

DATA_DIR = Path("data")
OUT_DIR = Path("output")
TAG = "_" + "_".join(args.biz) if args.biz else ""
RANDOM_STATE = 42
MAIN_BIZ = ["한식계열", "일식회집", "중국음식", "서양음식", "스넥", "제과점", "편의점"]
BIZ_LIST = args.biz or MAIN_BIZ
JOIN_KEY = ["SIDO_NM", "CCG_NM", "bc_업종"]

# LOCALDATA 폐업일자는 2026-09-16까지만 실제로 쌓여 있음(이후는 4건뿐) -> 관측 종료를 09-16으로 잡는다.
LANDMARKS = {
    "L1": dict(landmark=pd.Timestamp("2026-03-31"), end=pd.Timestamp("2026-06-30"), months=[202601, 202602, 202603]),
    "L2": dict(landmark=pd.Timestamp("2026-06-30"), end=pd.Timestamp("2026-09-16"), months=[202604, 202605, 202606]),
}

# ============================================
# 1. 로드
# ============================================
print("=== 로드 ===")
USECOLS = ["관리번호", "인허가일자", "폐업일자", "bc_업종", "SIDO_NM", "CCG_NM",
           "is_franchise", "dist_to_region_centroid_m"]
df = pd.read_csv(DATA_DIR / "final_joined.csv", encoding="utf-8-sig", usecols=USECOLS,
                  parse_dates=["인허가일자", "폐업일자"], low_memory=False)
df = df[df["bc_업종"].isin(BIZ_LIST)].copy()

spatial = pd.read_csv(OUT_DIR / "5b_spatial_competitor.csv", encoding="utf-8-sig")
df = df.merge(spatial, on="관리번호", how="left")
df["log_spatial_competitor"] = np.log1p(df["spatial_competitor_500m"])
df["log_dist_to_centroid"] = np.log1p(df["dist_to_region_centroid_m"])

bc = pd.read_csv(DATA_DIR / "bc_clean.csv", encoding="utf-8-sig", dtype={"GENDER_CD": str, "AGE_CD": str})
# join_datasets.py와 동일: 제물포구는 (구)중구+(구)동구 합성
jemulpo = bc[(bc["SIDO_NM"] == "인천광역시") & (bc["CCG_NM"].isin(["중구", "동구"]))].copy()
jemulpo["CCG_NM"] = "제물포구"
bc = pd.concat([bc, jemulpo], ignore_index=True)
bc = bc[bc["bc_업종"].isin(BIZ_LIST)]


# ============================================
# 2. landmark별 BC카드 공변량 (+ 소규모 그룹 empirical Bayes 부분 풀링)
# ============================================
def eb_shrink(share, n, biz):
    """
    구성비(share: 그룹 x 카테고리)를 업종 평균쪽으로 축소(부분 풀링).
    표본 n(카드 결제건수)이 작은 그룹일수록 업종 평균 쪽으로 더 끌려간다.
    method of moments: tau2 = (그룹간 분산 - 평균 표본분산), w = tau2 / (tau2 + mu(1-mu)/n).
    금액 가중 구성비는 건수 기준 이항분산보다 흩어져 있어서 축소가 다소 약하게 걸리는 근사임.
    """
    out = share.copy()
    w_all = pd.DataFrame(index=share.index, columns=share.columns, dtype=float)
    for b in biz.unique():
        idx = biz.index[biz == b]
        s, nn = share.loc[idx], n.loc[idx].clip(lower=1)
        ok = s.notna().all(axis=1)
        s, nn = s[ok], nn[ok]
        if len(s) < 3:
            continue
        mu = s.mul(nn, axis=0).sum() / nn.sum()
        samp_var = pd.DataFrame(np.outer(1 / nn.values, (mu * (1 - mu)).values), index=s.index, columns=s.columns)
        tau2 = (((s - mu) ** 2).sum() / (len(s) - 1) - samp_var.mean()).clip(lower=0)
        w = tau2 / (tau2 + samp_var)
        shrunk = mu + w * (s - mu)
        shrunk = shrunk.div(shrunk.sum(axis=1), axis=0)
        out.loc[s.index] = shrunk
        w_all.loc[s.index] = w
    return out, w_all


def bc_window_covariates(months):
    w = bc[bc["STRD_YYMM"].isin(months)]
    key = w[JOIN_KEY].drop_duplicates().reset_index(drop=True)
    cov = key.set_index(JOIN_KEY)

    # 성별/연령은 소규모셀 마스킹('x')을 각자 따로 제외(join_datasets.py와 동일 방침)
    for col, prefix in [("GENDER_CD", "amt_share_gender_"), ("AGE_CD", "amt_share_age_")]:
        d = w[w[col] != "x"]
        amt = d.groupby(JOIN_KEY + [col])["amt"].sum().unstack(col, fill_value=0)
        share = amt.div(amt.sum(axis=1), axis=0)
        n = d.groupby(JOIN_KEY)["cnt"].sum().reindex(share.index)
        share_eb, weight = eb_shrink(share, n, share.index.get_level_values("bc_업종").to_series(index=share.index))
        cov = cov.join(share_eb.add_prefix(prefix))
        cov[prefix + "eb_w"] = weight.mean(axis=1)

    # 월별 추세/변동성 (lookback 3개월 기준)
    monthly = w.groupby(JOIN_KEY + ["STRD_YYMM"])["amt"].sum().reset_index()

    def trend(g):
        y = g.sort_values("STRD_YYMM")["amt"].to_numpy(dtype=float)
        if len(y) < 2 or y.mean() == 0:
            return pd.Series({"bc_amt_trend_slope": 0.0, "bc_amt_cv": 0.0})
        x = np.arange(len(y))
        return pd.Series({"bc_amt_trend_slope": np.polyfit(x, y, 1)[0] / y.mean(), "bc_amt_cv": y.std() / y.mean()})

    tr = monthly.groupby(JOIN_KEY).apply(trend, include_groups=False)
    return cov.join(tr).reset_index()


# ============================================
# 3. landmark별 at-risk 모집단 + 라벨
# ============================================
def build_landmark(tag, cfg):
    lm, end = cfg["landmark"], cfg["end"]
    d = df[(df["인허가일자"] <= lm) & (df["폐업일자"].isna() | (df["폐업일자"] > lm))].copy()
    closed = d["폐업일자"].notna() & (d["폐업일자"] <= end)
    d["event"] = closed.astype(int)
    d["duration"] = np.where(closed, (d["폐업일자"] - lm).dt.days, (end - lm).days) / 365.25
    d["log_age"] = np.log1p((lm - d["인허가일자"]).dt.days / 365.25)   # landmark 시점까지의 영업연수
    cov = bc_window_covariates(cfg["months"])
    d = d.merge(cov, on=JOIN_KEY, how="left")
    d["landmark"] = tag
    print(f"\n[{tag}] landmark {lm.date()} at-risk {len(d):,}행 / 관측창 {(end - lm).days}일 "
          f"/ 폐업 {int(d['event'].sum()):,}건 ({d['event'].mean()*100:.2f}%)")
    w_cols = [c for c in cov.columns if c.endswith("eb_w")]
    print(f"   EB 축소가중치(1=원자료 그대로, 0=업종평균): "
          + ", ".join(f"{c}: 중앙값 {cov[c].median():.2f}, 최소 {cov[c].min():.2f}" for c in w_cols))
    return d


print("\n=== landmark 모집단 구성 ===")
lm_df = {tag: build_landmark(tag, cfg) for tag, cfg in LANDMARKS.items()}

COV_GROUP = ["amt_share_gender_1", "amt_share_gender_2",
             "amt_share_age_2", "amt_share_age_3", "amt_share_age_4", "amt_share_age_5", "amt_share_age_6",
             "bc_amt_trend_slope", "bc_amt_cv"]
COV_STORE = ["log_age", "is_franchise", "log_dist_to_centroid", "log_spatial_competitor"]
BIZ_DUMMY = [f"biz_{b}" for b in BIZ_LIST[1:]]

full = pd.concat(lm_df.values(), ignore_index=True)
for b in BIZ_LIST[1:]:
    full[f"biz_{b}"] = (full["bc_업종"] == b).astype(int)
n0 = len(full)
full = full.dropna(subset=COV_GROUP + COV_STORE)
print(f"\n공변량 결측(BC 마스킹/좌표없음) 제거: {n0:,} -> {len(full):,}행")

# ============================================
# 4. 그룹 단위 분할 (업종 비율 유지) — 같은 그룹은 통째로 한쪽에만
# ============================================
groups = full[JOIN_KEY].drop_duplicates().reset_index(drop=True)
groups["group_id"] = np.arange(len(groups))
full = full.merge(groups, on=JOIN_KEY)
tr_g, te_g = train_test_split(groups, test_size=0.2, random_state=RANDOM_STATE, stratify=groups["bc_업종"])
tr_ids, te_ids = set(tr_g["group_id"]), set(te_g["group_id"])
full["is_train_group"] = full["group_id"].isin(tr_ids)

sets = {
    "train":      full[full["is_train_group"] & (full["landmark"] == "L1")],
    "valid_time": full[full["is_train_group"] & (full["landmark"] == "L2")],
    "test_group": full[~full["is_train_group"] & (full["landmark"] == "L1")],
    "test_both":  full[~full["is_train_group"] & (full["landmark"] == "L2")],
}
train = sets["train"]

# 누수 방어 검증
assert not (tr_ids & te_ids)
assert not (set(train["관리번호"]) & set(sets["test_both"]["관리번호"]))
assert not (set(train["관리번호"]) & set(sets["test_group"]["관리번호"]))
assert train["duration"].max() <= (LANDMARKS["L1"]["end"] - LANDMARKS["L1"]["landmark"]).days / 365.25 + 1e-9

split_summary = pd.DataFrame([
    {"set": k, "landmark": v["landmark"].iloc[0], "groups": v["group_id"].nunique(), "rows": len(v),
     "events": int(v["event"].sum()), "event_rate_pct": round(v["event"].mean() * 100, 2)}
    for k, v in sets.items()])
print("\n=== 분할 요약 ===")
print(split_summary.to_string(index=False))
split_summary.to_csv(OUT_DIR / f"5_split_요약{TAG}.csv", index=False, encoding="utf-8-sig")


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


perf_rows = []


def record(model, risk_fn):
    for name, d in sets.items():
        ov, wb = cindex(d, risk_fn(d))
        perf_rows.append({"model": model, "set": name, "c_index": round(ov, 4), "c_index_within_biz": round(wb, 4)})
    print(pd.DataFrame(perf_rows).query("model == @model")[["set", "c_index", "c_index_within_biz"]].to_string(index=False))


# ============================================
# 6. Cox PH (그룹 단위 부트스트랩 SE)
# ============================================
# 같은 그룹의 사업장은 그룹공변량이 동일 -> 독립이 아니므로 표준오차는 그룹째로 재표집(cluster bootstrap)해서 구한다.
# lifelines의 cluster_col(robust 분산)은 50만행에서 시간이 표본수의 제곱꼴로 늘어(10만행 273초) 쓸 수 없었음.
# 업종은 strata 대신 더미로 넣는다(strata는 층간 baseline이 예측에 안 실려 업종 간 C-index가 왜곡됨).
N_BOOT = 50


def fit_cox(cols, label):
    print(f"\n=== Cox PH [{label}] ===")
    cph = CoxPHFitter()
    cph.fit(train[cols + BIZ_DUMMY + ["duration", "event"]], duration_col="duration", event_col="event")
    record(f"Cox_{label}", lambda d: cph.predict_log_partial_hazard(d[cols + BIZ_DUMMY]).to_numpy())
    return cph


def cluster_bootstrap_summary(cph, cols):
    rows_by_group = train.reset_index(drop=True).groupby("group_id").indices
    gids = np.array(list(rows_by_group))
    tr = train.reset_index(drop=True)[cols + BIZ_DUMMY + ["duration", "event"]]
    rng = np.random.default_rng(RANDOM_STATE)
    coefs = []
    for _ in range(N_BOOT):
        pick = rng.choice(gids, size=len(gids), replace=True)
        rows = np.concatenate([rows_by_group[g] for g in pick])
        c = CoxPHFitter().fit(tr.iloc[rows], duration_col="duration", event_col="event")
        coefs.append(c.params_)
    se = pd.DataFrame(coefs).std()
    out = pd.DataFrame({"coef": cph.params_, "exp(coef)": np.exp(cph.params_), "boot_se": se})
    out["z"] = out["coef"] / out["boot_se"]
    out["p"] = 2 * (1 - norm.cdf(out["z"].abs()))
    return out


cox_ctrl = fit_cox(COV_STORE, "가게특성만")
cox_full = fit_cox(COV_STORE + COV_GROUP, "가게특성+BC카드")
print(f"\n계수 (그룹 부트스트랩 SE, B={N_BOOT}):")
cox_summary = cluster_bootstrap_summary(cox_full, COV_STORE + COV_GROUP)
print(cox_summary.round(4))
cox_summary.to_csv(OUT_DIR / f"5_CoxPH_계수{TAG}.csv", encoding="utf-8-sig")

# 미학습그룹+미래 구간에서 위험도 십분위별 실제 폐업률(보정 확인)
te = sets["test_both"].copy()
te["risk"] = cox_full.predict_log_partial_hazard(te[COV_STORE + COV_GROUP + BIZ_DUMMY]).to_numpy()
te["decile"] = pd.qcut(te["risk"].rank(method="first"), 10, labels=range(1, 11))
calib = te.groupby("decile", observed=True).agg(rows=("event", "size"), event_rate_pct=("event", lambda s: s.mean() * 100)).round(3)
print("\n[test_both] 예측위험 십분위별 실제 폐업률(%):")
print(calib.T.to_string())
calib.to_csv(OUT_DIR / f"5_test_위험도십분위{TAG}.csv", encoding="utf-8-sig")

# ============================================
# 7. Random Survival Forest
# ============================================
print("\n=== Random Survival Forest ===")
RSF_COLS = COV_STORE + COV_GROUP + BIZ_DUMMY
rsf_tr = train.sample(n=min(args.rsf_n, len(train)), random_state=RANDOM_STATE)
y_tr = np.array(list(zip(rsf_tr["event"].astype(bool), rsf_tr["duration"])), dtype=[("event", bool), ("time", float)])
print(f"RSF 학습표본: {len(rsf_tr):,}행 (폐업 {int(rsf_tr['event'].sum()):,}건), 트리 {args.rsf_trees}개")
rsf = RandomSurvivalForest(n_estimators=args.rsf_trees, max_depth=8, min_samples_leaf=200,
                            n_jobs=4, random_state=RANDOM_STATE)
rsf.fit(rsf_tr[RSF_COLS], y_tr)
record("RSF", lambda d: rsf.predict(d[RSF_COLS]))

# permutation importance: 미학습그룹+미래(test_both) 표본에서 C-index 하락폭
te_s = sets["test_both"].sample(n=min(40_000, len(sets["test_both"])), random_state=RANDOM_STATE)
base_ci = concordance_index(te_s["duration"], -rsf.predict(te_s[RSF_COLS]), te_s["event"])
rng = np.random.default_rng(RANDOM_STATE)
imp = {}
for c in RSF_COLS:
    drops = []
    for _ in range(3):
        x = te_s[RSF_COLS].copy()
        x[c] = rng.permutation(x[c].to_numpy())
        drops.append(base_ci - concordance_index(te_s["duration"], -rsf.predict(x), te_s["event"]))
    imp[c] = np.mean(drops)
imp = pd.Series(imp).sort_values(ascending=False)
print(f"\nRSF 변수중요도(permutation, test_both C-index 하락폭, 기준 {base_ci:.4f}):\n{imp.round(4)}")
imp.to_csv(OUT_DIR / f"5_RSF_변수중요도{TAG}.csv", encoding="utf-8-sig")

perf = pd.DataFrame(perf_rows)
perf.to_csv(OUT_DIR / f"5_모델성능{TAG}.csv", index=False, encoding="utf-8-sig")
print("\n=== 5단계 결론 요약 (concordance: 0.5=무작위, 1.0=완벽) ===")
print(perf.pivot(index="model", columns="set", values="c_index")[list(sets)].to_string())
print("\n업종 내 concordance:")
print(perf.pivot(index="model", columns="set", values="c_index_within_biz")[list(sets)].to_string())
