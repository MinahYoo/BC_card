# -*- coding: utf-8 -*-
"""
지역 키 기준표 생성 (ABP 시군구 키가 표준)

- LOCALDATA(SIDO_NM, CCG_NM)는 preprocess_localdata.py가 주소에서 파싱한 뒤 ABP 표기로 맞춘 값이다.
- 이 표는 (1) ABP 기준 시군구 목록, (2) 각 시군구에 LOCALDATA가 얼마나 대응되는지, (3) 특수 처리(통합/분리/합성) 사례를 한곳에 모은다.
- 외부 데이터(소진공, 통계청 등)를 붙일 때 이 표를 기준으로 삼는다. 외부 시군구코드는 원본 파일에서 채워야 하므로
  `시군구코드_외부` 열은 비워두었다(추정으로 채우지 않는다).

출력: data/region_master.csv (ABP 시군구 + 합성 시군구), data/region_unmatched.csv (표준에 없는 LOCALDATA 라벨)
"""
import warnings

import pandas as pd

warnings.filterwarnings("ignore")
DATA = "data"

bc = pd.read_csv(f"{DATA}/bc_clean.csv", encoding="utf-8-sig", usecols=["SIDO_NM", "CCG_NM", "bc_업종"])
abp = (bc.groupby(["SIDO_NM", "CCG_NM"])["bc_업종"]
         .agg(abp_업종수="nunique", abp_업종=lambda s: ",".join(sorted(s.unique())))
         .reset_index())

loc = pd.read_csv(f"{DATA}/localdata_wide.csv", encoding="utf-8-sig",
                  usecols=["SIDO_NM", "CCG_NM", "개방자치단체코드", "bc_업종"],
                  dtype={"SIDO_NM": "category", "CCG_NM": "category", "bc_업종": "category"})
loc["SIDO_NM"] = loc["SIDO_NM"].astype(str)
loc["CCG_NM"] = loc["CCG_NM"].astype(str)
g = loc.groupby(["SIDO_NM", "CCG_NM"])
lo = pd.DataFrame({
    "local_행수": g.size(),
    "local_업종수": g["bc_업종"].nunique(),
    "개방자치단체코드_최빈": g["개방자치단체코드"].agg(lambda s: s.value_counts().index[0]),
    "개방자치단체코드_종류수": g["개방자치단체코드"].nunique(),
}).reset_index()

m = abp.merge(lo, on=["SIDO_NM", "CCG_NM"], how="outer", indicator=True)
in_abp = m["_merge"].isin(["both", "left_only"])
synthetic = (m["SIDO_NM"] == "인천광역시") & (m["CCG_NM"] == "제물포구")
m["in_ABP"] = in_abp
m["합성"] = synthetic


def note(r):
    s, c = r["SIDO_NM"], r["CCG_NM"]
    if s == "세종특별자치시":
        return "세종은 시군구 구분이 없어 CCG_NM을 SIDO_NM과 동일하게 통일"
    if s == "인천광역시" and c == "제물포구":
        return "합성 키: 2026-07-01 (구)중구(내륙)+(구)동구 통합 신설. ABP엔 없어 join에서 ABP 중구+동구 합산 공변량으로 대체"
    if s == "인천광역시" and c == "서구":
        return "LOCALDATA의 검단구·서해구를 옛 서구로 환원"
    if s == "인천광역시" and c == "중구":
        return ("LOCALDATA의 영종구를 옛 중구로 환원. 한계: ABP 중구 값은 옛 중구 전체(영종+내륙)라 영종구 사업장에는 "
                "내륙 소비까지 섞인 값이 붙음. 제물포구 합성에도 사용")
    if s == "인천광역시" and c == "동구":
        return "LOCALDATA에서는 옛 동구 사업장이 전부 '제물포구'로 표기되어 행이 0개(정상). 제물포구 합성에 사용"
    if s == "인천광역시" and c == "미추홀구":
        return "옛 '남구'(2018년 미추홀구로 개칭) 표기 행 포함"
    if s in ("광주광역시", "전라남도"):
        return "LOCALDATA 원본의 '전남광주통합특별시' 표기를 ABP 기준(광주 5개 구/전남 시·군)으로 분리"
    if s == "경기도" and c.startswith("화성시 "):
        return "화성시 4개 구(만세·동탄·병점·효행)는 ABP 기준. 구 정보가 없는 LOCALDATA 행은 미매칭"
    return ""


m["비고"] = m.apply(note, axis=1)
m["시군구코드_외부"] = ""  # 소진공 상가정보 등 실제 원본의 시군구코드로 채울 것(추정 입력 금지)

master = m[in_abp | synthetic].copy()
master = master.drop(columns="_merge")[["SIDO_NM", "CCG_NM", "in_ABP", "합성", "abp_업종수", "abp_업종", "local_행수",
                                         "local_업종수", "개방자치단체코드_최빈", "개방자치단체코드_종류수", "시군구코드_외부", "비고"]]
master = master.sort_values(["SIDO_NM", "CCG_NM"]).reset_index(drop=True)
master.to_csv(f"{DATA}/region_master.csv", index=False, encoding="utf-8-sig")

unmatched = m[~in_abp & ~synthetic][["SIDO_NM", "CCG_NM", "local_행수"]].sort_values("local_행수", ascending=False)
unmatched.to_csv(f"{DATA}/region_unmatched.csv", index=False, encoding="utf-8-sig")

print(f"기준표 시군구 수: {len(master)} (ABP {int(master['in_ABP'].sum())} + 합성 {int(master['합성'].sum())})")
no_local = master[master["local_행수"].isna()]
print(f"LOCALDATA 행이 없는 ABP 시군구: {len(no_local)}")
if len(no_local):
    print(no_local[["SIDO_NM", "CCG_NM", "abp_업종수"]].to_string(index=False))
tot = int(lo["local_행수"].sum())
matched_rows = int(master["local_행수"].sum())
print(f"\nLOCALDATA 행 중 기준표에 대응: {matched_rows:,} / {tot:,} ({matched_rows / tot * 100:.3f}%)")
print(f"표준에 없는 라벨: {len(unmatched)}종, {int(unmatched['local_행수'].sum()):,}행")
print(unmatched.head(10).to_string(index=False))
print("\n개방자치단체코드가 시군구당 여러 개인 곳(상위):")
print(master[master["개방자치단체코드_종류수"] > 1][["SIDO_NM", "CCG_NM", "개방자치단체코드_종류수"]].head(8).to_string(index=False))
