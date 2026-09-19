import pandas as pd
import numpy as np
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

# 시도명 신/구 표기 별칭 -> ABP가 쓰는 표기로 통일 (현재 원본엔 신 표기만 있어 실사용 영향 없지만
# 향후 데이터 갱신 시 구 표기가 섞여 들어와도 미매칭이 안 나도록 방어)
SIDO_ALIAS = {'강원도': '강원특별자치도', '전라북도': '전북특별자치도'}

# 인천 행정구역 개편(신설구) → ABP(2026 상반기 스냅샷)가 쓰는 개편 이전 구명
# 출처: 인천광역시 공식 발표(incheon.go.kr) 및 관련 법률(《인천광역시 서구 명칭 변경에
# 관한 법률》,《인천광역시 제물포구·영종구 및 검단구 설치 등에 관한 법률》, 2026-07-01 시행) 교차확인 완료.
#   - 검단구, 서해구  <- (구)서구 분리 (경인아라뱃길 기준 북부=검단구, 나머지=서해구 개칭)
#   - 영종구          <- (구)중구의 섬 지역(영종도)만 분리
#   - 제물포구        <- (구)중구(내륙) + (구)동구 통합 신설
# 제물포구는 두 구가 합쳐진 것이라 단일 구명으로 되돌릴 수 없음(미추홀구와는 무관한 별개 구
# — 원래 코드가 '제물포구'->'미추홀구'로 잘못 매핑하고 있었음, 8,491행 오염 확인 후 수정).
# 제물포구는 crosswalk에서 변환하지 않고 그대로 두고, join_datasets.py에서 ABP의
# 중구+동구 데이터를 합산한 합성 공변량으로 별도 매칭한다.
INCHEON_CROSSWALK = {
    '검단구': '서구',
    '서해구': '서구',
    '영종구': '중구',
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
    sido = SIDO_ALIAS.get(sido, sido)
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

# 매핑 전 업태구분명 공백만 제거해서 정규화(표기차이로 인한 미매핑 방지).
# 주의: clean_tp_buz_nm()은 재사용하지 않는다 — 그 함수는 '제과점영업'->'제과점',
# '아이스크림'->'제과점'처럼 내용을 바꿔버려서, 매핑 딕셔너리 키('제과점영업','아이스크림')와
# 어긋나 해당 행 전체가 매핑 실패로 사라지는 회귀 버그를 만든다.
def _strip_ws(s):
    return re.sub(r'\s+', '', str(s)) if pd.notna(s) else s


df_general['업태구분명_norm'] = df_general['업태구분명'].map(_strip_ws)
df_bakery['업태구분명_norm'] = df_bakery['업태구분명'].map(_strip_ws)
df_rest['업태구분명_norm'] = df_rest['업태구분명'].map(_strip_ws)

df_general['bc_업종'] = df_general['업태구분명_norm'].map(mapping_general)
df_bakery['bc_업종'] = df_bakery['업태구분명_norm'].map(mapping_bakery)
df_rest['bc_업종'] = df_rest['업태구분명_norm'].map(mapping_rest)

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

# 버그: 여기서 SIDO_NM/CCG_NM을 빼먹으면 대형할인점/슈퍼마켓 1,359행 전부 지역키가 NaN이 되어
# BC카드와 절대 매칭될 수 없었음(EDA의 미매칭 'NaN/NaN' 원인 — 주소파싱 실패가 아니라 이 누락이었음).
combined = pd.concat([
    df_general[df_general['bc_업종'].notna()][merge_cols],
    df_bakery[df_bakery['bc_업종'].notna()][merge_cols],
    df_rest[df_rest['bc_업종'].notna()][merge_cols],
    df_large_mapped[large_cols_present + ['bc_업종', 'SIDO_NM', 'CCG_NM']],
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

# 영업상태명 분포 — event_observed 정의 근거로 명시
print("\n=== 영업상태명 분포 (event_observed 기준: '폐업'만 1, 나머지는 censored) ===")
print(combined['영업상태명'].value_counts())
combined['event_observed'] = (combined['영업상태명'] == '폐업').astype(int)

# 날짜 정합성 문제(둘 다 배제 — 신뢰 가능한 종료일이 없으면 duration을 계산할 수 없음):
#   (a) 폐업일자 < 인허가일자 논리 오류
#   (b) event_observed==1(폐업)인데 폐업일자가 결측 -> 그동안 fillna(CUTOFF)로 채워져
#       "아직 생존중"처럼 계산되고 있었음(실제로는 폐업했는데 censored로 취급되는 오류)
bad_order = combined['폐업일자'].notna() & (combined['폐업일자'] < combined['인허가일자'])
event_missing_date = (combined['event_observed'] == 1) & combined['폐업일자'].isna()
bad = bad_order | event_missing_date
print(f"\n날짜 정합성 문제로 제외: 순서오류 {bad_order.sum()}행 + 폐업인데 폐업일자 결측 {event_missing_date.sum()}행"
      f" = 총 {bad.sum()}행 ({bad.sum()/len(combined)*100:.4f}%)")
combined = combined[~bad]

print("\n필터링 후 행 수:", len(combined))

# ============================================
# 4b. 가게 개별 특성 (기존엔 지역x업종 단위 공변량만 있고 개별 가게 특성이 전혀 없었음
#     -> Cox/RSF concordance가 낮았던 원인 중 하나. 프랜차이즈 여부 + 입지(중심가/골목) 추가)
# ============================================
FRANCHISE_KEYWORDS = [
    'CU', 'GS25', 'GS리테일', '세븐일레븐', '이마트24', '미니스톱', '씨스페이스',
    '파리바게뜯', '파리바게트', '뚜레쥬르', '던킨', '배스킨라빈스', '크리스피',
    '스타벅스', '이디야', '투썸', '메가mgc', '메가MGC', '컴포즈', '빽다방', '커피빈', '할리스',
    '맘스터치', '롯데리아', '맥도날드', '버거킹', 'KFC', '써브웨이',
    '김가네', '바르다김선생', '홍콩반점', '교촌', 'BBQ', '굽네',
]
_franchise_pat = '|'.join(pd.Series(FRANCHISE_KEYWORDS).str.replace(r'([\[\](){}.*+?^$|\\])', r'\\\1', regex=True))
combined['사업장명'] = combined['사업장명'].fillna('')
combined['is_franchise'] = combined['사업장명'].str.contains(_franchise_pat, case=False, regex=True, na=False).astype(int)
print(f"\n프랜차이즈 키워드 매칭: {combined['is_franchise'].sum()}행 ({combined['is_franchise'].mean()*100:.2f}%)")

# 입지: 같은 (SIDO_NM,CCG_NM) 안에서 좌표 중심점(centroid)까지의 거리(m) — 중심가/골목 상권 구분 proxy
coords_valid = combined['좌표정보(X)'].notna() & combined['좌표정보(Y)'].notna()
centroid = (
    combined.loc[coords_valid]
    .groupby(['SIDO_NM', 'CCG_NM'])[['좌표정보(X)', '좌표정보(Y)']]
    .transform('mean')
)
dist = np.sqrt((combined.loc[coords_valid, '좌표정보(X)'] - centroid['좌표정보(X)']) ** 2 +
               (combined.loc[coords_valid, '좌표정보(Y)'] - centroid['좌표정보(Y)']) ** 2)
combined['dist_to_region_centroid_m'] = np.nan
combined.loc[coords_valid, 'dist_to_region_centroid_m'] = dist
print(f"입지(중심점 거리) 계산: {coords_valid.sum()}행 ({coords_valid.mean()*100:.1f}%), "
      f"결측(좌표없음)은 NaN으로 남김")

# ============================================
# 5. 저장
# ============================================
out_path = DATA_DIR / 'localdata_clean.csv'
combined.to_csv(out_path, index=False, encoding='utf-8-sig')
print(f"\n저장 완료: {out_path}")
