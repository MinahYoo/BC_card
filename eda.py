# -*- coding: utf-8 -*-
"""
1단계 EDA — final_joined.csv 기반
체크리스트:
  - event_observed 재정의 근거 데이터(영업상태명 분포)
  - 미매칭행 재확인 (진짜 결측 vs 데이터 부재)
  - bc_업종별/시군구별 분포
  - 생존시간 분포 (censoring 포함) + 극단치 재점검
"""
import pandas as pd
import numpy as np
from pathlib import Path

DATA_DIR = Path("data")
OUT_DIR = Path("output")
OUT_DIR.mkdir(exist_ok=True)

# 주의: censoring 기준일은 ABP(BC카드) 스냅샷일(2026-06-30)이 아니라 LOCALDATA 자체의
# 최신 관측일로 잡아야 한다. LOCALDATA는 ABP보다 최신 시점까지 쿼리된 "살아있는" 데이터라
# 인허가일자 최댓값이 2026-09-16, 폐업일자 최댓값이 2026-09-28까지 존재함.
# ABP 스냅샷일을 censoring 기준일로 쓰면 그 이후 신규 인허가 건(9,986행)이 음수 생존기간이 됨.
CUTOFF = pd.Timestamp("2026-09-28")

print("=== 로드 ===")
df = pd.read_csv(
    DATA_DIR / "final_joined.csv",
    encoding="utf-8-sig",
    parse_dates=["인허가일자", "폐업일자"],
    low_memory=False,
)
print("행수:", len(df), "컬럼수:", len(df.columns))

# ============================================
# 1. event_observed 재정의 근거 — 영업상태명 분포
# ============================================
print("\n=== 1. 영업상태명 분포 (event_observed 재정의 근거) ===")
status_counts = df["영업상태명"].value_counts(dropna=False)
print(status_counts)
status_counts.to_csv(OUT_DIR / "1_영업상태명_분포.csv", encoding="utf-8-sig")

# event_observed=1인 것이 전부 '폐업'인지, 0인 것에 뭐가 섞여있는지 교차 확인
print("\nevent_observed x 영업상태명 크로스탭:")
cross = pd.crosstab(df["event_observed"], df["영업상태명"])
print(cross)
cross.to_csv(OUT_DIR / "1_event_observed_x_영업상태명.csv", encoding="utf-8-sig")

# ============================================
# 2. 미매칭행 재확인
# ============================================
print("\n=== 2. 미매칭행 (bc_amt_total NaN) ===")
unmatched = df[df["bc_amt_total"].isna()]
print(f"미매칭: {len(unmatched)}행 ({len(unmatched)/len(df)*100:.3f}%)")
combo = unmatched.groupby(["SIDO_NM", "CCG_NM", "bc_업종"], dropna=False).size().sort_values(ascending=False)
print(combo.head(30))
combo.to_csv(OUT_DIR / "2_미매칭_조합.csv", encoding="utf-8-sig")

# ============================================
# 3. bc_업종별 / 시군구별 분포
# ============================================
print("\n=== 3-a. bc_업종별 건수 ===")
biz_counts = df["bc_업종"].value_counts(dropna=False)
print(biz_counts)
biz_counts.to_csv(OUT_DIR / "3a_bc업종별_건수.csv", encoding="utf-8-sig")

print("\n=== 3-b. 시군구별 건수 (상위/하위 10) ===")
region_counts = df.groupby(["SIDO_NM", "CCG_NM"]).size().sort_values(ascending=False)
print("상위 10:\n", region_counts.head(10))
print("하위 10:\n", region_counts.tail(10))
region_counts.to_csv(OUT_DIR / "3b_시군구별_건수.csv", encoding="utf-8-sig")

print("\n=== 3-c. bc_업종 x 시도 피벗 (건수) ===")
pivot = pd.crosstab(df["SIDO_NM"], df["bc_업종"])
print(pivot)
pivot.to_csv(OUT_DIR / "3c_bc업종_x_시도.csv", encoding="utf-8-sig")

# ============================================
# 4. 생존시간 분포 + 극단치
# ============================================
print("\n=== 4. 생존시간(duration) 계산 ===")
df["duration_end"] = df["폐업일자"].fillna(CUTOFF)
df["duration_days"] = (df["duration_end"] - df["인허가일자"]).dt.days
df["duration_years"] = df["duration_days"] / 365.25

print(df["duration_days"].describe())

neg = (df["duration_days"] < 0).sum()
print(f"\nduration<0 (인허가일자 > 종료일, 논리오류): {neg}행")

huge = (df["duration_years"] > 80).sum()
print(f"duration>80년 (극단치 의심): {huge}행")

zero = (df["duration_days"] == 0).sum()
print(f"duration==0 (당일폐업): {zero}행")

df["duration_days"].describe().to_csv(OUT_DIR / "4_생존시간_기술통계.csv", encoding="utf-8-sig")

print("\n=== 4-b. bc_업종별 생존시간(년) 중앙값/평균 (event_observed=1만) ===")
died = df[df["event_observed"] == 1]
surv_by_biz = died.groupby("bc_업종")["duration_years"].agg(["count", "median", "mean", "std"])
print(surv_by_biz)
surv_by_biz.to_csv(OUT_DIR / "4b_업종별_생존시간_폐업건.csv", encoding="utf-8-sig")

print("\n저장 완료: output/ 폴더 확인")
