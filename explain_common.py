# -*- coding: utf-8 -*-
"""
explain_cox.py(SHAP 분해)와 moran_residuals.py(잔차 공간 점검)가 공유하는 코호트 로더와 Cox 적합 캐시.

cox_rsf.py를 고치지 않기 위해, 그 파일에서 "코호트 생성 ~ 모형 정의"까지의 앞부분(평가 도구 절 직전까지)을 그대로 실행해서
`full`(코호트 데이터), `MODELS`, `BIZ_DUMMY` 등을 가져온다. 코드를 복사하지 않으므로 코호트 정의가 두 곳에서 어긋날 일이 없다.
(cox_rsf.py의 "# 5. 평가 도구" 절 표시를 기준으로 자르므로, 팀원이 그 구조를 바꾸면 여기서 명확한 오류가 난다.)
"""
import contextlib
import hashlib
import io
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from lifelines import CoxPHFitter

CACHE_DIR = Path("output/_cache")
MARKER = "# 5. 평가 도구"


def load_cohort(design="cohort", end="2026-06-30", tag="_explain", expect=("635,567", "25,330")):
    """cox_rsf.py의 코호트 생성부를 실행해 네임스페이스를 돌려준다. 반환: (ns, 실행 로그)."""
    src = Path("cox_rsf.py").read_text(encoding="utf-8").replace("\r\n", "\n")
    if MARKER not in src:
        raise RuntimeError(f"cox_rsf.py에서 '{MARKER}' 절을 찾지 못했다. 파일 구조가 바뀌었으면 explain_common.py의 MARKER를 고쳐야 한다.")
    cut = src.rindex("# ====", 0, src.index(MARKER))
    old_argv = sys.argv
    # --tag: 앞부분이 쓰는 부수 산출물(좌표결측 비교 등)의 파일명이 본 실행 결과와 섞이지 않게 한다
    sys.argv = ["cox_rsf.py", "--design", design, "--end", end, "--tag", tag]
    buf = io.StringIO()
    ns = {"__name__": "cox_rsf_prefix", "__file__": "cox_rsf.py"}
    try:
        with contextlib.redirect_stdout(buf):
            exec(compile(src[:cut], "cox_rsf.py", "exec"), ns)
    finally:
        sys.argv = old_argv
    log = buf.getvalue()
    if design == "cohort" and end == "2026-06-30":
        missing = [x for x in expect if x not in log]
        if missing:
            raise RuntimeError(f"코호트 규모가 기대와 다르다(찾지 못한 값 {missing}). 원본 데이터나 코드 버전이 다른지 확인하라.\n{log[-1500:]}")
    return ns, log


def fit_cox_cached(name, cols, full, use_cache=True, strata=None, cluster_col=None):
    """지정한 열로 Cox PH를 적합한다. 같은 (이름, 행 수, 열, 층, 군집)이면 캐시를 재사용한다.
    strata: 층별로 기저위험을 따로 두는 열(예: ["region_id"]). cluster_col: 군집-강건(sandwich) 분산에 쓸 열."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    ident = (name, len(full), tuple(cols)) + ((tuple(strata), cluster_col) if (strata or cluster_col) else ())   # 옵션이 없으면 기존 캐시 키와 같다
    key = "cox_" + hashlib.md5(repr(ident).encode("utf-8")).hexdigest()[:12] + ".joblib"   # hash()는 실행마다 달라져 못 쓴다
    path = CACHE_DIR / key
    if use_cache and path.exists():
        return joblib.load(path)
    keep = list(dict.fromkeys(list(cols) + ["duration", "event"] + (list(strata) if strata else []) + ([cluster_col] if cluster_col else [])))   # 중복 열 방지
    cph = CoxPHFitter(strata=list(strata) if strata else None).fit(
        full[keep], duration_col="duration", event_col="event", cluster_col=cluster_col)
    joblib.dump(cph, path)
    return cph


def model_cols(ns, name):
    """모형 이름 -> 열 목록(업종 더미 포함)."""
    return list(ns["MODELS"][name]) + list(ns["BIZ_DUMMY"])
