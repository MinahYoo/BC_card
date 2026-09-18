import pandas as pd
import re
from pathlib import Path

DATA_DIR = Path("data")

# ============================================
# 0. 상수
# ============================================
VALID_SIDO = {
    '서울특별시', '부산광역시', '대구광역시', '인천광역시', '광주광역시',
    '대전광역시', '울산광역시', '세종특별자치시', '경기도',
    '강원특별자치도', '강원도', '충청북도', '충청남도',
    '전북특별자치도', '전라북도', '전라남도', '경상북도', '경상남도',
    '제주특별자치도',
    '전남광주통합특별시',  # 원본 데이터에 실존하는 표기 — 아래 fix_region()에서 ABP 기준(전라남도/광주광역시)으로 분리
}

# 전남광주통합특별시 하위 CCG_NM 중 옛 광주광역시 5개 구 — 나머지는 전부 옛 전라남도 시/군
GWANGJU_GU = {'광산구', '서구', '북구', '동구', '남구'}

# 인천 행정구역 개편(신설구) → ABP(2026 상반기 스냅샷)가 쓰는 개편 이전 구명
# 출처: 공개된 개편 계획 기준 — 팀에서 한 번 더 교차확인 권장
INCHEON_CROSSWALK = {
    '검단구': '서구',
    '서해구': '서구',
    '영종구': '중구',
    '제물포구': '미추홀구',
}

# 일반구를 가진 시 — 주소 3번째 토큰(구)을 CCG_NM에 합쳐줘야 ABP(SIDO_NM,CCG_NM) 포맷과 일치
GU_PATTERN = re.compile(r'^[가-힣]{1,5}구$')


# ---- 유틸: 주소에서 시도/시군구 추출, 업종명 정규화
def parse_area(addr):
    """주소 문자열 1개에서 (SIDO_NM, CCG_NM)을 뽑는다. 파싱 실패(유효 시도 아님)면 None."""
    if pd.isna(addr):
        return None
    parts = re.split(r'\s+', str(addr).strip())
    if len(parts) < 2:
        return None
    sido, ccg = parts[0], parts[1]
    if sido not in VALID_SIDO:
        return None
    # 구가 있는 시(예: "경기도 수원시 영통구 ...") 대응 — 3번째 토큰이 구면 CCG_NM에 합침
    if len(parts) >= 3 and ccg.endswith('시') and GU_PATTERN.match(parts[2]):
        ccg = f'{ccg} {parts[2]}'
    return (sido, ccg)


def get_area_row(row):
    """지번주소 → 도로명주소 순으로 실제로 유효하게 파싱되는 쪽을 채택한다.
    (기존 버그: 첫 값이 비어있지 않기만 하면 채택해서, 지번주소가 '68-5 68동 8호'처럼
    시도명 없이 잘려 있어도 그대로 SIDO_NM='68-5' 같은 쓰레기값이 나왔음)
    """
    for col in ('지번주소', '도로명주소'):
        if col in row and pd.notna(row[col]):
            r = parse_area(row[col])
            if r:
                return r
    return (None, None)


def fix_region(sido, ccg):
    """LOCALDATA(최신 행정구역) → ABP(2026 상반기 스냅샷 기준 구명)로 정합."""
    if sido == '전남광주통합특별시':
        if ccg in GWANGJU_GU:
            return '광주광역시', ccg
        return '전라남도', ccg
    if sido == '인천광역시' and ccg in INCHEON_CROSSWALK:
        return sido, INCHEON_CROSSWALK[ccg]
    if sido == '세종특별자치시':
        # ABP는 세종시를 구/읍면동 구분 없이 SIDO_NM 자체를 CCG_NM으로 씀
        return sido, sido
    return sido, ccg


def clean_tp_buz_nm(s: str):
    if pd.isna(s):
        return s
    t = re.sub(r"\s+", "", str(s))
    tl = t.lower()
    if '편의' in tl:
        return '편의점'
    if '슈퍼' in tl or '슈퍼마켓' in tl or 'ssm' in tl:
        return '슈퍼마켓'
    if '제과' in tl or '빵' in tl or '도넛' in tl or '아이스크림' in tl:
        return '제과점'
    if '대형' in tl or '마트' in tl:
        return '대형할인점'
    return t


# ============================================
# 1. 데이터 로드
# ============================================
base_cols = ['관리번호', '인허가일자', '폐업일자', '영업상태명', '업태구분명',
             '사업장명', '도로명주소', '지번주소', '좌표정보(X)', '좌표정보(Y)']

df_general = pd.read_csv(DATA_DIR / '식품_일반음식점.csv', encoding='cp949', low_memory=False)[base_cols]
df_bakery = pd.read_csv(DATA_DIR / '식품_제과점영업.csv', encoding='cp949', low_memory=False)[base_cols]
df_rest = pd.read_csv(DATA_DIR / '식품_휴게음식점.csv', encoding='cp949', low_memory=False)[base_cols]
df_large = pd.read_csv(DATA_DIR / '생활_대규모점포.csv', encoding='cp949', low_memory=False)

print("로드 완료:", len(df_general), len(df_bakery), len(df_rest), len(df_large))

# ============================================
# 2. 업종 매핑
# ============================================
mapping_general = {
    '한식': '한식계열',
    '식육(숯불구이)': '한식계열',   # 추가 — 갈비전문점 대응
    '뷔페식': '한식계열',           # 추가 — BC카드 키워드에 "부페/뷔페" 명시
    '냉면집': '한식계열',           # 추가 — BC카드 키워드에 "냉면" 명시
    '일식': '일식회집', '횟집': '일식회집',
    '중국식': '중국음식',
    '경양식': '서양음식', '까페': '서양음식', '패스트푸드': '서양음식',
    '패밀리레스트랑': '서양음식', '외국음식전문점(인도,태국등)': '서양음식',
    '분식': '스넥', '김밥(도시락)': '스넥',
}

mapping_bakery = {
    '제과점영업': '제과점',
}

mapping_rest = {
    '커피숍': '서양음식', '다방': '서양음식', '전통찻집': '서양음식',
    '떡카페': '서양음식', '까페': '서양음식', '패스트푸드': '서양음식',
    '과자점': '제과점', '아이스크림': '제과점',
    '분식': '스넥', '김밥(도시락)': '스넥',
    '편의점': '편의점',
}

df_general['bc_업종'] = df_general['업태구분명'].map(mapping_general)
df_bakery['bc_업종'] = df_bakery['업태구분명'].map(mapping_bakery)
df_rest['bc_업종'] = df_rest['업태구분명'].map(mapping_rest)

# 대규모점포 (대형할인점 + SSM 슈퍼마켓)
ssm_keywords = r'지에스리테일|GS더프레시|에브리데이리테일|롯데슈퍼|홈플러스\s?익스프레스|이마트에브리데이'

df_large['bc_업종'] = None
df_large.loc[df_large['업태구분명'] == '대형마트', 'bc_업종'] = '대형할인점'
df_large.loc[df_large['사업장명'].str.contains(ssm_keywords, na=False, regex=True), 'bc_업종'] = '슈퍼마켓'

# ============================================
# 2b. 주소에서 SIDO/CCG 추출(수정판) + 지역명 크로스워크 + 업태명 정규화
# ============================================
for _df in (df_general, df_bakery, df_rest, df_large):
    areas = _df.apply(get_area_row, axis=1, result_type='expand')
    areas.columns = ['SIDO_NM', 'CCG_NM']
    fixed = areas.apply(lambda r: fix_region(r['SIDO_NM'], r['CCG_NM']) if pd.notna(r['SIDO_NM']) else (None, None),
                         axis=1, result_type='expand')
    fixed.columns = ['SIDO_NM', 'CCG_NM']
    _df['SIDO_NM'] = fixed['SIDO_NM']
    _df['CCG_NM'] = fixed['CCG_NM']

    if '업태구분명' in _df.columns:
        _df['업태구분명_clean'] = _df['업태구분명'].map(clean_tp_buz_nm)
    if '사업장명' in _df.columns:
        _df['사업장명_clean'] = _df['사업장명'].map(clean_tp_buz_nm)

# 주소 파싱 실패율 리포트
for name, _df in (('일반음식점', df_general), ('제과점', df_bakery), ('휴게음식점', df_rest), ('대규모점포', df_large)):
    fail = _df['SIDO_NM'].isna().sum()
    print(f"[{name}] 주소 파싱 실패: {fail}행 / {len(_df)}행 ({fail / len(_df) * 100:.3f}%)")

# ============================================
# 3. 통합 (컬럼 존재 확인 후 진행)
# ============================================
large_cols_present = [c for c in base_cols if c in df_large.columns]
missing = set(base_cols) - set(large_cols_present)
if missing:
    print(f"⚠ 대규모점포 파일에 없는 컬럼: {missing} — 아래서 확인 후 매핑 필요")

merge_cols = base_cols + ['bc_업종', 'SIDO_NM', 'CCG_NM']

df_large_mapped = df_large[df_large['bc_업종'].notna()]

combined = pd.concat([
    df_general[df_general['bc_업종'].notna()][merge_cols],
    df_bakery[df_bakery['bc_업종'].notna()][merge_cols],
    df_rest[df_rest['bc_업종'].notna()][merge_cols],
    df_large_mapped[large_cols_present + ['bc_업종']],
], ignore_index=True)

print("\n=== 최종 bc_업종별 건수 ===")
print(combined['bc_업종'].value_counts())
print("\n전체 행 수:", len(combined))

# ============================================
# 4. 날짜 처리 + 극단치 필터링
# ============================================
combined['인허가일자'] = pd.to_datetime(combined['인허가일자'], errors='coerce')
combined['폐업일자'] = pd.to_datetime(combined['폐업일자'], errors='coerce')

before = len(combined)
combined = combined[combined['인허가일자'] >= '1950-01-01']
print(f"\n인허가일자<1950 필터: {before - len(combined)}행 제거")

# 폐업일자가 인허가일자보다 빠른 논리 오류 건 플래그(제거하지 않고 표시만 — 필요시 별도 처리)
bad_order = combined['폐업일자'].notna() & (combined['폐업일자'] < combined['인허가일자'])
print(f"폐업일자 < 인허가일자 (논리 오류 의심): {bad_order.sum()}행")

# 영업상태명 분포 — event_observed 정의 근거로 명시
print("\n=== 영업상태명 분포 (event_observed 기준: '폐업'만 1, 나머지는 censored) ===")
print(combined['영업상태명'].value_counts())
combined['event_observed'] = (combined['영업상태명'] == '폐업').astype(int)

print("\n필터링 후 행 수:", len(combined))

# ============================================
# 5. 저장
# ============================================
out_path = DATA_DIR / 'localdata_clean.csv'
combined.to_csv(out_path, index=False, encoding='utf-8-sig')
print(f"\n저장 완료: {out_path}")
