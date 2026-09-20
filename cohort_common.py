"""
cohort_common.py — 주 설계(단순 코호트: 2026-01-01 영업 중 사업장을 --end까지 추적)의 코호트·공변량 생성을 한 곳에 둔 모듈.
shap_decomposition.py / shap_rsf_approx.py가 쓴다. cox_rsf.py·rsf_eval.py와 같은 정의이며(같은 결과 재현을 rsf_eval.py 로그의
n=635,567·폐업 25,330건으로 확인), 두 스크립트는 건드리지 않았다.
"""
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedGroupKFold

DATA_DIR = Path("data")
BIZ_LIST = ["한식계열", "일식회집", "중국음식", "서양음식", "스넥", "제과점", "편의점"]
JOIN_KEY = ["SIDO_NM", "CCG_NM", "bc_업종"]
BC_MONTHS = [202601, 202602, 202603, 202604, 202605, 202606]
GROUP_BC = ["amt_share_gender_1", "amt_share_gender_2",            # 준거범주: 성별 3(법인), 연령 1
            "amt_share_age_2", "amt_share_age_3", "amt_share_age_4", "amt_share_age_5", "amt_share_age_6"]
NUM = ["log_age", "is_franchise", "log_dist_to_centroid", "is_multiuse", "size_z", "size_missing", "coord_missing",
       "phone_recorded", "g_closure_rate_1y"] + GROUP_BC
BIZ_DUMMY = [f"biz_{b}" for b in BIZ_LIST[1:]]                     # 준거범주: 한식계열(cox_rsf.py와 동일)
X_COLS = NUM + BIZ_DUMMY

# 설명용 블록: 여러 열을 하나의 의미 단위로 묶는다(SHAP은 가법적이라 블록 안에서 합산해도 정확하다).
BLOCKS = {
    "영업연수": ["log_age"],
    "프랜차이즈": ["is_franchise"],
    "시설 크기": ["size_z", "size_missing"],
    "입지(중심지 거리)": ["log_dist_to_centroid", "coord_missing"],
    "다중이용업소": ["is_multiuse"],
    "전화번호 기재": ["phone_recorded"],
    "지역 최근 폐업률": ["g_closure_rate_1y"],
    "BC 성별 구성": ["amt_share_gender_1", "amt_share_gender_2"],
    "BC 연령 구성": ["amt_share_age_2", "amt_share_age_3", "amt_share_age_4", "amt_share_age_5", "amt_share_age_6"],
    "업종": BIZ_DUMMY,
}
assert sorted(sum(BLOCKS.values(), [])) == sorted(X_COLS)


def build_cohort(end="2026-06-30", data_dir=DATA_DIR):
    """모집단: 2026-01-01 영업 중. event = 폐업일자가 (1/1, end], time = 일(그 외 end에서 censored)."""
    lm, end_ts = pd.Timestamp("2026-01-01"), pd.Timestamp(end)
    horizon = (end_ts - lm).days
    df = pd.read_csv(Path(data_dir) / "final_joined.csv", encoding="utf-8-sig", parse_dates=["인허가일자", "폐업일자"], low_memory=False,
                     usecols=["관리번호", "인허가일자", "폐업일자", "bc_업종", "SIDO_NM", "CCG_NM", "is_franchise",
                              "dist_to_region_centroid_m", "is_multiuse", "log시설총규모_업종내z", "시설총규모_결측여부",
                              "좌표결측", "전화번호_기재"])
    df = df[df["bc_업종"].isin(BIZ_LIST)].copy()
    df["log_dist_to_centroid"] = np.log1p(df["dist_to_region_centroid_m"])     # NaN은 그대로 둔다(대체는 train에서만 fit)
    df["coord_missing"] = df["좌표결측"].astype(int)
    df["size_z"] = df["log시설총규모_업종내z"].fillna(0)                        # 업종 내 z-score라 결측 = 업종 평균(0) (CHANGELOG ⑩)
    df["size_missing"] = df["시설총규모_결측여부"].astype(int)
    df["phone_recorded"] = df["전화번호_기재"].astype(int)

    bc = pd.read_csv(Path(data_dir) / "bc_clean.csv", encoding="utf-8-sig", dtype={"GENDER_CD": str, "AGE_CD": str})
    jemulpo = bc[(bc["SIDO_NM"] == "인천광역시") & (bc["CCG_NM"].isin(["중구", "동구"]))].copy()
    jemulpo["CCG_NM"] = "제물포구"
    bc = pd.concat([bc, jemulpo], ignore_index=True)
    bc = bc[bc["bc_업종"].isin(BIZ_LIST) & bc["STRD_YYMM"].isin(BC_MONTHS)]
    cov = pd.DataFrame(index=bc.groupby(JOIN_KEY).size().index)
    for col, prefix in [("GENDER_CD", "amt_share_gender_"), ("AGE_CD", "amt_share_age_")]:
        amt = bc[bc[col] != "x"].groupby(JOIN_KEY + [col])["amt"].sum().unstack(col, fill_value=0)
        cov = cov.join(amt.div(amt.sum(axis=1), axis=0).add_prefix(prefix))
    cov = cov.reset_index()

    d = df[(df["인허가일자"] <= lm) & (df["폐업일자"].isna() | (df["폐업일자"] > lm))].copy()
    closed = d["폐업일자"].notna() & (d["폐업일자"] <= end_ts)
    d["event"] = closed.to_numpy()
    d["time"] = np.where(closed, (d["폐업일자"] - lm).dt.days, horizon).astype(float)
    d["log_age"] = np.log1p((lm - d["인허가일자"]).dt.days / 365.25)

    y_ = pd.Timedelta(days=365)                                                # 1/1 이전 1년 정보만 사용
    alive = lambda t: (df["인허가일자"] <= t) & (df["폐업일자"].isna() | (df["폐업일자"] > t))
    g = pd.concat([df[alive(lm - y_)].groupby(JOIN_KEY).size().rename("n_ago"),
                   df[(df["폐업일자"] > lm - y_) & (df["폐업일자"] <= lm)].groupby(JOIN_KEY).size().rename("closed_1y")],
                  axis=1).fillna(0)
    g["g_closure_rate_1y"] = g["closed_1y"] / g["n_ago"].clip(lower=1)
    n0 = len(d)
    d = d.merge(cov, on=JOIN_KEY, how="left", validate="m:1").merge(g[["g_closure_rate_1y"]].reset_index(), on=JOIN_KEY,
                                                                    how="left", validate="m:1")
    d["g_closure_rate_1y"] = d["g_closure_rate_1y"].fillna(0)
    assert len(d) == n0
    d["group_id"] = d.groupby(JOIN_KEY).ngroup()
    for b in BIZ_LIST[1:]:
        d[f"biz_{b}"] = (d["bc_업종"] == b).astype(int)
    return d.reset_index(drop=True), horizon


def split_train_test(d, seed=42):
    """rsf_eval.py와 같은 그룹 hold-out 분할(event stratify + 그룹 유지). 같은 seed면 같은 train/test다."""
    sgkf = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=seed)
    tr_idx, te_idx = next(sgkf.split(d, d["event"], d["group_id"]))
    assert not (set(d.iloc[tr_idx]["group_id"]) & set(d.iloc[te_idx]["group_id"]))
    return tr_idx, te_idx
