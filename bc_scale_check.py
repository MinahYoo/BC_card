# -*- coding: utf-8 -*-
"""
M4(경쟁밀도·상권 규모)와 M5(BC카드 소비 규모: 점포당 소비, 객단가)가 M3보다 미학습 그룹의 위험 순위를 더 잘 맞히는가.
연령 구성 블록의 증분(confound_check.py의 잔여 질문)도 같은 틀로 다시 잰다.

[confound_check.py와 다른 점]
  - 단일 80/20 분할(미학습 그룹 212개, 신뢰구간 +-0.05~0.09) 대신 **그룹 5-fold 교차검증**: 모든 그룹이 한 번씩 미학습이 되어 약 1,500개 그룹으로 평가한다.
  - 시군구를 통째로 빼는 **시군구 5-fold**도 함께 본다(같은 시군구의 다른 업종이 학습에 들어가는 누수 없음). 시군구 층화 모형은 미학습 시군구를 예측할 수 없어 그룹 fold에서만 평가한다.
  - 평가 값은 fold별 모형이 미학습 그룹에 낸 선형예측자(beta'(x−학습평균), fold 간 상수 차이를 없애기 위해 중심화)를 모아 그룹 평균 -> 관측 그룹 폐업률과의 Spearman. 시군구 cluster bootstrap 신뢰구간.

[새 변수 — 모두 1/1 이전에 정해지거나 1월 소비 기준]
  M4  log_n_grp   : 같은 시군구x업종의 1/1 영업 점포 수(경쟁밀도, 코호트에서 직접 셈. 소진공 6월 스냅샷은 폐업 점포가 빠져 쓰지 않음)
  M4v log_n_reg   : 시군구의 1/1 영업 외식·대규모점포 수(9업종 합. LOCALDATA는 음식점·제과·휴게·대규모점포만 있어 '전체 상권'이 아니라 외식 규모)
      log_dens500 : 시군구 내 점포의 500m 이웃 점포 수 중앙값(로그) — 규모가 아니라 밀집도
  M5J spend_jan   : 1월 BC 소비액 / 1/1 점포 수(로그) = 점포당 소비.   unit_z_jan: 1월 객단가(금액/건수)의 업종 내 표준화
  M5S spend_6f    : 1~6월 월평균 소비액 / 1/1 점포 수.               unit_z_6  : 6개월 객단가 업종 내 z
  M5D spend_6d    : 월별 (소비액 / 그 달 1일 영업 점포 수)의 평균 — 폐업한 점포가 분자와 분모에서 함께 빠져 역인과 편향이 줄어든다.
  * ABP는 시군구x업종 집계라 점포별 매출이 없어 '폐업점포 매출 제외' 재계산은 불가능하다. M5J(1월)와 M5S/M5D(6개월)를 비교해 역인과가 결과를 흔드는지 본다.
  * 소비 변수도 그룹 단위 값이라 생태학적 해석이며 인과가 아니다.

산출물: output/8_group_features.csv, 8_cv_group_spearman.csv, 8_cv_group_increment.csv, 8_cv_region_*.csv, 8_fullfit_new_vars.csv
"""
import argparse
import hashlib
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from lifelines import CoxPHFitter
from lifelines.utils import concordance_index
from scipy.spatial import cKDTree
from scipy.stats import spearmanr
from sklearn.model_selection import KFold, StratifiedKFold

from explain_common import CACHE_DIR, load_cohort, model_cols

ap = argparse.ArgumentParser()
ap.add_argument("--folds", type=int, default=5)
ap.add_argument("--B", type=int, default=500)
ap.add_argument("--min-n", type=int, default=100)
ap.add_argument("--skip-region", action="store_true", help="시군구 fold 생략")
ap.add_argument("--no-cache", action="store_true")
args = ap.parse_args()
K, B, MIN_N = args.folds, args.B, args.min_n

print("코호트 로드...", flush=True)
ns, log = load_cohort()
full = ns["full"].reset_index(drop=True)
df = ns["df"]
JOIN_KEY, REGION_KEY, TOP = ns["JOIN_KEY"], ns["REGION_KEY"], ns["TOP"]
LM = pd.Timestamp("2026-01-01")


def alive(d, t):
    return (d["인허가일자"] <= t) & (d["폐업일자"].isna() | (d["폐업일자"] > t))


# ============================================
# 1. 그룹 단위 새 변수
# ============================================
months = [pd.Timestamp(f"2026-{m:02d}-01") for m in range(1, 7)]
yymm = [202601 + i for i in range(6)]
n_m = pd.concat({y: df[alive(df, t)].groupby(JOIN_KEY).size() for y, t in zip(yymm, months)}, axis=1)
n1 = n_m[yymm[0]]
print(f"1/1 영업 점포(7업종) {int(n1.sum()):,}  / 코호트 행 {len(full):,}", flush=True)

bcm = ns["bc"].groupby(JOIN_KEY + ["STRD_YYMM"])[["amt", "cnt"]].sum().reset_index()
amt = bcm.pivot_table(index=JOIN_KEY, columns="STRD_YYMM", values="amt")
cnt = bcm.pivot_table(index=JOIN_KEY, columns="STRD_YYMM", values="cnt")
amt, cnt = amt.reindex(columns=yymm), cnt.reindex(columns=yymm)
nm = n_m.reindex(amt.index)

gf = pd.DataFrame(index=amt.index)
gf["n_jan1"] = n1.reindex(gf.index)
gf["log_n_grp"] = np.log(gf["n_jan1"].clip(lower=1))
gf["spend_jan"] = np.log(amt[yymm[0]].clip(lower=1) / gf["n_jan1"].clip(lower=1))
gf["spend_6f"] = np.log(amt.mean(axis=1).clip(lower=1) / gf["n_jan1"].clip(lower=1))
per_store_m = amt.to_numpy() / nm.to_numpy().clip(min=1)
gf["spend_6d"] = np.log(np.nanmean(per_store_m, axis=1).clip(min=1))
gf["unit_jan"] = np.log((amt[yymm[0]] / cnt[yymm[0]].clip(lower=1)).clip(lower=1))
gf["unit_6"] = np.log((amt.sum(axis=1) / cnt.sum(axis=1).clip(lower=1)).clip(lower=1))
for src, dst in (("unit_jan", "unit_z_jan"), ("unit_6", "unit_z_6")):    # 업종 내 표준화(그룹 표에서 계산: 사업장 수 가중 없음)
    g = gf[src].groupby(level="bc_업종")
    gf[dst] = (gf[src] - g.transform("mean")) / g.transform("std")
# --- M6: 아직 안 뽑아 본 BC 특성(연령 집중도, 지역 대비 업종 고객 편차, 지역 소비력, 그룹의 지역 소비 점유, 6개월 변화) ---
bc7 = ns["bc"]
ac = bc7[bc7["AGE_CD"] != "x"].copy()
ac["age_code"] = ac["AGE_CD"].astype(int)


def age_stats(keys):
    t = ac.groupby(keys + ["age_code"])["amt"].sum().unstack("age_code", fill_value=0)
    sh = t.div(t.sum(axis=1), axis=0)
    return pd.DataFrame({"hhi": (sh ** 2).sum(axis=1), "mean": (sh * sh.columns.to_numpy()).sum(axis=1)})


def female_share(keys):
    t = bc7[bc7["GENDER_CD"].isin(["1", "2"])].groupby(keys + ["GENDER_CD"])["amt"].sum().unstack("GENDER_CD", fill_value=0)
    return t["2"] / (t["1"] + t["2"])


ga, ra = age_stats(JOIN_KEY), age_stats(REGION_KEY)
reg_of = gf.index.droplevel("bc_업종")
gf["age_hhi"] = ga["hhi"].reindex(gf.index)
gf["age_mean_dev"] = ga["mean"].reindex(gf.index) - ra["mean"].reindex(reg_of).to_numpy()          # 이 업종 고객이 그 지역 평균보다 얼마나 나이 든/젊은가
gf["fem_dev"] = female_share(JOIN_KEY).reindex(gf.index) - female_share(REGION_KEY).reindex(reg_of).to_numpy()
rs = bc7.groupby(REGION_KEY)["amt"].sum() / 6                                                        # 시군구 월평균 BC 소비(7업종)
n1_reg = n1.groupby(level=[0, 1]).sum()
gf["reg_spend_ps"] = np.log((rs / n1_reg.reindex(rs.index).clip(lower=1)).reindex(reg_of).to_numpy().clip(min=1))   # 지역 소비력(점포당)
gf["grp_share_reg"] = np.log(amt.mean(axis=1).clip(lower=1) / rs.reindex(reg_of).to_numpy())          # 지역 소비 중 이 업종의 점유
gf["bc_growth"] = np.log(amt[yymm[-1]].clip(lower=1) / amt[yymm[0]].clip(lower=1))                   # 6월/1월(동시기 관측이라 역인과 가능)
gf["bc_cv"] = amt.std(axis=1) / amt.mean(axis=1).clip(lower=1)
gf = gf.reset_index()

# 시군구 단위: 9업종 전체 1/1 영업 점포 수, 500m 밀집도
print("시군구 규모·밀집도 계산(final_joined 재조회)...", flush=True)
allst = pd.read_csv("data/final_joined.csv", encoding="utf-8-sig",
                    usecols=["인허가일자", "폐업일자", "SIDO_NM", "CCG_NM", "좌표정보(X)", "좌표정보(Y)", "좌표의심"],
                    parse_dates=["인허가일자", "폐업일자"], low_memory=False)
a = allst[alive(allst, LM)].reset_index(drop=True)
reg = a.groupby(REGION_KEY).size().rename("n_reg").reset_index()
reg["log_n_reg"] = np.log(reg["n_reg"])
ok = a["좌표정보(X)"].notna() & a["좌표정보(Y)"].notna() & (a["좌표의심"].fillna(0) == 0)
xy = a.loc[ok, ["좌표정보(X)", "좌표정보(Y)"]].to_numpy(float)
cntn = cKDTree(xy).query_ball_point(xy, r=500, return_length=True, workers=-1) - 1
a.loc[ok, "nbr500"] = np.log1p(cntn)
reg = reg.merge(a.groupby(REGION_KEY)["nbr500"].median().rename("log_dens500").reset_index(), on=REGION_KEY, how="left")
del allst, a

n0 = len(full)
full = full.merge(gf.drop(columns="n_jan1"), on=JOIN_KEY, how="left", validate="m:1")
full = full.merge(reg[REGION_KEY + ["log_n_reg", "log_dens500"]], on=REGION_KEY, how="left", validate="m:1")
assert len(full) == n0
M6_VARS = ["age_hhi", "age_mean_dev", "fem_dev", "reg_spend_ps", "grp_share_reg", "bc_growth", "bc_cv"]
NEW = ["log_n_grp", "spend_jan", "spend_6f", "spend_6d", "unit_z_jan", "unit_z_6", "log_n_reg", "log_dens500", *M6_VARS]
for c in NEW:
    na = int(full[c].isna().sum())
    if na:
        print(f"  결측 {c}: {na:,}행 -> 중앙값 대체")
        full[c] = full[c].fillna(full[c].median())
# --- M7: 그룹 구성(맥락 효과) — 사업장 단위 변수의 그룹 평균. 전부 1/1 코호트에서 계산(사전 결정) ---
CTX = ["ctx_fr", "ctx_age", "ctx_multi"]
for src, dst in (("is_franchise", "ctx_fr"), ("log_age", "ctx_age"), ("is_multiuse", "ctx_multi")):
    full[dst] = full.groupby("group_id")[src].transform("mean")
NEW = NEW + CTX
full.drop_duplicates(JOIN_KEY)[JOIN_KEY + NEW].to_csv("output/8_group_features.csv", index=False, encoding="utf-8-sig")
grp1 = full.drop_duplicates(JOIN_KEY)
print("\n새 변수 그룹 단위 상관(Spearman):")
print(grp1[NEW].corr(method="spearman").round(2).to_string(), flush=True)

# ============================================
# 2. 모형 정의
# ============================================
M3 = model_cols(ns, TOP)
age_cols = [c for c in M3 if "amt_share_age" in c]
M3n = [c for c in M3 if c not in age_cols]
M4 = M3 + ["log_n_grp"]
M2c, M2hc = model_cols(ns, ns["BASE"]), model_cols(ns, ns["REF"])
SPEC = {   # 이름: (열, 층)
    "M2": (M2c, None), "M2h": (M2hc, None), "M6": (M4 + M6_VARS, None),
    "M7": (M4 + CTX, None),
    "M3": (M3, None), "M3-연령": (M3n, None), "M4": (M4, None),
    "M4v": (M4 + ["log_n_reg", "log_dens500"], None),
    "M5J": (M4 + ["spend_jan", "unit_z_jan"], None),
    "M5S": (M4 + ["spend_6f", "unit_z_6"], None),
    "M5D": (M4 + ["spend_6d", "unit_z_6"], None),
}
ST = ["region_id"]
SPEC_S = {"M7s": (M4 + CTX, ST), "M6s": (M4 + [v for v in M6_VARS if v not in ("reg_spend_ps", "age_mean_dev")], ST), "M3s": (M3, ST), "M3s-연령": (M3n, ST), "M4s": (M4, ST),
          "M5Js": (M4 + ["spend_jan", "unit_z_jan"], ST), "M5Ds": (M4 + ["spend_6d", "unit_z_6"], ST)}
PAIRS = [("M7", "M4", "그룹 구성(프랜차이즈·영업연수·다중이용 그룹 평균)"), ("M3", "M2h", "BC카드 전체(성별·연령)"), ("M2h", "M2", "지역 최근 폐업률"), ("M6", "M4", "추가 BC 특성 7개(M6)"),
         ("M3", "M3-연령", "연령 블록"), ("M4", "M3", "경쟁밀도(그룹)"), ("M4v", "M4", "시군구 규모·밀집도"),
         ("M5J", "M4", "소비(1월)"), ("M5S", "M4", "소비(6개월, 1/1 분모)"), ("M5D", "M4", "소비(6개월, 월별 분모)"),
         ("M5J", "M5D", "1월 vs 6개월(월별 분모) 차이")]
PAIRS_S = [("M7s", "M4s", "그룹 구성(프랜차이즈·영업연수·다중이용 그룹 평균)"), ("M6s", "M4s", "추가 BC 특성 7개(M6)"), ("M3s", "M3s-연령", "연령 블록"), ("M4s", "M3s", "경쟁밀도(그룹)"),
           ("M5Js", "M4s", "소비(1월)"), ("M5Ds", "M4s", "소비(6개월, 월별 분모)")]


def fit_params(name, cols, train, strata=None):
    """계수와 (일반)표준오차만 캐시한다(모형 객체는 학습 데이터를 품고 있어 무겁다)."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    ident = ("p", name, len(train), tuple(cols), tuple(strata or ()))
    path = CACHE_DIR / ("par_" + hashlib.md5(repr(ident).encode("utf-8")).hexdigest()[:12] + ".joblib")
    if not args.no_cache and path.exists():
        return joblib.load(path)
    keep = list(dict.fromkeys(list(cols) + ["duration", "event"] + list(strata or ())))
    cph = CoxPHFitter(strata=list(strata) if strata else None).fit(train[keep], duration_col="duration", event_col="event")
    out = {"params": cph.params_.copy(), "se": cph.standard_errors_.copy()}
    joblib.dump(out, path)
    return out


# ============================================
# 3. 그룹 단위 평가 도구
# ============================================
gid = full["group_id"].to_numpy()
G = int(gid.max()) + 1
n_g = np.bincount(gid, minlength=G).astype(float)
ev_g = np.bincount(gid, weights=full["event"].to_numpy(float), minlength=G)
rate_g = ev_g / np.maximum(n_g, 1)
reg_g = np.zeros(G, dtype=int)
reg_g[gid] = full["region_id"].to_numpy()
keep = n_g >= MIN_N
cnt_reg = np.bincount(reg_g[keep], minlength=reg_g.max() + 1)
keep2 = keep & (cnt_reg[reg_g] >= 2)          # 시군구 내 편차는 같은 시군구에 평가 그룹이 2개 이상일 때만 의미가 있다
R = int(reg_g.max()) + 1


def group_lp(lp):
    return np.bincount(gid, weights=lp, minlength=G) / np.maximum(n_g, 1)


def dev_within(x, mask):
    w = np.where(mask, n_g, 0.0)
    rm = np.bincount(reg_g, weights=w * x, minlength=R) / np.maximum(np.bincount(reg_g, weights=w, minlength=R), 1e-9)
    return x - rm[reg_g]


def rho(x, y):
    return float(spearmanr(x, y).statistic)


def make_boots(mask, rng):
    idx = np.where(mask)[0]
    by = {r: idx[reg_g[idx] == r] for r in np.unique(reg_g[idx])}
    ks = list(by)
    return [np.concatenate([by[k] for k in rng.choice(ks, size=len(ks), replace=True)]) for _ in range(B)]


def evaluate(oof, pairs, tag, label, allow_overall=True):
    """oof: {모형: 행 단위 선형예측자}. 그룹 평균 위험점수 vs 관측 폐업률의 Spearman과 모형 간 증분."""
    lpg = {n: group_lp(v) for n, v in oof.items()}
    rng = np.random.default_rng(42)
    boots = {"전체 그룹": make_boots(keep, rng), "같은 시군구 내 편차": make_boots(keep2, rng)}
    dev = {n: dev_within(x, keep2) for n, x in lpg.items()}
    rate_dev = dev_within(rate_g, keep2)
    view = {"전체 그룹": (lpg, rate_g, keep), "같은 시군구 내 편차": (dev, rate_dev, keep2)}
    print(f"\n[{label}] 평가 그룹(n>={MIN_N}) {int(keep.sum())}개, 시군구 {len(np.unique(reg_g[keep]))}개 / 시군구 내 편차 대상 {int(keep2.sum())}개", flush=True)
    rows, inc = [], []
    for kind, (xs, y, m) in view.items():
        bs = boots[kind]
        for n in oof:
            if kind == "전체 그룹" and n.endswith("s") or (kind == "전체 그룹" and "s-" in n):
                continue                                   # 층화 모형은 시군구 간 차이를 지워서 전체 기준이 무의미
            v = np.array([rho(xs[n][b], y[b]) for b in bs])
            rows.append({"설계": label, "기준": kind, "모형": n, "Spearman": round(rho(xs[n][m], y[m]), 3),
                         "95% CI": f"[{np.percentile(v, 2.5):.3f}, {np.percentile(v, 97.5):.3f}]"})
        for a_, b_, what in pairs:
            if a_ not in xs or b_ not in xs:
                continue
            if kind == "전체 그룹" and (a_.endswith("s") or "s-" in a_):
                continue
            d0 = rho(xs[a_][m], y[m]) - rho(xs[b_][m], y[m])
            v = np.array([rho(xs[a_][b], y[b]) - rho(xs[b_][b], y[b]) for b in bs])
            lo, hi = np.percentile(v, [2.5, 97.5])
            inc.append({"설계": label, "기준": kind, "블록": what, "비교": f"{a_} − {b_}", "ΔSpearman": round(d0, 3),
                        "95% CI": f"[{lo:.3f}, {hi:.3f}]", "CI가 0 제외": "예" if (lo > 0 or hi < 0) else "아니오"})
    t1, t2 = pd.DataFrame(rows), pd.DataFrame(inc)
    t1.to_csv(f"output/8_cv_{tag}_spearman.csv", index=False, encoding="utf-8-sig")
    t2.to_csv(f"output/8_cv_{tag}_increment.csv", index=False, encoding="utf-8-sig")
    print(t1.to_string(index=False))
    print(t2.to_string(index=False), flush=True)
    return t1, t2


def cross_val(fold_row, specs, tag):
    oof = {n: np.full(len(full), np.nan) for n in specs}
    for k in range(K):
        te = fold_row == k
        tr_df, te_df = full[~te], full[te]
        for n, (cols, st) in specs.items():
            t0 = time.time()
            p = fit_params(f"{tag}{k}|{n}", cols, tr_df, st)
            b = p["params"].reindex(cols).to_numpy()
            oof[n][te] = (te_df[cols].to_numpy(float) - tr_df[cols].to_numpy(float).mean(axis=0)) @ b   # 학습 평균으로 중심화: fold마다 달라지는 상수를 없앤다
            print(f"  [{tag} fold {k + 1}/{K}] {n}: {time.time() - t0:.0f}s", flush=True)
    for n in oof:
        assert not np.isnan(oof[n]).any()
    return oof


# ============================================
# 4. 전체 적합: 새 변수 계수(일반 SE는 상대 비교용)
# ============================================
print("\n=== 전체 코호트 적합: 새 변수 계수 ===", flush=True)
rows = []
for n in ("M4", "M4v", "M5J", "M5D", "M6", "M7"):
    cols, _ = SPEC[n]
    p = fit_params("full|" + n, cols, full)
    for c in cols:
        if c in NEW:
            sd = float(full[c].std())
            rows.append({"모형": n, "변수": c, "coef": round(p["params"][c], 4), "HR/1SD": round(float(np.exp(p["params"][c] * sd)), 3),
                         "SD": round(sd, 3), "z(일반SE, 상대비교용)": round(p["params"][c] / p["se"][c], 1)})
ft = pd.DataFrame(rows)
ft.to_csv("output/8_fullfit_new_vars.csv", index=False, encoding="utf-8-sig")
print(ft.to_string(index=False), flush=True)

# ============================================
# 5. 그룹 5-fold
# ============================================
groups = ns["groups"]
fg = np.zeros(len(groups), dtype=int)
for k, (_, te_i) in enumerate(StratifiedKFold(K, shuffle=True, random_state=42).split(groups, groups["bc_업종"])):
    fg[te_i] = k
fold_row = fg[gid]
specs_all = {**SPEC, **SPEC_S}
oof = cross_val(fold_row, specs_all, "g")
np.savez("output/_cache/oof_group.npz", **oof)   # moran_residuals.py가 미학습 예측 잔차를 볼 때 쓴다
ev = full["event"].to_numpy()
du = full["duration"].to_numpy()
cidx = {n: round(concordance_index(du, -v, ev), 4) for n, v in oof.items() if not (n.endswith("s") or "s-" in n)}
print("\n사업장 단위 C-index(모은 미학습 예측, 층화 제외):", cidx, flush=True)
pd.Series(cidx, name="C-index(OOF)").to_csv("output/8_cv_group_cindex.csv", encoding="utf-8-sig")
evaluate(oof, PAIRS + PAIRS_S, "group", "그룹 5-fold")

# ============================================
# 6. 시군구 5-fold (미학습 시군구 외삽)
# ============================================
if not args.skip_region:
    rids = np.arange(R)
    fr = np.zeros(R, dtype=int)
    for k, (_, te_i) in enumerate(KFold(K, shuffle=True, random_state=42).split(rids)):
        fr[te_i] = k
    oof_r = cross_val(fr[full["region_id"].to_numpy()], SPEC, "r")
    evaluate(oof_r, PAIRS, "region", "시군구 5-fold")
print("\n완료", flush=True)
