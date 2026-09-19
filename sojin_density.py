# -*- coding: utf-8 -*-
"""
소진공 상가(상권)정보 -> 시군구x bc_업종 경쟁밀도(현재 영업중인 동종업종 점포수) 테이블 생성.

주의사항 (LOCALDATA/ABP 조인 때와 동일한 문제 재확인됨):
  - '전남광주통합특별시' 병합 표기 존재 -> GWANGJU_GU 기준으로 광주/전남 재분리 필요.
  - 인천은 이미 신설구명(검단구/서해구/영종구/제물포구)을 쓰고 있음(2026-07 개편, 스냅샷은
    202606이지만 이미 신규 지명 반영) -> preprocess_localdata.py와 동일한 INCHEON_CROSSWALK
    적용(검단구/서해구->서구, 영종구->중구). 제물포구는 소진공에도 독립 구로 존재하고
    final_joined.csv의 CCG_NM='제물포구'와 동일 레벨이므로 그대로 둔다(합성 불필요).
"""
import pandas as pd
from pathlib import Path

DATA_DIR = Path("data/sojin_sanga")
OUT_DIR = Path("output")
OUT_DIR.mkdir(exist_ok=True)

GWANGJU_GU = {"광산구", "서구", "북구", "동구", "남구"}
INCHEON_CROSSWALK = {"검단구": "서구", "서해구": "서구", "영종구": "중구"}

# 상권업종중분류명 -> bc_업종 (1:1로 끝나는 것)
MID_MAP = {
    "한식": "한식계열",
    "일식": "일식회집",
    "중식": "중국음식",
    "서양식": "서양음식",
    "동남아시아": "서양음식",
    "비알코올": "서양음식",  # 커피/음료 -> LOCALDATA쪽 '커피숍/다방/전통찻집'과 동일 취지로 서양음식에 포함
}

# 상권업종소분류명 -> bc_업종 (중분류가 '기타 간이'/'종합 소매'로 뭉쳐있어 소분류로 세분화 필요)
SUB_MAP = {
    "김밥/만두/분식": "스넥",
    "빵/도넛": "제과점",
    "떡/한과": "제과점",
    "아이스크림/빙수": "제과점",
    "피자": "서양음식",
    "버거": "서양음식",
    "토스트/샌드위치/샐러드": "서양음식",
    "편의점": "편의점",
    "슈퍼마켓": "슈퍼마켓",
    # 제외(치킨/호프 등은 LOCALDATA 매핑에서도 제외 대상): 매핑 안 하면 자동으로 None -> 제외
}


def fix_region(sido, ccg):
    if sido == "전남광주통합특별시":
        return ("광주광역시", ccg) if ccg in GWANGJU_GU else ("전라남도", ccg)
    if sido == "인천광역시" and ccg in INCHEON_CROSSWALK:
        return (sido, INCHEON_CROSSWALK[ccg])
    return (sido, ccg)


cols = ["시도명", "시군구명", "상권업종중분류명", "상권업종소분류명"]
frames = []
for f in sorted(DATA_DIR.glob("*.csv")):
    d = pd.read_csv(f, usecols=cols, dtype=str)
    for c in ["시도명", "시군구명", "상권업종중분류명", "상권업종소분류명"]:
        d[c] = d[c].str.strip()
    frames.append(d)
    print(f"로드: {f.name} ({len(d)}행)")

df = pd.concat(frames, ignore_index=True)
print("\n전체 상가업소:", len(df), "행")

df["bc_업종"] = df["상권업종중분류명"].map(MID_MAP)
sub_mapped = df["상권업종소분류명"].map(SUB_MAP)
df["bc_업종"] = df["bc_업종"].fillna(sub_mapped)

mapped = df[df["bc_업종"].notna()].copy()
print(f"bc_업종 매핑됨: {len(mapped)}행 / 제외: {len(df) - len(mapped)}행")
print(mapped["bc_업종"].value_counts())

fixed = mapped.apply(lambda r: fix_region(r["시도명"], r["시군구명"]), axis=1, result_type="expand")
fixed.columns = ["SIDO_NM", "CCG_NM"]
mapped["SIDO_NM"] = fixed["SIDO_NM"]
mapped["CCG_NM"] = fixed["CCG_NM"]

density = (
    mapped.groupby(["SIDO_NM", "CCG_NM", "bc_업종"])
    .size()
    .reset_index(name="competitor_n")
)
print("\n경쟁밀도 테이블:", len(density), "개 키")
density.to_csv(OUT_DIR / "5_경쟁밀도_시군구x업종.csv", index=False, encoding="utf-8-sig")
print("저장 완료: output/5_경쟁밀도_시군구x업종.csv")
