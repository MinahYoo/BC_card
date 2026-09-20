# -*- coding: utf-8 -*-
"""
상권 생존 지도 웹사이트 site/index.html 을 만든다 (서버 없는 단일 HTML; GitHub Pages 등 정적 호스팅에 그대로 올릴 수 있다).

탭: 지도 탐색(시군구 버블 지도 · 업종 필터 · 위험 배수 · "왜" 요인 분해 · BC 구성/월별 · 이웃 5곳 · 규칙 기반 설명 입력창)
    상권 분석(시군구 프로필 · 업종별 위험 순위 · 소비-폐업 산점도) / 모형 근거(리포트 본문: 어떤 요인이 왜 폐업 위험을 가르는가)
사전 조건: prep_site_data.py 실행(output/site_data.json). 생존 분석 탭은 build_report.py의 본문을 그대로 재사용한다.
모든 수치는 분석 산출물에서 왔고, 설명 문장은 규칙으로 만든다(LLM 없음 -> 값이 틀리거나 지어질 수 없다).
"""
import json
import re
from pathlib import Path

import build_report as R                     # report/index.html도 함께 갱신된다
from site_surv import transform as surv_transform, TIP_MIN

data = Path("output/site_data.json").read_text(encoding="utf-8")
css = re.search(r"<style>(.*?)</style>", R.HTML, re.S).group(1)
surv = surv_transform(R.HTML[R.HTML.index("<h2>한눈에"):R.HTML.index("<footer>")])   # 표시용 다듬기(site_surv.py) — 숫자는 그대로
nat = json.loads(data)["national"]

EXTRA_CSS = r"""
/* ===== 디자인 토큰 =====
   UI 액센트(--accent 계열, 딥그린): 탭·선택 칩·링크·버튼·차트의 강조/유의 막대.
   데이터 위험 스케일(--risk-*): 빨강(위험↑) ↔ 파랑(위험↓)은 지도·배수·요인 막대 전용. 지도 버블 색은 JS의 col()과 같은 값이다. */
:root{
 --accent:#12684f;--accent-strong:#0a4a37;--accent-tint:#e4f0ea;--accent-fg:#fff;
 --risk-hi:#d64541;--risk-lo:#2d6ebe;--neutral:#e8e6de;--risk-hi-text:#b42f2b;--risk-lo-text:#1f5aa6;
 --risk-hi-soft:rgba(214,69,65,.15);--risk-lo-soft:rgba(45,110,190,.15);--flat:#7d8696;
 --bg:#f6f5f1;--bg-alt:#eaf2ed;--card:#fff;--fg:#1f2328;--sub:#566173;--line:#e3e1da;
 --s1:4px;--s2:8px;--s3:12px;--s4:16px;--s5:24px;--s6:40px;--s7:64px;
 --r-sm:8px;--r-md:12px;--r-lg:20px;
 --sh-sm:0 1px 2px rgba(20,32,26,.06),0 1px 3px rgba(20,32,26,.05);--sh-md:0 8px 24px rgba(20,32,26,.12);
 --fs-xs:12px;--fs-sm:14px;--fs-md:16px;--fs-lg:20px;--fs-xl:28px;--fs-2xl:40px;--fs-3xl:56px;
 --head-h:66px;
 /* 이전 이름(코드 곳곳에서 쓰임) — 새 토큰의 별칭 */
 --acc:var(--accent);--acc-fg:var(--accent-fg);--acc-soft:var(--accent-tint);
 --hi:var(--risk-hi);--lo:var(--risk-lo);--hi-text:var(--risk-hi-text);--lo-text:var(--risk-lo-text);--hi-soft:var(--risk-hi-soft);--lo-soft:var(--risk-lo-soft);
 --pos:var(--risk-lo);--r:var(--r-md)}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
 --accent:#62d3a4;--accent-strong:#8ae5c0;--accent-tint:rgba(98,211,164,.14);--accent-fg:#08201a;
 --risk-hi:#f0716d;--risk-lo:#6ea8f0;--neutral:#3a404b;--risk-hi-text:#f59e9b;--risk-lo-text:#8fbcf5;
 --risk-hi-soft:rgba(240,113,109,.2);--risk-lo-soft:rgba(110,168,240,.2);--flat:#8c95a5;
 --bg:#14161a;--bg-alt:#171d1a;--card:#1c1f25;--fg:#e8eaed;--sub:#a8b1c0;--line:#2d323b;
 --sh-sm:0 1px 2px rgba(0,0,0,.35);--sh-md:0 8px 24px rgba(0,0,0,.5)}}
html{scroll-padding-top:calc(var(--head-h) + 8px)}
/* 타이포 위계: h1 40(모바일 28)·h2 28·h3 20·본문 16/1.65, 제목 자간 -0.02em */
h1,h2,h3,h4{letter-spacing:-.02em}
h2{font-size:var(--fs-xl);font-weight:800;line-height:1.25}
h3{font-size:var(--fs-lg);line-height:1.35}
body{scroll-behavior:smooth}
button,select,input{font-family:inherit}
:focus-visible{outline:2px solid var(--acc);outline-offset:2px}
.top{position:sticky;top:0;z-index:20;background:var(--bg);border-bottom:1px solid var(--line)}
.top .in{max-width:1180px;margin:0 auto;padding:10px var(--s4);display:flex;flex-wrap:wrap;gap:var(--s2) 18px;align-items:center;justify-content:space-between}
.brand{font-weight:800;font-size:var(--fs-md)} .brand span{color:var(--sub);font-weight:500;font-size:var(--fs-sm);margin-left:var(--s2)}
nav{display:flex;gap:var(--s1);flex-wrap:wrap}
nav button{justify-content:center;border:1px solid transparent;background:transparent;color:var(--fg);padding:5px 14px 4px;border-radius:var(--r-md);font-size:var(--fs-sm);line-height:1.3;cursor:pointer;display:flex;flex-direction:column;align-items:center}
nav button small{font-size:var(--fs-xs);font-weight:400;color:var(--sub)}@media (max-width:1000px){nav button small{display:none}} nav button[aria-selected="true"] small{color:inherit;opacity:.92}
nav button:hover{background:var(--accent-tint);color:var(--accent-strong)}
nav button[aria-selected="true"],nav button[aria-selected="true"]:hover{background:var(--accent);border-color:var(--accent);color:var(--accent-fg)}
main.wide{max-width:1180px;padding-bottom:80px} section.tab{display:none;padding-top:var(--s4)} section.tab.on{display:block}
.hero{padding:2px 0 var(--s2)} .hero h1{font-size:clamp(28px,4.2vw,var(--fs-2xl));font-weight:800;letter-spacing:-.02em;line-height:1.2;margin:0 0 var(--s1)} .hero p{margin:0;color:var(--sub);font-size:var(--fs-sm)}
.ctrl{display:flex;flex-wrap:wrap;gap:10px 14px;align-items:center;margin:var(--s2) 0 14px}
.toolbar{display:flex;flex-wrap:wrap;gap:var(--s2) var(--s3);align-items:center;margin:var(--s2) 0 6px}
.toolbar label{display:flex;align-items:center;gap:6px;color:var(--sub);font-size:var(--fs-sm)}
.chips{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin:0 0 6px}
.chip-b{border:1px solid var(--line);background:var(--card);color:var(--fg);padding:6px 12px;border-radius:999px;font-size:var(--fs-sm);cursor:pointer}
.chip-b:hover{border-color:var(--acc);background:var(--acc-soft)}
.chip-b.on,.chip-b.pri{background:var(--acc);color:var(--acc-fg);border-color:var(--acc)}
.chip-b.pri:hover{filter:brightness(1.08)}
select,input[type=text]{font-size:var(--fs-sm);padding:7px 10px;border:1px solid var(--line);border-radius:var(--r-sm);background:var(--card);color:var(--fg)}
select:hover,input[type=text]:hover{border-color:var(--acc)}
input[type=text]{min-width:min(260px,100%);flex:1}
.grid2{display:grid;grid-template-columns:minmax(0,1.1fr) minmax(0,1fr);gap:var(--s4);align-items:start}
.mapcard{position:sticky;top:calc(var(--head-h) + 12px);padding:6px;isolation:isolate}
#map{width:100%;height:clamp(440px,calc(100vh - 300px),760px);border-radius:var(--r-sm);z-index:0}
@media (max-width:767px){.grid2{grid-template-columns:1fr}.mapcard{position:static}#map{height:min(62vh,520px);min-height:340px}.brand span{display:none}.top{position:static}.top .in{padding:var(--s2) var(--s4)}nav button{padding:6px 10px}nav button small{display:none}.maplegend{width:184px;font-size:13px;padding:5px 8px 4px}.maplegend .lg-ticks{font-size:13px}.maplegend .lg-t{font-size:13px;margin-bottom:3px}.maplegend .lg-r.lg-d{display:none}.maplegend .lg-d{display:none}}
.leaflet-container{font:inherit;background:var(--card)} .leaflet-tile-pane .tiles-osm{filter:grayscale(1) contrast(.88) brightness(1.08)}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]) .leaflet-tile-pane .tiles-osm{filter:grayscale(1) invert(1) contrast(.85) brightness(.85)}}
.leaflet-tooltip{font-size:13px;line-height:1.4}
.maplegend{background:color-mix(in srgb,var(--card) 93%,transparent);color:var(--fg);border:1px solid var(--line);border-radius:var(--r-sm);padding:7px 10px 8px;font-size:var(--fs-sm);line-height:1.35;box-shadow:var(--sh-sm);width:258px}
.maplegend .lg-t{font-weight:700;margin-bottom:5px}
.maplegend .lg-bar{height:10px;border-radius:5px;background:linear-gradient(90deg,rgb(45,110,190),rgb(232,230,222),rgb(214,69,65))}   /* JS col()의 지도 버블 색과 동일(테마와 무관하게 고정) */
.maplegend .lg-ticks{position:relative;height:20px;margin-top:2px;color:var(--sub);font-size:var(--fs-sm)}
.maplegend .lg-ticks span{position:absolute;top:3px;white-space:nowrap} .maplegend .lg-ticks i{position:absolute;top:-1px;width:1px;height:4px;background:var(--sub)}
.maplegend .lg-r{display:flex;align-items:center;gap:6px;color:var(--sub);margin-top:3px}
.maplegend .dot{display:inline-block;border-radius:50%;background:var(--flat);border:1px solid rgba(0,0,0,.4);flex:none}
.maplegend .dot.dash{width:11px;height:11px;background:rgba(154,160,166,.35);border:1.5px dashed #6b7280}
.leaflet-control-attribution{font-size:11px;line-height:1.35}
.mapbtns{display:flex;gap:6px}
.mapbtns button{font-size:13px;padding:6px 10px;border-radius:var(--r-sm);border:1px solid var(--line);background:var(--card);color:var(--fg);cursor:pointer;box-shadow:var(--sh-sm)}
.mapbtns button:hover{border-color:var(--acc);color:var(--acc)}
.city-lbl{font-size:var(--fs-xs);font-weight:600;color:#5b6472;text-shadow:0 0 3px #fff,0 0 3px #fff,0 0 3px #fff;white-space:nowrap;pointer-events:none}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]) .city-lbl{color:#b7bfcc;text-shadow:0 0 3px #000,0 0 3px #000}}
.panel h3{margin:0 0 2px;font-size:var(--fs-lg)} .panel .sub2{color:var(--sub);font-size:var(--fs-sm)}
.panel .clear{margin-left:0} .only-m{display:none} @media (max-width:767px){.only-m{display:inline-block}div.only-m{display:block}}
.big{display:flex;align-items:baseline;gap:14px;flex-wrap:wrap;margin:var(--s2) 0 2px} .big b{font-size:var(--fs-3xl);font-weight:800;line-height:1;letter-spacing:-.03em;font-variant-numeric:tabular-nums}
@media (max-width:767px){.big b{font-size:var(--fs-2xl)}}
.big span{color:var(--sub);font-size:var(--fs-sm)}
.t-hi{color:var(--hi-text)}.t-lo{color:var(--lo-text)} .big .delta{font-weight:700;font-size:var(--fs-md)}
.hasq{position:relative}
.q{width:20px;height:20px;border-radius:50%;border:1px solid var(--sub);background:transparent;color:var(--sub);font-size:var(--fs-sm);line-height:1;padding:0;margin-left:4px;cursor:help;flex:none;vertical-align:middle}
.q:hover,.q:focus-visible,.q.open{border-color:var(--acc);color:var(--acc)}
.q::after{content:attr(data-tip);display:none;position:absolute;z-index:30;left:0;top:calc(100% + 4px);width:min(290px,78vw);padding:8px 10px;border-radius:var(--r-sm);background:var(--fg);color:var(--bg);font-size:var(--fs-sm);font-weight:400;line-height:1.5;text-align:left;box-shadow:var(--sh-md)}
.q:hover::after,.q:focus-visible::after,.q.open::after{display:block}
.fx{margin:4px 0}
.fxrow{display:grid;grid-template-columns:minmax(118px,36%) minmax(0,1fr) 68px;align-items:center;gap:var(--s2);margin:7px 0;font-size:var(--fs-sm)}
.fxrow .nm{display:flex;align-items:center;line-height:1.3}
.fxrow .trk{position:relative;height:16px}
.fxrow .trk::before{content:"";position:absolute;left:50%;top:-5px;bottom:-5px;border-left:1px dashed var(--sub)}
.fxrow .fbar{position:absolute;top:0;bottom:0;border-radius:3px}
.fxrow .fbar.hi{background:var(--hi)}.fxrow .fbar.lo{background:var(--lo)}.fxrow .fbar.soft{opacity:.42}
.fxrow .val{white-space:nowrap;text-align:right;font-weight:600;font-variant-numeric:tabular-nums}
.exp{list-style:none;margin:0;padding:0}
.exp>li{margin:9px 0;font-size:var(--fs-md);line-height:1.6}
.exp .k{display:block;color:var(--acc);font-size:var(--fs-sm);font-weight:700;margin-bottom:1px}
.exp .subl{list-style:none;margin:2px 0 0;padding:0}
.exp .subl>li{margin:5px 0;padding-left:10px;border-left:3px solid var(--line)}
.tag{white-space:nowrap}
.fxrow.isflat .nm{color:var(--sub)}
.fxrow .fbar{min-width:2px}
.fxrow .fbar.flat{background:var(--flat)}
.t-flat{color:var(--sub)}
.fxaxis{margin-top:2px}.fxaxis .ax span{white-space:nowrap}.fxaxis .ax{display:grid;grid-template-columns:1fr auto 1fr;color:var(--sub);font-size:var(--fs-sm)}.fxaxis .ax span:last-child{text-align:right}
.tbl th.srt{cursor:pointer;user-select:none;white-space:nowrap;font-size:var(--fs-sm)}
.tbl th.srt::after{content:" ↕";opacity:.45}
.tbl th.srt[data-dir="desc"]::after{content:" ↓";opacity:1;color:var(--acc)}
.tbl th.srt[data-dir="asc"]::after{content:" ↑";opacity:1;color:var(--acc)}
.tbl th.srt:hover{color:var(--acc)}
.tbl tr.clk td:first-child{white-space:nowrap}
.tbl tr.clk{cursor:pointer}.tbl tr.clk:hover td:not([style]){background:var(--acc-soft)}.tbl tr.cur td:first-child{font-weight:700;box-shadow:inset 3px 0 0 var(--acc)}
.tbl th,.tbl td{font-size:var(--fs-sm)}
@media (max-width:520px){.fxrow{grid-template-columns:minmax(0,1fr) auto;row-gap:4px;margin:12px 0}.fxrow .val{grid-column:2;grid-row:1}.fxrow .trk{grid-column:1/3;grid-row:2}
 .fxaxis{grid-template-columns:1fr}.fxaxis>div:first-child,.fxaxis>div:last-child{display:none}}
.sugwrap{position:relative;flex:1;min-width:min(260px,100%)}.sugwrap input{width:100%}
.sug{position:absolute;z-index:40;left:0;right:0;top:calc(100% + 4px);margin:0;padding:4px;list-style:none;background:var(--card);border:1px solid var(--line);border-radius:var(--r-md);box-shadow:var(--sh-md);max-height:320px;overflow:auto}
.sug[hidden]{display:none}
.sug li{display:flex;justify-content:space-between;gap:var(--s2);padding:7px 10px;border-radius:6px;cursor:pointer;font-size:var(--fs-sm)}
.sug li[aria-selected="true"],.sug li:hover{background:var(--acc-soft)}.sug .tp{color:var(--sub);font-size:13px;white-space:nowrap}
.guide{display:flex;align-items:center;gap:var(--s3);background:var(--acc-soft);border:1px solid var(--acc);border-radius:var(--r);padding:6px var(--s3);margin:6px 0;font-size:var(--fs-sm)}
.guide[hidden]{display:none}
.guide ol{display:flex;flex-wrap:wrap;gap:4px 18px;margin:0;padding:0;list-style:none;flex:1;counter-reset:g}
.guide li{counter-increment:g}.guide li::before{content:counter(g);display:inline-grid;place-items:center;width:20px;height:20px;border-radius:50%;background:var(--acc);color:var(--acc-fg);font-size:var(--fs-xs);font-weight:700;margin-right:6px}
body.guide-on #map{height:clamp(400px,calc(100vh - 355px),760px)}
@media (max-width:767px){body.guide-on #map{height:min(62vh,520px)}}
.cmp{display:grid;grid-template-columns:1fr 1fr;gap:var(--s4)}@media (max-width:767px){.cmp{grid-template-columns:1fr}}
.cmp h4{margin:0}.cmp .big b{font-size:var(--fs-2xl)}.cmpdiff{margin:12px 0 0;font-size:var(--fs-md)}
.sumbox{padding:var(--s5);margin:0 0 var(--s2)}
.sumbox h2{font-size:var(--fs-xl);margin:0 0 var(--s1)}.sumlist{margin:0 0 4px;padding-left:22px}.sumlist li{margin:5px 0;font-size:var(--fs-md)}
.sumcta{display:flex;flex-wrap:wrap;gap:var(--s2)}.sumcta a.chip-b{text-decoration:none;display:inline-block}
.plain{font-size:var(--fs-md);margin:6px 0 10px}
details.stat{border:1px solid var(--line);border-radius:var(--r);background:var(--card);margin:8px 0 14px}
details.stat>summary{cursor:pointer;padding:10px 14px;font-weight:600;color:var(--acc)}
details.stat>summary:hover{background:var(--acc-soft)}
details.stat[open]>summary{border-bottom:1px solid var(--line)}
.statbody{padding:8px 14px 14px}
.how{color:var(--sub);font-size:var(--fs-sm);margin:2px 0 8px}
.imps{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(420px,100%),1fr));gap:12px;margin-bottom:8px}
.imp{background:var(--card);border:1px solid var(--line);border-radius:var(--r-md);padding:14px 16px}
.imp h4{margin:0 0 8px;font-size:var(--fs-md);line-height:1.4}
.imp dl{margin:0;display:grid;grid-template-columns:auto 1fr;gap:4px 10px;font-size:var(--fs-sm)}
.imp dt{font-weight:700;color:var(--acc);white-space:nowrap}.imp dd{margin:0}
.lgbox{margin:0 0 12px}
/* 쉬운 이름 먼저 · 전문 용어는 작게 병기 */
.tn{font-size:var(--fs-sm);font-weight:400;color:var(--sub);letter-spacing:0}
.techsub{margin:2px 0 0;font-size:var(--fs-sm);color:var(--sub)}
.lookfor{display:block;font-size:var(--fs-sm);font-weight:700;color:var(--accent);margin-bottom:2px}
.ubline{margin:0 0 6px}
.ubadge{display:inline-flex;align-items:center;gap:2px;padding:1px 10px;border:1px solid var(--line);border-radius:999px;background:var(--card);font-size:var(--fs-sm);color:var(--sub)}
.hbrow .hbar.pos.int{background:repeating-linear-gradient(135deg,var(--accent) 0 6px,color-mix(in srgb,var(--accent) 50%,var(--card)) 6px 12px)}
.sw.int{background:repeating-linear-gradient(135deg,var(--accent) 0 3px,color-mix(in srgb,var(--accent) 50%,var(--card)) 3px 6px)}
.perf h3{margin:var(--s4) 0 var(--s2)}
.perfgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(260px,100%),1fr));gap:var(--s3);margin-bottom:var(--s3)}
.perfcard{padding:var(--s4)}.perfcard .pk{margin:0 0 var(--s1);font-weight:700}.perfcard .pd{margin:var(--s1) 0;font-size:var(--fs-sm)}
dl.ainfo{display:grid;grid-template-columns:auto 1fr;gap:2px var(--s3);margin:6px 0;font-size:var(--fs-sm)}
dl.ainfo dt{font-weight:700;color:var(--accent);white-space:nowrap}dl.ainfo dd{margin:0}
/* ===== 마이크로 인터랙션(절제): 호버 -2px + 그림자 한 단계(150ms), 탭 전환 페이드(200ms), 포커스 링, 표 행 하이라이트 ===== */
.chip-b,.nb button,.rk,.imp,.mapbtns button,nav button{transition:transform .15s ease,box-shadow .15s ease,background-color .15s ease,border-color .15s ease,color .15s ease}
.chip-b:hover,.nb button:hover,.rk:hover,.mapbtns button:hover{transform:translateY(-2px);box-shadow:var(--sh-sm)}
.imp:hover{transform:translateY(-2px);box-shadow:var(--sh-md)}
section.tab.on{animation:fadein .2s ease}
@keyframes fadein{from{opacity:0}to{opacity:1}}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
input:focus-visible,select:focus-visible{outline:2px solid var(--accent);outline-offset:1px;border-color:var(--accent)}
tbody tr:hover>td:not([style]),tbody tr:hover>th[scope=row]{background:var(--accent-tint)}
.scroll{max-height:min(78vh,760px);overflow:auto}
.scroll thead th{position:sticky;top:0;z-index:3;background:var(--card)}
table.grp thead th:first-child,table.ov thead th:first-child{z-index:4}
@media (prefers-reduced-motion:reduce){*,*::before,*::after{transition:none!important;animation:none!important}html,body{scroll-behavior:auto!important}.chip-b:hover,.nb button:hover,.rk:hover,.mapbtns button:hover,.imp:hover{transform:none}}
/* 카드 3단계 — primary(핵심·시사점, 페이지당 6개 이내) / default(흰 배경+얇은 테두리+sm 그림자) / subtle(테두리만) */
.card{box-shadow:var(--sh-sm)}
.primary{background:var(--accent-tint);border:1px solid transparent;border-left:4px solid var(--accent);box-shadow:none}
.card.subtle,details.stat{background:transparent;box-shadow:none}
.imp.primary{border-radius:var(--r-md);padding:var(--s4) var(--s5)}
.findings-box{padding:var(--s2) var(--s5)}
.findings-box .finding{background:none;border:0;border-bottom:1px solid color-mix(in srgb,var(--accent) 22%,transparent);border-radius:0;margin:0;padding:var(--s4) 0;box-shadow:none}
.findings-box .finding:last-child{border-bottom:0}
/* 섹션 리듬 — 배경 교차(--bg / --bg-alt) + 큰 여백, 제목 위 작은 라벨(eyebrow) */
body{overflow-x:clip}
.band{position:relative;isolation:isolate;padding:var(--s7) 0}
.band.first{padding-top:var(--s4);padding-bottom:var(--s5)}
.band.alt::before{content:"";position:absolute;z-index:-1;top:0;bottom:0;left:50%;width:100vw;margin-left:-50vw;background:var(--bg-alt)}
.band h2{margin:0 0 var(--s2)}
.eyebrow{margin:0 0 var(--s2);font-size:var(--fs-xs);font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:var(--accent)}
@media (max-width:767px){.band{padding:var(--s6) 0}}
.hero{display:flex;flex-wrap:wrap;align-items:flex-end;justify-content:space-between;gap:var(--s3) var(--s5)}
.hero .hd{min-width:0}
.survlink{background:var(--acc-soft);border:1px solid var(--acc);border-radius:var(--r);padding:10px var(--s4);margin:8px 0;font-size:var(--fs-md)}
.survlink a{color:var(--acc);font-weight:600}
table.ov{min-width:560px}
table.ov th{white-space:normal;vertical-align:bottom}table.ov th small{font-weight:400;color:var(--sub);font-size:var(--fs-sm)}
table.ov th[scope=row],table.ov thead th:first-child{position:sticky;left:0;z-index:2;background:var(--card);text-align:left;font-weight:600;color:var(--fg);box-shadow:1px 0 0 var(--line)}
table.ov td.ovc{text-align:center;font-variant-numeric:tabular-nums;font-size:var(--fs-sm)}
.concl{margin:2px 0 6px;font-size:var(--fs-md)}
.stat-number{display:flex;flex-direction:column;gap:2px;margin:2px 0 6px}
.stat-number .num{font-size:var(--fs-2xl);font-weight:800;line-height:1.1;color:var(--accent);font-variant-numeric:tabular-nums;letter-spacing:-.02em}
.stat-number .lbl{color:var(--sub);font-size:var(--fs-sm);line-height:1.4}
.finding h4{font-size:var(--fs-lg);font-weight:700;line-height:1.35}
.finding>div:last-child{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:var(--s1) var(--s5);align-items:center}
.finding .stat-number{grid-column:2;grid-row:1/3;align-items:flex-end;text-align:right;max-width:340px;margin:0}
.finding details.tech{grid-column:1;grid-row:2}
@media (min-width:1000px){.finding .stat-number{max-width:none}.finding .stat-number .lbl{white-space:nowrap}}   /* 넓은 화면에서는 핵심 숫자 설명을 한 줄로 */
@media (max-width:767px){.finding>div:last-child{grid-template-columns:1fr}.finding .stat-number{grid-column:1;grid-row:auto;align-items:flex-start;text-align:left;max-width:none;margin:var(--s1) 0}.finding details.tech{grid-row:auto}.stat-number .num{font-size:var(--fs-xl)}}
details.tech{margin-top:2px}details.tech>summary{cursor:pointer;color:var(--acc);font-size:var(--fs-sm);font-weight:600}
details.tech>p{margin:6px 0 0;color:var(--sub);font-size:var(--fs-sm)}
.toc{position:sticky;top:var(--head-h);z-index:15;display:flex;flex-wrap:nowrap;gap:6px;overflow-x:auto;white-space:nowrap;padding:8px 0;margin:6px 0 4px;background:var(--bg);border-bottom:1px solid var(--line)}
.toc a.chip-b{text-decoration:none;flex:none}.toc a.chip-b.on{background:var(--acc);color:var(--acc-fg);border-color:var(--acc)}
#t-surv h2{scroll-margin-top:calc(var(--head-h) + 64px)}
@media (max-width:767px){.toc{top:0}#t-surv h2{scroll-margin-top:64px}}
.hbaxis .ax{position:relative;height:26px;margin-top:2px}
.hbaxis .tk{position:absolute;top:-4px;height:5px;border-left:1px solid var(--sub)}
.hbaxis .lb{position:absolute;top:3px;transform:translateX(-50%);font-size:var(--fs-sm);color:var(--sub);white-space:nowrap}
.hbaxis .lb.l{transform:none}.hbaxis .lb.r{transform:translateX(-100%)}
@media (max-width:520px){.hbaxis>div:first-child,.hbaxis>div:last-child{display:none}.hbaxis .ax{grid-column:1/3;grid-row:auto}}
.hbrow.hl{outline:2px solid var(--acc);outline-offset:3px;border-radius:6px;animation:hlp 2.4s ease-out}
@keyframes hlp{0%{background:var(--acc-soft)}100%{background:transparent}}
.lgd{display:flex;flex-wrap:wrap;gap:4px 16px;font-size:var(--fs-sm);color:var(--sub);margin:0 0 6px}.lgd .lgi{white-space:nowrap}
.sw{display:inline-block;width:12px;height:12px;border-radius:3px;vertical-align:-1px;margin-right:5px}
.sw.pos{background:var(--acc)}.sw.muted{background:var(--flat)}.sw.neg{background:#b45309}
table.grp{min-width:780px}
table.grp th{white-space:normal;vertical-align:bottom;font-size:var(--fs-sm);min-width:74px}
table.grp th:first-child,table.grp td.gname{position:sticky;left:0;z-index:2;background:var(--card);box-shadow:1px 0 0 var(--line)}
table.grp td.chip{font-size:var(--fs-sm)}
table.grp td.chip .ar{margin-right:2px}
table.grp td.chip.flat{background:rgba(125,134,150,.16);color:var(--sub)}
#t-surv .sub{font-size:var(--fs-sm)}
th{font-size:var(--fs-sm)}
.finding .n{color:var(--acc-fg)}
@media (max-width:767px){table.grp{min-width:700px}table.grp .gname{min-width:150px}}
#scat{overflow-x:auto}.scat{min-width:760px}
.toast{position:fixed;left:50%;bottom:24px;transform:translateX(-50%);background:var(--fg);color:var(--bg);padding:10px 18px;border-radius:999px;font-size:var(--fs-sm);opacity:0;pointer-events:none;transition:opacity .2s;z-index:100}
.toast.on{opacity:1}
.skel{display:flex;flex-direction:column;gap:12px;padding:6px 0}
.skel i,#map:not(.leaflet-container){display:block;height:16px;border-radius:var(--r-sm);background:linear-gradient(90deg,var(--line) 25%,var(--card) 45%,var(--line) 65%);background-size:200% 100%;animation:shim 1.3s infinite linear}
@keyframes shim{to{background-position:-200% 0}}
@media (prefers-reduced-motion:reduce){.skel i,#map:not(.leaflet-container){animation:none}}
.phead{display:flex;flex-wrap:wrap;gap:var(--s2) var(--s3);align-items:flex-start;justify-content:space-between}
.acts{display:flex;flex-wrap:wrap;gap:6px}
.hb{margin:6px 0}
.hbrow{display:grid;grid-template-columns:minmax(132px,34%) minmax(0,1fr) 78px;gap:var(--s2);align-items:center;margin:9px 0;font-size:var(--fs-sm)}
.hbrow .nm{line-height:1.3}.hbrow .val{text-align:right;font-weight:600;font-variant-numeric:tabular-nums;white-space:nowrap}
.hbrow .trk{position:relative;height:20px}
.hbrow .zero{position:absolute;top:-5px;bottom:-5px;border-left:1px dashed var(--sub)}
.hbrow .hbar{position:absolute;top:0;bottom:0;border-radius:3px;min-width:2px;background:var(--flat)}
.hbrow .hbar.pos{background:var(--acc)}.hbrow .hbar.ref{background:var(--sub)}.hbrow .hbar.neg{background:#b45309}
.hbrow .wk{position:absolute;top:50%;border-top:1.5px solid var(--fg)}.hbrow .wkc{position:absolute;top:4px;bottom:4px;border-left:1.5px solid var(--fg)}
@media (max-width:520px){.hbrow{grid-template-columns:minmax(0,1fr) auto;row-gap:4px;margin:13px 0}.hbrow .val{grid-column:2;grid-row:1}.hbrow .trk{grid-column:1/3;grid-row:2}}
.q.flip::after{left:auto;right:0}
h2 .q,h3 .q,h4 .q{vertical-align:middle}
.rklist{display:flex;flex-direction:column;gap:6px}
.rk{display:grid;grid-template-columns:24px minmax(0,1fr) auto;column-gap:var(--s2);align-items:baseline;text-align:left;width:100%;border:1px solid var(--line);background:var(--card);color:var(--fg);border-radius:var(--r-sm);padding:7px 10px;font-size:var(--fs-sm);cursor:pointer}
.rk:hover{border-color:var(--acc);background:var(--acc-soft)}
.rk .rn{color:var(--sub);font-weight:700}.rk .rt{font-weight:600}.rk .rv{font-weight:700}.rk .rs{grid-column:2/4;color:var(--sub)}
.tag{display:inline-block;padding:1px 9px;border-radius:999px;font-size:var(--fs-sm);background:var(--line);color:var(--fg);margin:0 2px}
.tag.hi{background:var(--hi-soft);color:var(--hi-text)} .tag.lo{background:var(--lo-soft);color:var(--lo-text)}
.why{margin:6px 0 4px} .why p{margin:6px 0;font-size:var(--fs-md)}
.blk{border-top:1px solid var(--line);margin-top:14px;padding-top:var(--s3)} .blk h4{margin:0 0 6px;font-size:var(--fs-sm);color:var(--sub);font-weight:600}
.two{display:grid;grid-template-columns:1fr 1fr;gap:var(--s3)} @media (max-width:520px){.two{grid-template-columns:1fr}}
.mini{max-width:280px;width:100%}.mini text{font-size:11px;fill:var(--fg)} .mini .v{fill:var(--sub)}
.spark{width:100%;max-width:320px;height:auto}
.nb{display:flex;flex-wrap:wrap;gap:6px} .nb button{border:1px solid var(--line);background:var(--card);color:var(--fg);border-radius:var(--r-sm);padding:5px 10px;font-size:var(--fs-sm);cursor:pointer}
.nb button:hover{border-color:var(--acc);background:var(--acc-soft)}
.warn{background:var(--warn);border:1px solid var(--warnb);border-radius:var(--r-sm);padding:8px 12px;font-size:var(--fs-sm);margin:var(--s2) 0}
.hint{color:var(--sub);font-size:var(--fs-sm)}
.tbl td.b1{min-width:120px} .mb{display:inline-block;height:9px;border-radius:3px;vertical-align:middle;margin-right:6px}
.kp{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin:10px 0}
.kp div{background:var(--bg);border:1px solid var(--line);border-radius:var(--r);padding:10px var(--s3)} .kp b{display:block;font-size:var(--fs-lg)} .kp span{font-size:var(--fs-sm);color:var(--sub)}
.scat circle{opacity:.5} .scat text{font-size:13px;fill:var(--sub)}
.cols3{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:14px}
.legend2{display:flex;flex-wrap:wrap;align-items:center;gap:6px 10px;font-size:var(--fs-sm);color:var(--sub);margin:var(--s2) 4px 2px}.legend2 span{white-space:nowrap}
.cap{font-size:var(--fs-sm)}
#err{display:none;background:#fee;color:#900;padding:8px;font-size:var(--fs-xs)}
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
<button data-t="map" aria-selected="true">지도 탐색<small>위험 지도로 보기</small></button><button data-t="area" aria-selected="false">상권 분석<small>업종·지역 비교</small></button>
<button data-t="surv" aria-selected="false">모형 근거</button></nav>
</div></div>
<main class="wide">

<section class="tab on" id="t-map">
<div class="hero"><div class="hd"><p class="eyebrow">CLOSURE RISK MAP</p><h1>어느 지역·업종이 왜 위험한가</h1>
<p>붉은 지역일수록 폐업 위험이 높고, 푸른 지역일수록 낮아요. 지역을 누르면 왜 그런지 이유를 볼 수 있어요.</p></div>
</div>
<div class="guide" id="guide" hidden><ol><li>지도에서 지역을 누르거나 검색해요</li><li>색(상대 폐업 위험)과 요인 막대로 이유를 봐요</li><li>업종 버튼으로 업종별로 비교해요</li></ol><button type="button" class="chip-b" id="guideX" aria-label="가이드 닫기">닫기 ✕</button></div>
<div class="toolbar">
<span class="sugwrap"><input type="text" id="ask" placeholder="예) 동탄 서양음식 / 합천 한식 / 한식 위험한 곳" aria-label="지역·업종 질문" autocomplete="off" role="combobox" aria-autocomplete="list" aria-expanded="false" aria-controls="sug"><ul class="sug" id="sug" role="listbox" hidden></ul></span>
<button class="chip-b pri" id="askbtn">설명 보기</button>
<label>색 기준 <select id="mode"><option value="mult">상대 폐업 위험 (평균 점포 = ×1.0)</option><option value="rate">실제 폐업률 (전국 대비)</option></select></label>
</div>
<div class="chips" id="bizbar"></div>
<div class="hint" id="askhelp" style="margin:0 0 var(--s3)">지역·업종·위험/안전을 조합해 검색해 보세요. 예: <button class="chip-b" data-q="동탄 서양음식">동탄 서양음식</button> <button class="chip-b" data-q="합천 한식">합천 한식</button> <button class="chip-b" data-q="강남구">강남구</button> <button class="chip-b" data-q="한식 위험한 곳">한식 위험한 곳</button> <button class="chip-b" data-q="경남 한식 안전한 곳">경남 한식 안전한 곳</button></div>
<div class="grid2">
<div class="card mapcard"><div id="map" role="region" aria-label="시군구 버블 지도. 붉을수록 폐업 위험이 높고 푸를수록 낮아요. 같은 정보를 오른쪽 순위 카드와 검색으로도 볼 수 있어요."></div><div class="hint only-m" style="margin:6px 4px 2px">버블 크기 = 점포 수 · 점선 회색 = 표본 30개 미만(업종 선택 시)</div><div class="hint" id="tilenote" style="margin:2px 4px 0;color:var(--hi-text)"></div></div>
<div class="card panel" id="panel"><div class="skel" aria-hidden="true"><i style="width:55%;height:26px"></i><i style="width:85%"></i><i style="width:70%"></i><i style="height:52px"></i><i style="height:52px"></i><i style="height:52px"></i></div></div>
</div>
</section>

<section class="tab" id="t-area">
<div class="band first"><div class="hero"><div class="hd"><p class="eyebrow">AREA PROFILE</p><h1>상권 분석</h1><p>시군구를 고르면 업종별 점포 수·실제 폐업률·상대 폐업 위험·영업연수·프랜차이즈 비중·BC카드 월평균 소비를 한눈에 봅니다.</p></div></div>
<div class="ctrl"><input type="text" id="areaq" list="rlist" placeholder="시군구 검색 (예: 화성시 동탄구, 강남구, 합천군)"><datalist id="rlist"></datalist></div>
<div id="areaout" class="card"><p class="hint">시군구를 선택하세요.</p></div></div>
<div class="band alt"><p class="eyebrow">COMPARE</p><h2>두 지역 비교</h2>
<div class="ctrl"><input type="text" id="cmpA" list="rlist" placeholder="지역 A (예: 서울특별시 마포구)" aria-label="비교할 지역 A"><span class="hint">vs</span><input type="text" id="cmpB" list="rlist" placeholder="지역 B (예: 서울특별시 강남구)" aria-label="비교할 지역 B"><select id="cmpBiz" aria-label="비교할 업종"></select></div>
<div id="cmpOut" class="card"><p class="hint">두 지역을 고르면 상대 폐업 위험과 요인 막대를 나란히 보여 줘요.</p></div></div>
<div class="band"><p class="eyebrow">RANKING</p><h2>시군구 위험·안전 Top 10 (전체 업종) <span class="hasq"><button type="button" class="q" data-tip="__TIP_MIN__" aria-label="설명: __TIP_MIN__">?</button></span></h2>
<p class="hint" style="margin:0 0 8px">점포 2,000개 이상 시군구만 순위에 넣었어요. 행을 누르면 지도에서 열려요.</p>
<div class="cols3"><div class="card" id="rg-hi"></div><div class="card" id="rg-lo"></div></div></div>
<div class="band alt"><p class="eyebrow">BY INDUSTRY</p><h2>업종별 위험 순위 (점포 300개 이상 조합) <span class="hasq"><button type="button" class="q" data-tip="__TIP_MIN__" aria-label="설명: __TIP_MIN__">?</button></span></h2>
<div class="ctrl"><select id="rankbiz"></select></div>
<div class="cols3"><div class="card" id="rk-hi"></div><div class="card" id="rk-lo"></div></div></div>
<div class="band"><p class="eyebrow">CONSUMPTION</p><h2>소비가 많으면 버티는가? — 점포당 소비와 실제 폐업률 <span class="hasq"><button type="button" class="q" data-tip="__TIP_MIN__" aria-label="설명: __TIP_MIN__">?</button></span></h2>
<div class="card"><div id="scat"></div><p class="cap">점 하나 = 시군구×업종 조합(점포 100개 이상), 굵은 선 = 소비 10분위별 실제 폐업률. 소비 하위 구간의 폐업률이 가장 낮고 중·상위에서는 비슷한 수준으로 이어집니다 — 소비가 높다고 덜 폐업하지 않습니다. 업종 안 소비 순위와 폐업률의 순위상관은 전체 __RHO_ALL__, 같은 시군구 안에서는 __RHO_IN__(관계 없음)입니다.</p></div></div>
</section>

<section class="tab" id="t-surv">__SURV__</section>
</main>
<div id="toast" class="toast" role="status" aria-live="polite"></div>
<noscript><p style="padding:16px">이 지도는 JavaScript가 필요해요. 브라우저에서 JavaScript를 켜 주세요.</p></noscript>

<script>__LEAFLET_JS__</script>
<script>
window.onerror=function(m,s,l){var e=document.getElementById('err');e.style.display='block';e.textContent='JS 오류: '+m+' (줄 '+l+')';};
const D=__DATA__;
const NAT=D.national, BIZ=D.biz.map(n=>n==='스넥'?'스낵':n);   // 표시 라벨만 통일(데이터 키 D.biz는 그대로, 인덱스 동일)
const $=(s,el=document)=>el.querySelector(s);
const UP=new URLSearchParams(location.search);   // 페이지를 연 시점의 주소(상태 저장이 주소를 바꾸기 전에 읽어 둔다)
const pct=(v,d=1)=>(v*100).toFixed(d)+'%';
// 요인 표시 이름·설명. key는 코드 내부 식별자, idx는 모형 출력 x의 위치(데이터 키)라 바꾸지 않는다.
const SHOW=[
 {key:'yrs',label:'영업연수',idx:[0],tip:'문을 연 지 몇 년 됐는지예요. 오래 영업한 점포가 많을수록 위험이 낮게 나와요.'},
 {key:'fr',label:'프랜차이즈 비중',idx:[1],tip:'프랜차이즈(가맹) 점포의 비중이에요. 이 모형에서는 비중이 높은 곳이 위험이 낮게 나와요.'},
 {key:'site',label:'점포 규모·운영 특성',idx:[3],tip:'점포 규모, 다중이용시설 여부처럼 점포 자체의 특성이에요.'},
 {key:'hist',label:'지역 폐업 흐름',idx:[5],tip:'이 시군구와 이웃 시군구에서 2026-01-01 기준 직전 1년 동안 폐업한 점포의 비율이에요. 높을수록 위험이 높아요.'},
 {key:'age',label:'BC카드 고객 연령대',idx:[7],tip:'BC카드 결제 고객의 연령대 구성이에요. 같은 시군구 안에서는 위험을 가르지 못했고, 어떤 유형의 지역인지 알려 주는 신호일 뿐이에요. 원인으로 읽으면 안 되어서 옅게 표시하고 해설에서는 뺐어요.'},
 {key:'gen',label:'BC카드 고객 성별',idx:[6],tip:'BC카드 결제 고객의 남성·여성·법인 비중이에요. 최종 모형에는 들어 있지만, 같은 시군구 안에서는 빼는 편이 예측이 조금 더 나았어요(생존 분석 탭 참고). 그래서 참고용으로 봐 주세요.'},
 {key:'biz',label:'업종 자체의 위험',idx:[8],tip:'업종마다 평균적으로 폐업이 잦은 정도가 달라요. 그 업종 자체가 가진 기본 위험이에요.'},
 {key:'etc',label:'입지·기타 요인',idx:[2,4],tip:'위 항목에 들어가지 않는 입지 등 나머지 요인을 합친 값이에요.'}];
const factors=x=>SHOW.map(s=>({key:s.key,label:s.label,tip:s.tip,m:s.idx.reduce((a,i)=>a*x[i],1)}));
const qa=t=>t.replace(/"/g,'&quot;');
const qtip=t=>'<button type="button" class="q" data-tip="'+qa(t)+'" aria-label="설명: '+qa(t)+'">?</button>';   // (?) 도움말: 마우스를 올리거나 누르면 열린다
document.addEventListener('click',e=>{const g=e.target.closest('[data-go-tab]');if(g)tab(g.dataset.goTab);const jm=e.target.closest('[data-jump]');if(jm){e.preventDefault();const el=document.getElementById(jm.dataset.jump);if(el)el.scrollIntoView({behavior:'smooth'});}
  const q=e.target.closest('.q');document.querySelectorAll('.q.open').forEach(x=>{if(x!==q)x.classList.remove('open');});if(q){q.classList.toggle('open');q.classList.toggle('flip',q.getBoundingClientRect().left>innerWidth/2);}});
const MX=m=>'<b class="'+(m>=1?'t-hi':'t-lo')+'">'+(m>=1?'▲':'▼')+' ×'+m.toFixed(2)+'</b>';   // 색만으로 구분하지 않도록 ▲/▼를 함께 쓴다
const heat=m=>'color-mix(in srgb,var('+(m>=1?'--hi':'--lo')+') '+(Math.min(Math.abs(Math.log(m))/Math.log(1.9),1)*20).toFixed(0)+'%,transparent)';   // 값 크기에 비례하는 약한 배경색
function makeSortable(t){   // th[data-k]를 누르면 tbody 행의 data-<k> 값으로 정렬한다(행 클릭 동작은 그대로)
  const tb=t.tBodies[0];
  t.querySelectorAll('th[data-k]').forEach(th=>{
    th.classList.add('srt');th.tabIndex=0;th.setAttribute('role','button');
    const go=()=>{const k=th.dataset.k,dir=th.dataset.dir?(th.dataset.dir==='desc'?'asc':'desc'):(th.dataset.first||'desc');
      t.querySelectorAll('th[data-k]').forEach(x=>{x.removeAttribute('data-dir');x.removeAttribute('aria-sort');});
      th.dataset.dir=dir;th.setAttribute('aria-sort',dir==='desc'?'descending':'ascending');
      [...tb.rows].sort((a,b)=>dir==='desc'?b.dataset[k]-a.dataset[k]:a.dataset[k]-b.dataset[k]).forEach(r=>tb.appendChild(r));};
    th.addEventListener('click',go);th.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();go();}});});
}
const DELTA=m=>{const pc=Math.round(Math.abs(m-1)*100);return pc===0?'평균 점포와 비슷함':(m>=1?'▲ 평균 점포보다 '+pc+'% 높음':'▼ 평균 점포보다 '+pc+'% 낮음');};
const TIP_MIN='__TIP_MIN__';
const TIP_RISK='같은 조건(영업연수·규모 등)을 맞춘 뒤 평균 점포와 비교한 폐업 위험의 배수예요. ×1.0이 평균, ×1.5면 평균보다 50% 높다는 뜻이에요. 연관일 뿐 원인은 아니에요.';
const NOTE_RATE='폐업률은 단순 비율이고, 상대 폐업 위험은 영업연수·규모 등을 통제한 뒤 평균 점포와 비교한 값이라 순위가 다를 수 있어요.';
const GI=new Map(); D.groups.forEach((g,i)=>GI.set(g.r*10+g.b,i));
const S={biz:-1,mode:'mult',sel:null,home:true,lastQ:null};
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
const nbLayer=L.layerGroup().addTo(map),nbLines={};
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
  nbLayer.clearLayers(); for(const k in nbLines)delete nbLines[k]; if(S.sel===null) return; const a=D.regions[S.sel];
  a.nb.forEach(j=>{const b=D.regions[j];nbLines[j]=L.polyline([[a.lat,a.lon],[b.lat,b.lon]],{color:dark?'#ddd':'#222',weight:1.3,dashArray:'4 4',opacity:.75,interactive:false}).addTo(nbLayer);});
  if(D.regions[S.sel]&&!map.getBounds().contains([a.lat,a.lon])) map.panTo([a.lat,a.lon]);
}
// 이웃 칩에 올리면(또는 포커스하면) 지도에서 그 이웃으로 가는 점선과 버블을 강조한다
function hlNb(j,on){
  const ln=nbLines[j];if(!ln)return;if(!on){update();return;}
  const acc=getComputedStyle(document.documentElement).getPropertyValue('--acc').trim()||'#12684f';
  ln.setStyle({color:acc,weight:4.5,opacity:1,dashArray:null});ln.bringToFront();markers[j].setStyle({color:acc,weight:4});markers[j].bringToFront();
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
  $('#maplegend').innerHTML='<div class="lg-t">'+(r?'실제 폐업률 (전국 평균 대비)':'상대 폐업 위험 (평균 점포 = ×1.0)')+'</div><div class="lg-bar"></div>'+
   '<div class="lg-ticks"><i style="left:0"></i><i style="left:50%"></i><i style="right:0"></i><span style="left:0">×0.53↓</span><span style="left:50%;transform:translateX(-50%)">×1.0</span><span style="right:0">×1.9↑</span></div><div class="lg-r lg-d" style="justify-content:space-between;margin-top:0"><span>◀ 안전</span><span>위험 ▶</span></div>'+
   '<div class="lg-r lg-d"><span class="dot" style="width:7px;height:7px"></span><span class="dot" style="width:13px;height:13px"></span> 점포 수가 많을수록 큰 원</div>'+
   '<div class="lg-r lg-d"><span class="dot dash"></span> 점선 회색 = 표본 30개 미만</div>';
}

// ---------- 패널 ----------
function whyChart(x,order){   // order: 요인 key 배열(두 지역을 같은 순서로 나란히 볼 때). 없으면 영향이 큰 순서
  const f=factors(x).sort(order?(a,b)=>order.indexOf(a.key)-order.indexOf(b.key):(a,b)=>Math.abs(Math.log(b.m))-Math.abs(Math.log(a.m))),mx=Math.log(1.6);   // 막대 길이는 로그 스케일, 가운데 = ×1.0(눈금 ×0.63~×1.6)
  const rows=f.map(d=>{const l=Math.log(d.m),flat=d.m>=0.97&&d.m<=1.03,up=l>=0,w=Math.min(Math.abs(l)/mx,1)*50;   // ±3% 이내는 회색
    const cls=flat?'flat':(up?'hi':'lo');
    return '<div class="fxrow'+(flat?' isflat':'')+'"><div class="nm hasq">'+d.label+qtip(d.tip)+'</div><div class="trk"><i class="fbar '+cls+(d.key==='age'?' soft':'')+'" style="'+(up?'left':'right')+':50%;width:'+w.toFixed(1)+'%"></i></div><div class="val '+(flat?'t-flat':(up?'t-hi':'t-lo'))+'">'+(flat?'':(up?'▲ ':'▼ '))+'×'+d.m.toFixed(2)+'</div></div>';}).join('');
  const ar='요인별 배수: '+f.map(d=>d.label+' ×'+d.m.toFixed(2)).join(', ');
  return '<div class="fx" role="group" aria-label="'+ar+'">'+rows+'<div class="fxrow fxaxis"><div></div><div class="ax"><span>◀ ×0.63</span><span>×1.0</span><span>×1.6 ▶</span></div><div></div></div></div>';
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
  const f=factors(v.x),g=v.g,a=g?g.age_yr:R.age_yr,fr=g?g.fr:R.fr;
  const ageF=f.find(d=>d.key==='age'), core=f.filter(d=>d.key!=='age');
  const up=core.filter(d=>d.m>=1.03).sort((x,y)=>y.m-x.m).slice(0,3), dn=core.filter(d=>d.m<=0.97).sort((x,y)=>x.m-y.m).slice(0,3);
  const pc=Math.round(Math.abs(v.mult-1)*100);
  const phrase=(d,isUp)=>{   // 요인별 한 문장(마침표로 끝난다). 배수 칩은 문장 뒤에 붙인다
    switch(d.key){
      case 'yrs': return (isUp?'영업 기간이 짧은 점포가 많아요':'오래 영업한 점포가 많아요')+'(평균 '+a.toFixed(1)+'년, 전국 '+NAT.age_yr.toFixed(1)+'년).';
      case 'fr': return '프랜차이즈 비중이 '+(isUp?'낮아요':'높아요')+'('+pct(fr)+', 전국 '+pct(NAT.fr)+').';
      case 'site': return '점포 규모·다중이용 등 점포 특성이 '+(isUp?'위험한':'안정적인')+' 쪽이에요.';
      case 'hist': return g?'이 시군구('+pct(g.reg_hist)+')와 이웃 지역('+pct(g.nb_hist)+')의 직전 1년 폐업률이 '+(isUp?'높아요.':'낮아요.'):'이 지역과 이웃 지역의 직전 1년 폐업률이 '+(isUp?'높아요.':'낮아요.');
      case 'gen': return '고객 성별 구성이 '+(isUp?'위험한':'안정적인')+' 쪽이에요.';
      case 'biz': return '업종 자체의 기본 위험이 평균보다 '+(isUp?'높아요.':'낮아요.');
      default: return '입지 등 기타 요인이 '+(isUp?'위험한':'안정적인')+' 쪽이에요.';
    }};
  const chip=(d,isUp)=>' <span class="tag '+(isUp?'hi':'lo')+'">'+(isUp?'▲':'▼')+' ×'+d.m.toFixed(2)+'</span>';
  const li=(k,body)=>'<li><b class="k">'+k+'</b>'+body+'</li>', sub=a=>'<ul class="subl">'+a.map(x=>'<li>'+x+'</li>').join('')+'</ul>';
  let t='<ul class="exp">'+li('요약','<b>'+nm+'</b>는 평균 점포보다 폐업 위험이 '+(pc===0?'비슷한 수준':'약 <b>'+pc+'% '+(v.mult>=1?'높은':'낮은')+'</b> 수준')+'으로 추정돼요. 실제 폐업률은 '+pct(v.rate)+'(전국 '+pct(NAT.rate)+', 점포 '+v.n.toLocaleString()+'개)예요.');
  t+=li('위험을 높이는 요인',up.length?sub(up.map(d=>phrase(d,true)+chip(d,true))):'<span class="hint">뚜렷하게 위험을 높이는 요인은 없어요(±3% 이내).</span>');
  if(dn.length) t+=li('위험을 낮추는 요인',sub(dn.map(d=>phrase(d,false)+chip(d,false))));
  const ref=[];
  const nbm=R.nb.map(j=>val(j,b)).filter(Boolean).map(z=>z.mult);
  if(nbm.length) ref.push('가까운 이웃 '+nbm.length+'곳의 평균 상대 폐업 위험은 ×'+(nbm.reduce((x,y)=>x+y,0)/nbm.length).toFixed(2)+'예요.');
  if(ageF&&Math.abs(Math.log(ageF.m))>=0.03) ref.push('고객 연령대(×'+ageF.m.toFixed(2)+')는 '+(ageF.m>=1?'위험이 높은':'위험이 낮은')+' 지역 유형과 닮았다는 신호일 뿐이라 위 요인에서 뺐어요.');
  ref.push('평균 점포와의 통계적 연관이며 원인이나 정책 효과는 아니에요.'+(v.n<30?' 이 조합은 점포가 30개 미만이라 실제 폐업률이 불안정해요.':''));
  return t+li('참고',sub(ref))+'</ul>';
}
function renderPanel(){
  const p=$('#panel'); if(S.sel===null) return; const r=S.sel,R=D.regions[r],b=S.biz,v=val(r,b);
  const nm=R.sido+' '+R.name;
  S.home=false;
  let h='<div class="phead"><div><h3>'+nm+'</h3><div class="sub2">'+(b>=0?BIZ[b]:'전체 7개 업종')+' · 점포 '+(v?v.n.toLocaleString():0)+'개</div></div><div class="acts"><button class="chip-b only-m" data-act="tomap">↑ 지도 보기</button><button class="chip-b" data-act="copy" title="지금 화면의 주소를 복사해요">링크 복사</button><button class="chip-b" data-act="csv" title="이 지역의 업종별 값을 CSV로 저장해요">CSV 저장</button><button class="chip-b" data-act="clear">✕ 선택 해제</button></div></div>';
  if(!v){$('#panel').innerHTML=h+'<p class="hint">이 시군구에는 해당 업종 점포가 없습니다.</p>'+bizRows(r);bindPanel(p);return;}
  const up=v.mult>=1;
  h+='<div class="sub2 hasq" style="margin-top:6px">상대 폐업 위험'+qtip(TIP_RISK)+'</div><div class="big"><b class="'+(up?'t-hi':'t-lo')+'">×'+v.mult.toFixed(2)+'</b><span class="delta '+(up?'t-hi':'t-lo')+'">'+DELTA(v.mult)+'</span></div>';
  h+='<div class="sub2">실제 폐업률 '+pct(v.rate)+' <span class="hint">(전국 '+pct(NAT.rate)+')</span></div>';
  if(b>=0&&v.n<30) h+='<div class="warn">점포가 30개 미만이라 실제 폐업률은 우연 변동이 큽니다. 상대 폐업 위험은 모형 기반이라 상대적으로 안정적입니다.</div>';
  h+='<div class="blk"><h4>왜 그런가 — 요인별 배수 (▲ 붉음: 위험 높임 · ▼ 푸름: 위험 낮춤 · 회색: ±3% 이내)</h4>'+whyChart(v.x)+'<p class="hint" style="margin:2px 0 0">옅은 막대는 참고용 신호예요(? 를 누르면 이유가 나와요). 막대 길이는 로그 눈금이에요.</p></div>';
  h+='<div class="blk why"><h4>해설</h4>'+explain(r,b)+'</div>';
  if(v.g){const g=v.g;
    h+='<div class="blk"><h4>BC카드 소비 구성 (2026-01~06, 맥락 정보)</h4><div class="two"><div>'+barsMini(g.age,AGE,x=>pct(x,0))+'<p class="hint" style="margin:2px 0 6px">연령 코드별 소비액 비중</p>'+barsMini(g.gen,GEN,x=>pct(x,0))+'</div><div>'+spark(g.amt)+'</div></div></div>';
    h+='<div class="blk"><h4>상권 프로필</h4><div class="kp"><div><b>'+g.age_yr.toFixed(1)+'년</b><span>평균 영업연수 (전국 '+NAT.age_yr.toFixed(1)+')</span></div><div><b>'+pct(g.fr)+'</b><span>프랜차이즈 (전국 '+pct(NAT.fr)+')</span></div><div><b>'+pct(g.reg_hist)+' / '+pct(g.nb_hist)+'</b><span>2026-01-01 기준 직전 1년 폐업률 (이 시군구 / 이웃)</span></div><div><b>'+g.n.toLocaleString()+'개</b><span>같은 업종 경쟁 점포</span></div></div></div>';
  } else h+=bizRows(r);
  h+='<div class="blk"><h4>모형이 참고하는 가까운 이웃 5곳 (누르면 이동 · 올리면 지도의 점선 강조)</h4><div class="nb">'+R.nb.map(j=>{const z=val(j,b);return '<button data-r="'+j+'" title="누르면 이 지역으로 이동해요">'+D.regions[j].name+(z?' '+MX(z.mult):'')+'</button>';}).join('')+'</div></div>';
  p.innerHTML=h; p.querySelectorAll('.nb button').forEach(x=>{const j=+x.dataset.r;x.addEventListener('click',()=>select(j,true));
    ['mouseenter','focus'].forEach(ev=>x.addEventListener(ev,()=>hlNb(j,true)));['mouseleave','blur'].forEach(ev=>x.addEventListener(ev,()=>hlNb(j,false)));});
  bindPanel(p);
}
function bindPanel(p){
  p.querySelectorAll('table.sortable').forEach(makeSortable);
  p.querySelectorAll('tr[data-b]').forEach(x=>x.addEventListener('click',()=>{setBiz(+x.dataset.b);}));
  p.querySelectorAll('[data-act="clear"]').forEach(x=>x.addEventListener('click',clearSel));
  p.querySelectorAll('[data-act="copy"]').forEach(x=>x.addEventListener('click',copyLink));
  p.querySelectorAll('[data-act="csv"]').forEach(x=>x.addEventListener('click',()=>downloadCsv(S.sel)));
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
  S.home=true;S.lastQ=null;const b=S.biz,nm=b>=0?BIZ[b]:'전체 업종';
  $('#panel').innerHTML='<h3>어디부터 볼까요?</h3><p class="hint" style="margin:2px 0 4px">지도의 버블을 누르거나 검색창에 지역·업종을 입력해 보세요. 아래 지역을 누르면 바로 그 지역으로 이동해요.</p>'+
   '<div class="blk"><h4>▲ 폐업 위험이 높은 곳 TOP 5 · '+nm+'</h4><div class="rklist">'+topRows(b,'hi',5).map((x,i)=>rkCard(x,b,i)).join('')+'</div></div>'+
   '<div class="blk"><h4>▼ 폐업 위험이 낮은(안전한) 곳 TOP 5 · '+nm+'</h4><div class="rklist">'+topRows(b,'lo',5).map((x,i)=>rkCard(x,b,i)).join('')+'</div></div>'+
   '<p class="hint" style="margin:12px 0 0">점포가 '+(b>=0?300:2000)+'개 이상인 곳만 순위에 넣었어요'+'<span class="hasq">'+qtip(TIP_MIN)+'</span>. 상대 폐업 위험은 평균 점포를 ×1.0으로 놓고 비교한 값이에요.</p>';
  bindGo($('#panel'));syncUrl();
}
function bindGo(root){root.querySelectorAll('[data-r]').forEach(x=>x.addEventListener('click',()=>{if(x.dataset.b!==undefined)setBizQuiet(+x.dataset.b);select(+x.dataset.r,true);}));
  root.querySelectorAll('[data-q]').forEach(x=>x.addEventListener('click',()=>{$('#ask').value=x.dataset.q;ask();}));}
function bizRows(r){
  let s='<div class="blk"><h4>업종별 (행을 누르면 그 업종으로 전환 · 제목을 누르면 정렬)</h4><p class="hint" style="margin:0 0 6px">'+NOTE_RATE+'</p><div class="scroll"><table class="tbl sortable"><thead><tr><th data-k="b" data-first="asc">업종</th><th class="num" data-k="n">점포</th><th class="num" data-k="rate">폐업률</th><th class="num" data-k="mult">상대 폐업 위험</th></tr></thead><tbody>';
  BIZ.forEach((nm,b)=>{const v=val(r,b);if(!v)return;s+='<tr data-b="'+b+'" data-n="'+v.n+'" data-rate="'+v.rate+'" data-mult="'+v.mult+'" class="clk'+(b===S.biz?' cur':'')+'"><td>'+nm+'</td><td class="num">'+v.n.toLocaleString()+'</td><td class="num">'+pct(v.rate)+'</td><td class="num" style="background:'+heat(v.mult)+'">'+MX(v.mult)+'</td></tr>';});
  return s+'</tbody></table></div></div>';
}
const isMobile=()=>window.matchMedia('(max-width:767px)').matches;
function select(i,fly){S.sel=i;S.lastQ=null;update();renderPanel();firePulse();syncUrl();if(fly)goRegion(i);if(isMobile())$('#panel').scrollIntoView({behavior:'smooth',block:'start'});}
function clearSel(){S.sel=null;S.lastQ=null;update();renderHome();goNational();}
function setBiz(b){S.biz=b;document.querySelectorAll('#bizbar .chip-b').forEach(x=>x.classList.toggle('on',+x.dataset.b===b));update();if(S.sel===null&&S.home)renderHome();else renderPanel();syncUrl();}
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
function say(html){S.home=false;$('#panel').innerHTML=html;bindGo($('#panel'));syncUrl();}
function toast(m){const el=$('#toast');el.textContent=m;el.classList.add('on');clearTimeout(toast.t);toast.t=setTimeout(()=>el.classList.remove('on'),2200);}
async function copyLink(){
  const u=location.href;
  try{await navigator.clipboard.writeText(u);}
  catch(e){const ta=document.createElement('textarea');ta.value=u;ta.style.cssText='position:fixed;opacity:0';document.body.appendChild(ta);ta.select();try{document.execCommand('copy');}catch(e2){}ta.remove();}
  toast('링크를 복사했어요');
}
function downloadCsv(r){   // 선택한 시군구의 업종별 값(화면 데이터 그대로)을 CSV로 저장. 엑셀에서 한글이 깨지지 않게 BOM을 붙인다
  if(r===null||r===undefined)return;const R=D.regions[r],nm=R.sido+' '+R.name;
  const rows=[['시군구','업종','점포 수','실제 폐업률(%)','상대 폐업 위험'].concat(SHOW.map(s=>s.label+'(배수)'))];
  [-1].concat(BIZ.map((n,i)=>i)).forEach(b=>{const v=val(r,b);if(!v)return;rows.push([nm,b<0?'전체 업종':BIZ[b],v.n,(v.rate*100).toFixed(2),v.mult].concat(factors(v.x).map(d=>d.m.toFixed(3))));});
  const csv='\ufeff'+rows.map(x=>x.map(c=>'"'+String(c).replace(/"/g,'""')+'"').join(',')).join('\r\n');
  const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}));a.download='상권생존지도_'+nm.replace(/\s+/g,'_')+'.csv';document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(a.href),1000);
  toast('CSV를 저장했어요');
}
const fullName=i=>D.regions[i].sido+' '+D.regions[i].name;
function syncUrl(){   // 현재 지역·업종을 URL에 저장한다(?region=서울특별시 마포구&industry=서양음식, 비교는 &compare=서울특별시 강남구) — 복사한 링크로 같은 화면이 열린다
  try{const P=new URLSearchParams(location.search);
    P.delete('compare');   // 지도 상태가 바뀌면 두 지역 비교 링크 상태는 끝난 것
    if(S.sel!==null){P.set('region',fullName(S.sel));P.delete('q');}else{P.delete('region');if(S.lastQ)P.set('q',S.lastQ);else P.delete('q');}
    if(S.biz>=0)P.set('industry',BIZ[S.biz]);else P.delete('industry');
    const qs=P.toString();history.replaceState(null,'',location.pathname+(qs?'?'+qs:'')+location.hash);}catch(e){}
}
const EX=['동탄 서양음식','합천 한식','마포구 제과점','강남구','한식 위험한 곳','서울 제과점 안전한 곳'];
const HELP='<div class="blk" style="border:0;margin-top:8px;padding-top:0"><h4 style="color:var(--fg);font-size:16px">이렇게 검색해 보세요</h4><div class="nb">'+EX.map(q=>'<button type="button" data-q="'+q+'">'+q+'</button>').join('')+'</div>'+
 '<p class="hint" style="margin:8px 0 0">지역은 시군구 이름의 일부만 써도 돼요(동탄, 합천). 업종은 한식·일식·중식·서양(양식)·스낵(분식)·제과점(빵)·편의점 중에서 고를 수 있어요.</p></div>';
function ask(keepBiz){   // keepBiz: 딥링크 복원 때 URL의 업종을 유지
  const q=$('#ask').value.replace(/\s+/g,' ').trim(); if(!q) return; S.lastQ=q;
  const esc=q.replace(/</g,'&lt;');
  if(UNSUP.some(k=>q.includes(k))){say('<p>“'+esc+'”는 아직 다루지 않는 업종이에요. 이 사이트는 한식·일식·중식·서양음식·스낵·제과점·편의점 7개 업종만 볼 수 있어요.</p>'+HELP);return;}
  let b=keepBiz===true?S.biz:-1;for(const k in BIZKEY){if(q.includes(k)){b=BIZKEY[k];break;}}
  const intent=/(위험한|위험 ?높|폐업 ?많|많이 ?망|취약)/.test(q)?'hi':(/(안전|위험 ?낮|덜 ?망|안정)/.test(q)?'lo':null);
  const toks=q.split(/[ ,?]+/).filter(t=>t.length>=2&&!Object.keys(BIZKEY).some(k=>t.includes(k))&&!/(왜|위험|해줘|알려|어때|설명|곳|안전|폐업|많이|제일|가장)/.test(t));
  if(intent){ // 순위 질문: 업종(선택) + 시도(선택)
    let sido=null;for(const t of toks){const x=sidoOf(t);if(x){sido=x;break;}}
    const rows=topRows(b,intent,8,sido);
    if(!rows.length){say('<p>조건에 맞는 지역이 없어요. 점포 수가 충분한 곳만 순위에 넣고 있어요.</p>'+HELP);return;}
    setBizQuiet(b);S.sel=null;update();sido?goRegions(D.regions.map((R,i)=>i).filter(i=>D.regions[i].sido===sido)):goNational();
    say('<h3>'+(sido?sido.replace(/특별시|광역시|특별자치도|특별자치시/,'')+' ':'전국 ')+(b>=0?BIZ[b]:'전체 업종')+' — 위험이 '+(intent==='hi'?'높은':'낮은')+' 곳 상위 '+rows.length+'</h3><p class="hint">점포 '+(b>=0?300:2000)+'개 이상인 곳만 순위에 넣었습니다. 누르면 설명이 열립니다.</p><div class="nb" style="flex-direction:column;align-items:stretch">'+
      rows.map(x=>'<button data-r="'+x.r+'" data-b="'+b+'" style="text-align:left">'+rname(x.r)+' · '+MX(x.m)+' · 폐업률 '+pct(x.rate)+' · 점포 '+x.n.toLocaleString()+'</button>').join('')+'</div>');
    return;
  }
  let cand=[],exact=-1;   // 자동완성·URL의 “시도 시군구” 전체 이름은 그대로 인식한다
  D.regions.forEach((r,i)=>{const f=r.sido+' '+r.name;if(q.includes(f)&&(exact<0||f.length>(D.regions[exact].sido+' '+D.regions[exact].name).length))exact=i;});
  if(exact>=0)cand=[exact];
  else for(const t of toks){const t2=t.replace(/(시|군|구)$/,'');
    cand=D.regions.map((r,i)=>i).filter(i=>{const full=D.regions[i].sido+' '+D.regions[i].name;return full.includes(t)||(t2.length>=2&&full.includes(t2));});
    if(cand.length) break;}
  if(!cand.length){if(b>=0){setBizQuiet(b);update();say('<p>“'+esc+'”에서 업종(<b>'+BIZ[b]+'</b>)은 읽었지만 지역을 찾지 못했어요. 지역 이름도 함께 입력해 주세요.</p>'+HELP);}else say('<p>“'+esc+'”에서 지역을 찾지 못했어요.</p>'+HELP);return;}
  setBizQuiet(b);
  if(cand.length>1){S.sel=null;update();goRegions(cand);say('<p>여러 시군구가 맞아요. 하나를 선택해 주세요.</p><div class="nb">'+cand.slice(0,14).map(i=>'<button data-r="'+i+'">'+D.regions[i].sido+' '+D.regions[i].name+'</button>').join('')+'</div>');return;}
  select(cand[0],true);
}
// ---------- 검색창 자동완성 (시군구·업종 목록 기반, ↑↓/Enter/Esc) ----------
const BIZALIAS=[['한식',0],['일식',1],['회집',1],['중식',2],['중국',2],['서양',3],['양식',3],['스낵',4],['스넥',4],['분식',4],['제과',5],['빵',5],['편의점',6]];
let sugItems=[],sugI=-1;
function suggest(v){
  const m=v.match(/^(.*?)(\S*)$/),pre=m[1],tok=m[2]; if(!tok) return [];
  const bs=new Set();BIZ.forEach((n,i)=>{if(n.includes(tok))bs.add(i);});BIZALIAS.forEach(a=>{if(a[0].startsWith(tok)||tok.startsWith(a[0])&&tok.length<=a[0].length)bs.add(a[1]);});
  const out=[...bs].slice(0,3).map(i=>({t:'업종',label:BIZ[i],b:i,pre}));
  const rs=[];D.regions.forEach((r,i)=>{const full=r.sido+' '+r.name;if(!full.includes(tok))return;rs.push({t:'시군구',label:full,i,pre,k:r.name.startsWith(tok)?0:r.name.includes(tok)?1:2,n:r.n});});
  rs.sort((x,y)=>x.k-y.k||y.n-x.n);
  return out.concat(rs.slice(0,7));
}
function sugRender(){
  const ul=$('#sug');ul.hidden=!sugItems.length;$('#ask').setAttribute('aria-expanded',String(!!sugItems.length));
  ul.innerHTML=sugItems.map((x,i)=>'<li role="option" id="sug-'+i+'" data-i="'+i+'" aria-selected="'+(i===sugI)+'"><span>'+x.label+'</span><span class="tp">'+x.t+'</span></li>').join('');
  if(sugI>=0)$('#ask').setAttribute('aria-activedescendant','sug-'+sugI);else $('#ask').removeAttribute('aria-activedescendant');
  ul.querySelectorAll('li').forEach(li=>li.addEventListener('mousedown',e=>{e.preventDefault();sugPick(+li.dataset.i);}));
}
function sugHide(){sugItems=[];sugI=-1;sugRender();}
function sugPick(i){
  const x=sugItems[i];if(!x)return;sugHide();
  if(x.t==='시군구'){$('#ask').value=x.pre+x.label;ask();}
  else if(x.pre.trim()){$('#ask').value=x.pre+x.label;ask();}
  else{$('#ask').value=x.label+' ';setBizQuiet(x.b);update();if(S.sel===null&&S.home)renderHome();syncUrl();$('#ask').focus();}
}
$('#ask').addEventListener('input',()=>{sugItems=suggest($('#ask').value);sugI=-1;sugRender();});
$('#ask').addEventListener('keydown',e=>{
  if(e.key==='ArrowDown'||e.key==='ArrowUp'){if(!sugItems.length){sugItems=suggest($('#ask').value);}if(!sugItems.length)return;e.preventDefault();sugI=(sugI+(e.key==='ArrowDown'?1:-1)+sugItems.length)%sugItems.length;sugRender();}
  else if(e.key==='Enter'){if(sugI>=0){e.preventDefault();sugPick(sugI);}else{sugHide();ask();}}
  else if(e.key==='Escape'){sugHide();}});
$('#ask').addEventListener('blur',()=>setTimeout(sugHide,120));
function setBizQuiet(b){S.biz=b;document.querySelectorAll('#bizbar .chip-b').forEach(x=>x.classList.toggle('on',+x.dataset.b===b));}
$('#askbtn').addEventListener('click',()=>ask());
document.querySelectorAll('#askhelp [data-q]').forEach(x=>x.addEventListener('click',()=>{$('#ask').value=x.dataset.q;ask();}));

// ---------- 상권 분석 ----------
const RL=$('#rlist');D.regions.forEach((r,i)=>{const o=document.createElement('option');o.value=r.sido+' '+r.name;RL.appendChild(o);});
function areaShow(){
  const q=$('#areaq').value.trim();const i=D.regions.findIndex(r=>(r.sido+' '+r.name)===q)>=0?D.regions.findIndex(r=>(r.sido+' '+r.name)===q):D.regions.findIndex(r=>r.name.includes(q)&&q.length>=2);
  if(i<0){$('#areaout').innerHTML='<p class="hint">일치하는 시군구가 없습니다.</p>';return;}
  const R=D.regions[i];let s='<h3 style="margin:0">'+R.sido+' '+R.name+'</h3><div class="kp"><div><b>'+R.n.toLocaleString()+'개</b><span>점포(7개 업종)</span></div><div><b>'+pct(R.rate)+'</b><span>180일 폐업률 (전국 '+pct(NAT.rate)+')</span></div><div>'+MX(R.mult)+'<span>상대 폐업 위험(지역 평균)</span></div><div><b>'+R.age_yr.toFixed(1)+'년</b><span>평균 영업연수 (전국 '+NAT.age_yr.toFixed(1)+')</span></div><div><b>'+pct(R.fr)+'</b><span>프랜차이즈 (전국 '+pct(NAT.fr)+')</span></div></div>';
  s+='<p class="hint" style="margin:0 0 6px">'+NOTE_RATE+'</p><div class="scroll"><table class="tbl sortable"><thead><tr><th data-k="b" data-first="asc">업종</th><th class="num" data-k="n">점포</th><th data-k="rate">실제 폐업률</th><th data-k="mult">상대 폐업 위험</th><th class="num" data-k="age">평균 영업연수</th><th class="num" data-k="fr">프랜차이즈</th><th class="num" data-k="amt">BC 월평균 소비(백만원)</th><th class="num" data-k="unit">점포당(백만원)</th></tr></thead><tbody>';
  BIZ.forEach((nm,b)=>{const g=GI.has(i*10+b)?D.groups[GI.get(i*10+b)]:null;if(!g)return;const am=g.amt.filter(v=>v!==null),mean=am.length?am.reduce((a,c)=>a+c,0)/am.length:null;
    s+='<tr data-b="'+b+'" data-n="'+g.n+'" data-rate="'+g.rate+'" data-mult="'+g.mult+'" data-age="'+g.age_yr+'" data-fr="'+g.fr+'" data-amt="'+(mean===null?-1:mean)+'" data-unit="'+(mean===null?-1:mean/g.n)+'"><td>'+nm+'</td><td class="num">'+g.n.toLocaleString()+'</td><td class="b1"><span class="mb" style="width:'+Math.min(g.rate/0.09*90,100).toFixed(0)+'px;background:var(--ref)"></span>'+pct(g.rate)+'</td><td class="b1"><span class="mb" style="width:'+Math.min(g.mult/2*90,100).toFixed(0)+'px;background:'+(g.mult>=1?'var(--hi)':'var(--lo)')+'"></span>×'+g.mult.toFixed(2)+'</td><td class="num">'+g.age_yr.toFixed(1)+'</td><td class="num">'+pct(g.fr)+'</td><td class="num">'+(mean===null?'-':Math.round(mean).toLocaleString())+'</td><td class="num">'+(mean===null?'-':(mean/g.n).toFixed(2))+'</td></tr>';});
  s+='</tbody></table></div><p class="cap">BC 소비는 시군구×업종 집계이며 점포당 값은 (월평균 소비 ÷ 2026-01-01 영업 점포 수)입니다. <a href="#" id="tomap" style="color:var(--acc)">지도에서 보기 →</a></p>';
  $('#areaout').innerHTML=s;document.querySelectorAll('#areaout table.sortable').forEach(makeSortable);$('#tomap').addEventListener('click',ev=>{ev.preventDefault();tab('map');setTimeout(()=>select(i,true),90);});
}
$('#areaq').addEventListener('change',areaShow);$('#areaq').addEventListener('input',()=>{if(D.regions.some(r=>(r.sido+' '+r.name)===$('#areaq').value.trim()))areaShow();});
const RB=$('#rankbiz');RB.innerHTML=BIZ.map((n,i)=>'<option value="'+i+'">'+n+'</option>').join('');
function rank(){
  const b=+RB.value,gs=D.groups.filter(g=>g.b===b&&g.n>=300).sort((a,c)=>c.mult-a.mult);
  const row=g=>{const R=D.regions[g.r],f=factors(g.x).filter(d=>d.key!=='age').sort((a,c)=>Math.abs(Math.log(c.m))-Math.abs(Math.log(a.m)))[0];
    return '<tr><td>'+R.sido.replace(/특별시|광역시|특별자치도|특별자치시/,'')+' '+R.name+'</td><td class="num">'+MX(g.mult)+'</td><td class="num">'+pct(g.rate)+'</td><td class="num">'+g.n.toLocaleString()+'</td><td>'+f.label+' ×'+f.m.toFixed(2)+'</td></tr>';};
  const head='<table class="tbl"><thead><tr><th>지역</th><th class="num">상대 폐업 위험</th><th class="num">폐업률</th><th class="num">점포</th><th>가장 큰 요인</th></tr></thead><tbody>';
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
  let s='<svg viewBox="0 0 '+Wd+' '+Ht+'" class="chart scat" role="img" aria-label="산점도: 가로는 업종 안에서의 점포당 BC 소비 순위(백분위), 세로는 실제 폐업률(180일, %). 소비 순위가 높다고 폐업률이 낮아지지 않는 경향이며, 굵은 선은 소비 10분위별 실제 폐업률이에요."><line x1="'+L+'" x2="'+(Wd-Rr)+'" y1="'+Y(NAT.rate)+'" y2="'+Y(NAT.rate)+'" class="axis"/><text x="'+(L+4)+'" y="'+(Y(NAT.rate)-5)+'">전국 평균 '+pct(NAT.rate)+'</text>';
  [0,0.03,0.06,0.09,0.12].forEach(v=>{s+='<text x="'+(L-6)+'" y="'+(Y(v)+4)+'" text-anchor="end">'+pct(v,0)+'</text>';});
  [0,0.25,0.5,0.75,1].forEach(v=>{s+='<text x="'+X(v)+'" y="'+(Ht-16)+'" text-anchor="middle">'+Math.round(v*100)+'</text>';});
  s+='<text transform="rotate(-90)" x="'+(-(T+(Ht-B-T)/2))+'" y="12" text-anchor="middle">실제 폐업률 (180일, %)</text>';
  gs.forEach(g=>{s+='<circle cx="'+X(pctl[GI.get(g.r*10+g.b)]).toFixed(1)+'" cy="'+Y(g.rate).toFixed(1)+'" r="3" fill="'+colors[g.b]+'"><title>'+rname(g.r)+' '+BIZ[g.b]+' · 점포 '+g.n.toLocaleString()+'개 · 폐업률 '+pct(g.rate)+'</title></circle>';});
  const bins=[];for(let k=0;k<10;k++){const m=gs.filter(g=>{const q=pctl[GI.get(g.r*10+g.b)];return q>k/10&&q<=(k+1)/10;});if(m.length){const n=m.reduce((a,c)=>a+c.n,0);bins.push([X((k+.5)/10),Y(m.reduce((a,c)=>a+c.ev,0)/n)]);}}
  s+='<polyline fill="none" stroke="var(--fg)" stroke-width="2.4" points="'+bins.map(p=>p[0].toFixed(1)+','+p[1].toFixed(1)).join(' ')+'"/>';
  s+='<text x="'+(L+(Wd-L-Rr)/2)+'" y="'+(Ht-2)+'" text-anchor="middle">업종 안에서의 점포당 BC 소비 순위 (백분위, 오른쪽일수록 소비가 많음) →</text></svg><div class="legend2">'+BIZ.map((n,i)=>'<span><span style="display:inline-block;width:9px;height:9px;border-radius:50%;background:'+colors[i]+';margin-right:4px"></span>'+n+'</span>').join('')+'<span><b style="border-top:2.4px solid var(--fg);display:inline-block;width:18px;vertical-align:middle"></b> 10분위별 실제 폐업률(점포 수 가중)</span></div>';
  $('#scat').innerHTML=s;
})();

(function(){ // 시군구 위험·안전 Top 10 (전체 업종, 점포 2,000개 이상 — 지도 첫 화면 카드와 같은 기준)
  const head='<table class="tbl"><thead><tr><th>#</th><th>시군구</th><th class="num">상대 폐업 위험</th><th class="num">폐업률</th><th class="num">점포</th></tr></thead><tbody>';
  const row=(x,i)=>'<tr class="clk" data-r="'+x.r+'"><td>'+(i+1)+'</td><td>'+rname(x.r)+'</td><td class="num">'+MX(x.m)+'</td><td class="num">'+pct(x.rate)+'</td><td class="num">'+x.n.toLocaleString()+'</td></tr>';
  $('#rg-hi').innerHTML='<h4 style="margin:0 0 6px">▲ 위험 상위 10</h4>'+head+topRows(-1,'hi',10).map(row).join('')+'</tbody></table>';
  $('#rg-lo').innerHTML='<h4 style="margin:0 0 6px">▼ 안전 상위 10</h4>'+head+topRows(-1,'lo',10).map(row).join('')+'</tbody></table>';
  document.querySelectorAll('#rg-hi tr[data-r],#rg-lo tr[data-r]').forEach(tr=>tr.addEventListener('click',()=>{const i=+tr.dataset.r;setBizQuiet(-1);tab('map');setTimeout(()=>select(i,true),90);}));
})();

let cmpRestore=null;
(function(){ // 두 지역 비교: 같은 업종 기준으로 요인 막대를 같은 순서로 나란히 놓는다
  $('#cmpBiz').innerHTML='<option value="-1">전체 업종</option>'+BIZ.map((n,i)=>'<option value="'+i+'">'+n+'</option>').join('');
  const find=t=>{t=t.trim();if(!t)return -1;let i=D.regions.findIndex(r=>(r.sido+' '+r.name)===t);if(i>=0)return i;
    const c=D.regions.map((r,k)=>k).filter(k=>t.length>=2&&(D.regions[k].sido+' '+D.regions[k].name).includes(t));return c.length===1?c[0]:-1;};
  const card=(i,v,order)=>'<div><h4>'+rname(i)+'</h4><div class="big"><b class="'+(v.mult>=1?'t-hi':'t-lo')+'">×'+v.mult.toFixed(2)+'</b><span class="delta '+(v.mult>=1?'t-hi':'t-lo')+'">'+DELTA(v.mult)+'</span></div><div class="sub2" style="color:var(--sub)">실제 폐업률 '+pct(v.rate)+' · 점포 '+v.n.toLocaleString()+'개</div><div class="blk">'+whyChart(v.x,order)+'</div><button type="button" class="chip-b" data-go="'+i+'">지도에서 보기</button></div>';
  function show(){
    const a=find($('#cmpA').value),b=find($('#cmpB').value),bz=+$('#cmpBiz').value,out=$('#cmpOut');
    if(a<0||b<0){cmpUrl('','',bz);out.innerHTML='<p class="hint">'+((!$('#cmpA').value.trim()&&!$('#cmpB').value.trim())?'두 지역을 고르면 상대 폐업 위험과 요인 막대를 나란히 보여 줘요.':'지역 이름을 목록에서 골라 주세요. 이름이 여러 곳과 겹치면 “서울특별시 마포구”처럼 시도까지 써 주세요.')+'</p>';return;}
    const va=val(a,bz),vb=val(b,bz);
    if(!va||!vb){out.innerHTML='<p class="hint">선택한 업종의 점포가 없는 지역이 있어 비교할 수 없어요. 업종을 바꿔 보세요.</p>';return;}
    const fa=factors(va.x),fb=factors(vb.x),lg=m=>Math.log(m);
    const order=fa.map(d=>d.key).sort((k1,k2)=>{const g=k=>Math.max(Math.abs(lg(fa.find(d=>d.key===k).m)),Math.abs(lg(fb.find(d=>d.key===k).m)));return g(k2)-g(k1);});
    const dk=fa.filter(d=>d.key!=='age').map(d=>({d,e:fb.find(z=>z.key===d.key),gap:Math.abs(lg(d.m)-lg(fb.find(z=>z.key===d.key).m))})).sort((x,y)=>y.gap-x.gap)[0];
    out.innerHTML='<div class="cmp">'+card(a,va,order)+card(b,vb,order)+'</div><p class="cmpdiff">두 지역의 가장 큰 차이는 <b>'+dk.d.label+'</b>이에요 ('+rname(a)+' ×'+dk.d.m.toFixed(2)+' · '+rname(b)+' ×'+dk.e.m.toFixed(2)+'). 요인 배수를 모두 곱하면 각 지역의 상대 폐업 위험이 돼요.</p>'+
      '<p class="cap"><button type="button" class="chip-b" data-act="copy">링크 복사</button> 같은 업종 기준('+(bz>=0?BIZ[bz]:'전체 업종')+')이며 통계적 연관이지 원인은 아니에요. 옅은 막대(BC카드 고객 연령대)는 참고용이라 차이 비교에서 뺐어요.</p>';
    out.querySelectorAll('[data-go]').forEach(x=>x.addEventListener('click',()=>{const i=+x.dataset.go;setBizQuiet(bz);tab('map');setTimeout(()=>select(i,true),90);}));
    out.querySelectorAll('[data-act="copy"]').forEach(x=>x.addEventListener('click',copyLink));
    cmpUrl(fullName(a),fullName(b),bz);
  }
  function cmpUrl(a,b,bz){try{const P=new URLSearchParams(location.search);P.delete('q');if(a&&b){P.set('region',a);P.set('compare',b);}else{P.delete('compare');}if(bz>=0)P.set('industry',BIZ[bz]);else P.delete('industry');const qs=P.toString();history.replaceState(null,'',location.pathname+(qs?'?'+qs:'')+location.hash);}catch(e){}}
  cmpRestore=(a,b,bz)=>{$('#cmpA').value=a;$('#cmpB').value=b;$('#cmpBiz').value=String(bz);show();};
  ['cmpA','cmpB'].forEach(id=>{$('#'+id).addEventListener('change',show);$('#'+id).addEventListener('input',()=>{if(find($('#'+id).value)>=0)show();});});
  $('#cmpBiz').addEventListener('change',show);
})();

(function(){ // 생존 분석 탭 상단 목차: 지금 보는 섹션 칩을 강조
  const chips=[...document.querySelectorAll('.toc a')],hs=chips.map(a=>document.getElementById(a.dataset.jump));
  function upd(){if(!$('#t-surv').classList.contains('on'))return;let cur=-1;hs.forEach((h,i)=>{if(h&&h.getBoundingClientRect().top<210)cur=i;});chips.forEach((a,i)=>a.classList.toggle('on',i===cur));}
  window.addEventListener('scroll',upd,{passive:true});
})();

// 생존 분석(모형 근거) 탭 ↔ 지도 연결: 지금 선택한 지역·업종에서 가장 크게 작용한 요인과 그 근거 차트
const SURVMAP={   // 요인 → 근거 차트 카드 id, 강조할 행 라벨, 차트 이름 (모두 표시용 연결표)
  yrs:{c:'chart-c',rows:['영업연수'],name:'점포 단위 판별력 차트'},
  fr:{c:'chart-c',rows:['프랜차이즈'],name:'점포 단위 판별력 차트'},
  site:{c:'chart-c',rows:['점포 규모·운영 특성'],name:'점포 단위 판별력 차트'},
  hist:{c:'chart-s',rows:['지역 폐업 흐름'],name:'지역 간 순위 차트'},
  gen:{c:'chart-w',rows:['BC카드 고객 성별'],name:'같은 시군구 안 순위 차트'},
  biz:{c:'chart-w',rows:['업종'],name:'같은 시군구 안 순위 차트'},
  etc:{c:'chart-c',rows:['입지','지역·업종 직전 폐업률'],name:'점포 단위 판별력 차트'}};
function renderSurvLink(){
  const el=$('#survlink');if(!el)return;el.hidden=false;
  if(S.sel===null){el.innerHTML='<b>지도와 연결</b> 지도에서 지역을 고르면, 그 지역에서 가장 크게 작용한 요인의 근거를 여기서 바로 볼 수 있다. <button type="button" class="chip-b" data-go-tab="map">지도로 가기</button>';return;}
  const v=val(S.sel,S.biz);if(!v){el.hidden=true;return;}
  const core=factors(v.x).filter(d=>d.key!=='age').sort((a,b)=>Math.abs(Math.log(b.m))-Math.abs(Math.log(a.m))),d=core[0],who='<b>'+rname(S.sel)+(S.biz>=0?' '+BIZ[S.biz]:' 전체')+'</b>('+MX(v.mult)+')';
  if(d.m>=0.97&&d.m<=1.03){el.innerHTML='지금 보고 있는 '+who+'에서는 뚜렷하게 작용한 요인이 없다(모두 ±3% 이내).';return;}
  el.innerHTML='지금 보고 있는 '+who+'에서 가장 크게 작용한 요인은 <b>'+d.label+'</b>('+(d.m>=1?'위험을 높임 ▲':'위험을 낮춤 ▼')+' ×'+d.m.toFixed(2)+')이다. <a href="#'+SURVMAP[d.key].c+'" data-see="'+d.key+'">이 요인의 근거: '+SURVMAP[d.key].name+' 보기 →</a>';
}
document.addEventListener('click',e=>{const a=e.target.closest('[data-see]');if(!a)return;e.preventDefault();
  const mp=SURVMAP[a.dataset.see],card=document.getElementById(mp.c);if(!card)return;
  for(let d=card.closest('details');d;d=d.parentElement&&d.parentElement.closest('details'))d.open=true;   // 접힌 통계 상세를 연다
  card.scrollIntoView({behavior:'smooth',block:'center'});
  card.querySelectorAll('.hbrow').forEach(r=>{const nm=r.querySelector('.nm');if(nm&&mp.rows.includes(nm.textContent.replace(/^[★▼]\s*/,'').trim())){r.classList.add('hl');setTimeout(()=>r.classList.remove('hl'),2600);}});});

// 데스크톱에서는 지도가 첫 화면(뷰포트) 안에 들어오도록 높이를 맞춘다(모바일은 CSS)
function fitMap(){
  const m=$('#map'),c=$('.mapcard');if(!m||!c)return;
  if(isMobile()){m.style.height='';return;}
  if(!$('#t-map').classList.contains('on'))return;
  const top=c.getBoundingClientRect().top+window.scrollY;
  m.style.height=Math.max(440,Math.min(760,window.innerHeight-top-28))+'px';map.invalidateSize();
}
let fitT;window.addEventListener('resize',()=>{clearTimeout(fitT);fitT=setTimeout(fitMap,120);});

// ---------- 탭 ----------
function tab(t){document.querySelectorAll('#nav button').forEach(x=>x.setAttribute('aria-selected',x.dataset.t===t));document.querySelectorAll('section.tab').forEach(x=>x.classList.toggle('on',x.id==='t-'+t));history.replaceState(null,'','#'+t);window.scrollTo(0,0);if(t==='map')setTimeout(()=>{fitMap();map.invalidateSize();},50);if(t==='surv')renderSurvLink();}
document.querySelectorAll('#nav button').forEach(x=>x.addEventListener('click',()=>tab(x.dataset.t)));
if(location.hash&&$('#t-'+location.hash.slice(1)))tab(location.hash.slice(1));
window.addEventListener('hashchange',()=>{const k=location.hash.slice(1);if($('#t-'+k)&&!$('#t-'+k).classList.contains('on'))tab(k);});   // 같은 문서에서 #surv 등으로 바꿔도 탭이 열린다
renderLegend();renderHome();update();
$('#btn-nat').addEventListener('click',clearSel);$('#btn-sudo').addEventListener('click',goSudo);
const aq=new URLSearchParams(location.search).get('area');if(aq){$('#areaq').value=aq;areaShow();}
const bizFromName=v=>{const i=BIZ.indexOf(v);if(i>=0)return i;for(const k in BIZKEY)if(v.includes(k))return BIZKEY[k];return -1;};
const qP=UP.get('region')||UP.get('q'),cP=UP.get('compare'),bi=UP.get('industry')?bizFromName(UP.get('industry')):-1;   // 옛 링크의 ?q= 도 그대로 열린다
if(bi>=0)setBizQuiet(bi);
if(cP&&qP){update();renderHome();tab('area');cmpRestore(qP,cP,bi);}   // 초기 렌더가 주소를 정리한 뒤 비교 상태를 복원한다
else if(qP){$('#ask').value=qP;ask(bi>=0);}else if(bi>=0){update();renderHome();}
(function(){ // 첫 방문자용 3단계 가이드(닫으면 이 브라우저에서 다시 보이지 않는다). 링크로 들어온 경우엔 띄우지 않는다
  let seen=false;try{seen=localStorage.getItem('bc_guide_v1')==='1';}catch(e){}
  const g=$('#guide');if(!seen&&!qP){g.hidden=false;document.body.classList.add('guide-on');}
  $('#guideX').addEventListener('click',()=>{g.hidden=true;document.body.classList.remove('guide-on');fitMap();try{localStorage.setItem('bc_guide_v1','1');}catch(e){}});
})();
fitMap();window.addEventListener('load',fitMap);
</script></body></html>"""

html_out = (TEMPLATE.replace("__CSS__", css).replace("__EXTRA__", EXTRA_CSS).replace("__DATA__", data).replace("__SURV__", surv).replace("__LEAFLET_CSS__", Path("vendor/leaflet.css").read_text(encoding="utf-8")).replace("__LEAFLET_JS__", Path("vendor/leaflet.js").read_text(encoding="utf-8"))
            .replace("__TIP_MIN__", TIP_MIN).replace("__N__", f"{nat['n']:,}").replace("__EV__", f"{nat['events']:,}").replace("__RATE__", f"{nat['rate'] * 100:.2f}")
            .replace("__RHO_ALL__", f"{R.rho_all:+.2f}").replace("__RHO_IN__", f"{R.rho_in:+.2f}"))
for d in ("site", "docs"):             # site/는 로컬 확인용, docs/는 GitHub Pages(main 브랜치 /docs)용 — 내용 동일
    Path(d).mkdir(exist_ok=True)
    Path(d, "index.html").write_text(html_out, encoding="utf-8")
Path("docs/.nojekyll").write_text("", encoding="utf-8")
print(f"site/index.html, docs/index.html 작성 ({len(html_out) / 1024:.0f} KB)")
