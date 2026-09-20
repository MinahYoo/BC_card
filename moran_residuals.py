# -*- coding: utf-8 -*-
"""
모형 잔차에 공간 자기상관(Moran's I)이 남아 있는가 — 시군구 단위.

잔차가 공간적으로 몰려 있으면(이웃한 시군구가 비슷하게 '예상보다 많이/적게 폐업') 지역 효과를 지리적으로 더 살려야 한다는 신호다(공간 지연 변수, GNN 등).

[잔차 정의]
  사업장 i의 기대 폐업확률 p_i = 1 - exp(-c * exp(LP_i)),  c는 모형별로 sum p = 관측 폐업 수가 되게 맞춘 상수(교정).
  시군구 j의 Pearson 잔차 z_j = (관측 폐업 수 - 기대 폐업 수) / sqrt(sum p(1-p))  — 사업장 수가 달라도 분산이 비슷해지도록 표준화.
  대상 시군구는 사업장 >= MIN_N(기본 200)개.
[두 종류의 잔차]
  in-sample: 전체 코호트에 적합한 모형의 잔차(모형이 이미 본 데이터. BC 변수는 그룹 단위라 in-sample에서는 지역 구조를 일부 흡수해 낙관적일 수 있다).
  OOF: 그룹 5-fold 미학습 예측(bc_scale_check.py가 저장한 output/_cache/oof_group.npz)의 잔차.
[공간 가중]  시군구 중심점(좌표 중앙값, EPSG:5174 m) k-최근접(k=5, 10) 행 표준화. 순열 검정 5,000회.
[비교 기준] 원자료 폐업률(모형 없음), M2, M2h, M3.
산출물: output/10_moran_summary.csv, 10_moran_by_biz.csv, 10_local_hotspots.csv
"""
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

from explain_common import fit_cox_cached, load_cohort, model_cols

MIN_N = 200
PERM = 5000
print("코호트 로드...", flush=True)
ns, log = load_cohort()
full = ns["full"].reset_index(drop=True)
JOIN_KEY, REGION_KEY = ns["JOIN_KEY"], ns["REGION_KEY"]
MODEL = {"M2": ns["BASE"], "M2h": ns["REF"], "M3": ns["TOP"]}

# ---- 시군구 중심점 ----
xy = pd.read_csv("data/final_joined.csv", encoding="utf-8-sig", usecols=REGION_KEY + ["좌표정보(X)", "좌표정보(Y)", "좌표의심"], low_memory=False)
xy = xy[xy["좌표정보(X)"].notna() & xy["좌표정보(Y)"].notna() & (xy["좌표의심"].fillna(0) == 0)]
cent = xy.groupby(REGION_KEY)[["좌표정보(X)", "좌표정보(Y)"]].median().reset_index().rename(columns={"좌표정보(X)": "cx", "좌표정보(Y)": "cy"})
del xy


def calibrated_p(lp, target):
    """sum p = target 이 되도록 c를 이분법으로 찾는다."""
    e = np.exp(lp - lp.max())
    lo, hi = 1e-12, 1e6
    for _ in range(80):
        c = np.sqrt(lo * hi)
        s = (1 - np.exp(-c * e)).sum()
        lo, hi = (c, hi) if s < target else (lo, c)
    return 1 - np.exp(-c * e)


ev_all = full["event"].to_numpy(float)
target = ev_all.sum()
lps = {}
for k, name in MODEL.items():
    cols = model_cols(ns, name)
    cph = fit_cox_cached(name, cols, full)
    lps[f"{k} (in-sample)"] = cph.predict_log_partial_hazard(full[cols]).to_numpy()
oof = np.load("output/_cache/oof_group.npz")
for k in MODEL:
    lps[f"{k} (OOF)"] = oof[k]
for k in ("M2hR", "M2hL", "M3L"):        # 공간 지연 변수를 넣은 모형(bc_scale_check.py의 미학습 예측)
    if k in oof.files:
        lps[f"{k} (OOF)"] = oof[k]
ps = {name: calibrated_p(lp, target) for name, lp in lps.items()}
for name, p in ps.items():
    print(f"교정 {name}: 평균 기대 {p.mean() * 100:.3f}% vs 관측 {ev_all.mean() * 100:.3f}%")
p_raw = np.full(len(full), ev_all.mean())        # 모형 없음: 전국 평균 폐업률을 모두에게


def region_resid(p, mask=None):
    d = full.assign(_p=p, _v=p * (1 - p))
    if mask is not None:
        d = d[mask]
    g = d.groupby(REGION_KEY, observed=True).agg(n=("event", "size"), obs=("event", "sum"), exp=("_p", "sum"), var=("_v", "sum")).reset_index()
    g = g[g["n"] >= MIN_N].merge(cent, on=REGION_KEY, how="inner")
    g["z"] = (g["obs"] - g["exp"]) / np.sqrt(g["var"].clip(lower=1e-9))
    return g


def knn_weights(pts, k):
    tree = cKDTree(pts)
    _, idx = tree.query(pts, k=k + 1)
    n = len(pts)
    W = np.zeros((n, n))
    for i in range(n):
        W[i, idx[i, 1:]] = 1.0 / k
    return W


def moran(z, W, rng):
    z = z - z.mean()
    den = (z ** 2).sum()
    I = len(z) / W.sum() * (z @ W @ z) / den
    perm = np.empty(PERM)
    for b in range(PERM):
        zp = rng.permutation(z)
        perm[b] = len(z) / W.sum() * (zp @ W @ zp) / den
    return I, -1 / (len(z) - 1), (I - perm.mean()) / perm.std(), (1 + (perm >= I).sum()) / (PERM + 1)


rows = []
rng = np.random.default_rng(42)
targets = {"원자료 폐업률(모형 없음)": p_raw, **ps}
regs = None
for name, p in targets.items():
    g = region_resid(p)
    if regs is None:
        regs = g
        print(f"\n대상 시군구 {len(g)}개(사업장>={MIN_N}, 중심점 확보)", flush=True)
    else:
        assert len(g) == len(regs)
    pts = g[["cx", "cy"]].to_numpy()
    for k in (5, 10):
        W = knn_weights(pts, k)
        I, E, zsc, pv = moran(g["z"].to_numpy(), W, rng)
        rows.append({"잔차 기준": name, "k": k, "Moran I": round(I, 3), "기대값": round(E, 3), "순열 z": round(zsc, 1), "p(단측)": round(pv, 4), "시군구 수": len(g)})
summ = pd.DataFrame(rows)
print("\n=== Moran's I (시군구 Pearson 잔차) ===")
print(summ.to_string(index=False), flush=True)
summ.to_csv("output/10_moran_summary.csv", index=False, encoding="utf-8-sig")

# ---- 업종별(M3 in-sample / OOF) ----
rows = []
for biz in sorted(full["bc_업종"].unique()):
    for name in ("M3 (in-sample)", "M3 (OOF)"):
        g = region_resid(ps[name], mask=(full["bc_업종"] == biz).to_numpy())
        g = g[g["n"] >= 100]
        if len(g) < 30:
            continue
        W = knn_weights(g[["cx", "cy"]].to_numpy(), 5)
        I, E, zsc, pv = moran(g["z"].to_numpy(), W, rng)
        rows.append({"업종": biz, "잔차 기준": name, "시군구 수": len(g), "Moran I(k=5)": round(I, 3), "순열 z": round(zsc, 1), "p(단측)": round(pv, 4)})
byb = pd.DataFrame(rows)
print("\n=== 업종별 Moran's I (사업장>=100인 시군구, k=5) ===")
print(byb.to_string(index=False), flush=True)
byb.to_csv("output/10_moran_by_biz.csv", index=False, encoding="utf-8-sig")

# ---- 국지 핫스폿(M3 OOF, k=5): 잔차가 크고 이웃도 큰 시군구 ----
g = region_resid(ps["M3 (OOF)"])
W = knn_weights(g[["cx", "cy"]].to_numpy(), 5)
z = g["z"].to_numpy() - g["z"].mean()
g["국지 I"] = z * (W @ z) / (z ** 2).mean()
g["이웃 평균 z"] = W @ g["z"].to_numpy()
hot = g.sort_values("국지 I", ascending=False)
show = REGION_KEY + ["n", "obs", "exp", "z", "이웃 평균 z", "국지 I"]
print("\n=== 국지 군집 상위 12: 예상보다 폐업이 많고 이웃도 그런 시군구 (M3 OOF) ===")
print(hot[hot["z"] > 0].head(12)[show].round(2).to_string(index=False))
print("\n=== 예상보다 폐업이 적고 이웃도 그런 시군구 상위 12 ===")
print(hot[hot["z"] < 0].head(12)[show].round(2).to_string(index=False), flush=True)
hot[show].round(3).to_csv("output/10_local_hotspots.csv", index=False, encoding="utf-8-sig")
print("\n완료", flush=True)
