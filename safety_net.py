# -*- coding: utf-8 -*-
"""
3단계 안전판 검증: 표본 큰 업종 1개(편의점)로 조인->전처리->생존모델 전체 파이프라인을
끝까지 실행해본다. 여기서 문제가 없으면 11개 업종 전체로 확장한다.
"""
import pandas as pd
from lifelines import KaplanMeierFitter
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
plt.rcParams["font.family"] = "AppleGothic"
plt.rcParams["axes.unicode_minus"] = False
from pathlib import Path

DATA_DIR = Path("data")
OUT_DIR = Path("output")
OUT_DIR.mkdir(exist_ok=True)
CUTOFF = pd.Timestamp("2026-09-16")  # LOCALDATA 폐업일자는 09-16까지만 실제로 쌓여 있음(이후 4건)

print("=== 로드 ===")
df = pd.read_csv(
    DATA_DIR / "final_joined.csv",
    encoding="utf-8-sig",
    parse_dates=["인허가일자", "폐업일자"],
    low_memory=False,
)

biz = df[df["bc_업종"] == "편의점"].copy()
print(f"편의점 표본: {len(biz)}행")

# 공변량 매칭 확인
n_missing_cov = biz["bc_amt_total"].isna().sum()
print(f"BC카드 공변량 미매칭: {n_missing_cov}행 ({n_missing_cov/len(biz)*100:.3f}%)")

# 생존시간/이벤트 계산
biz["duration_days"] = (biz["폐업일자"].fillna(CUTOFF) - biz["인허가일자"]).dt.days
biz["duration_years"] = biz["duration_days"] / 365.25
assert (biz["duration_days"] >= 0).all(), "음수 생존기간 존재 — CUTOFF/날짜 파싱 재확인 필요"

n_event = (biz["event_observed"] == 1).sum()
n_censored = (biz["event_observed"] == 0).sum()
print(f"event(폐업)={n_event}, censored(영업중 등)={n_censored}")

# ============================================
# Kaplan-Meier 적합 (전체 편의점)
# ============================================
kmf = KaplanMeierFitter()
kmf.fit(durations=biz["duration_years"], event_observed=biz["event_observed"], label="편의점 전체")

median_surv = kmf.median_survival_time_
print(f"\n편의점 전체 KM 중위 생존시간: {median_surv:.2f}년")
print("5년/10년 생존율:", kmf.survival_function_at_times([5, 10]).values)

# 시군구 상위 5개(표본 큰 곳) vs 하위 5개 비교 — 지역차 존재하는지 1차 확인
region_counts = biz.groupby(["SIDO_NM", "CCG_NM"]).size().sort_values(ascending=False)
top5 = region_counts.head(5).index.tolist()
bot5 = region_counts[region_counts >= 30].tail(5).index.tolist()  # 표본 30 미만은 KM 불안정하므로 제외

fig, ax = plt.subplots(figsize=(8, 6))
kmf.plot_survival_function(ax=ax)
for sido, ccg in top5:
    sub = biz[(biz["SIDO_NM"] == sido) & (biz["CCG_NM"] == ccg)]
    KaplanMeierFitter().fit(sub["duration_years"], sub["event_observed"], label=f"{ccg}(상위표본)").plot_survival_function(ax=ax)
ax.set_xlabel("영업 기간(년)")
ax.set_ylabel("생존확률(폐업하지 않을 확률)")
ax.set_title("편의점 안전판 검증 — 전체 vs 표본 큰 시군구 5곳")
fig.tight_layout()
fig.savefig(OUT_DIR / "3_안전판_편의점_KM.png", dpi=120)
print(f"\nKM 곡선 저장: {OUT_DIR}/3_안전판_편의점_KM.png")

# 지역별 KM 중위생존시간 표 (표본 30 이상만)
print("\n=== 시군구별 KM 중위생존시간 (표본>=30) ===")
rows = []
for (sido, ccg), n in region_counts.items():
    if n < 30:
        continue
    sub = biz[(biz["SIDO_NM"] == sido) & (biz["CCG_NM"] == ccg)]
    k = KaplanMeierFitter().fit(sub["duration_years"], sub["event_observed"])
    rows.append({"SIDO_NM": sido, "CCG_NM": ccg, "n": n, "median_surv_years": k.median_survival_time_})
region_km = pd.DataFrame(rows).sort_values("median_surv_years")
print(region_km.head(10))
print("...")
print(region_km.tail(10))
region_km.to_csv(OUT_DIR / "3_안전판_시군구별_중위생존시간.csv", index=False, encoding="utf-8-sig")

print("\n=== 안전판 검증 결론 ===")
print("- 데이터 로드/필터링/duration+event 계산/KM 적합까지 에러 없이 완료")
print("- 지역별 중위생존시간에 편차 존재 확인 (아래 표 최소/최대 참고)")
print(f"  최단: {region_km.iloc[0].to_dict()}")
print(f"  최장: {region_km.iloc[-1].to_dict()}")
