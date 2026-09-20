# -*- coding: utf-8 -*-
"""4단계: 업종별 Kaplan-Meier 1차 스크리닝 (전체 데이터)."""
import pandas as pd
from lifelines import KaplanMeierFitter
from lifelines.statistics import multivariate_logrank_test
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
plt.rcParams["font.family"] = ["AppleGothic", "Malgun Gothic", "NanumGothic"]   # macOS / Windows / Linux 순으로 있는 글꼴을 사용
plt.rcParams["axes.unicode_minus"] = False
from pathlib import Path

DATA_DIR = Path("data")
OUT_DIR = Path("output")
CUTOFF = pd.Timestamp("2026-09-16")  # LOCALDATA 폐업일자는 09-16까지만 실제로 쌓여 있음(이후 4건)

df = pd.read_csv(DATA_DIR / "final_joined.csv", encoding="utf-8-sig",
                  parse_dates=["인허가일자", "폐업일자"], low_memory=False,
                  usecols=["인허가일자", "폐업일자", "event_observed", "bc_업종", "SIDO_NM", "CCG_NM"])   # final_joined 42컬럼 전부를 읽으면 메모리가 크다
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
# 탐색용 기술통계(전체 이력 기준)이며 모델 입력이 아니다. 작은 지역의 우연한 극단값을 걸러내려고
# 사업장 30개 이상 AND 폐업(사건) 30건 이상인 그룹만 남기고, 5년 생존율의 95% 신뢰구간(Greenwood)을 함께 낸다.
# 중위생존시간은 곡선이 0.5 아래로 안 내려가면 inf라서, 5년 생존율을 비교 기준으로 쓴다.
MIN_N, MIN_EVENT = 30, 30
rows = []
for (sido, ccg, biz), sub in sub_all.groupby(["SIDO_NM", "CCG_NM", "bc_업종"]):
    n_event = int(sub["event_observed"].sum())
    if len(sub) < MIN_N or n_event < MIN_EVENT:
        continue
    k = KaplanMeierFitter().fit(sub["duration_years"], sub["event_observed"])
    ci = k.confidence_interval_.loc[:5].iloc[-1]
    rows.append({"SIDO_NM": sido, "CCG_NM": ccg, "bc_업종": biz, "n": len(sub), "n_event": n_event,
                 "median_surv_years": k.median_survival_time_,
                 "surv_5y": k.survival_function_at_times(5).values[0], "surv_5y_lo95": ci.iloc[0], "surv_5y_hi95": ci.iloc[1]})
region_km = pd.DataFrame(rows)
region_km.to_csv(OUT_DIR / "4c_지역x업종_KM.csv", index=False, encoding="utf-8-sig")
print(f"\n지역x업종 KM: {len(region_km)}개 그룹(사업장>={MIN_N}, 폐업>={MIN_EVENT}) 저장 -> output/4c_지역x업종_KM.csv")
big = region_km[region_km["n"] >= 100].sort_values("surv_5y")
print("\n5년 생존율 최저 10개 (사업장>=100, 95% CI 포함):")
print(big.head(10)[["SIDO_NM", "CCG_NM", "bc_업종", "n", "n_event", "surv_5y", "surv_5y_lo95", "surv_5y_hi95"]].round(3).to_string(index=False))
print("\n5년 생존율 최고 10개:")
print(big.tail(10)[["SIDO_NM", "CCG_NM", "bc_업종", "n", "n_event", "surv_5y", "surv_5y_lo95", "surv_5y_hi95"]].round(3).to_string(index=False))
print("\n업종별 지역간 5년 생존율 범위:\n", big.groupby("bc_업종")["surv_5y"].agg(["min", "median", "max"]).round(3))

# ============================================
# 개업 코호트별 5년 생존율 — 전체 이력을 한 곡선에 합치면 시대(경기·코로나·임대료 등) 차이가 섞인다
# ============================================
# 5년을 관측하려면 개업 후 5년이 지났어야 하므로 2021년 이전 개업만 본다. 이 KM은 '역사적 pooled 생존'이지 2026년 신규 사업장의 예상 생존이 아니다.
sub_all = sub_all.assign(open_year=sub_all["인허가일자"].dt.year)
sub_all["cohort"] = pd.cut(sub_all["open_year"], [1949, 1999, 2004, 2009, 2014, 2021], labels=["~1999", "2000-04", "2005-09", "2010-14", "2015-21"])
crow = []
for (biz, coh), sub in sub_all.groupby(["bc_업종", "cohort"], observed=True):
    k = KaplanMeierFitter().fit(sub["duration_years"], sub["event_observed"])
    crow.append({"bc_업종": biz, "cohort": coh, "n": len(sub), "surv_5y": k.survival_function_at_times(5).values[0]})
cohort_km = pd.DataFrame(crow).pivot(index="bc_업종", columns="cohort", values="surv_5y").round(3)
cohort_km.to_csv(OUT_DIR / "4d_개업코호트별_5년생존율.csv", encoding="utf-8-sig")
print("\n개업 코호트별 5년 생존율:\n", cohort_km.to_string())

# ============================================
# 별도 취급 업종(대형할인점·슈퍼마켓) — 전체 이력 KM으로만 본다
# ============================================
# 2026년 폐업이 각각 14건·9건뿐이라 생존모델(Cox/RSF)은 돌리지 않는다(CHANGELOG ⑫). 폐업 이력 자체는 114건·210건이라 KM은 가능하다.
# 주의: BC카드 공변량과는 연결하지 않는다(BC는 2026년 6개월뿐). 슈퍼마켓은 LOCALDATA에 SSM 체인만 있어 BC 슈퍼마켓 소비(대부분 개인슈퍼)와
# 대상이 다르다. 대규모점포의 '직권취소' 등은 event=0(censored)이라 실제 폐업 이력이 소폭 과소 집계될 수 있다.
special_biz = ["대형할인점", "슈퍼마켓"]
fig2, ax2 = plt.subplots(figsize=(9, 6))
srows = []
for biz in special_biz:
    sub = df[df["bc_업종"] == biz]
    k = KaplanMeierFitter().fit(sub["duration_years"], sub["event_observed"], label=biz)
    k.plot_survival_function(ax=ax2)
    srows.append({"bc_업종": biz, "n": len(sub), "n_event": int(sub["event_observed"].sum()),
                  "median_surv_years": k.median_survival_time_,
                  "surv_5y": k.survival_function_at_times(5).values[0], "surv_10y": k.survival_function_at_times(10).values[0]})
ax2.set_xlabel("영업 기간(년)")
ax2.set_ylabel("생존확률")
ax2.set_title("대형할인점·슈퍼마켓 Kaplan-Meier (전체 이력, 생존모델 제외 업종)")
fig2.tight_layout()
fig2.savefig(OUT_DIR / "4e_대형할인점_슈퍼마켓_KM.png", dpi=120)
special = pd.DataFrame(srows)
special.to_csv(OUT_DIR / "4e_대형할인점_슈퍼마켓_KM_요약.csv", index=False, encoding="utf-8-sig")
print("\n대형할인점·슈퍼마켓 KM(전체 이력, 생존모델 제외 업종):\n", special.round(3).to_string(index=False))
