# -*- coding: utf-8 -*-
"""4단계: 업종별 Kaplan-Meier 1차 스크리닝 (전체 데이터)."""
import pandas as pd
from lifelines import KaplanMeierFitter
from lifelines.statistics import multivariate_logrank_test
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
plt.rcParams["font.family"] = "AppleGothic"
plt.rcParams["axes.unicode_minus"] = False
from pathlib import Path

DATA_DIR = Path("data")
OUT_DIR = Path("output")
CUTOFF = pd.Timestamp("2026-09-16")  # LOCALDATA 폐업일자는 09-16까지만 실제로 쌓여 있음(이후 4건)

df = pd.read_csv(DATA_DIR / "final_joined.csv", encoding="utf-8-sig",
                  parse_dates=["인허가일자", "폐업일자"], low_memory=False)
df["duration_years"] = (df["폐업일자"].fillna(CUTOFF) - df["인허가일자"]).dt.days / 365.25

# 대형할인점/슈퍼마켓은 표본 극소 + 체인 출점 역학이 달라 별도 취급(팀 매핑 문서 방침)
main_biz = ["한식계열", "일식회집", "중국음식", "서양음식", "스넥", "제과점", "편의점"]

fig, ax = plt.subplots(figsize=(9, 6))
rows = []
for biz in main_biz:
    sub = df[df["bc_업종"] == biz]
    kmf = KaplanMeierFitter()
    kmf.fit(sub["duration_years"], sub["event_observed"], label=biz)
    kmf.plot_survival_function(ax=ax)
    rows.append({
        "bc_업종": biz, "n": len(sub),
        "median_surv_years": kmf.median_survival_time_,
        "surv_5y": kmf.survival_function_at_times(5).values[0],
        "surv_10y": kmf.survival_function_at_times(10).values[0],
    })

ax.set_xlabel("영업 기간(년)")
ax.set_ylabel("생존확률")
ax.set_title("업종별 Kaplan-Meier 생존곡선 (전체)")
fig.tight_layout()
fig.savefig(OUT_DIR / "4_업종별_KM.png", dpi=120)
print("저장: output/4_업종별_KM.png\n")

summary = pd.DataFrame(rows).sort_values("median_surv_years")
print(summary.to_string(index=False))
summary.to_csv(OUT_DIR / "4_업종별_KM_요약.csv", index=False, encoding="utf-8-sig")

# 업종간 생존곡선이 통계적으로 다른지 (log-rank test)
sub_all = df[df["bc_업종"].isin(main_biz)]
result = multivariate_logrank_test(sub_all["duration_years"], sub_all["bc_업종"], sub_all["event_observed"])
print(f"\n업종간 log-rank test: chi2={result.test_statistic:.1f}, p={result.p_value:.2e}")

# ============================================
# 지역(시군구) x 업종별 KM — 위험/안정 패턴 1차 발견
# ============================================
# 탐색용 기술통계(전체 이력 기준)이며 모델 입력이 아니다. 표본 30 미만 그룹은 KM이 불안정해 제외.
# 중위생존시간은 곡선이 0.5 아래로 안 내려가면 inf라서, 5년 생존율을 비교 기준으로 함께 낸다.
rows = []
for (sido, ccg, biz), sub in sub_all.groupby(["SIDO_NM", "CCG_NM", "bc_업종"]):
    if len(sub) < 30:
        continue
    k = KaplanMeierFitter().fit(sub["duration_years"], sub["event_observed"])
    rows.append({"SIDO_NM": sido, "CCG_NM": ccg, "bc_업종": biz, "n": len(sub),
                 "n_event": int(sub["event_observed"].sum()),
                 "median_surv_years": k.median_survival_time_,
                 "surv_5y": k.survival_function_at_times(5).values[0]})
region_km = pd.DataFrame(rows)
region_km.to_csv(OUT_DIR / "4c_지역x업종_KM.csv", index=False, encoding="utf-8-sig")
print(f"\n지역x업종 KM: {len(region_km)}개 그룹(표본>=30) 저장 -> output/4c_지역x업종_KM.csv")
big = region_km[region_km["n"] >= 100].sort_values("surv_5y")
print("\n5년 생존율 최저 10개 (표본>=100):")
print(big.head(10)[["SIDO_NM", "CCG_NM", "bc_업종", "n", "surv_5y"]].to_string(index=False))
print("\n5년 생존율 최고 10개 (표본>=100):")
print(big.tail(10)[["SIDO_NM", "CCG_NM", "bc_업종", "n", "surv_5y"]].to_string(index=False))
spread = big.groupby("bc_업종")["surv_5y"].agg(["min", "median", "max"]).round(3)
print("\n업종별 지역간 5년 생존율 범위:\n", spread)
