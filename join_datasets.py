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
# 2. BC카드 → 지역×업종 단위 공변량으로 집계
# ============================================
# GENDER_CD='x'/AGE_CD='x'는 소규모셀 마스킹으로 성별·연령 breakdown이 비공개 처리된 행
# (금액 자체는 존재) — 합계에는 포함하되, 성별/연령 구성비 계산에서는 제외한다.
totals = bc.groupby(JOIN_KEY, as_index=False)[['amt', 'cnt']].sum()
totals = totals.rename(columns={'amt': 'bc_amt_total', 'cnt': 'bc_cnt_total'})

demo = bc[(bc['GENDER_CD'] != 'x') & (bc['AGE_CD'] != 'x')].copy()
masked_n = len(bc) - len(demo)
print(f"성별/연령 마스킹('x') 행: {masked_n} / {len(bc)} ({masked_n / len(bc) * 100:.1f}%) — 구성비 계산에서 제외, 합계에는 포함")

# 지역×업종 내 성별 구성비
gender_amt = demo.groupby(JOIN_KEY + ['GENDER_CD'])['amt'].sum().unstack('GENDER_CD', fill_value=0)
gender_share = gender_amt.div(gender_amt.sum(axis=1), axis=0).add_prefix('amt_share_gender_')

# 지역×업종 내 연령 구성비
age_amt = demo.groupby(JOIN_KEY + ['AGE_CD'])['amt'].sum().unstack('AGE_CD', fill_value=0)
age_share = age_amt.div(age_amt.sum(axis=1), axis=0).add_prefix('amt_share_age_')

bc_covariates = totals.merge(gender_share, on=JOIN_KEY, how='left').merge(age_share, on=JOIN_KEY, how='left')
print("\nBC카드 지역×업종 공변량 테이블:", len(bc_covariates), "개 키")

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
