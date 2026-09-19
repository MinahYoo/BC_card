# -*- coding: utf-8 -*-
"""
실제 좌표 기반 경쟁밀도: 각 LOCALDATA 가게 기준 반경 500m 내 동일 bc_업종
소진공 점포 수를 계산한다. 기존 sojin_density.py는 시군구 단위 총 점포수라
'같은 시군구면 다 똑같은 값'이었는데, 여기서는 가게별로 실제 다른 값이 나온다.

좌표계: LOCALDATA(좌표정보X/Y)는 EPSG:5174(Bessel 중부원점TM, 미터단위).
        소진공(경도/위도)은 EPSG:4326(WGS84) -> pyproj로 5174로 변환해 같은 평면에서 비교.
"""
import pandas as pd
import numpy as np
from pathlib import Path
from pyproj import Transformer
from scipy.spatial import cKDTree

DATA_DIR = Path("data")
SOJIN_DIR = DATA_DIR / "sojin_sanga"
OUT_DIR = Path("output")
RADIUS_M = 500

GWANGJU_GU = {"광산구", "서구", "북구", "동구", "남구"}
INCHEON_CROSSWALK = {"검단구": "서구", "서해구": "서구", "영종구": "중구"}
MID_MAP = {"한식": "한식계열", "일식": "일식회집", "중식": "중국음식", "서양식": "서양음식",
           "동남아시아": "서양음식", "비알코올": "서양음식"}
SUB_MAP = {"김밥/만두/분식": "스넥", "빵/도넛": "제과점", "떡/한과": "제과점",
           "아이스크림/빙수": "제과점", "피자": "서양음식", "버거": "서양음식",
           "토스트/샌드위치/샐러드": "서양음식", "편의점": "편의점", "슈퍼마켓": "슈퍼마켓"}
MAIN_BIZ = ["한식계열", "일식회집", "중국음식", "서양음식", "스넥", "제과점", "편의점"]


def fix_region(sido, ccg):
    if sido == "전남광주통합특별시":
        return ("광주광역시", ccg) if ccg in GWANGJU_GU else ("전라남도", ccg)
    if sido == "인천광역시" and ccg in INCHEON_CROSSWALK:
        return (sido, INCHEON_CROSSWALK[ccg])
    return (sido, ccg)


# ============================================
# 1. 소진공 로드 + bc_업종 매핑 + WGS84->EPSG:5174 변환
# ============================================
print("=== 소진공 로드 ===")
cols = ["시도명", "시군구명", "상권업종중분류명", "상권업종소분류명", "경도", "위도"]
frames = []
for f in sorted(SOJIN_DIR.glob("*.csv")):
    d = pd.read_csv(f, usecols=cols)
    for c in ["시도명", "시군구명", "상권업종중분류명", "상권업종소분류명"]:
        d[c] = d[c].astype(str).str.strip()
    frames.append(d)
sojin = pd.concat(frames, ignore_index=True)

sojin["bc_업종"] = sojin["상권업종중분류명"].map(MID_MAP)
sojin["bc_업종"] = sojin["bc_업종"].fillna(sojin["상권업종소분류명"].map(SUB_MAP))
sojin = sojin[sojin["bc_업종"].isin(MAIN_BIZ)].dropna(subset=["경도", "위도"]).copy()

transformer = Transformer.from_crs("EPSG:4326", "EPSG:5174", always_xy=True)
sojin["X"], sojin["Y"] = transformer.transform(sojin["경도"].to_numpy(), sojin["위도"].to_numpy())
print(f"소진공 매핑+변환 완료: {len(sojin)}행")

# bc_업종별 KDTree 미리 구축
trees = {}
for biz in MAIN_BIZ:
    pts = sojin.loc[sojin["bc_업종"] == biz, ["X", "Y"]].to_numpy()
    trees[biz] = cKDTree(pts) if len(pts) else None
    print(f"  {biz}: 소진공 {len(pts)}개 포인트로 KDTree 구축")

# ============================================
# 2. LOCALDATA 로드 + 반경 500m 내 동일업종 카운트
# ============================================
print("\n=== LOCALDATA 로드 ===")
local = pd.read_csv(DATA_DIR / "localdata_clean.csv", encoding="utf-8-sig",
                     usecols=["관리번호", "bc_업종", "좌표정보(X)", "좌표정보(Y)"], low_memory=False)
local = local[local["bc_업종"].isin(MAIN_BIZ)].copy()

result = pd.Series(np.nan, index=local.index, dtype=float)
for biz in MAIN_BIZ:
    mask = (local["bc_업종"] == biz) & local["좌표정보(X)"].notna() & local["좌표정보(Y)"].notna()
    n = mask.sum()
    if trees[biz] is None or n == 0:
        continue
    pts = local.loc[mask, ["좌표정보(X)", "좌표정보(Y)"]].to_numpy()
    counts = trees[biz].query_ball_point(pts, r=RADIUS_M, return_length=True)
    result.loc[mask] = counts
    print(f"  {biz}: {n}행 계산 완료 (평균 {counts.mean():.1f}개 경쟁점포/{RADIUS_M}m)")

local["spatial_competitor_500m"] = result
out = local[["관리번호", "spatial_competitor_500m"]]
out.to_csv(OUT_DIR / "5b_spatial_competitor.csv", index=False, encoding="utf-8-sig")
print(f"\n저장 완료: output/5b_spatial_competitor.csv ({len(out)}행)")
print(f"좌표 결측으로 계산 못한 행: {result.isna().sum()}행 ({result.isna().mean()*100:.2f}%)")
