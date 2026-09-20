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
# 출처(팀원 브랜치에서 교차확인 완료): 인천광역시 공식 발표 및 관련 법률(2026-07-01 시행).
#   - 검단구, 서해구 <- (구)서구 분리 / 영종구 <- (구)중구의 섬 지역(영종도)만 분리 / 제물포구 <- (구)중구(내륙)+(구)동구 통합 신설
# 검단구·서해구·영종구는 기존 구에서 분리된 신설구라 옛 이름으로 단순 대응 가능.
# 제물포구는 여기 넣지 않는다 — 2026-07-01 (구)중구+(구)동구 "통합"으로 신설된 구라
# ABP 쪽 어느 한 구에도 대응되지 않음(미추홀구와는 무관, 팀원이 확인). 이 경우는 단순
# 이름 매핑이 아니라 join_datasets.py에서 중구+동구 BC카드 데이터를 합산한 합성 행으로 처리.
INCHEON_CROSSWALK = {
    '검단구': '서구',
    '서해구': '서구',
    '영종구': '중구',
}

# 시도명 신/구 표기 별칭 -> ABP가 쓰는 표기로 통일(현재 원본엔 신 표기만 있어 영향 없음, 향후 갱신 대비 방어. 팀원 브랜치와 동일)
SIDO_ALIAS = {'강원도': '강원특별자치도', '전라북도': '전북특별자치도'}

# 일반구를 가진 시 — 주소 3번째 토큰(구)을 CCG_NM에 합쳐줘야 ABP(SIDO_NM,CCG_NM) 포맷과 일치
GU_PATTERN = re.compile(r'^[가-힣]{1,5}구$')
# 대규모점포 원본 주소엔 시와 구가 공백 없이 붙은 표기가 있다("성남시분당구", "고양시일산동구", "부천시소사구괴안동")
GLUED_CITY_GU = re.compile(r'^([가-힣]{1,4}시)([가-힣]{1,5}?구)')


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
    # 공백 없이 붙은 시+구(예: "성남시분당구", "부천시소사구괴안동") -> "성남시 분당구"
    glued = GLUED_CITY_GU.match(ccg)
    if glued:
        ccg = f'{glued.group(1)} {glued.group(2)}'
    # 구가 있는 시(예: "경기도 수원시 영통구 ...") 대응 — 3번째 토큰이 구면 CCG_NM에 합침
    elif len(parts) >= 3 and ccg.endswith('시') and GU_PATTERN.match(parts[2]):
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
    if sido == '인천광역시' and ccg == '남구':
        # 인천 남구는 2018년 미추홀구로 개칭됨 — 옛 주소가 남은 행. ABP는 미추홀구를 씀
        return sido, '미추홀구'
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
# 컬럼을 사람이 골라서 들고 오지 않는다. 아래 "규칙 기반 제외" 목록에 든 것만 빼고 원본 컬럼을 전부 로드해서
# 정제한 뒤(3c), EDA로 모델에 쓸 컬럼을 고른다(SELECTED_COLS). 제외 근거는 CHANGELOG ⑨ 참고.
DROP_COLS = {
    # 죽은 컬럼: 커버리지 약 1.5% 이하 + 상수/전부 0
    '월세액', '보증액', '본사직원수', '공장사무직직원수', '공장판매직직원수', '공장생산직직원수',
    '전통업소지정번호', '전통업소주된음식', '건물소유구분명', '홈페이지',
    # 중복: 다른 컬럼과 정보가 같음(위생업태명==업태구분명 99.99%, 코드==명)
    '위생업태명', '영업상태코드', '상세영업상태코드',
    # 레거시 구우편번호(XXX-XXX), 도로명우편번호(5자리)로 대체됨
    '소재지우편번호',
    # 레코드 관리 메타: 사업장 특성이 아니라 갱신 이력이라 폐업과 얽힌 누수 위험(폐업 시 U로 갱신됨)
    '데이터갱신구분', '데이터갱신시점',
}
FOOD_ONLY_CATS = ['등급구분명', '영업장주변구분명', '급수시설구분명']  # 식품 3개 파일에만 있는 범주형
LARGE_ONLY_CATS = ['점포구분명']  # 대규모점포에만 있는 범주형


def load(fname):
    return pd.read_csv(DATA_DIR / fname, encoding='cp949', low_memory=False, usecols=lambda c: c not in DROP_COLS)


df_general = load('식품_일반음식점.csv')
df_bakery = load('식품_제과점영업.csv')
df_rest = load('식품_휴게음식점.csv')
df_large = load('생활_대규모점포.csv')
df_general['원본파일'], df_bakery['원본파일'], df_rest['원본파일'], df_large['원본파일'] = \
    '일반음식점', '제과점영업', '휴게음식점', '대규모점포'

print("로드 완료:", len(df_general), len(df_bakery), len(df_rest), len(df_large))
print("식품 컬럼 수:", len(df_general.columns), " 대규모점포 컬럼 수:", len(df_large.columns))

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

# 주소 파싱 실패율 리포트
for name, _df in (('일반음식점', df_general), ('제과점', df_bakery), ('휴게음식점', df_rest), ('대규모점포', df_large)):
    fail = _df['SIDO_NM'].isna().sum()
    print(f"[{name}] 주소 파싱 실패: {fail}행 / {len(_df)}행 ({fail / len(_df) * 100:.3f}%)")

# ============================================
# 3. 통합 (컬럼 존재 확인 후 진행)
# ============================================
# 컬럼을 이름으로 골라 붙이지 않고 4개 파일의 컬럼 합집합을 그대로 쌓는다(없는 컬럼은 NaN).
# (예전엔 컬럼 목록을 골라 붙이다가 대규모점포 SIDO_NM/CCG_NM이 빠져 1,359행이 조인 불가였던 버그가 있었음)
combined = pd.concat(
    [d[d['bc_업종'].notna()] for d in (df_general, df_bakery, df_rest, df_large)],
    ignore_index=True,
)
print(f"통합 컬럼 수(합집합): {len(combined.columns)}")

print("\n=== 최종 bc_업종별 건수 ===")
print(combined['bc_업종'].value_counts())
print("\n전체 행 수:", len(combined))

# ============================================
# 3b. 물리적 이상치 정제 — 좌표, 시설총규모
# ============================================
import numpy as np
from scipy.spatial import cKDTree

# 좌표 ① 음수는 오류가 아니다. EPSG:5174는 원점이 북위 38도라 남쪽 끝 제주(Y<0, 서귀포시는 전부
# 음수)와 서쪽 끝 섬(옹진군 백령·대청, X<0)은 정상적으로 음수 좌표가 나온다. 실제 데이터에서도 음수 좌표는
# 제주/옹진군에만 있고 다른 지역엔 0건이다. 한국 영토를 벗어나는 값만 물리적 불가능으로 본다.
X_MIN, X_MAX, Y_MIN, Y_MAX = -20_000, 700_000, -60_000, 660_000
out_of_territory = (combined['좌표정보(X)'] < X_MIN) | (combined['좌표정보(X)'] > X_MAX) | \
                   (combined['좌표정보(Y)'] < Y_MIN) | (combined['좌표정보(Y)'] > Y_MAX)
print(f"\n한국 영토 범위 밖 좌표(물리적으로 불가능): {out_of_territory.sum()}행 -> 결측 처리")
combined.loc[out_of_territory, ['좌표정보(X)', '좌표정보(Y)']] = np.nan

# 좌표 ② 시군구별 median 기준 MAD(median absolute deviation)로 1차 후보 탐지.
# 전역 범위 하나로는 못 잡음 — 강원도처럼 넓은 시군구엔 너무 빡빡하고, 좁은 시군구엔 너무 느슨함.
valid = combined['좌표정보(X)'].notna() & combined['좌표정보(Y)'].notna() & combined['SIDO_NM'].notna()
sub = combined.loc[valid, ['SIDO_NM', 'CCG_NM', '좌표정보(X)', '좌표정보(Y)']]
grp = sub.groupby(['SIDO_NM', 'CCG_NM'])
med_x = grp['좌표정보(X)'].transform('median')
med_y = grp['좌표정보(Y)'].transform('median')
dist_from_med = np.sqrt((sub['좌표정보(X)'] - med_x) ** 2 + (sub['좌표정보(Y)'] - med_y) ** 2)
mad = grp.apply(
    lambda g: np.sqrt((g['좌표정보(X)'] - g['좌표정보(X)'].median()) ** 2 +
                       (g['좌표정보(Y)'] - g['좌표정보(Y)'].median()) ** 2).median(),
    include_groups=False,
)
mad_values = sub.set_index(['SIDO_NM', 'CCG_NM']).index.map(mad)
robust_std = (1.4826 * pd.Series(mad_values, index=sub.index)).clip(lower=1)
K_MAD = 4
mad_flagged = dist_from_med > (K_MAD * robust_std)
print(f"시군구별 median 기준 {K_MAD}*MAD 벗어난 좌표: {mad_flagged.sum()}행 (이것만으로는 오류 판정 안 함)")

# 좌표 ③ 주소-좌표 일치 검사. "시군구 중심에서 멀다"/"이웃이 적다"는 오류가 아니라 외딴 곳일 뿐이다
# (예전 MAD+1km밀도 규칙은 홍천·상주 등 농촌의 정상 점포를 2,773행 잘못 지웠음: 이웃 5개가 같은
# 시군구인 비율 82.7%). 오류의 신호는 "주소상 지역"과 "좌표 주변 지역"이 어긋나는 것이다.
# 좌표 기준 최근접 5개 이웃이 전부 내 주소 시군구와 다르면 '좌표주소불일치'.
# 결측 처리는 하지 않고 플래그만 남긴다(경계 지역·주소 파싱 라벨 문제도 섞여 있어 오탐이 있음).
pts = sub[['좌표정보(X)', '좌표정보(Y)']].to_numpy()
tree = cKDTree(pts)
_, nb_idx = tree.query(pts, k=6)  # 자기 자신 포함 6개
region_code = pd.factorize(sub['SIDO_NM'] + '|' + sub['CCG_NM'])[0]
is_self = nb_idx == np.arange(len(sub))[:, None]
same_region = (region_code[nb_idx] == region_code[:, None]) & ~is_self
agree = same_region.sum(axis=1) / np.maximum((~is_self).sum(axis=1), 1)
mismatch = agree == 0

combined['좌표주소불일치'] = 0
combined.loc[sub.index[mismatch], '좌표주소불일치'] = 1
combined['좌표의심'] = 0  # 불일치 + 시군구 중앙값에서도 4*MAD 초과: 진짜 좌표 오류일 가능성이 가장 큰 부류
combined.loc[sub.index[mismatch & mad_flagged.to_numpy()], '좌표의심'] = 1
print(f"좌표주소불일치(이웃 5개 시군구가 전부 다름): {mismatch.sum()}행 / 그중 좌표의심(+MAD 초과): "
      f"{int(combined['좌표의심'].sum())}행 -> 결측 처리 안 함, 플래그만")

# 시설총규모: 도메인 상한 캡(식당류가 현실적으로 넘기 어려운 규모) + 0값 재처리.
# 0을 "진짜 크기 0"으로 두면 안 됨(영업 중인 매장의 물리적 크기가 0일 수 없음) -> 결측 처리.
# 결측이라는 사실 자체도 정보(소규모/미신고 신호일 수 있음)라 별도 플래그 컬럼으로 보존.
SIZE_CAP = 3000  # ㎡. 상위 0.01%(2,811㎡)~최댓값(108,048㎡) 구간은 명백한 입력 오류로 판단
too_big = combined['시설총규모'] > SIZE_CAP
zero_size = combined['시설총규모'] == 0
print(f"\n시설총규모 > {SIZE_CAP}㎡(비현실적 극단치): {too_big.sum()}행 -> 결측 처리")
print(f"시설총규모 == 0(물리적으로 불가능): {zero_size.sum()}행 -> 결측 처리")
combined.loc[too_big | zero_size, '시설총규모'] = np.nan
combined['시설총규모_결측여부'] = combined['시설총규모'].isna().astype(int)

# ============================================
# 3c. 나머지 컬럼 타입별 정제 (EDA 전에 모든 컬럼을 정제된 상태로 만든다)
# ============================================
# 소재지면적: 0은 물리적으로 불가능 -> 결측. 식품 파일은 값이 999.99에서 잘려 있어(필드 자릿수 제한) 990 이상은
# 절단 의심 플래그. 대규모점포는 규모가 크므로(수천~수십만㎡) 절단 플래그 대상 아님. 이상치 상한은 EDA에서 결정.
combined['소재지면적'] = pd.to_numeric(combined['소재지면적'], errors='coerce')
print(f"\n소재지면적 == 0: {(combined['소재지면적'] == 0).sum()}행 -> 결측 처리")
combined.loc[combined['소재지면적'] == 0, '소재지면적'] = np.nan
combined['소재지면적_절단의심'] = ((combined['소재지면적'] >= 990) & (combined['원본파일'] != '대규모점포')).astype(int)

# 다중이용업소여부: Y/N -> 1/0 (결측 유지)
combined['is_multiuse'] = combined['다중이용업소여부'].map({'Y': 1, 'N': 0})
combined = combined.drop(columns=['다중이용업소여부'])

# 범주형: 공백 정리 + 결측을 명시적 범주로. 원본 파일에 그 컬럼이 아예 없는 경우(구조적 결측)는 '해당없음',
# 있는데 비어 있으면(실제 미기재) '미기재'로 구분한다.
for col in FOOD_ONLY_CATS + LARGE_ONLY_CATS:
    s = combined[col].astype('string').str.strip()
    exists_in_source = (combined['원본파일'] == '대규모점포') if col in LARGE_ONLY_CATS else (combined['원본파일'] != '대규모점포')
    combined[col] = s.mask(s.isna() & exists_in_source, '미기재').mask(~exists_in_source, '해당없음')

# 사업장명 공백 정리, 종사자수는 그대로(2010년 전후 신고율 붕괴는 제도 변화라 EDA에서 별도 판단)
combined['사업장명'] = combined['사업장명'].astype('string').str.strip()

# 도로명우편번호: float으로 읽혀 앞자리 0이 잘렸다(4자리 279,615건) -> 5자리로 복원
zc = pd.to_numeric(combined['도로명우편번호'], errors='coerce')
combined['도로명우편번호'] = zc.astype('Int64').astype('string').str.zfill(5)

# 전화번호: 번호 자체는 사업장 특성이 아니고 개인정보성이라 버리고, 기재 여부만 파생
combined['전화번호_기재'] = combined['전화번호'].notna().astype(int)
combined = combined.drop(columns=['전화번호'])

# ============================================
# 4. 날짜 처리 + 극단치 필터링
# ============================================
for dcol in ['인허가일자', '폐업일자', '최종수정시점', '휴업시작일자', '휴업종료일자', '재개업일자', '인허가취소일자']:
    if dcol in combined.columns:
        combined[dcol] = pd.to_datetime(combined[dcol], errors='coerce')

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

# 날짜 정합성 문제 행 제외(팀원 step5 브랜치에서 발견, 우리도 동일 문제 확인):
#   (a) 폐업일자 < 인허가일자 논리 오류
#   (b) 폐업(event=1)인데 폐업일자가 결측 -> 종료일이 없어 생존시간을 못 구하고, 그대로 두면 fillna로
#       "아직 영업 중"처럼 처리되거나 in_bc_window에서 생존자로 잡힌다(폐업했는데 censored로 취급되는 오류).
event_missing_date = (combined['event_observed'] == 1) & combined['폐업일자'].isna()
bad = bad_order | event_missing_date
print(f"날짜 정합성 문제로 제외: 순서오류 {bad_order.sum()}행 + 폐업인데 폐업일자 결측 {event_missing_date.sum()}행 "
      f"= 총 {bad.sum()}행 ({bad.sum() / len(combined) * 100:.4f}%)")
combined = combined[~bad]

# ============================================
# 4b. 사업장 개별 특성 파생 (팀원 step5 브랜치의 is_franchise / 중심점 거리를 이식)
# ============================================
# 프랜차이즈(체인) 브랜드 키워드는 코드가 아니라 franchise_brands.csv에서 읽는다(use=1인 행만 사용).
# 목록을 늘리거나 공정위 브랜드 목록 등으로 교체할 때 코드를 고칠 필요가 없고, 제외한 후보와 사유(김밥천국 등)도 같은 파일에 남긴다.
# 정의는 가맹점뿐 아니라 직영 포함 "체인/브랜드 소속"이다. 한글 키워드는 공백 제거 후 부분일치, latin은 영문자 경계 정규식.
_brands = pd.read_csv('franchise_brands.csv', encoding='utf-8-sig')
_brands = _brands[_brands['use'] == 1]
FRANCHISE_KOREAN = _brands.loc[_brands['match'] == 'ko', 'keyword'].tolist()
FRANCHISE_LATIN = _brands.loc[_brands['match'] == 'latin', 'keyword'].tolist()
print(f"프랜차이즈 키워드: 한글 {len(FRANCHISE_KOREAN)}개, 영문 {len(FRANCHISE_LATIN)}개")
_pat_ko = '|'.join(re.escape(k) for k in FRANCHISE_KOREAN)
_pat_lat = r'(?<![A-Za-z])(?:' + '|'.join(FRANCHISE_LATIN) + r')(?![A-Za-z])'
_name = combined['사업장명'].fillna('')
_name_nows = _name.str.replace(r'\s+', '', regex=True)  # 한글 브랜드는 띄어쓰기 제거 후 매칭('이마트 24' 대응)
combined['is_franchise'] = (_name_nows.str.contains(_pat_ko, case=False, regex=True, na=False) |
                            _name.str.contains(_pat_lat, case=False, regex=True, na=False)).astype(int)
print(f"\n프랜차이즈 키워드 매칭: {combined['is_franchise'].sum()}행 ({combined['is_franchise'].mean() * 100:.2f}%)")
print((combined.groupby('bc_업종')['is_franchise'].mean() * 100).round(1).to_string())

# 입지: 같은 (SIDO_NM, CCG_NM) 안에서 좌표 중심점까지의 거리(m) — 중심가/골목 구분 proxy.
# 주의: 옹진군처럼 섬들이 흩어진 시군구는 중심점이 바다 한가운데라 이 지표의 의미가 약하다.
coords_valid = combined['좌표정보(X)'].notna() & combined['좌표정보(Y)'].notna() & (combined['좌표의심'] == 0)
centroid = combined.loc[coords_valid].groupby(['SIDO_NM', 'CCG_NM'])[['좌표정보(X)', '좌표정보(Y)']].transform('mean')
combined['dist_to_region_centroid_m'] = np.nan
combined.loc[coords_valid, 'dist_to_region_centroid_m'] = np.sqrt(
    (combined.loc[coords_valid, '좌표정보(X)'] - centroid['좌표정보(X)']) ** 2 +
    (combined.loc[coords_valid, '좌표정보(Y)'] - centroid['좌표정보(Y)']) ** 2)
print(f"중심점 거리 계산: {coords_valid.sum()}행 ({coords_valid.mean() * 100:.1f}%), 나머지는 NaN")

# 좌표 결측 여부: 좌표가 없는 사업장은 같은 나이·업종 대비 폐업률이 낮았다(O/E 0.77). 결측 행을 통째로 지우면 이 집단이
# 사라지므로 표시로 남긴다.
combined['좌표결측'] = combined['좌표정보(X)'].isna().astype(int)

# 시설총규모의 업종 내 표준화(log 후 z-score). 업종마다 전형적인 크기가 크게 달라(편의점 3㎡ vs 한식 60㎡) 원값을 그대로 쓰면
# 업종 효과와 크기 효과가 섞인다. 편의점은 값의 31.5%가 3.3㎡ 플레이스홀더라 크기 정보가 없다고 보고 0(업종 평균)으로 둔다.
_ls = np.log(combined['시설총규모'])
_g = _ls.groupby(combined['bc_업종'])
combined['log시설총규모_업종내z'] = (_ls - _g.transform('mean')) / _g.transform('std')
combined.loc[combined['bc_업종'] == '편의점', 'log시설총규모_업종내z'] = 0.0

print("\n필터링 후 행 수:", len(combined))

# ============================================
# 5. 저장
# ============================================
# 죽은 컬럼 규칙을 통합 후에도 적용: 99.9% 넘게 비어 있으면 정보가 없다.
# (대규모점포 전용 날짜 컬럼 4개가 여기 해당: 대규모점포 행에서만 값이 있고 그마저 0.6~3%, 나머지 99.94%는 구조적 결측)
_dead = [c for c in combined.columns if combined[c].isna().mean() > 0.999]
print(f"\n99.9% 초과 결측이라 제외한 컬럼: {_dead}")
combined = combined.drop(columns=_dead)

# 넓은 통합본: 정제된 모든 컬럼. EDA용 작업대이며 여기서 후보 컬럼을 검토한다.
wide_path = DATA_DIR / 'localdata_wide.csv'
combined.to_csv(wide_path, index=False, encoding='utf-8-sig')
print(f"\n넓은 통합본 저장: {wide_path} ({len(combined)}행, {len(combined.columns)}컬럼)")

# 모델/조인에 실제로 쓰는 컬럼(EDA 결과로 이 목록을 갱신한다). 현재는 EDA 이전 상태의 기본값.
SELECTED_COLS = ['관리번호', '원본파일', '인허가일자', '폐업일자', '영업상태명', '업태구분명', '사업장명',
                 '도로명주소', '지번주소', '좌표정보(X)', '좌표정보(Y)', '시설총규모', 'is_multiuse',
                 'bc_업종', 'SIDO_NM', 'CCG_NM', '좌표주소불일치', '좌표의심', '시설총규모_결측여부', 'event_observed',
                 'is_franchise', 'dist_to_region_centroid_m',
                 # EDA(나이·업종 보정 O/E) 결과로 추가한 후보. 최종 채택은 모델의 블록 추가 검증으로 결정
                 '전화번호_기재', '등급구분명', '급수시설구분명', '좌표결측', 'log시설총규모_업종내z']
out_path = DATA_DIR / 'localdata_clean.csv'
combined[SELECTED_COLS].to_csv(out_path, index=False, encoding='utf-8-sig')
print(f"선택 컬럼본 저장: {out_path} ({len(SELECTED_COLS)}컬럼)")
print("\n[넓은 통합본 컬럼별 결측률(%)]")
print((combined.isna().mean() * 100).round(1).sort_values(ascending=False).to_string())
