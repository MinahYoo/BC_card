# -*- coding: utf-8 -*-
"""
최종 모형 M3L(사업장 변수 + 그룹 직전 폐업률 + 자기·이웃 시군구 폐업 이력 + BC 성별·연령 구성)의 설명 산출물.

(1) Cox 선형예측자의 정확한 분해(explain_cox.py와 같은 정의): 사업장 i의 변수 j 기여 = beta_j * (x_ij - mean_j). exp(기여) = 평균 사업장 대비 상대위험 배수. 연관이지 인과가 아니다.
(2) **블록 제거 예측 중요도**: 블록을 뺀 모형을 그룹 5-fold로 다시 적합해 미학습 그룹 순위(Spearman)와 사업장 C-index가 얼마나 떨어지는지 본다.
    SHAP 기여의 크기는 변수 간 겹침(특히 그룹 단위 BC 변수의 in-sample 과적합)에 부풀려질 수 있어, "정말 예측에 필요한 블록"은 이 표로 판단한다.
    fold 분할과 적합 캐시는 bc_scale_check.py와 같다(M3L 예측은 저장된 oof_group.npz를 재사용).
산출물: output/11_final_coef.csv, 11_final_block_importance.csv, 11_final_drop_block.csv, 11_final_group_blocks.csv, 11_final_region_blocks.csv
"""
import hashlib

import joblib
import numpy as np
import pandas as pd
from lifelines import CoxPHFitter
from lifelines.utils import concordance_index
from scipy.stats import spearmanr
from sklearn.model_selection import StratifiedKFold

from explain_common import CACHE_DIR, fit_cox_cached, load_cohort, model_cols

K, B, MIN_N = 5, 300, 100
ns, log = load_cohort()
full = ns["full"].reset_index(drop=True)
JOIN_KEY, REGION_KEY, TOP = ns["JOIN_KEY"], ns["REGION_KEY"], ns["TOP"]
LAG3 = ["reg_hist", "nb_reg_hist", "nb_grp_hist"]
feat = pd.read_csv("output/8_group_features.csv", encoding="utf-8-sig", usecols=JOIN_KEY + LAG3)
n0 = len(full)
full = full.merge(feat, on=JOIN_KEY, how="left", validate="m:1")
assert len(full) == n0 and not full[LAG3].isna().any().any()
cols = model_cols(ns, TOP) + LAG3
share = ns["COV_SHARE"]
BLOCKS = {
    "영업연수": ["log_age"], "프랜차이즈": ["is_franchise"], "입지(중심점 거리)": ["log_dist_to_centroid"],
    "사업장 확장(다중이용·크기·좌표결측·전화)": list(ns["STORE_EXT"]),
    "그룹 직전 1년 폐업률": list(ns["COV_HIST"]),
    "자기·이웃 시군구 폐업 이력": LAG3,
    "BC 성별 구성": [c for c in share if "gender" in c], "BC 연령 구성": [c for c in share if "age" in c],
    "업종": list(ns["BIZ_DUMMY"]),
}
BLOCKS = {k: [c for c in v if c in cols] for k, v in BLOCKS.items()}
BLOCKS = {k: v for k, v in BLOCKS.items() if v}
assert sorted(c for v in BLOCKS.values() for c in v) == sorted(cols), "블록에 배정되지 않은 변수가 있다"

# ---- (1) 정확한 분해 ----
cph = fit_cox_cached("M3L", cols, full)
beta = cph.params_.reindex(cols)
X = full[cols].astype(float)
mu = X.mean()
contrib = (X - mu) * beta
err = float(np.abs(contrib.sum(axis=1).to_numpy() - cph.predict_log_partial_hazard(full[cols]).to_numpy()).max())
print(f"[검증] 분해 오차 {err:.2e}", flush=True)
assert err < 1e-6
blk = pd.DataFrame({k: contrib[v].sum(axis=1) for k, v in BLOCKS.items()})
coef = pd.DataFrame({"coef": beta, "HR": np.exp(beta), "평균": mu, "표준편차": X.std()})
coef["1SD당_HR"] = np.exp(beta * X.std())
coef["블록"] = [next(k for k, v in BLOCKS.items() if c in v) for c in coef.index]
coef.round(4).to_csv("output/11_final_coef.csv", encoding="utf-8-sig")
imp = pd.DataFrame({"평균_절대기여(log HR)": blk.abs().mean(), "기여의_표준편차(log HR)": blk.std()})
imp["전형적_배수"] = np.exp(imp["평균_절대기여(log HR)"])
imp["절대기여_비중(%)"] = imp["평균_절대기여(log HR)"] / imp["평균_절대기여(log HR)"].sum() * 100
imp = imp.sort_values("평균_절대기여(log HR)", ascending=False)
imp.round(4).to_csv("output/11_final_block_importance.csv", encoding="utf-8-sig")
print("\n=== 블록별 SHAP 중요도(사업장 단위, in-sample) ===")
print(imp.round(3).to_string(), flush=True)

gid = full["group_id"].to_numpy()
G = int(gid.max()) + 1
n_g = np.bincount(gid, minlength=G).astype(float)
ev_g = np.bincount(gid, weights=full["event"].to_numpy(float), minlength=G)
reg_g = np.zeros(G, dtype=int)
reg_g[gid] = full["region_id"].to_numpy()
grp = full.drop_duplicates("group_id").set_index("group_id").sort_index()[JOIN_KEY]
gm = blk.groupby(gid).mean()
lp_g = gm.sum(axis=1)
g_out = grp.assign(n=n_g, events=ev_g, obs_rate=ev_g / np.maximum(n_g, 1), mean_LP=lp_g.to_numpy(), 상대위험_배수=np.exp(lp_g.to_numpy()))
for c in gm:
    g_out[f"x_{c}"] = np.exp(gm[c].to_numpy())
g_out["region_id"] = reg_g
g_out.round(4).to_csv("output/11_final_group_blocks.csv", index=False, encoding="utf-8-sig")
rm = blk.groupby(full["region_id"]).mean()
r_info = full.groupby("region_id").agg(SIDO_NM=("SIDO_NM", "first"), CCG_NM=("CCG_NM", "first"), n=("event", "size"), obs_rate=("event", "mean"))
r_out = r_info.join(rm.rename(columns=lambda c: f"x_{c}").pipe(np.exp))
r_out["mean_LP"] = rm.sum(axis=1)
r_out["상대위험_배수"] = np.exp(r_out["mean_LP"])
r_out.round(4).to_csv("output/11_final_region_blocks.csv", index=False, encoding="utf-8-sig")
print(f"그룹 {len(g_out):,}개, 시군구 {len(r_out)}개 저장", flush=True)

# ---- (2) 블록 제거 예측 중요도(그룹 5-fold) ----
def fit_params(name, cs, train):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    ident = ("p", name, len(train), tuple(cs), tuple())       # bc_scale_check.py의 fit_params와 같은 키 -> M3L 적합을 재사용
    path = CACHE_DIR / ("par_" + hashlib.md5(repr(ident).encode("utf-8")).hexdigest()[:12] + ".joblib")
    if path.exists():
        return joblib.load(path)
    keep = list(dict.fromkeys(list(cs) + ["duration", "event"]))
    m = CoxPHFitter().fit(train[keep], duration_col="duration", event_col="event")
    out = {"params": m.params_.copy(), "se": m.standard_errors_.copy()}
    joblib.dump(out, path)
    return out


groups = ns["groups"]
fg = np.zeros(len(groups), dtype=int)
for k, (_, te_i) in enumerate(StratifiedKFold(K, shuffle=True, random_state=42).split(groups, groups["bc_업종"])):
    fg[te_i] = k
fold_row = fg[gid]


def oof_lp(name, cs):
    out = np.full(len(full), np.nan)
    for k in range(K):
        te = fold_row == k
        tr = full[~te]
        b = fit_params(f"g{k}|{name}", cs, tr)["params"].reindex(cs).to_numpy()
        out[te] = (full.loc[te, cs].to_numpy(float) - tr[cs].to_numpy(float).mean(axis=0)) @ b
    return out


keep = n_g >= MIN_N
cnt_reg = np.bincount(reg_g[keep], minlength=reg_g.max() + 1)
keep2 = keep & (cnt_reg[reg_g] >= 2)
R = int(reg_g.max()) + 1
rate = ev_g / np.maximum(n_g, 1)


def glp(lp):
    return np.bincount(gid, weights=lp, minlength=G) / np.maximum(n_g, 1)


def dev(x, mask):
    w = np.where(mask, n_g, 0.0)
    m = np.bincount(reg_g, weights=w * x, minlength=R) / np.maximum(np.bincount(reg_g, weights=w, minlength=R), 1e-9)
    return x - m[reg_g]


def boots(mask, rng):
    idx = np.where(mask)[0]
    by = {r: idx[reg_g[idx] == r] for r in np.unique(reg_g[idx])}
    ks = list(by)
    return [np.concatenate([by[k] for k in rng.choice(ks, size=len(ks), replace=True)]) for _ in range(B)]


rng = np.random.default_rng(42)
bt_all, bt_in = boots(keep, rng), boots(keep2, rng)
rho = lambda a, b: float(spearmanr(a, b).statistic)
ev, du = full["event"].to_numpy(), full["duration"].to_numpy()
oof_full = np.load("output/_cache/oof_group.npz")["M3L"]
lp_full = glp(oof_full)
rate_dev = dev(rate, keep2)
dev_full = dev(lp_full, keep2)
rows = [{"모형": "M3L (전체)", "제거 블록": "-", "Spearman(전체)": round(rho(lp_full[keep], rate[keep]), 3),
         "Spearman(시군구 내)": round(rho(dev_full[keep2], rate_dev[keep2]), 3), "C-index": round(concordance_index(du, -oof_full, ev), 4)}]
print("\n=== 블록 제거 예측 중요도(그룹 5-fold; 값이 클수록 그 블록이 예측에 필요) ===", flush=True)
for name, cs_b in BLOCKS.items():
    cs = [c for c in cols if c not in cs_b]
    o = oof_lp("M3L-" + name, cs)
    lp_m = glp(o)
    dm = dev(lp_m, keep2)
    d_all = rho(lp_full[keep], rate[keep]) - rho(lp_m[keep], rate[keep])
    d_in = rho(dev_full[keep2], rate_dev[keep2]) - rho(dm[keep2], rate_dev[keep2])
    v_all = [rho(lp_full[b], rate[b]) - rho(lp_m[b], rate[b]) for b in bt_all]
    v_in = [rho(dev_full[b], rate_dev[b]) - rho(dm[b], rate_dev[b]) for b in bt_in]
    c_full, c_m = concordance_index(du, -oof_full, ev), concordance_index(du, -o, ev)
    row = {"모형": "M3L − 블록", "제거 블록": name, "Spearman(전체)": round(rho(lp_m[keep], rate[keep]), 3),
           "Spearman(시군구 내)": round(rho(dm[keep2], rate_dev[keep2]), 3), "C-index": round(c_m, 4),
           "ΔSpearman 전체": round(d_all, 3), "ΔSpearman 전체 95% CI": f"[{np.percentile(v_all, 2.5):.3f}, {np.percentile(v_all, 97.5):.3f}]",
           "ΔSpearman 시군구 내": round(d_in, 3), "ΔSpearman 시군구 내 95% CI": f"[{np.percentile(v_in, 2.5):.3f}, {np.percentile(v_in, 97.5):.3f}]",
           "ΔC-index": round(c_full - c_m, 4)}
    rows.append(row)
    print(f"  {name}: ΔSpearman 전체 {row['ΔSpearman 전체']} {row['ΔSpearman 전체 95% CI']} / 시군구 내 {row['ΔSpearman 시군구 내']} {row['ΔSpearman 시군구 내 95% CI']} / ΔC {row['ΔC-index']}", flush=True)
drop = pd.DataFrame(rows)
drop.to_csv("output/11_final_drop_block.csv", index=False, encoding="utf-8-sig")
print(drop.to_string(index=False), flush=True)

# ---- 대표 그룹 ----
big = g_out[g_out["n"] >= 300].sort_values("mean_LP")
show = ["SIDO_NM", "CCG_NM", "bc_업종", "n", "obs_rate", "상대위험_배수"] + [f"x_{c}" for c in blk.columns]
print("\n=== 가장 위험한 그룹 8개 (사업장>=300; 열은 평균 사업장 대비 상대위험 배수) ===")
print(big.tail(8).iloc[::-1][show].round(3).to_string(index=False))
print("\n=== 가장 안전한 그룹 8개 ===")
print(big.head(8)[show].round(3).to_string(index=False), flush=True)
print("\n완료", flush=True)
