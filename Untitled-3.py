import pandas as pd

data = pd.read_csv("C:/Users/안서영/Desktop/식품_일반음식점.csv", 
                    encoding="cp949")
print(data.head())
print(data.info())
print(len(data))

# 1. 업태구분명 — 6개 외식업종 매핑의 핵심
print(data['업태구분명'].value_counts())

# 2. 영업상태명/상세영업상태명 — 생존분석 이벤트 정의용
print(data['영업상태명'].value_counts())
print(data['상세영업상태명'].value_counts())

# 3. 인허가일자/폐업일자 결측 확인
print(data['인허가일자'].isna().sum())
print(data['폐업일자'].isna().sum())

# 4. 날짜형 변환 확인
data['인허가일자'] = pd.to_datetime(data['인허가일자'], errors='coerce')
data['폐업일자'] = pd.to_datetime(data['폐업일자'], errors='coerce')
print(data[['인허가일자','폐업일자']].describe())

print(data['위생업태명'].value_counts())
print()
print(data['전통업소주된음식'].value_counts())  # 한식 세분화 힌트 있을 수도