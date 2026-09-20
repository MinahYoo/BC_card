# -*- coding: utf-8 -*-
"""
상권 생존 분석 웹사이트 site/index.html 을 만든다 (서버 없는 단일 HTML; GitHub Pages 등 정적 호스팅에 그대로 올릴 수 있다).

탭: 지도 탐색(시군구 버블 지도 · 업종 필터 · 위험 배수 · "왜" 요인 분해 · BC 구성/월별 · 이웃 5곳 · 규칙 기반 설명 입력창)
    상권 분석(시군구 프로필 · 업종별 위험 순위 · 소비-폐업 산점도) / 생존 분석(리포트 본문) / 방법·한계
사전 조건: prep_site_data.py 실행(output/site_data.json). 생존 분석 탭은 build_report.py의 본문을 그대로 재사용한다.
모든 수치는 분석 산출물에서 왔고, 설명 문장은 규칙으로 만든다(LLM 없음 -> 값이 틀리거나 지어질 수 없다).
"""
import json
import re
from pathlib import Path

import build_report as R                     # report/index.html도 함께 갱신된다

data = Path("output/site_data.json").read_text(encoding="utf-8")
css = re.search(r"<style>(.*?)</style>", R.HTML, re.S).group(1)
surv = R.HTML[R.HTML.index("<h2>한눈에"):R.HTML.index("<footer>")]
nat = json.loads(data)["national"]

EXTRA_CSS = r"""
/* 디자인 토큰: UI 강조색(--acc)은 하나로 통일하고, 빨강/파랑(--hi/--lo)은 위험·안전 데이터 표현에만 쓴다 */
:root{--acc:#0f6b63;--acc-fg:#fff;--acc-soft:rgba(15,107,99,.10);--sub:#566173;
 --hi:#d64541;--lo:#2d6ebe;--hi-text:#b42f2b;--lo-text:#1f5aa6;--hi-soft:rgba(214,69,65,.15);--lo-soft:rgba(45,110,190,.15);--flat:#7d8696;
 --s1:4px;--s2:8px;--s3:12px;--s4:16px;--s5:24px;--fs-sm:14px;--fs-md:15px;--fs-lg:18px;--r:10px;--head-h:58px}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--acc:#5fd3c6;--acc-fg:#0b1f1d;--acc-soft:rgba(95,211,198,.14);--sub:#a8b1c0;
 --hi:#f0716d;--lo:#6ea8f0;--hi-text:#f59e9b;--lo-text:#8fbcf5;--hi-soft:rgba(240,113,109,.2);--lo-soft:rgba(110,168,240,.2);--flat:#8c95a5}}
html{scroll-padding-top:calc(var(--head-h) + 8px)}
body{scroll-behavior:smooth}
button,select,input{font-family:inherit}
:focus-visible{outline:2px solid var(--acc);outline-offset:2px}
.top{position:sticky;top:0;z-index:20;background:var(--bg);border-bottom:1px solid var(--line)}
.top .in{max-width:1180px;margin:0 auto;padding:10px var(--s4);display:flex;flex-wrap:wrap;gap:var(--s2) 18px;align-items:center;justify-content:space-between}
.brand{font-weight:800;font-size:16px} .brand span{color:var(--sub);font-weight:500;font-size:var(--fs-sm);margin-left:var(--s2)}
nav{display:flex;gap:var(--s1);flex-wrap:wrap}
nav button{border:1px solid var(--line);background:var(--card);color:var(--fg);padding:7px 14px;border-radius:999px;font-size:var(--fs-sm);cursor:pointer}
nav button:hover{border-color:var(--acc);color:var(--acc)}
nav button[aria-selected="true"],nav button[aria-selected="true"]:hover{background:var(--acc);border-color:var(--acc);color:var(--acc-fg)}
main.wide{max-width:1180px;padding-bottom:80px} section.tab{display:none;padding-top:var(--s4)} section.tab.on{display:block}
.hero{padding:2px 0 var(--s2)} .hero h1{font-size:clamp(20px,3vw,26px);margin:0 0 2px} .hero p{margin:0;color:var(--sub);font-size:var(--fs-sm)}
.ctrl{display:flex;flex-wrap:wrap;gap:10px 14px;align-items:center;margin:var(--s2) 0 14px}
.toolbar{display:flex;flex-wrap:wrap;gap:var(--s2) var(--s3);align-items:center;margin:var(--s2) 0 6px}
.toolbar label{display:flex;align-items:center;gap:6px;color:var(--sub);font-size:var(--fs-sm)}
.chips{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin:0 0 6px}
.chip-b{border:1px solid var(--line);background:var(--card);color:var(--fg);padding:6px 12px;border-radius:999px;font-size:var(--fs-sm);cursor:pointer}
.chip-b:hover{border-color:var(--acc);background:var(--acc-soft)}
.chip-b.on,.chip-b.pri{background:var(--acc);color:var(--acc-fg);border-color:var(--acc)}
.chip-b.pri:hover{filter:brightness(1.08)}
select,input[type=text]{font-size:var(--fs-sm);padding:7px 10px;border:1px solid var(--line);border-radius:8px;background:var(--card);color:var(--fg)}
select:hover,input[type=text]:hover{border-color:var(--acc)}
input[type=text]{min-width:min(260px,100%);flex:1}
.grid2{display:grid;grid-template-columns:minmax(0,1.1fr) minmax(0,1fr);gap:var(--s4);align-items:start}
.mapcard{position:sticky;top:calc(var(--head-h) + 12px);padding:6px;isolation:isolate}
#map{width:100%;height:clamp(440px,calc(100vh - 300px),760px);border-radius:8px;z-index:0}
@media (max-width:767px){.grid2{grid-template-columns:1fr}.mapcard{position:static}#map{height:min(62vh,520px);min-height:340px}.brand span{display:none}.top{position:static}.top .in{padding:var(--s2) var(--s4)}nav button{padding:6px 10px}.maplegend{width:156px;font-size:12px;padding:5px 8px 4px}.maplegend .lg-t{font-size:11.5px;margin-bottom:3px}.maplegend .lg-d{display:none}}
.leaflet-container{font:inherit;background:var(--card)} .leaflet-tile-pane .tiles-osm{filter:grayscale(1) contrast(.88) brightness(1.08)}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]) .leaflet-tile-pane .tiles-osm{filter:grayscale(1) invert(1) contrast(.85) brightness(.85)}}
.leaflet-tooltip{font-size:13px;line-height:1.4}
.maplegend{background:color-mix(in srgb,var(--card) 93%,transparent);color:var(--fg);border:1px solid var(--line);border-radius:8px;padding:7px 10px 8px;font-size:12.5px;line-height:1.35;box-shadow:0 1px 5px rgba(0,0,0,.18);width:224px}
.maplegend .lg-t{font-weight:700;margin-bottom:5px}
.maplegend .lg-bar{height:10px;border-radius:5px;background:linear-gradient(90deg,rgb(45,110,190),rgb(232,230,222),rgb(214,69,65))}
.maplegend .lg-ticks{position:relative;height:17px;margin-top:2px;color:var(--sub);font-size:12px}
.maplegend .lg-ticks span{position:absolute;top:3px;white-space:nowrap} .maplegend .lg-ticks i{position:absolute;top:-1px;width:1px;height:4px;background:var(--sub)}
.maplegend .lg-r{display:flex;align-items:center;gap:6px;color:var(--sub);margin-top:3px}
.maplegend .dot{display:inline-block;border-radius:50%;background:var(--flat);border:1px solid rgba(0,0,0,.4);flex:none}
.maplegend .dot.dash{width:11px;height:11px;background:rgba(154,160,166,.35);border:1.5px dashed #6b7280}
.leaflet-control-attribution{font-size:11px;line-height:1.35}
.mapbtns{display:flex;gap:6px}
.mapbtns button{font-size:13px;padding:6px 10px;border-radius:8px;border:1px solid var(--line);background:var(--card);color:var(--fg);cursor:pointer;box-shadow:0 1px 4px rgba(0,0,0,.18)}
.mapbtns button:hover{border-color:var(--acc);color:var(--acc)}
.city-lbl{font-size:12px;font-weight:600;color:#5b6472;text-shadow:0 0 3px #fff,0 0 3px #fff,0 0 3px #fff;white-space:nowrap;pointer-events:none}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]) .city-lbl{color:#b7bfcc;text-shadow:0 0 3px #000,0 0 3px #000}}
.panel h3{margin:0 0 2px;font-size:20px} .panel .sub2{color:var(--sub);font-size:var(--fs-sm)}
.panel .clear{float:right;margin-left:var(--s2)} .only-m{display:none} @media (max-width:767px){.only-m{display:inline-block}div.only-m{display:block}}
.big{display:flex;align-items:baseline;gap:14px;flex-wrap:wrap;margin:var(--s2) 0 2px} .big b{font-size:38px;line-height:1}
.big span{color:var(--sub);font-size:var(--fs-sm)}
.t-hi{color:var(--hi-text)}.t-lo{color:var(--lo-text)} .big .delta{font-weight:700;font-size:var(--fs-md)}
.hasq{position:relative}
.q{width:18px;height:18px;border-radius:50%;border:1px solid var(--sub);background:transparent;color:var(--sub);font-size:12px;line-height:1;padding:0;margin-left:4px;cursor:help;flex:none;vertical-align:middle}
.q:hover,.q:focus-visible,.q.open{border-color:var(--acc);color:var(--acc)}
.q::after{content:attr(data-tip);display:none;position:absolute;z-index:30;left:0;top:calc(100% + 4px);width:min(290px,78vw);padding:8px 10px;border-radius:8px;background:var(--fg);color:var(--bg);font-size:var(--fs-sm);font-weight:400;line-height:1.5;text-align:left;box-shadow:0 4px 14px rgba(0,0,0,.25)}
.q:hover::after,.q:focus-visible::after,.q.open::after{display:block}
.fx{margin:4px 0}
.fxrow{display:grid;grid-template-columns:minmax(118px,38%) minmax(0,1fr) 52px;align-items:center;gap:var(--s2);margin:7px 0;font-size:var(--fs-sm)}
.fxrow .nm{display:flex;align-items:center;line-height:1.3}
.fxrow .trk{position:relative;height:16px}
.fxrow .trk::before{content:"";position:absolute;left:50%;top:-5px;bottom:-5px;border-left:1px dashed var(--sub)}
.fxrow .fbar{position:absolute;top:0;bottom:0;border-radius:3px}
.fxrow .fbar.hi{background:var(--hi)}.fxrow .fbar.lo{background:var(--lo)}.fxrow .fbar.soft{opacity:.42}
.fxrow .val{text-align:right;font-weight:600;font-variant-numeric:tabular-nums}
.rklist{display:flex;flex-direction:column;gap:6px}
.rk{display:grid;grid-template-columns:24px minmax(0,1fr) auto;column-gap:var(--s2);align-items:baseline;text-align:left;width:100%;border:1px solid var(--line);background:var(--card);color:var(--fg);border-radius:8px;padding:7px 10px;font-size:var(--fs-sm);cursor:pointer}
.rk:hover{border-color:var(--acc);background:var(--acc-soft)}
.rk .rn{color:var(--sub);font-weight:700}.rk .rt{font-weight:600}.rk .rv{font-weight:700}.rk .rs{grid-column:2/4;color:var(--sub)}
.tag{display:inline-block;padding:1px 9px;border-radius:999px;font-size:13px;background:var(--line);color:var(--fg);margin:0 2px}
.tag.hi{background:var(--hi-soft);color:var(--hi-text)} .tag.lo{background:var(--lo-soft);color:var(--lo-text)}
.why{margin:6px 0 4px} .why p{margin:6px 0;font-size:var(--fs-md)}
.blk{border-top:1px solid var(--line);margin-top:14px;padding-top:var(--s3)} .blk h4{margin:0 0 6px;font-size:var(--fs-sm);color:var(--sub);font-weight:600}
.two{display:grid;grid-template-columns:1fr 1fr;gap:var(--s3)} @media (max-width:520px){.two{grid-template-columns:1fr}}
.mini{max-width:280px;width:100%}.mini text{font-size:11px;fill:var(--fg)} .mini .v{fill:var(--sub)}
.spark{width:100%;max-width:320px;height:auto}
.nb{display:flex;flex-wrap:wrap;gap:6px} .nb button{border:1px solid var(--line);background:var(--card);color:var(--fg);border-radius:8px;padding:5px 10px;font-size:var(--fs-sm);cursor:pointer}
.nb button:hover{border-color:var(--acc);background:var(--acc-soft)}
.warn{background:var(--warn);border:1px solid var(--warnb);border-radius:8px;padding:8px 12px;font-size:var(--fs-sm);margin:var(--s2) 0}
.hint{color:var(--sub);font-size:var(--fs-sm)}
.tbl td.b1{min-width:120px} .mb{display:inline-block;height:9px;border-radius:3px;vertical-align:middle;margin-right:6px}
.kp{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin:10px 0}
.kp div{background:var(--bg);border:1px solid var(--line);border-radius:var(--r);padding:10px var(--s3)} .kp b{display:block;font-size:20px} .kp span{font-size:var(--fs-sm);color:var(--sub)}
.scat circle{opacity:.75} .scat text{font-size:11px;fill:var(--sub)}
.cols3{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:14px}
.legend2{display:flex;flex-wrap:wrap;align-items:center;gap:6px 10px;font-size:var(--fs-sm);color:var(--sub);margin:var(--s2) 4px 2px}.legend2 span{white-space:nowrap}
.cap{font-size:var(--fs-sm)}
#err{display:none;background:#fee;color:#900;padding:8px;font-size:12px}
"""

TEMPLATE = r"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>상권 생존 지도</title>
<style>__LEAFLET_CSS__
__CSS__
__EXTRA__</style></head><body>
<div id="err"></div>
<div class="top"><div class="in">
<div class="brand">상권 생존 지도<span>BC카드 소비데이터 공모전</span></div>
<nav id="nav" role="tablist">
<button data-t="map" aria-selected="true">지도 탐색</button><button data-t="area" aria-selected="false">상권 분석</button>
<button data-t="surv" aria-selected="false">생존 분석</button><button data-t="method" aria-selected="false">방법 · 한계</button></nav>
</div></div>
<main class="wide">

<section class="tab on" id="t-map">
<div class="hero"><h1>어느 지역·업종이 왜 위험한가</h1>
<p>2026-01-01 영업 중이던 점포 __N__개를 180일 추적했어요. 색은 평균 점포 대비 폐업 위험(연관이며 인과 아님)이고, 버블을 누르면 이유를 볼 수 있어요.</p></div>
<div class="toolbar">
<input type="text" id="ask" placeholder="예) 동탄 서양음식 / 합천 한식 / 한식 위험한 곳" aria-label="지역·업종 질문">
<button class="chip-b pri" id="askbtn">설명 보기</button>
<label>색 기준 <select id="mode"><option value="mult">폐업 위험도 (평균 점포 대비)</option><option value="rate">실제 폐업률 (전국 대비)</option></select></label>
</div>
<div class="chips" id="bizbar"></div>
<div class="hint" id="askhelp" style="margin:0 0 var(--s3)">지역·업종·위험/안전을 조합해 검색해 보세요. 예: <button class="chip-b" data-q="동탄 서양음식">동탄 서양음식</button> <button class="chip-b" data-q="합천 한식">합천 한식</button> <button class="chip-b" data-q="강남구">강남구</button> <button class="chip-b" data-q="한식 위험한 곳">한식 위험한 곳</button> <button class="chip-b" data-q="경남 한식 안전한 곳">경남 한식 안전한 곳</button></div>
<div class="grid2">
<div class="card mapcard"><div id="map" role="region" aria-label="시군구 버블 지도"></div><div class="hint only-m" style="margin:6px 4px 2px">버블 크기 = 점포 수 · 점선 회색 = 표본 30개 미만(업종 선택 시)</div><div class="hint" id="tilenote" style="margin:2px 4px 0;color:var(--hi-text)"></div></div>
<div class="card panel" id="panel"></div>
</div>
</section>

<section class="tab" id="t-area">
<div class="hero"><h1>상권 분석</h1><p>시군구를 고르면 업종별 점포 수·실제 폐업률·위험 배수·영업연수·프랜차이즈 비중·BC카드 월평균 소비를 한눈에 봅니다.</p></div>
<div class="ctrl"><input type="text" id="areaq" list="rlist" placeholder="시군구 검색 (예: 화성시 동탄구, 강남구, 합천군)"><datalist id="rlist"></datalist></div>
<div id="areaout" class="card"><p class="hint">시군구를 선택하세요.</p></div>
<h3 style="margin-top:28px">업종별 위험 순위 (점포 300개 이상 그룹)</h3>
<div class="ctrl"><select id="rankbiz"></select></div>
<div class="cols3"><div class="card" id="rk-hi"></div><div class="card" id="rk-lo"></div></div>
<h3 style="margin-top:28px">소비가 많으면 버티는가? — 점포당 소비와 실제 폐업률</h3>
<div class="card"><div id="scat"></div><p class="cap">점 하나 = 시군구×업종 그룹(점포 100개 이상), 굵은 선 = 소비 10분위별 실제 폐업률. 소비 하위 구간의 폐업률이 가장 낮고 중·상위에서는 비슷한 수준으로 이어집니다 — 소비가 높다고 덜 폐업하지 않습니다. 업종 안 소비 순위와 폐업률의 순위상관은 전체 __RHO_ALL__, 같은 시군구 안에서는 __RHO_IN__(관계 없음)입니다.</p></div>
</section>

<section class="tab" id="t-surv">__SURV__</section>

<section class="tab" id="t-method">
<div class="hero"><h1>방법과 한계</h1></div>
<div class="card"><ul>
<li><b>대상·결과:</b> LOCALDATA 인허가 4종의 2026-01-01 영업 중 점포(7개 업종, __N__개)를 2026-06-30까지 180일 추적, 폐업 __EV__건(__RATE__%).</li>
<li><b>모형(M3L):</b> Cox 비례위험 모형. 사업장 변수(영업연수·프랜차이즈·입지·사업장 특성) + 그룹 직전 1년 폐업률 + 자기·이웃 시군구 폐업 이력(1/1 이전 정보만) + BC카드 성별·연령 구성 + 업종.</li>
<li><b>“왜” 분해:</b> 선형예측자를 요인별 기여 β·(x−평균)로 정확히 분해(오차 10⁻¹⁵). exp(기여) = 평균 점포 대비 배수, 요인 배수의 곱 = 위험 배수. <b>연관이며 인과가 아닙니다.</b></li>
<li><b>검증:</b> 그룹 5-fold, 시군구 5-fold. 신뢰구간은 시군구 단위 부트스트랩. 미학습 그룹 점포 단위 C-index 0.637(0.5 = 무작위)로 중간 정도의 판별력입니다.</li>
<li><b>BC 데이터의 한계:</b> 시군구×업종 평균이라 점포 매출이 아닙니다. 연령 구성은 같은 시군구 안에서 위험을 가르지 못했고 지역 유형 신호로 읽어야 합니다. 소비 규모·객단가·성장률은 예측을 개선하지 못했습니다(3장 표).</li>
<li><b>지도:</b> 시군구 경계가 아니라 시군구 내 점포 좌표의 중앙값(EPSG:5174를 위·경도로 변환, 오차 수백 m)에 놓은 버블입니다. 배경 지도는 OpenStreetMap 타일(회색조)이며 인터넷 연결이 필요합니다(끊겨도 버블·패널은 동작). 2026년 개편 지역명을 그대로 씁니다. 그룹당 점포가 30개 미만이면 실제 폐업률이 불안정해 회색 점선으로 표시합니다.</li>
<li><b>설명 문장:</b> 규칙으로 만든 문장이며 LLM을 쓰지 않습니다. 숫자는 모두 위 분해 결과에서 옵니다.</li>
<li><b>화면 용어:</b> 지도 탭의 “폐업 위험도”는 위 모형(M3L)이 계산한 “위험 배수”(평균 점포 = ×1.0)입니다. 폐업률은 단순 비율이라 순위가 다를 수 있고, 위험 배수는 영업연수·규모 등을 통제한 뒤 평균 점포와 비교한 값입니다.</li>
<li><b>검색창의 범위:</b> 정해진 형식(지역 + 업종, 지역만, 업종 + 위험/안전)만 이해하는 규칙 기반이며 LLM이 아닙니다. 업종은 한식·일식·중식·서양음식·스낵·제과점·편의점 7개뿐이고, 카페·치킨 등 다른 업종, 두 지역 비교, 시점별 추세, 예측 질문은 지원하지 않습니다. 점포 수가 적은 곳(전체 2,000개·업종별 300개 미만)은 순위에서 제외합니다.</li>
<li><b>주의:</b> 6개월 관측 창 하나, 프랜차이즈는 수작업 브랜드 목록 기반, 연령 코드 정의(1~6)는 원자료 명세로 재확인이 필요합니다. 배수는 정책 효과가 아닙니다.</li>
</ul></div>
</section>
</main>

<script>__LEAFLET_JS__</script>
<script>
window.onerror=function(m,s,l){var e=document.getElementById('err');e.style.display='block';e.textContent='JS 오류: '+m+' (줄 '+l+')';};
const D=__DATA__;
const NAT=D.national, BIZ=D.biz;
const $=(s,el=document)=>el.querySelector(s);
const pct=(v,d=1)=>(v*100).toFixed(d)+'%';
// 요인 표시 이름·설명. key는 코드 내부 식별자, idx는 모형 출력 x의 위치(데이터 키)라 바꾸지 않는다.
const SHOW=[
 {key:'yrs',label:'영업 기간',idx:[0],tip:'문을 연 지 얼마나 됐는지예요. 영업한 지 오래된 점포가 많을수록 위험이 낮게 나와요.'},
 {key:'fr',label:'프랜차이즈 비중',idx:[1],tip:'프랜차이즈(가맹) 점포의 비중이에요. 이 모형에서는 비중이 높은 곳이 위험이 낮게 나와요.'},
 {key:'site',label:'점포 규모·운영 특성',idx:[3],tip:'점포 규모, 다중이용시설 여부처럼 점포 자체의 특성이에요.'},
 {key:'hist',label:'지역의 최근 폐업 흐름',idx:[5],tip:'이 시군구와 이웃 시군구에서 2026년 1월 이전 1년 동안 문을 닫은 점포의 비율이에요. 높을수록 위험이 높아요.'},
 {key:'age',label:'BC카드 고객 연령대',idx:[7],tip:'BC카드 결제 고객의 연령대 구성이에요. 같은 시군구 안에서는 위험을 가르지 못했고, 어떤 유형의 지역인지 알려 주는 신호일 뿐이에요. 원인으로 읽으면 안 되어서 옅게 표시하고 해설에서는 뺐어요.'},
 {key:'gen',label:'BC카드 고객 성별',idx:[6],tip:'BC카드 결제 고객의 남성·여성·법인 비중이에요.'},
 {key:'biz',label:'업종 자체의 위험',idx:[8],tip:'업종마다 평균적으로 폐업이 잦은 정도가 달라요. 그 업종 자체가 가진 기본 위험이에요.'},
 {key:'etc',label:'입지·기타 요인',idx:[2,4],tip:'위 항목에 들어가지 않는 입지 등 나머지 요인을 합친 값이에요.'}];
const factors=x=>SHOW.map(s=>({key:s.key,label:s.label,tip:s.tip,m:s.idx.reduce((a,i)=>a*x[i],1)}));
const qa=t=>t.replace(/"/g,'&quot;');
const qtip=t=>'<button type="button" class="q" data-tip="'+qa(t)+'" aria-label="설명: '+qa(t)+'">?</button>';   // (?) 도움말: 마우스를 올리거나 누르면 열린다
document.addEventListener('click',e=>{const q=e.target.closest('.q');document.querySelectorAll('.q.open').forEach(x=>{if(x!==q)x.classList.remove('open');});if(q)q.classList.toggle('open');});
const DELTA=m=>{const pc=Math.round(Math.abs(m-1)*100);return pc===0?'평균 점포와 비슷함':(m>=1?'▲ 평균 점포보다 '+pc+'% 높음':'▼ 평균 점포보다 '+pc+'% 낮음');};
const TIP_RISK='같은 조건(영업연수·규모 등)을 맞춘 뒤 평균 점포와 비교한 폐업 위험의 배수(위험 배수)예요. ×1.0이 평균, ×1.5면 평균보다 50% 높다는 뜻이에요. 연관일 뿐 원인은 아니에요.';
const NOTE_RATE='폐업률은 단순 비율이고, 위험 배수는 영업연수·규모 등을 통제한 뒤 평균 점포와 비교한 값이라 순위가 다를 수 있어요.';
const GI=new Map(); D.groups.forEach((g,i)=>GI.set(g.r*10+g.b,i));
const S={biz:-1,mode:'mult',sel:null,home:true};
const AGE=['연령1','연령2','연령3','연령4','연령5','연령6'], GEN=['남','여','법인'];

function val(r,b){
  if(b<0){const R=D.regions[r];return {mult:R.mult,rate:R.rate,n:R.n,x:R.x,g:null};}
  const i=GI.get(r*10+b); if(i===undefined) return null; const g=D.groups[i];
  return {mult:g.mult,rate:g.rate,n:g.n,x:g.x,g:g};
}
function col(ratio){
  const t=ratio>0?Math.max(-1,Math.min(1,Math.log(ratio)/Math.log(1.9))):-1;
  const neu=[232,230,222],tg=t>=0?[214,69,65]:[45,110,190],a=Math.abs(t);
  return 'rgb('+neu.map((n,i)=>Math.round(n+(tg[i]-n)*a)).join(',')+')';
}
const colorOf=v=>S.mode==='mult'?col(v.mult):col(v.rate/NAT.rate);

// ---------- 지도 (Leaflet + 배경 지도 타일) ----------
// 배경 타일은 외부(Esri 라이트 그레이 → OpenStreetMap 순으로 대체)에서 불러온다. 타일을 못 불러와도 버블과 패널은 그대로 동작한다.
// (CARTO 타일은 현재 API 키가 없으면 워터마크가 붙어 쓰지 않는다.) Esri 라이트/다크 그레이 "Base" 타일은 주변국 지명이 거의 없어 버블이 눈에 띈다.
// 주요 도시 이름만 아래에서 직접 얹는다.
const dark=window.matchMedia&&window.matchMedia('(prefers-color-scheme: dark)').matches&&document.documentElement.dataset.theme!=='light';
const reduceMotion=window.matchMedia&&window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const KR=[[33.0,125.0],[38.7,130.8]], MAXB=[[32.0,123.5],[39.6,132.5]], SUDO=[[36.95,126.45],[37.95,127.65]];
const map=L.map('map',{minZoom:6,maxZoom:14,zoomSnap:0.5,preferCanvas:true,attributionControl:true,maxBounds:MAXB,maxBoundsViscosity:0.9});
const TILES=[
 L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_'+(dark?'Dark':'Light')+'_Gray_Base/MapServer/tile/{z}/{y}/{x}',{maxZoom:15,attribution:'Tiles © Esri — Esri, HERE, Garmin, © OpenStreetMap contributors'}),
 L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,className:'tiles-osm',attribution:'© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'})];
const TILE_NAME=['Esri','OpenStreetMap'];
let tcur=0,terr=0;const qtiles=new URLSearchParams(location.search).get('tiles');
function tileNote(t){$('#tilenote').textContent=t;}
function useTiles(k){if(k>=TILES.length){tileNote('배경 지도를 불러오지 못했습니다(인터넷 연결이나 차단을 확인하세요). 버블은 좌표 기준으로 표시됩니다.');return;}
  if(TILES[tcur]&&map.hasLayer(TILES[tcur]))map.removeLayer(TILES[tcur]);
  tcur=k;terr=0;TILES[k].addTo(map);TILES[k].bringToBack();if(k>0)tileNote(TILE_NAME[k-1]+' 타일을 불러오지 못해 대체 배경('+TILE_NAME[k]+')을 쓰고 있습니다.');}
TILES.forEach((t,k)=>{t.on('tileload',()=>{if(k===tcur)terr=0;});t.on('tileerror',()=>{if(k===tcur&&++terr>=4)useTiles(k+1);});});
useTiles(qtiles==='osm'?1:0);
map.fitBounds(KR);
function fitMin(){map.setMinZoom(Math.max(5.5,map.getBoundsZoom(MAXB)));}
fitMin();map.on('resize',fitMin);
// 주요 도시 이름(배경 지도 대신 직접 표기, 버블 아래 층에 그린다)
map.createPane('labels').style.zIndex=350;
[['서울',37.5665,126.978],['인천',37.4563,126.7052],['수원',37.2636,127.0286],['춘천',37.8813,127.7298],['강릉',37.7519,128.8761],['청주',36.6424,127.489],['대전',36.3504,127.3845],
 ['전주',35.8242,127.148],['광주',35.1595,126.8526],['목포',34.8118,126.3922],['안동',36.5684,128.7294],['대구',35.8714,128.6014],['포항',36.019,129.3435],['울산',35.5384,129.3114],
 ['창원',35.2281,128.6811],['부산',35.1796,129.0756],['제주',33.4996,126.5312]].forEach(c=>L.marker([c[1],c[2]],{pane:'labels',interactive:false,keyboard:false,icon:L.divIcon({className:'city-lbl',html:c[0],iconSize:[0,0]})}).addTo(map));
const order=D.regions.map((r,i)=>i).sort((a,b)=>D.regions[b].n-D.regions[a].n);   // 큰 버블을 먼저 그려 작은 버블이 위에 오게 한다
const markers={};
const tipHtml=i=>{const v=val(i,S.biz),R=D.regions[i];
  return '<b>'+R.sido.replace(/특별시|광역시|특별자치도|특별자치시/,'')+' '+R.name+'</b>'+(S.biz>=0?' · '+BIZ[S.biz]:'')+'<br>'+(v?'위험 ×'+v.mult.toFixed(2)+' · 폐업률 '+pct(v.rate)+' · 점포 '+v.n.toLocaleString():'해당 업종 점포 없음');};
order.forEach(i=>{const R=D.regions[i];
  const m=L.circleMarker([R.lat,R.lon],{radius:5,weight:.8,color:'rgba(0,0,0,.45)',fillOpacity:.86}).addTo(map);
  m.on('click',()=>select(i)); m.bindTooltip(()=>tipHtml(i),{sticky:true,direction:'top',opacity:.95}); markers[i]=m;});
const ZF=()=>Math.max(0.75,Math.min(2.6,Math.pow(1.28,map.getZoom()-7)));      // 확대할수록 버블을 키워 겹침을 줄인다
const RMAX=7.5;                                                                  // 큰 시군구가 이웃을 덮지 않도록 기본 반지름 상한
const ringCol=dark?'#fff':'#111';
const ringHalo=L.circleMarker([0,0],{radius:1,fill:false,weight:8,color:dark?'#111':'#fff',opacity:0,interactive:false}).addTo(map);
const ring=L.circleMarker([0,0],{radius:1,fill:false,weight:4,color:ringCol,opacity:0,interactive:false}).addTo(map);
const pulse=L.circleMarker([0,0],{radius:1,fill:false,weight:3,color:ringCol,opacity:0,interactive:false}).addTo(map);
const nbLayer=L.layerGroup().addTo(map);
let ringR=0,pulseRAF=0;
function firePulse(){
  cancelAnimationFrame(pulseRAF);if(S.sel===null||reduceMotion)return;
  const a=D.regions[S.sel],t0=performance.now(),r0=ringR;pulse.setLatLng([a.lat,a.lon]);
  (function f(t){const k=Math.min(1,(t-t0)/1000);pulse.setRadius(r0+k*30);pulse.setStyle({opacity:.7*(1-k)});if(k<1)pulseRAF=requestAnimationFrame(f);else pulse.setStyle({opacity:0});})(t0);
}
function update(){
  const zf=ZF();let showRing=false;
  order.forEach(i=>{const m=markers[i],v=val(i,S.biz);
    if(!v){m.setStyle({opacity:0,fillOpacity:0,radius:0.1});return;}
    const k=S.biz<0?0.055:0.09,small=S.biz>=0&&v.n<30,sel=i===S.sel,r=Math.min(2.2+k*Math.sqrt(v.n),RMAX)*zf;
    m.setStyle({radius:r,fillColor:small?'#9aa0a6':colorOf(v),fillOpacity:small?0.35:0.86,color:sel?(dark?'#fff':'#111'):'rgba(0,0,0,.45)',weight:sel?2:0.8,opacity:1,dashArray:small?'2 2':null});
    if(sel){ringR=r+5;showRing=true;const R=D.regions[i];ring.setLatLng([R.lat,R.lon]);ringHalo.setLatLng([R.lat,R.lon]);ring.setRadius(ringR);ringHalo.setRadius(ringR);m.bringToFront();}});
  ring.setStyle({opacity:showRing?1:0});ringHalo.setStyle({opacity:showRing?.9:0});if(showRing){ringHalo.bringToFront();ring.bringToFront();}
  drawLinks();
}
map.on('zoomend',update);
function drawLinks(){
  nbLayer.clearLayers(); if(S.sel===null) return; const a=D.regions[S.sel];
  a.nb.forEach(j=>{const b=D.regions[j];L.polyline([[a.lat,a.lon],[b.lat,b.lon]],{color:dark?'#ddd':'#222',weight:1.3,dashArray:'4 4',opacity:.75,interactive:false}).addTo(nbLayer);});
  if(D.regions[S.sel]&&!map.getBounds().contains([a.lat,a.lon])) map.panTo([a.lat,a.lon]);
}
// 지도 이동: 지역 선택 시 해당 지역으로, 해제 시 전국으로
const flyOpt={duration:reduceMotion?0:.8};
const goNational=()=>map.flyToBounds(KR,flyOpt);
const goSudo=()=>map.flyToBounds(SUDO,flyOpt);
const goRegion=i=>{const R=D.regions[i];map.flyTo([R.lat,R.lon],Math.max(map.getZoom(),9.5),flyOpt);};
const goRegions=is=>{if(!is.length)return goNational();map.flyToBounds(L.latLngBounds(is.map(i=>[D.regions[i].lat,D.regions[i].lon])),{maxZoom:10.5,padding:[30,30],...flyOpt});};
// 지도 위 버튼
const BTNS=L.control({position:'topright'});
BTNS.onAdd=()=>{const d=L.DomUtil.create('div','mapbtns');d.innerHTML='<button type="button" id="btn-nat" title="선택을 해제하고 전국 지도로 돌아갑니다">전국 보기</button><button type="button" id="btn-sudo" title="서울·경기·인천으로 확대합니다">수도권</button>';L.DomEvent.disableClickPropagation(d);return d;};
BTNS.addTo(map);
// 범례(지도 위 오버레이): 색 눈금은 col()의 실제 스케일(배수 1/1.9 ~ 1.9에서 포화)과 같다
const LG=L.control({position:'bottomright'});   // 제주도가 있는 좌하단을 피해 동해 쪽 빈 공간에 둔다
LG.onAdd=()=>{const d=L.DomUtil.create('div','maplegend');d.id='maplegend';L.DomEvent.disableClickPropagation(d);return d;};
LG.addTo(map);
function renderLegend(){
  const r=S.mode==='rate';
  $('#maplegend').innerHTML='<div class="lg-t">'+(r?'실제 폐업률 (전국 평균 대비)':'폐업 위험도 (평균 점포 대비)')+'</div><div class="lg-bar"></div>'+
   '<div class="lg-ticks"><i style="left:0"></i><i style="left:50%"></i><i style="right:0"></i><span style="left:0">×0.53↓</span><span style="left:50%;transform:translateX(-50%)">×1.0</span><span style="right:0">×1.9↑</span></div><div class="lg-r lg-d" style="justify-content:space-between;margin-top:0"><span>◀ 안전</span><span>위험 ▶</span></div>'+
   '<div class="lg-r lg-d"><span class="dot" style="width:7px;height:7px"></span><span class="dot" style="width:13px;height:13px"></span> 점포 수가 많을수록 큰 원</div>'+
   '<div class="lg-r lg-d"><span class="dot dash"></span> 점선 회색 = 표본 30개 미만</div>';
}

// ---------- 패널 ----------
function whyChart(x){
  const f=factors(x).sort((a,b)=>Math.abs(Math.log(b.m))-Math.abs(Math.log(a.m))),mx=Math.log(1.6);   // 막대 길이는 로그 스케일, 가운데 = ×1.0
  return '<div class="fx">'+f.map(d=>{const l=Math.log(d.m),w=Math.min(Math.abs(l)/mx,1)*50,up=l>=0;
    return '<div class="fxrow"><div class="nm hasq">'+d.label+qtip(d.tip)+'</div><div class="trk"><i class="fbar '+(up?'hi':'lo')+(d.key==='age'?' soft':'')+'" style="'+(up?'left':'right')+':50%;width:'+Math.max(w,1.2).toFixed(1)+'%"></i></div><div class="val">×'+d.m.toFixed(2)+'</div></div>';}).join('')+'</div>';
}
function barsMini(arr,labels,fmt){
  const h=15,g=4,lw=46,Wd=200;let s='<svg viewBox="0 0 '+Wd+' '+(arr.length*(h+g))+'" class="mini">';
  const m=Math.max(...arr);
  arr.forEach((v,i)=>{const y=i*(h+g),w=(Wd-lw-44)*v/m;s+='<text x="'+(lw-4)+'" y="'+(y+11)+'" text-anchor="end">'+labels[i]+'</text><rect x="'+lw+'" y="'+y+'" width="'+w.toFixed(1)+'" height="'+h+'" rx="2" fill="var(--ref)"/><text class="v" x="'+(lw+w+4)+'" y="'+(y+11)+'">'+fmt(v)+'</text>';});
  return s+'</svg>';
}
function spark(amt){
  const pts=amt.map((v,i)=>v===null?null:[i,v]).filter(Boolean); if(pts.length<2) return '<p class="hint">월별 자료 부족</p>';
  const vs=pts.map(p=>p[1]),mn=Math.min(...vs),mxv=Math.max(...vs),Wd=220,Ht=70,pd=8;
  const X=i=>pd+i*(Wd-2*pd)/5,Y=v=>Ht-pd-(v-mn)/(mxv-mn||1)*(Ht-2*pd-8);
  let s='<svg viewBox="0 0 '+Wd+' '+(Ht+14)+'" class="spark"><polyline fill="none" stroke="var(--ref)" stroke-width="2" points="'+pts.map(p=>X(p[0]).toFixed(1)+','+Y(p[1]).toFixed(1)).join(' ')+'"/>';
  pts.forEach(p=>{s+='<circle cx="'+X(p[0]).toFixed(1)+'" cy="'+Y(p[1]).toFixed(1)+'" r="2.6" fill="var(--ref)"/>';});
  D.months.forEach((m,i)=>{s+='<text x="'+X(i).toFixed(1)+'" y="'+(Ht+10)+'" text-anchor="middle" font-size="10" fill="var(--sub)">'+String(m).slice(4)+'월</text>';});
  return s+'</svg><p class="hint" style="margin:0">월별 BC 소비액(백만원) '+mn.toLocaleString()+' ~ '+mxv.toLocaleString()+'</p>';
}
function explain(r,b){
  const v=val(r,b),R=D.regions[r]; if(!v) return '';
  const nm=R.sido.replace(/특별시|광역시|특별자치도|특별자치시/,'')+' '+R.name+(b>=0?' '+BIZ[b]:' 전체');
  const f=factors(v.x),g=v.g;
  const ageF=f.find(d=>d.key==='age'), core=f.filter(d=>d.key!=='age');
  const up=core.filter(d=>d.m>=1.03).sort((a,b)=>b.m-a.m), dn=core.filter(d=>d.m<=0.97).sort((a,b)=>a.m-b.m);
  const chg=v.mult>=1?((v.mult-1)*100).toFixed(0)+'% 높':((1-v.mult)*100).toFixed(0)+'% 낮';
  const phrase=(d,isUp)=>{
    const a=g?g.age_yr:R.age_yr, fr=g?g.fr:R.fr;
    switch(d.key){
      case 'yrs': return isUp?'영업 기간이 짧은 점포가 많고(평균 '+a.toFixed(1)+'년, 전국 '+NAT.age_yr.toFixed(1)+'년)':'오래 영업한 점포가 많고(평균 '+a.toFixed(1)+'년, 전국 '+NAT.age_yr.toFixed(1)+'년)';
      case 'fr': return isUp?'프랜차이즈 비중이 낮고('+pct(fr)+', 전국 '+pct(NAT.fr)+')':'프랜차이즈 비중이 높고('+pct(fr)+', 전국 '+pct(NAT.fr)+')';
      case 'site': return isUp?'점포 규모·다중이용 등 점포 특성이 위험 쪽이고':'점포 규모·다중이용 등 점포 특성이 안정 쪽이고';
      case 'hist': return g?(isUp?'이 시군구('+pct(g.reg_hist)+')와 이웃 지역('+pct(g.nb_hist)+')의 직전 1년 폐업률이 높고':'이 시군구('+pct(g.reg_hist)+')와 이웃 지역('+pct(g.nb_hist)+')의 직전 1년 폐업률이 낮고'):(isUp?'이 지역과 이웃 지역의 직전 1년 폐업률이 높고':'이 지역과 이웃 지역의 직전 1년 폐업률이 낮고');
      case 'age': return '고객 연령 구성이 '+(isUp?'폐업 위험이 높은':'폐업 위험이 낮은')+' 지역 유형과 닮았고(지역 유형 신호이며 같은 지역 안의 원인이라는 근거는 없음)';
      case 'gen': return '고객 성별 구성이 '+(isUp?'위험 쪽이고':'안정 쪽이고');
      case 'biz': return isUp?'업종 자체의 기본 위험이 평균보다 높고':'업종 자체의 기본 위험이 평균보다 낮고';
      default: return '입지 등 기타 요인이 '+(isUp?'위험 쪽이고':'안정 쪽이고');
    }};
  let t='<p><b>'+nm+'</b>는 평균 점포보다 폐업 위험이 <b>×'+v.mult.toFixed(2)+'</b>(약 '+chg+'음)으로 추정됩니다. 실제 폐업률은 '+pct(v.rate)+'(전국 '+pct(NAT.rate)+', 점포 '+v.n.toLocaleString()+'개)입니다.</p>';
  if(up.length) t+='<p>🔺 위험을 높이는 요인: '+up.slice(0,3).map(d=>phrase(d,true)+' <span class="tag hi">×'+d.m.toFixed(2)+'</span>').join(', ')+'.</p>';
  if(dn.length) t+='<p>🔻 위험을 낮추는 요인: '+dn.slice(0,3).map(d=>phrase(d,false)+' <span class="tag lo">×'+d.m.toFixed(2)+'</span>').join(', ')+'.</p>';
  if(ageF&&Math.abs(Math.log(ageF.m))>=0.03) t+='<p class="hint">참고: 고객 연령 구성(×'+ageF.m.toFixed(2)+')은 '+(ageF.m>=1?'위험이 높은':'위험이 낮은')+' 지역 유형과 닮았다는 신호일 뿐이며, 같은 시군구 안에서 위험을 가른다는 근거는 없어 위 요인에서 제외했습니다.</p>';
  const nbm=R.nb.map(j=>val(j,b)).filter(Boolean).map(z=>z.mult);
  if(nbm.length) t+='<p>가까운 이웃 '+nbm.length+'곳의 평균 위험 배수는 ×'+(nbm.reduce((a,c)=>a+c,0)/nbm.length).toFixed(2)+'입니다.</p>';
  t+='<p class="hint">이 배수는 평균 점포와의 통계적 연관이며 원인이나 정책 효과가 아닙니다.'+(v.n<30?' 이 그룹은 점포가 30개 미만이라 실제 폐업률이 불안정합니다.':'')+'</p>';
  return t;
}
function renderPanel(){
  const p=$('#panel'); if(S.sel===null) return; const r=S.sel,R=D.regions[r],b=S.biz,v=val(r,b);
  const nm=R.sido+' '+R.name;
  S.home=false;
  let h='<button class="chip-b clear" data-act="clear">✕ 선택 해제</button><button class="chip-b clear only-m" data-act="tomap">↑ 지도 보기</button><h3>'+nm+'</h3><div class="sub2">'+(b>=0?BIZ[b]:'전체 7개 업종')+' · 점포 '+(v?v.n.toLocaleString():0)+'개</div>';
  if(!v){$('#panel').innerHTML=h+'<p class="hint">이 시군구에는 해당 업종 점포가 없습니다.</p>'+bizRows(r);bindPanel(p);return;}
  const up=v.mult>=1;
  h+='<div class="sub2 hasq" style="margin-top:6px">폐업 위험도'+qtip(TIP_RISK)+'</div><div class="big"><b class="'+(up?'t-hi':'t-lo')+'">×'+v.mult.toFixed(2)+'</b><span class="delta '+(up?'t-hi':'t-lo')+'">'+DELTA(v.mult)+'</span></div>';
  h+='<div class="sub2">실제 폐업률 '+pct(v.rate)+' <span class="hint">(전국 '+pct(NAT.rate)+')</span></div>';
  if(b>=0&&v.n<30) h+='<div class="warn">점포가 30개 미만이라 실제 폐업률은 우연 변동이 큽니다. 배수는 모형 기반이라 상대적으로 안정적입니다.</div>';
  h+='<div class="blk"><h4>왜 그런가 — 요인별 배수 (붉음: 위험 ↑, 푸름: 위험 ↓)</h4>'+whyChart(v.x)+'<p class="hint" style="margin:2px 0 0">옅은 막대는 참고용 신호예요(? 를 누르면 이유가 나와요).</p></div>';
  h+='<div class="blk why"><h4>한 줄 해설</h4>'+explain(r,b)+'</div>';
  if(v.g){const g=v.g;
    h+='<div class="blk"><h4>BC카드 소비 구성 (2026-01~06, 맥락 정보)</h4><div class="two"><div>'+barsMini(g.age,AGE,x=>pct(x,0))+'<p class="hint" style="margin:2px 0 6px">연령 코드별 소비액 비중</p>'+barsMini(g.gen,GEN,x=>pct(x,0))+'</div><div>'+spark(g.amt)+'</div></div></div>';
    h+='<div class="blk"><h4>상권 프로필</h4><div class="kp"><div><b>'+g.age_yr.toFixed(1)+'년</b><span>평균 영업연수 (전국 '+NAT.age_yr.toFixed(1)+')</span></div><div><b>'+pct(g.fr)+'</b><span>프랜차이즈 (전국 '+pct(NAT.fr)+')</span></div><div><b>'+pct(g.reg_hist)+' / '+pct(g.nb_hist)+'</b><span>직전 1년 폐업률 자기 / 이웃</span></div><div><b>'+g.n.toLocaleString()+'개</b><span>경쟁 점포(같은 업종)</span></div></div></div>';
  } else h+=bizRows(r);
  h+='<div class="blk"><h4>모형이 참고하는 가까운 이웃 5곳(지도의 점선)</h4><div class="nb">'+R.nb.map(j=>{const z=val(j,b);return '<button data-r="'+j+'">'+D.regions[j].name+(z?' ×'+z.mult.toFixed(2):'')+'</button>';}).join('')+'</div></div>';
  p.innerHTML=h; p.querySelectorAll('.nb button').forEach(x=>x.addEventListener('click',()=>select(+x.dataset.r,true)));
  bindPanel(p);
}
function bindPanel(p){
  p.querySelectorAll('tr[data-b]').forEach(x=>x.addEventListener('click',()=>{setBiz(+x.dataset.b);}));
  p.querySelectorAll('[data-act="clear"]').forEach(x=>x.addEventListener('click',clearSel));
  p.querySelectorAll('[data-act="tomap"]').forEach(x=>x.addEventListener('click',()=>$('#map').scrollIntoView({behavior:'smooth',block:'center'})));
}
// 순위 기준은 기존 순위 질문과 같다: 전체 업종은 점포 2,000개 이상 시군구, 업종을 고르면 300개 이상 그룹
function topRows(b,intent,k,sido){
  const rows=b>=0?D.groups.filter(g=>g.b===b&&g.n>=300&&(!sido||D.regions[g.r].sido===sido)).map(g=>({r:g.r,m:g.mult,rate:g.rate,n:g.n}))
    :D.regions.map((R,i)=>({r:i,m:R.mult,rate:R.rate,n:R.n})).filter(x=>x.n>=2000&&(!sido||D.regions[x.r].sido===sido));
  rows.sort((x,y)=>intent==='hi'?y.m-x.m:x.m-y.m);return rows.slice(0,k);
}
const rkCard=(x,b,i)=>'<button type="button" class="rk" data-r="'+x.r+'" data-b="'+b+'"><span class="rn">'+(i+1)+'</span><span class="rt">'+rname(x.r)+'</span><span class="rv '+(x.m>=1?'t-hi':'t-lo')+'">'+(x.m>=1?'▲':'▼')+' ×'+x.m.toFixed(2)+'</span><span class="rs">폐업률 '+pct(x.rate)+' · 점포 '+x.n.toLocaleString()+'개</span></button>';
function renderHome(){
  S.home=true;const b=S.biz,nm=b>=0?BIZ[b]:'전체 업종';
  $('#panel').innerHTML='<h3>어디부터 볼까요?</h3><p class="hint" style="margin:2px 0 4px">지도의 버블을 누르거나 검색창에 지역·업종을 입력해 보세요. 아래 지역을 누르면 바로 그 지역으로 이동해요.</p>'+
   '<div class="blk"><h4>▲ 폐업 위험이 높은 곳 TOP 5 · '+nm+'</h4><div class="rklist">'+topRows(b,'hi',5).map((x,i)=>rkCard(x,b,i)).join('')+'</div></div>'+
   '<div class="blk"><h4>▼ 폐업 위험이 낮은(안전한) 곳 TOP 5 · '+nm+'</h4><div class="rklist">'+topRows(b,'lo',5).map((x,i)=>rkCard(x,b,i)).join('')+'</div></div>'+
   '<p class="hint" style="margin:12px 0 0">점포가 '+(b>=0?300:2000)+'개 이상인 곳만 순위에 넣었어요. 폐업 위험도는 평균 점포를 ×1.0으로 놓고 비교한 값이에요.</p>';
  bindGo($('#panel'));
}
function bindGo(root){root.querySelectorAll('[data-r]').forEach(x=>x.addEventListener('click',()=>{if(x.dataset.b!==undefined)setBizQuiet(+x.dataset.b);select(+x.dataset.r,true);}));
  root.querySelectorAll('[data-q]').forEach(x=>x.addEventListener('click',()=>{$('#ask').value=x.dataset.q;ask();}));}
function bizRows(r){
  let s='<div class="blk"><h4>업종별 (누르면 그 업종으로 전환)</h4><p class="hint" style="margin:0 0 6px">'+NOTE_RATE+'</p><table class="tbl"><thead><tr><th>업종</th><th class="num">점포</th><th class="num">폐업률</th><th class="num">위험 배수</th></tr></thead><tbody>';
  BIZ.forEach((nm,b)=>{const v=val(r,b);if(!v)return;s+='<tr data-b="'+b+'" style="cursor:pointer"><td>'+nm+'</td><td class="num">'+v.n.toLocaleString()+'</td><td class="num">'+pct(v.rate)+'</td><td class="num"><b style="color:'+(v.mult>=1?'var(--hi-text)':'var(--lo-text)')+'">×'+v.mult.toFixed(2)+'</b></td></tr>';});
  return s+'</tbody></table></div>';
}
const isMobile=()=>window.matchMedia('(max-width:767px)').matches;
function select(i,fly){S.sel=i;update();renderPanel();firePulse();if(fly)goRegion(i);if(isMobile())$('#panel').scrollIntoView({behavior:'smooth',block:'start'});}
function clearSel(){S.sel=null;update();renderHome();goNational();}
function setBiz(b){S.biz=b;document.querySelectorAll('#bizbar .chip-b').forEach(x=>x.classList.toggle('on',+x.dataset.b===b));update();if(S.sel===null&&S.home)renderHome();else renderPanel();}
// 업종 필터
(function(){const bar=$('#bizbar');bar.innerHTML='<span class="hint">업종</span>'+['전체'].concat(BIZ).map((nm,i)=>'<button class="chip-b'+(i===0?' on':'')+'" data-b="'+(i-1)+'">'+nm+'</button>').join('');
  bar.querySelectorAll('.chip-b').forEach(x=>x.addEventListener('click',()=>setBiz(+x.dataset.b)));})();
$('#mode').addEventListener('change',e=>{S.mode=e.target.value;renderLegend();update();});

// ---------- 규칙 기반 질문 (LLM 아님: 정해진 형태만 이해한다) ----------
const BIZKEY={'한식':0,'일식':1,'회집':1,'횟집':1,'중국':2,'중식':2,'서양':3,'양식':3,'스넥':4,'스낵':4,'분식':4,'제과':5,'빵':5,'베이커리':5,'편의점':6};
const UNSUP=['치킨','카페','커피','피자','술집','호프','주점','고기','삼겹','미용','학원','약국','세탁'];
const SIDOALIAS={'경남':'경상남도','경북':'경상북도','충남':'충청남도','충북':'충청북도','전남':'전라남도','전북':'전북특별자치도','강원':'강원특별자치도','제주':'제주특별자치도','세종':'세종특별자치시'};
const SIDOS=[...new Set(D.regions.map(r=>r.sido))];
const sidoOf=t=>SIDOALIAS[t]||SIDOS.find(x=>t.length>=2&&x.includes(t));
const rname=i=>D.regions[i].sido.replace(/특별시|광역시|특별자치도|특별자치시/,'')+' '+D.regions[i].name;
function say(html){S.home=false;$('#panel').innerHTML=html;bindGo($('#panel'));}
const EX=['동탄 서양음식','합천 한식','마포구 제과점','강남구','한식 위험한 곳','서울 제과점 안전한 곳'];
const HELP='<div class="blk" style="border:0;margin-top:8px;padding-top:0"><h4 style="color:var(--fg);font-size:16px">이렇게 검색해 보세요</h4><div class="nb">'+EX.map(q=>'<button type="button" data-q="'+q+'">'+q+'</button>').join('')+'</div>'+
 '<p class="hint" style="margin:8px 0 0">지역은 시군구 이름의 일부만 써도 돼요(동탄, 합천). 업종은 한식·일식·중식·서양(양식)·스낵(분식)·제과점(빵)·편의점 중에서 고를 수 있어요. 자세한 범위는 “방법 · 한계” 탭에 있어요.</p></div>';
function ask(){
  const q=$('#ask').value.replace(/\s+/g,' ').trim(); if(!q) return;
  const esc=q.replace(/</g,'&lt;');
  if(UNSUP.some(k=>q.includes(k))){say('<p>“'+esc+'”는 아직 다루지 않는 업종이에요. 이 사이트는 한식·일식·중식·서양음식·스낵·제과점·편의점 7개 업종만 볼 수 있어요.</p>'+HELP);return;}
  let b=-1;for(const k in BIZKEY){if(q.includes(k)){b=BIZKEY[k];break;}}
  const intent=/(위험한|위험 ?높|폐업 ?많|많이 ?망|취약)/.test(q)?'hi':(/(안전|위험 ?낮|덜 ?망|안정)/.test(q)?'lo':null);
  const toks=q.split(/[ ,?]+/).filter(t=>t.length>=2&&!Object.keys(BIZKEY).some(k=>t.includes(k))&&!/(왜|위험|해줘|알려|어때|설명|곳|안전|폐업|많이|제일|가장)/.test(t));
  if(intent){ // 순위 질문: 업종(선택) + 시도(선택)
    let sido=null;for(const t of toks){const x=sidoOf(t);if(x){sido=x;break;}}
    const rows=topRows(b,intent,8,sido);
    if(!rows.length){say('<p>조건에 맞는 지역이 없어요. 점포 수가 충분한 곳만 순위에 넣고 있어요.</p>'+HELP);return;}
    setBizQuiet(b);S.sel=null;update();sido?goRegions(D.regions.map((R,i)=>i).filter(i=>D.regions[i].sido===sido)):goNational();
    say('<h3>'+(sido?sido.replace(/특별시|광역시|특별자치도|특별자치시/,'')+' ':'전국 ')+(b>=0?BIZ[b]:'전체 업종')+' — 위험이 '+(intent==='hi'?'높은':'낮은')+' 곳 상위 '+rows.length+'</h3><p class="hint">점포 '+(b>=0?300:2000)+'개 이상인 곳만 순위에 넣었습니다. 누르면 설명이 열립니다.</p><div class="nb" style="flex-direction:column;align-items:stretch">'+
      rows.map(x=>'<button data-r="'+x.r+'" data-b="'+b+'" style="text-align:left">'+rname(x.r)+' · <b style="color:'+(x.m>=1?'var(--hi-text)':'var(--lo-text)')+'">×'+x.m.toFixed(2)+'</b> · 폐업률 '+pct(x.rate)+' · 점포 '+x.n.toLocaleString()+'</button>').join('')+'</div>');
    return;
  }
  let cand=[];
  for(const t of toks){const t2=t.replace(/(시|군|구)$/,'');
    cand=D.regions.map((r,i)=>i).filter(i=>{const full=D.regions[i].sido+' '+D.regions[i].name;return full.includes(t)||(t2.length>=2&&full.includes(t2));});
    if(cand.length) break;}
  if(!cand.length){if(b>=0){setBizQuiet(b);update();say('<p>“'+esc+'”에서 업종은 <b>'+BIZ[b]+'</b>으로 읽었지만 지역을 찾지 못했어요. 지역 이름도 함께 입력해 주세요.</p>'+HELP);}else say('<p>“'+esc+'”에서 지역을 찾지 못했어요.</p>'+HELP);return;}
  setBizQuiet(b);
  if(cand.length>1){S.sel=null;update();goRegions(cand);say('<p>여러 시군구가 맞아요. 하나를 선택해 주세요.</p><div class="nb">'+cand.slice(0,14).map(i=>'<button data-r="'+i+'">'+D.regions[i].sido+' '+D.regions[i].name+'</button>').join('')+'</div>');return;}
  select(cand[0],true);
}
function setBizQuiet(b){S.biz=b;document.querySelectorAll('#bizbar .chip-b').forEach(x=>x.classList.toggle('on',+x.dataset.b===b));}
$('#askbtn').addEventListener('click',ask);$('#ask').addEventListener('keydown',e=>{if(e.key==='Enter')ask();});
document.querySelectorAll('#askhelp [data-q]').forEach(x=>x.addEventListener('click',()=>{$('#ask').value=x.dataset.q;ask();}));

// ---------- 상권 분석 ----------
const RL=$('#rlist');D.regions.forEach((r,i)=>{const o=document.createElement('option');o.value=r.sido+' '+r.name;RL.appendChild(o);});
function areaShow(){
  const q=$('#areaq').value.trim();const i=D.regions.findIndex(r=>(r.sido+' '+r.name)===q)>=0?D.regions.findIndex(r=>(r.sido+' '+r.name)===q):D.regions.findIndex(r=>r.name.includes(q)&&q.length>=2);
  if(i<0){$('#areaout').innerHTML='<p class="hint">일치하는 시군구가 없습니다.</p>';return;}
  const R=D.regions[i];let s='<h3 style="margin:0">'+R.sido+' '+R.name+'</h3><div class="kp"><div><b>'+R.n.toLocaleString()+'개</b><span>점포(7개 업종)</span></div><div><b>'+pct(R.rate)+'</b><span>180일 폐업률 (전국 '+pct(NAT.rate)+')</span></div><div><b style="color:'+(R.mult>=1?'var(--hi-text)':'var(--lo-text)')+'">×'+R.mult.toFixed(2)+'</b><span>위험 배수(지역 평균)</span></div><div><b>'+R.age_yr.toFixed(1)+'년</b><span>평균 영업연수 (전국 '+NAT.age_yr.toFixed(1)+')</span></div><div><b>'+pct(R.fr)+'</b><span>프랜차이즈 (전국 '+pct(NAT.fr)+')</span></div></div>';
  s+='<p class="hint" style="margin:0 0 6px">'+NOTE_RATE+'</p><div class="scroll"><table class="tbl"><thead><tr><th>업종</th><th class="num">점포</th><th>실제 폐업률</th><th>위험 배수</th><th class="num">평균 영업연수</th><th class="num">프랜차이즈</th><th class="num">BC 월평균 소비(백만원)</th><th class="num">점포당(백만원)</th></tr></thead><tbody>';
  BIZ.forEach((nm,b)=>{const g=GI.has(i*10+b)?D.groups[GI.get(i*10+b)]:null;if(!g)return;const am=g.amt.filter(v=>v!==null),mean=am.length?am.reduce((a,c)=>a+c,0)/am.length:null;
    s+='<tr><td>'+nm+'</td><td class="num">'+g.n.toLocaleString()+'</td><td class="b1"><span class="mb" style="width:'+Math.min(g.rate/0.09*90,100).toFixed(0)+'px;background:var(--ref)"></span>'+pct(g.rate)+'</td><td class="b1"><span class="mb" style="width:'+Math.min(g.mult/2*90,100).toFixed(0)+'px;background:'+(g.mult>=1?'var(--hi)':'var(--lo)')+'"></span>×'+g.mult.toFixed(2)+'</td><td class="num">'+g.age_yr.toFixed(1)+'</td><td class="num">'+pct(g.fr)+'</td><td class="num">'+(mean===null?'-':Math.round(mean).toLocaleString())+'</td><td class="num">'+(mean===null?'-':(mean/g.n).toFixed(2))+'</td></tr>';});
  s+='</tbody></table></div><p class="cap">BC 소비는 시군구×업종 집계이며 점포당 값은 (월평균 소비 ÷ 1/1 영업 점포 수)입니다. <a href="#" id="tomap" style="color:var(--acc)">지도에서 보기 →</a></p>';
  $('#areaout').innerHTML=s;$('#tomap').addEventListener('click',ev=>{ev.preventDefault();tab('map');setTimeout(()=>select(i,true),90);});
}
$('#areaq').addEventListener('change',areaShow);$('#areaq').addEventListener('input',()=>{if(D.regions.some(r=>(r.sido+' '+r.name)===$('#areaq').value.trim()))areaShow();});
const RB=$('#rankbiz');RB.innerHTML=BIZ.map((n,i)=>'<option value="'+i+'">'+n+'</option>').join('');
function rank(){
  const b=+RB.value,gs=D.groups.filter(g=>g.b===b&&g.n>=300).sort((a,c)=>c.mult-a.mult);
  const row=g=>{const R=D.regions[g.r],f=factors(g.x).filter(d=>d.key!=='age').sort((a,c)=>Math.abs(Math.log(c.m))-Math.abs(Math.log(a.m)))[0];
    return '<tr><td>'+R.sido.replace(/특별시|광역시|특별자치도|특별자치시/,'')+' '+R.name+'</td><td class="num"><b style="color:'+(g.mult>=1?'var(--hi-text)':'var(--lo-text)')+'">×'+g.mult.toFixed(2)+'</b></td><td class="num">'+pct(g.rate)+'</td><td class="num">'+g.n.toLocaleString()+'</td><td>'+f.label+' ×'+f.m.toFixed(2)+'</td></tr>';};
  const head='<table class="tbl"><thead><tr><th>지역</th><th class="num">배수</th><th class="num">폐업률</th><th class="num">점포</th><th>가장 큰 요인</th></tr></thead><tbody>';
  $('#rk-hi').innerHTML='<h4 style="margin:0 0 6px">위험 상위 10 · '+BIZ[b]+'</h4>'+head+gs.slice(0,10).map(row).join('')+'</tbody></table>';
  $('#rk-lo').innerHTML='<h4 style="margin:0 0 6px">안전 상위 10 · '+BIZ[b]+'</h4>'+head+gs.slice(-10).reverse().map(row).join('')+'</tbody></table>';
}
RB.addEventListener('change',rank);rank();
(function(){ // 산점도: 업종 내 점포당 소비 백분위 vs 폐업률
  const gs=D.groups.filter(g=>g.n>=100);
  const pctl={}; BIZ.forEach((_,b)=>{const v=gs.filter(g=>g.b===b).map(g=>g.spend).sort((x,y)=>x-y);gs.filter(g=>g.b===b).forEach(g=>{pctl[GI.get(g.r*10+g.b)]=v.filter(z=>z<=g.spend).length/v.length;});});
  const Wd=760,Ht=340,L=52,B=34,T=10,Rr=14,mxy=0.12;
  const X=v=>L+v*(Wd-L-Rr),Y=v=>Ht-B-Math.min(v,mxy)/mxy*(Ht-B-T);
  const colors=['#1f5eff','#c2410c','#2a9d8f','#9b5de5','#e9a800','#e63946','#6b7280'];
  let s='<svg viewBox="0 0 '+Wd+' '+Ht+'" class="chart scat"><line x1="'+L+'" x2="'+(Wd-Rr)+'" y1="'+Y(NAT.rate)+'" y2="'+Y(NAT.rate)+'" class="axis"/><text x="'+(L+4)+'" y="'+(Y(NAT.rate)-5)+'">전국 평균 '+pct(NAT.rate)+'</text>';
  [0,0.03,0.06,0.09,0.12].forEach(v=>{s+='<text x="'+(L-6)+'" y="'+(Y(v)+4)+'" text-anchor="end">'+pct(v,0)+'</text>';});
  [0,0.25,0.5,0.75,1].forEach(v=>{s+='<text x="'+X(v)+'" y="'+(Ht-16)+'" text-anchor="middle">'+Math.round(v*100)+'%</text>';});
  gs.forEach(g=>{s+='<circle cx="'+X(pctl[GI.get(g.r*10+g.b)]).toFixed(1)+'" cy="'+Y(g.rate).toFixed(1)+'" r="3" fill="'+colors[g.b]+'"><title>'+D.regions[g.r].name+' '+BIZ[g.b]+' · 폐업률 '+pct(g.rate)+'</title></circle>';});
  const bins=[];for(let k=0;k<10;k++){const m=gs.filter(g=>{const q=pctl[GI.get(g.r*10+g.b)];return q>k/10&&q<=(k+1)/10;});if(m.length){const n=m.reduce((a,c)=>a+c.n,0);bins.push([X((k+.5)/10),Y(m.reduce((a,c)=>a+c.ev,0)/n)]);}}
  s+='<polyline fill="none" stroke="var(--fg)" stroke-width="2.4" points="'+bins.map(p=>p[0].toFixed(1)+','+p[1].toFixed(1)).join(' ')+'"/>';
  s+='<text x="'+(L+(Wd-L-Rr)/2)+'" y="'+(Ht-2)+'" text-anchor="middle">업종 안에서의 점포당 BC 소비 순위(백분위) →</text></svg><div class="legend2">'+BIZ.map((n,i)=>'<span><span style="display:inline-block;width:9px;height:9px;border-radius:50%;background:'+colors[i]+';margin-right:4px"></span>'+n+'</span>').join('')+'<span><b style="border-top:2.4px solid var(--fg);display:inline-block;width:18px;vertical-align:middle"></b> 10분위별 실제 폐업률(점포 수 가중)</span></div>';
  $('#scat').innerHTML=s;
})();

// ---------- 탭 ----------
function tab(t){document.querySelectorAll('#nav button').forEach(x=>x.setAttribute('aria-selected',x.dataset.t===t));document.querySelectorAll('section.tab').forEach(x=>x.classList.toggle('on',x.id==='t-'+t));history.replaceState(null,'','#'+t);window.scrollTo(0,0);if(t==='map')setTimeout(()=>map.invalidateSize(),50);}
document.querySelectorAll('#nav button').forEach(x=>x.addEventListener('click',()=>tab(x.dataset.t)));
if(location.hash&&$('#t-'+location.hash.slice(1)))tab(location.hash.slice(1));
renderLegend();renderHome();update();
$('#btn-nat').addEventListener('click',clearSel);$('#btn-sudo').addEventListener('click',goSudo);
const aq=new URLSearchParams(location.search).get('area');if(aq){$('#areaq').value=aq;areaShow();}
const qs=new URLSearchParams(location.search).get('q');if(qs){$('#ask').value=qs;ask();}
</script></body></html>"""

html_out = (TEMPLATE.replace("__CSS__", css).replace("__EXTRA__", EXTRA_CSS).replace("__DATA__", data).replace("__SURV__", surv).replace("__LEAFLET_CSS__", Path("vendor/leaflet.css").read_text(encoding="utf-8")).replace("__LEAFLET_JS__", Path("vendor/leaflet.js").read_text(encoding="utf-8"))
            .replace("__N__", f"{nat['n']:,}").replace("__EV__", f"{nat['events']:,}").replace("__RATE__", f"{nat['rate'] * 100:.2f}")
            .replace("__RHO_ALL__", f"{R.rho_all:+.2f}").replace("__RHO_IN__", f"{R.rho_in:+.2f}"))
for d in ("site", "docs"):             # site/는 로컬 확인용, docs/는 GitHub Pages(main 브랜치 /docs)용 — 내용 동일
    Path(d).mkdir(exist_ok=True)
    Path(d, "index.html").write_text(html_out, encoding="utf-8")
Path("docs/.nojekyll").write_text("", encoding="utf-8")
print(f"site/index.html, docs/index.html 작성 ({len(html_out) / 1024:.0f} KB)")
