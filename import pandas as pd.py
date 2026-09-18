import pandas as pd

data2 = pd.read_csv("C:/Users/안서영/Desktop/식품_제과점영업.csv", 
                    encoding="cp949")
data3 = pd.read_csv("C:/Users/안서영/Desktop/식품_휴게음식점.csv", 
                    encoding="cp949")
data4 = pd.read_csv("C:/Users/안서영/Desktop/생활_대규모점포.csv", 
                    encoding="cp949")
data5 = pd.read_csv("C:/Users/안서영/Desktop/식품_즉석판매제조가공업.csv", 
                    encoding="cp949")

print("=== 제과점영업 ===")
print(data2['업태구분명'].value_counts())

print("\n=== 휴게음식점 ===")
print(data3['업태구분명'].value_counts())

print("\n=== 대규모점포 ===")
print(data4['업태구분명'].value_counts())

print("\n=== 즉석판매제조가공업 ===")
print(data5['업태구분명'].value_counts())

print(data3[data3['업태구분명']=='편의점']['사업장명'].sample(30, random_state=1))