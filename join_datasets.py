import pandas as pd
from pathlib import Path

DATA_DIR = Path("data")
JOIN_KEY = ['SIDO_NM', 'CCG_NM', 'bc_업종']

# ============================================
# 1. 로드
# ============================================
localdata = pd.read_csv(DATA_DIR / 'localdata_clean.csv', encoding='utf-8-sig', low_memory=False)
bc = pd.read_csv(DATA_DIR / 'bc_clean.csv', encoding='utf-8-sig', dtype={'GENDER_CD': str, 'AGE_CD': str})

print("LOCALDATA(생존분석 관측단위):", len(localdata), "행")
print("BC카드(공변량 소스):", len(bc), "행")

# ============================================
# 1b. 인천 제물포구 합성 공변량 추가
# ============================================
# 제물포구(2026-07-01 신설)는 ABP 스냅샷 시점에는 없던 구명으로, (구)중구+(구)동구가
# 통합된 것이다(미추홀구와는 무관 — CHANGELOG/EDA에서 잘못된 크로스워크였음을 확인, 8,491행 영향).
# ABP는 이 통합을 모르므로 중구/동구 데이터를 그대로 갖고 있다 -> 여기서 두 구를 합산해
# '제물포구' 키의 합성 행을 만들어 bc(원본 amt/cnt 단위)에 추가한다.
jemulpo_src = bc[(bc['SIDO_NM'] == '인천광역시') & (bc['CCG_NM'].isin(['중구', '동구']))].copy()
if not jemulpo_src.empty:
    jemulpo_src['CCG_NM'] = '제물포구'
    bc = pd.concat([bc, jemulpo_src], ignore_index=True)
    print(f"\n인천 제물포구 합성 공변량: 중구+동구 {len(jemulpo_src)}행을 'CCG_NM=제물포구'로 복제 추가")

# ============================================
# 2. BC카드 → 지역×업종 단위 공변량으로 집계
# ============================================
# GENDER_CD='x'/AGE_CD='x'는 소규모셀 마스킹으로 성별·연령 breakdown이 비공개 처리된 행
# (금액 자체는 존재) — 합계에는 포함하되, 성별/연령 구성비 계산에서는 제외한다.
# 주의: 성별과 연령은 독립적으로 마스킹되므로 각자 따로 필터링한다(둘 다 공개된 행만 쓰면,
# 예: 성별은 공개(x아님)인데 연령만 마스킹된 행이 성별 구성비 계산에서도 불필요하게 빠짐).
totals = bc.groupby(JOIN_KEY, as_index=False)[['amt', 'cnt']].sum()
totals = totals.rename(columns={'amt': 'bc_amt_total', 'cnt': 'bc_cnt_total'})

gender_demo = bc[bc['GENDER_CD'] != 'x'].copy()
age_demo = bc[bc['AGE_CD'] != 'x'].copy()
print(f"성별 마스킹('x') 행: {len(bc)-len(gender_demo)} / {len(bc)} — 성별 구성비 계산에서 제외")
print(f"연령 마스킹('x') 행: {len(bc)-len(age_demo)} / {len(bc)} — 연령 구성비 계산에서 제외 (합계에는 둘 다 포함)")

# 지역×업종 내 성별 구성비
gender_amt = gender_demo.groupby(JOIN_KEY + ['GENDER_CD'])['amt'].sum().unstack('GENDER_CD', fill_value=0)
gender_share = gender_amt.div(gender_amt.sum(axis=1), axis=0).add_prefix('amt_share_gender_')

# 지역×업종 내 연령 구성비
age_amt = age_demo.groupby(JOIN_KEY + ['AGE_CD'])['amt'].sum().unstack('AGE_CD', fill_value=0)
age_share = age_amt.div(age_amt.sum(axis=1), axis=0).add_prefix('amt_share_age_')

bc_covariates = totals.merge(gender_share, on=JOIN_KEY, how='left').merge(age_share, on=JOIN_KEY, how='left')
print("\nBC카드 지역×업종 공변량 테이블:", len(bc_covariates), "개 키")

# ============================================
# 2b. BC카드 월별 변화량 (기존에는 6개월을 합쳐 flat total만 썼음 — 추세 정보 손실)
# ============================================
import numpy as np

monthly = bc.groupby(JOIN_KEY + ['STRD_YYMM'], as_index=False)['amt'].sum()


def trend_stats(g):
    g = g.sort_values('STRD_YYMM')
    y = g['amt'].to_numpy(dtype=float)
    if len(y) < 2 or y.mean() == 0:
        return pd.Series({'bc_amt_trend_slope': 0.0, 'bc_amt_cv': 0.0, 'bc_amt_growth_ratio': np.nan})
    # STRD_YYMM(202601~202606)에서 실제 월 간격을 index로 사용 — 관측행 순서(arange)가 아님.
    # 이번 데이터는 6개월 모두 항상 존재해 arange와 결과가 같지만, 향후 특정 월이 소규모셀
    # 마스킹 등으로 누락되는 경우에도 slope가 왜곡되지 않도록 방어.
    x = g['STRD_YYMM'].astype(int).to_numpy()
    x = x - x.min()
    slope = np.polyfit(x, y, 1)[0] / y.mean() if len(np.unique(x)) >= 2 else 0.0  # 월평균 대비 정규화된 증감 slope
    cv = y.std() / y.mean()  # 변동성(월별 매출 기복)
    growth_ratio = y[-1] / y[0] if y[0] > 0 else np.nan  # 마지막달/첫달 (성장중인지 축소중인지)
    return pd.Series({'bc_amt_trend_slope': slope, 'bc_amt_cv': cv, 'bc_amt_growth_ratio': growth_ratio})


trend = monthly.groupby(JOIN_KEY).apply(trend_stats, include_groups=False).reset_index()
bc_covariates = bc_covariates.merge(trend, on=JOIN_KEY, how='left')
print("BC카드 월별 변화량(trend_slope/cv/growth_ratio) 추가 완료")

# ============================================
# 3. LOCALDATA(row 단위 유지) <- BC카드 공변량 LEFT JOIN
# ============================================
joined = localdata.merge(bc_covariates, on=JOIN_KEY, how='left', indicator=True)

matched = (joined['_merge'] == 'both').sum()
unmatched = (joined['_merge'] == 'left_only').sum()
print(f"\n=== 조인 매칭률 ===")
print(f"매칭: {matched}행 ({matched / len(joined) * 100:.2f}%)")
print(f"미매칭: {unmatched}행 ({unmatched / len(joined) * 100:.2f}%)")

if unmatched:
    unmatched_rows = joined[joined['_merge'] == 'left_only']
    print("\n미매칭 상위 (SIDO_NM, CCG_NM, bc_업종) 조합 (건수순):")
    print(unmatched_rows.groupby(JOIN_KEY).size().sort_values(ascending=False).head(20))

joined = joined.drop(columns=['_merge'])

# ============================================
# 3b. BC카드 관측기간(2026-01~06)과 겹치는 사업장만 표시하는 코호트 플래그
# ============================================
# ABP는 2026년 상반기 6개월 스냅샷 하나뿐 — 그 이전에 이미 폐업한 사업장에
# 2026년 상반기 소비 패턴을 설명변수로 붙이면 시점이 맞지 않는다(사건이 공변량보다 과거).
# 행을 삭제하지 않고 플래그만 남겨서, 3단계(Cox/RSF, BC카드 공변량 사용)에서는 True만
# 쓰고, BC카드 없이 하는 순수 LOCALDATA 장기 트렌드/KM 분석에서는 전체를 그대로 쓴다.
BC_WINDOW_START = pd.Timestamp('2026-01-01')
BC_WINDOW_END = pd.Timestamp('2026-06-30')

joined['인허가일자'] = pd.to_datetime(joined['인허가일자'], errors='coerce')
joined['폐업일자'] = pd.to_datetime(joined['폐업일자'], errors='coerce')

joined['in_bc_window'] = (joined['인허가일자'] <= BC_WINDOW_END) & (
    joined['폐업일자'].isna() | (joined['폐업일자'] >= BC_WINDOW_START)
)

n_in = joined['in_bc_window'].sum()
print(f"\n=== BC카드 관측기간(2026-01~06) 코호트 ===")
print(f"기간 겹침(in_bc_window=True): {n_in}행 ({n_in / len(joined) * 100:.1f}%) — 3단계 Cox/RSF 대상")
print(f"기간 이전 폐업(in_bc_window=False): {len(joined) - n_in}행 ({(len(joined) - n_in) / len(joined) * 100:.1f}%) — BC카드 공변량 없이 장기 트렌드용으로만 사용")

# ============================================
# 4. 저장
# ============================================
out_path = DATA_DIR / 'final_joined.csv'
joined.to_csv(out_path, index=False, encoding='utf-8-sig')
print(f"\n저장 완료: {out_path} ({len(joined)}행, {len(joined.columns)}컬럼)")
