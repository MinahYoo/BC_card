# -*- coding: utf-8 -*-
"""
웹사이트(build_site.py)용 데이터 JSON을 만든다: output/site_data.json (분석 산출물 + 코호트 프로필 + BC 월별 구성 + 시군구 중심점·이웃).
새 분석은 없다 — 이미 계산된 M3L 요인 배수(output/11_final_*.csv), 코호트 프로필, BC 원자료 집계, 시군구 중심점(LOCALDATA 좌표 중앙값)을 한 파일로 묶는다.
"""
import json

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

from explain_common import load_cohort

ns, log = load_cohort()
full = ns["full"].reset_index(drop=True)
JOIN_KEY, REGION_KEY = ns["JOIN_KEY"], ns["REGION_KEY"]
bc = ns["bc"]
BIZ = list(ns["BIZ_LIST"])

grp = pd.read_csv("output/11_final_group_blocks.csv", encoding="utf-8-sig")
reg = pd.read_csv("output/11_final_region_blocks.csv", encoding="utf-8-sig")
feat = pd.read_csv("output/8_group_features.csv", encoding="utf-8-sig", usecols=JOIN_KEY + ["reg_hist", "nb_reg_hist", "nb_grp_hist", "spend_jan", "unit_z_jan"])
BLOCKS = ["영업연수", "프랜차이즈", "입지(중심점 거리)", "사업장 확장(다중이용·크기·좌표결측·전화)", "그룹 직전 1년 폐업률", "자기·이웃 시군구 폐업 이력", "BC 성별 구성", "BC 연령 구성", "업종"]

# ---- 시군구 중심점 + 이웃 5곳 ----
xy = pd.read_csv("data/final_joined.csv", encoding="utf-8-sig", usecols=REGION_KEY + ["좌표정보(X)", "좌표정보(Y)", "좌표의심"], low_memory=False)
xy = xy[xy["좌표정보(X)"].notna() & xy["좌표정보(Y)"].notna() & (xy["좌표의심"].fillna(0) == 0)]
cent = xy.groupby(REGION_KEY)[["좌표정보(X)", "좌표정보(Y)"]].median().reset_index().rename(columns={"좌표정보(X)": "cx", "좌표정보(Y)": "cy"})
del xy
reg = reg.merge(cent, on=REGION_KEY, how="left")
assert reg["cx"].notna().all(), "중심점이 없는 시군구가 있다"
reg = reg.reset_index(drop=True)
pts = reg[["cx", "cy"]].to_numpy(float)
_, nn = cKDTree(pts).query(pts, k=6)
reg["nb"] = [list(map(int, r[1:])) for r in nn]
rid = {(r.SIDO_NM, r.CCG_NM): i for i, r in enumerate(reg.itertuples())}

# ---- 코호트 프로필(그룹·시군구) ----
full["age_yr"] = np.expm1(full["log_age"])
prof = full.groupby(JOIN_KEY, observed=True).agg(age_yr=("age_yr", "mean"), fr=("is_franchise", "mean"), multi=("is_multiuse", "mean")).reset_index()
rprof = full.groupby(REGION_KEY, observed=True).agg(age_yr=("age_yr", "mean"), fr=("is_franchise", "mean")).reset_index()
reg = reg.merge(rprof, on=REGION_KEY, how="left")
rbiz = full.groupby(REGION_KEY + ["bc_업종"], observed=True).agg(n=("event", "size"), rate=("event", "mean")).reset_index()

# ---- BC 월별 ----
months = sorted(bc["STRD_YYMM"].unique())
mon = bc.groupby(JOIN_KEY + ["STRD_YYMM"])[["amt", "cnt"]].sum().reset_index()
ac = bc[bc["AGE_CD"] != "x"].groupby(JOIN_KEY + ["AGE_CD"])["amt"].sum().unstack("AGE_CD", fill_value=0)
ac = ac.div(ac.sum(axis=1), axis=0)
gc = bc[bc["GENDER_CD"] != "x"].groupby(JOIN_KEY + ["GENDER_CD"])["amt"].sum().unstack("GENDER_CD", fill_value=0)
gc = gc.div(gc.sum(axis=1), axis=0)

g = grp.merge(prof, on=JOIN_KEY, how="left").merge(feat, on=JOIN_KEY, how="left")
groups = []
for _, r in g.iterrows():
    key = (r["SIDO_NM"], r["CCG_NM"], r["bc_업종"])
    m = mon[(mon["SIDO_NM"] == key[0]) & (mon["CCG_NM"] == key[1]) & (mon["bc_업종"] == key[2])].set_index("STRD_YYMM")
    amt = [float(m["amt"].get(mm, np.nan)) for mm in months]
    cnt = [float(m["cnt"].get(mm, np.nan)) for mm in months]
    age = ac.loc[key].round(4).tolist() if key in ac.index else None
    gen = gc.loc[key].round(4).tolist() if key in gc.index else None
    groups.append({
        "r": rid[(r["SIDO_NM"], r["CCG_NM"])], "b": BIZ.index(r["bc_업종"]), "n": int(r["n"]), "ev": int(r["events"]), "rate": round(float(r["obs_rate"]), 4),
        "mult": round(float(r["상대위험_배수"]), 3), "x": [round(float(r[f"x_{b}"]), 3) for b in BLOCKS],
        "age_yr": round(float(r["age_yr"]), 2), "fr": round(float(r["fr"]), 4), "multi": round(float(r["multi"]), 4),
        "reg_hist": round(float(r["reg_hist"]), 4), "nb_hist": round(float(r["nb_reg_hist"]), 4),
        "spend": round(float(r["spend_jan"]), 3), "unit_z": round(float(r["unit_z_jan"]), 3) if pd.notna(r["unit_z_jan"]) else None,
        "amt": [None if np.isnan(v) else round(v / 1e6, 1) for v in amt], "cnt": [None if np.isnan(v) else int(v) for v in cnt],
        "age": age, "gen": gen})

regions = []
for i, r in reg.iterrows():
    rb = rbiz[(rbiz["SIDO_NM"] == r["SIDO_NM"]) & (rbiz["CCG_NM"] == r["CCG_NM"])]
    regions.append({"sido": r["SIDO_NM"], "name": r["CCG_NM"], "cx": round(float(r["cx"]), 0), "cy": round(float(r["cy"]), 0), "n": int(r["n"]),
                    "rate": round(float(r["obs_rate"]), 4), "mult": round(float(r["상대위험_배수"]), 3), "x": [round(float(r[f"x_{b}"]), 3) for b in BLOCKS],
                    "age_yr": round(float(r["age_yr"]), 2), "fr": round(float(r["fr"]), 4), "nb": r["nb"],
                    "biz": {BIZ.index(b): [int(n), round(float(v), 4)] for b, n, v in zip(rb["bc_업종"], rb["n"], rb["rate"])}})

out = {"biz": BIZ, "blocks": BLOCKS, "months": [int(m) for m in months], "regions": regions, "groups": groups,
       "national": {"rate": round(float(full["event"].mean()), 4), "n": int(len(full)), "events": int(full["event"].sum()), "age_yr": round(float(full["age_yr"].mean()), 2), "fr": round(float(full["is_franchise"].mean()), 4)}}
with open("output/site_data.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
print(f"시군구 {len(regions)}개, 그룹 {len(groups)}개, {len(json.dumps(out, ensure_ascii=False)) / 1024:.0f} KB -> output/site_data.json")
