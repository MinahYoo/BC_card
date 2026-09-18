import pandas as pd
import re
from pathlib import Path

DATA_DIR = Path("data")

# LOCALDATA 쪽(preprocess_localdata.py)의 bc_업종 값과 동일한 taxonomy로 맞춘다.
# ABP 원본은 일반한식/갈비전문점/한정식을 분리해서 주지만, LOCALDATA 인허가데이터는
# "한식" 단일 카테고리로만 존재해 분리가 불가능하므로(README 참고) 여기서도 통합한다.
TP_BUZ_MAP = {
    '일반한식': '한식계열', '갈비전문점': '한식계열', '한정식': '한식계열',
    '일식회집': '일식회집',
    '중국음식': '중국음식',
    '서양음식': '서양음식',
    '스넥': '스넥',
    '제과점': '제과점',
    '편의점': '편의점',
    '대형할인점': '대형할인점',
    '슈퍼마켓': '슈퍼마켓',
}


def normalize_ws(s):
    if pd.isna(s):
        return s
    return re.sub(r'\s+', '', str(s)).strip()


# ============================================
# 1. 로드
# ============================================
df = pd.read_csv(DATA_DIR / 'ABP_CONTEST_DATA.csv', encoding='utf-8', low_memory=False)
print("로드 완료:", len(df))
print("원본 TP_BUZ_NM 값:", sorted(df['TP_BUZ_NM'].unique().tolist()))

# ============================================
# 2. 정제
# ============================================
# TP_BUZ_NM 공백 제거("편 의 점" -> "편의점") 후 통합 업종(bc_업종)으로 매핑
df['TP_BUZ_NM_clean'] = df['TP_BUZ_NM'].map(normalize_ws)
df['bc_업종'] = df['TP_BUZ_NM_clean'].map(TP_BUZ_MAP)

unmapped = df[df['bc_업종'].isna()]
if len(unmapped):
    print(f"\n⚠ 매핑 안 된 TP_BUZ_NM: {unmapped['TP_BUZ_NM_clean'].unique().tolist()} ({len(unmapped)}행)")

# SIDO_NM/CCG_NM 공백 정리(연속 공백 -> 1칸)만, 값 자체는 LOCALDATA와 이미 동일 체계 확인됨
df['SIDO_NM'] = df['SIDO_NM'].str.strip()
df['CCG_NM'] = df['CCG_NM'].str.replace(r'\s+', ' ', regex=True).str.strip()

print("\n=== 정제 후 bc_업종별 건수 ===")
print(df['bc_업종'].value_counts())

# ============================================
# 3. 저장
# ============================================
out_cols = ['STRD_YYMM', 'SIDO_NM', 'CCG_NM', 'GENDER_CD', 'AGE_CD', 'bc_업종', 'amt', 'cnt']
out_path = DATA_DIR / 'bc_clean.csv'
df[out_cols].to_csv(out_path, index=False, encoding='utf-8-sig')
print(f"\n저장 완료: {out_path} ({len(df)}행)")
