# -*- coding: utf-8 -*-
"""
localdata_wide.csv 후보 변수 스크리닝 (모델 투입 전 마지막 점검용, 재실행 가능)

방법: 3/31, 6/30 시점(팀원 landmark와 동일)에 영업 중인 사업장이 이후 78일 안에 폐업하는지를 결과로 두고,
      업종 x 영업연수구간 x 시점별 기대 폐업 대비 관측 폐업 비(O/E)를 후보 변수의 수준별로 본다.
      O/E > 1이면 같은 나이·업종 대비 더 잘 폐업한다. 원시 폐업률은 나이에 오염되므로 쓰지 않는다.

주의: 나이·업종만 보정한 단변량 스크리닝이다. 지역과 다른 변수는 보정하지 않았으므로 최종 채택 판단은
      모델의 블록 추가 검증(추가 C-index의 시군구 단위 bootstrap CI)으로 한다. 여기서 신호가 없다고 wide에서 지우지 않는다.

결과: output/eda_candidates_oe.csv (후보, 수준, n, 폐업, O/E)
"""
import os
import warnings
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
pd.set_option("display.width", 200)

DATA, OUT = "data", "output"
os.makedirs(OUT, exist_ok=True)
BIZ_ALL = ["한식계열", "일식회집", "중국음식", "서양음식", "스넥", "제과점", "편의점", "대형할인점", "슈퍼마켓"]  # ABP 9개 통합업종 전부.
# 대형할인점·슈퍼마켓은 2026년 폐업이 14건·9건뿐이라 이 두 업종의 O/E는 사실상 정보가 없다(결과는 7개 업종이 좌우).
LANDMARKS = {"L1": pd.Timestamp("2026-03-31"), "L2": pd.Timestamp("2026-06-30")}
HORIZON = pd.Timedelta(days=78)
YEAR = pd.Timedelta(days=365)

cat_cols = ["bc_업종", "SIDO_NM", "CCG_NM", "원본파일", "등급구분명", "영업장주변구분명", "급수시설구분명"]
f32 = ["시설총규모", "소재지면적", "여성종사자수", "남성종사자수", "dist_to_region_centroid_m", "좌표정보(X)"]
cols = ["인허가일자", "폐업일자", "bc_업종", "SIDO_NM", "CCG_NM", "원본파일", "시설총규모", "is_multiuse", "소재지면적",
        "소재지면적_절단의심", "등급구분명", "영업장주변구분명", "급수시설구분명", "여성종사자수", "남성종사자수",
        "전화번호_기재", "is_franchise", "dist_to_region_centroid_m", "좌표정보(X)"]

chunks = []
for ch in pd.read_csv(f"{DATA}/localdata_wide.csv", encoding="utf-8-sig", usecols=cols, chunksize=300000,
                      dtype={**{c: "category" for c in cat_cols}, **{c: "float32" for c in f32}}):
    ch["인허가일자"] = pd.to_datetime(ch["인허가일자"], errors="coerce")
    ch["폐업일자"] = pd.to_datetime(ch["폐업일자"], errors="coerce")
    chunks.append(ch)
w = pd.concat(chunks, ignore_index=True)
del chunks
for c in cat_cols:
    w[c] = w[c].astype("category")
w["좌표결측"] = w["좌표정보(X)"].isna().astype("int8")
w["gid"] = (w["SIDO_NM"].cat.codes.astype("int64") * 100000 + w["CCG_NM"].cat.codes.astype("int64") * 100
            + w["bc_업종"].cat.codes.astype("int64"))


def alive(t):
    return (w["인허가일자"] <= t) & (w["폐업일자"].isna() | (w["폐업일자"] > t))


def group_feats(lm):
    """시군구 x 업종 그룹의 landmark 이전 정보만으로 만든 파생 후보(누수 없음)."""
    n_now = w[alive(lm)].groupby("gid").size().rename("g_open")
    n_ago = w[alive(lm - YEAR)].groupby("gid").size().rename("g_open_1y_ago")
    closed = w[(w["폐업일자"] > lm - YEAR) & (w["폐업일자"] <= lm)].groupby("gid").size().rename("g_closed_1y")
    opened = w[(w["인허가일자"] > lm - YEAR) & (w["인허가일자"] <= lm)].groupby("gid").size().rename("g_opened_1y")
    g = pd.concat([n_now, n_ago, closed, opened], axis=1).fillna(0)
    g["g_log_open"] = np.log1p(g["g_open"])
    g["g_closure_rate_1y"] = g["g_closed_1y"] / g["g_open_1y_ago"].clip(lower=1)
    g["g_opening_rate_1y"] = g["g_opened_1y"] / g["g_open_1y_ago"].clip(lower=1)
    return g[["g_log_open", "g_closure_rate_1y", "g_opening_rate_1y"]].reset_index()


parts = []
for tag, lm in LANDMARKS.items():
    d = w[alive(lm) & w["bc_업종"].isin(BIZ_ALL)].copy()
    d["event"] = (d["폐업일자"].notna() & (d["폐업일자"] <= lm + HORIZON)).astype(int)
    d["age"] = (lm - d["인허가일자"]).dt.days / 365.25
    d["lm"] = tag
    parts.append(d.merge(group_feats(lm), on="gid", how="left"))
r = pd.concat(parts, ignore_index=True)
r["agebin"] = pd.cut(r["age"], [-1, 1, 2, 3, 5, 8, 12, 20, 100])
r["exp"] = r.groupby(["bc_업종", "agebin", "lm"], observed=True)["event"].transform("mean")
print(f"위험집단(9개 업종, L1+L2): {len(r):,}행, 폐업 {r['event'].sum():,}건 ({r['event'].mean() * 100:.2f}%)")

rows = []


def oe(series, name, min_n=3000):
    g = pd.DataFrame({"lv": series.astype("object").where(series.notna(), "NaN(결측)"), "e": r["event"], "x": r["exp"]})
    t = g.groupby("lv").agg(n=("e", "size"), 폐업=("e", "sum"), 기대=("x", "sum"))
    t["O/E"] = (t["폐업"] / t["기대"]).round(2)
    t = t[t["n"] >= min_n].drop(columns="기대")
    for lv, x in t.iterrows():
        rows.append({"후보": name, "수준": lv, "n": int(x["n"]), "폐업": int(x["폐업"]), "O/E": x["O/E"]})
    print(f"--- {name} ---")
    print(t.to_string())
    print()


def qbin(s, q=5):
    return pd.qcut(s, q, duplicates="drop").astype(str).where(s.notna())


print("[원본 컬럼 후보]")
for c in ["is_franchise", "is_multiuse", "전화번호_기재", "좌표결측", "소재지면적_절단의심", "원본파일",
          "등급구분명", "영업장주변구분명", "급수시설구분명"]:
    oe(r[c], c)
for c, nm in [("시설총규모", "시설총규모(5분위)"), ("소재지면적", "소재지면적(5분위)"),
              ("dist_to_region_centroid_m", "중심점거리(5분위)")]:
    oe(qbin(r[c]), nm)
emp = r["남성종사자수"].add(r["여성종사자수"])
oe(pd.cut(emp, [-1, 0, 1, 3, 1000]).astype(str).where(emp.notna()), "종사자수 합")

print("[LOCALDATA만으로 만든 파생 후보 - 시군구x업종 그룹 단위, landmark 이전 정보만 사용]")
oe(qbin(r["g_log_open"]), "g_log_open (그룹 내 영업 중 점포 수, 밀도 대리)")
oe(qbin(r["g_closure_rate_1y"]), "g_closure_rate_1y (직전 1년 폐업률)")
oe(qbin(r["g_opening_rate_1y"]), "g_opening_rate_1y (직전 1년 개업률)")

pd.DataFrame(rows).to_csv(f"{OUT}/eda_candidates_oe.csv", index=False, encoding="utf-8-sig")
print(f"저장: {OUT}/eda_candidates_oe.csv")

print("\n[후보 간 상관(Spearman, 표본 20만)]")
sm = r.sample(200000, random_state=1)
sm = sm.assign(종사자수합=sm["남성종사자수"] + sm["여성종사자수"])
print(sm[["age", "is_franchise", "is_multiuse", "시설총규모", "소재지면적", "dist_to_region_centroid_m",
          "g_log_open", "g_closure_rate_1y", "g_opening_rate_1y"]].corr(method="spearman").round(2).to_string())
