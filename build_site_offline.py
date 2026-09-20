# -*- coding: utf-8 -*-
"""
output/ 없이 docs/index.html 을 다시 만든다(로컬에 분석 산출물이 없을 때의 대안).

build_site.py 와 같은 TEMPLATE/EXTRA_CSS 를 쓰고, 데이터·생존 분석 탭·리포트 CSS 는 site_parts/ 에 보관한
값(직전 build_site.py 실행 결과에서 그대로 떼어 둔 것)을 채운다. 즉 화면(표시·문구·레이아웃)만 build_site.py 에서
고치고 이 스크립트로 docs/ 를 갱신한다. 수치 데이터(site_parts/site_data.json)는 이 스크립트가 바꾸지 않는다.
"""
import json
import re
from pathlib import Path

src = Path("build_site.py").read_text(encoding="utf-8")
EXTRA_CSS = re.search(r'EXTRA_CSS = r"""(.*?)"""', src, re.S).group(1)
TEMPLATE = re.search(r'TEMPLATE = r"""(.*?</html>)"""', src, re.S).group(1)

P = Path("site_parts")
data = (P / "site_data.json").read_text(encoding="utf-8")
css = (P / "report.css").read_text(encoding="utf-8")
from site_surv import transform as surv_transform
surv = surv_transform((P / "surv.html").read_text(encoding="utf-8"))   # site_parts/surv.html은 원문 그대로 보관
meta = json.loads((P / "meta.json").read_text(encoding="utf-8"))
nat = json.loads(data)["national"]

html_out = (TEMPLATE.replace("__CSS__", css).replace("__EXTRA__", EXTRA_CSS).replace("__DATA__", data).replace("__SURV__", surv).replace("__LEAFLET_CSS__", Path("vendor/leaflet.css").read_text(encoding="utf-8")).replace("__LEAFLET_JS__", Path("vendor/leaflet.js").read_text(encoding="utf-8"))
            .replace("__N__", f"{nat['n']:,}").replace("__EV__", f"{nat['events']:,}").replace("__RATE__", f"{nat['rate'] * 100:.2f}")
            .replace("__RHO_ALL__", meta["rho_all"]).replace("__RHO_IN__", meta["rho_in"]))
Path("docs").mkdir(exist_ok=True)
Path("docs/index.html").write_text(html_out, encoding="utf-8")
Path("docs/.nojekyll").write_text("", encoding="utf-8")
print(f"docs/index.html 작성 ({len(html_out) / 1024:.0f} KB)")
