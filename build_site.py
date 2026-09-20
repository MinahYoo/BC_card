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
body{scroll-behavior:smooth}
.top{position:sticky;top:0;z-index:20;background:var(--bg);border-bottom:1px solid var(--line)}
.top .in{max-width:1180px;margin:0 auto;padding:10px 16px;display:flex;flex-wrap:wrap;gap:8px 18px;align-items:center;justify-content:space-between}
.brand{font-weight:800;font-size:16px} .brand span{color:var(--sub);font-weight:500;font-size:13px;margin-left:8px}
nav{display:flex;gap:4px;flex-wrap:wrap} nav button{border:1px solid var(--line);background:var(--card);color:var(--fg);padding:7px 14px;border-radius:999px;font:inherit;font-size:14px;cursor:pointer}
nav button[aria-selected="true"]{background:var(--acc);border-color:var(--acc);color:#fff}
main.wide{max-width:1180px;padding-bottom:80px} section.tab{display:none;padding-top:22px} section.tab.on{display:block}
.hero{padding:6px 0 14px} .hero h1{font-size:clamp(22px,4vw,32px);margin:0 0 6px} .hero p{margin:0;color:var(--sub);max-width:820px}
.ctrl{display:flex;flex-wrap:wrap;gap:10px 14px;align-items:center;margin:8px 0 14px}
.chip-b{border:1px solid var(--line);background:var(--card);color:var(--fg);padding:6px 12px;border-radius:999px;font:inherit;font-size:13.5px;cursor:pointer}
.chip-b.on{background:var(--fg);color:var(--bg);border-color:var(--fg)}
select,input[type=text]{font:inherit;font-size:14px;padding:7px 10px;border:1px solid var(--line);border-radius:8px;background:var(--card);color:var(--fg)}
input[type=text]{min-width:min(260px,100%);flex:1}
.grid2{display:grid;grid-template-columns:minmax(0,1.05fr) minmax(0,1fr);gap:16px;align-items:start}
@media (max-width:920px){.grid2{grid-template-columns:1fr}}
.mapcard{position:relative;padding:8px;isolation:isolate} #map{width:100%;height:min(78vh,700px);min-height:440px;border-radius:8px;z-index:0}
.leaflet-control-attribution{font-size:10px;padding:0 5px;color:var(--sub);background:color-mix(in srgb,var(--card) 72%,transparent)} .leaflet-control-attribution a{color:inherit} .leaflet-control-layers{background:var(--card);color:var(--fg);border:1px solid var(--line);border-radius:8px;box-shadow:none;font-size:12.5px} .leaflet-control-layers-toggle{border-radius:8px}
.leaflet-container{font:inherit;background:var(--card)} .tile-gray{filter:grayscale(1) contrast(.88) brightness(1.08)}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]) .tile-gray{filter:grayscale(1) invert(1) contrast(.85) brightness(.85)}} .leaflet-tooltip{font-size:12.5px;line-height:1.4}
.legend{display:flex;align-items:center;gap:8px;font-size:12.5px;color:var(--sub);margin:8px 4px 2px}
.legend .bar{height:10px;width:190px;border-radius:5px;background:linear-gradient(90deg,rgb(45,110,190),rgb(232,230,222),rgb(214,69,65))}
.panel h3{margin:0 0 2px;font-size:20px} .panel .sub2{color:var(--sub);font-size:13.5px}
.big{display:flex;align-items:baseline;gap:14px;flex-wrap:wrap;margin:8px 0 2px} .big b{font-size:38px;line-height:1}
.big span{color:var(--sub);font-size:14px}
.tag{display:inline-block;padding:2px 9px;border-radius:999px;font-size:12px;background:var(--line);color:var(--fg);margin-right:4px}
.tag.hi{background:rgba(214,69,65,.16);color:var(--neg)} .tag.lo{background:rgba(45,110,190,.16);color:var(--pos)}
.why{margin:6px 0 4px} .why p{margin:6px 0;font-size:14.5px}
.blk{border-top:1px solid var(--line);margin-top:14px;padding-top:12px} .blk h4{margin:0 0 6px;font-size:14px;color:var(--sub);font-weight:600}
.two{display:grid;grid-template-columns:1fr 1fr;gap:12px} @media (max-width:520px){.two{grid-template-columns:1fr}}
.mini{max-width:280px;width:100%}.mini text{font-size:11px;fill:var(--fg)} .mini .v{fill:var(--sub)}
.spark{width:100%;max-width:320px;height:auto}
.nb{display:flex;flex-wrap:wrap;gap:6px} .nb button{border:1px solid var(--line);background:var(--card);color:var(--fg);border-radius:8px;padding:4px 9px;font:inherit;font-size:12.5px;cursor:pointer}
.warn{background:var(--warn);border:1px solid var(--warnb);border-radius:8px;padding:8px 12px;font-size:13.5px;margin:8px 0}
.hint{color:var(--sub);font-size:13.5px}
.tbl td.b1{min-width:120px} .mb{display:inline-block;height:9px;border-radius:3px;vertical-align:middle;margin-right:6px}
.kp{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin:10px 0}
.kp div{background:var(--bg);border:1px solid var(--line);border-radius:10px;padding:10px 12px} .kp b{display:block;font-size:20px} .kp span{font-size:12.5px;color:var(--sub)}
.scat circle{opacity:.75} .scat text{font-size:11px;fill:var(--sub)}
.cols3{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:14px}
#panel .bar.neg{fill:#d64541}#panel .bar.pos{fill:#2d6ebe}#panel .bar.soft{opacity:.42}
.legend2{display:flex;flex-wrap:wrap;align-items:center;gap:6px 10px;font-size:12.5px;color:var(--sub);margin:8px 4px 2px}.legend2 span{white-space:nowrap}
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
<p>2026-01-01 영업 중이던 점포 __N__개를 180일 추적한 결과입니다. 색은 “평균 점포 대비 폐업 위험 배수”(연관, 인과 아님)이고, 버블을 누르면 <b>왜</b> 그런지(요인 분해)와 BC카드 소비 구성을 볼 수 있습니다.</p></div>
<div class="ctrl" id="bizbar"></div>
<div class="ctrl">
<label class="hint">색 기준 <select id="mode"><option value="mult">위험 배수 (모형 M3L)</option><option value="rate">실제 폐업률 (전국 대비)</option></select></label>
<input type="text" id="ask" placeholder="예) 동탄 서양음식 / 합천 한식 / 한식 위험한 곳" aria-label="지역·업종 질문">
<button class="chip-b" id="askbtn">설명 보기</button>
</div>
<div class="hint" id="askhelp" style="margin:-4px 0 12px">질문 형식은 <b>지역 + 업종</b>, <b>지역만</b>, <b>업종 + 위험한/안전한 곳</b> 세 가지입니다(LLM이 아니라 정해진 형식만 이해합니다). 예시: <button class="chip-b" data-q="동탄 서양음식">동탄 서양음식</button> <button class="chip-b" data-q="합천 한식">합천 한식</button> <button class="chip-b" data-q="강남구">강남구</button> <button class="chip-b" data-q="한식 위험한 곳">한식 위험한 곳</button> <button class="chip-b" data-q="경남 한식 안전한 곳">경남 한식 안전한 곳</button></div>
<div class="grid2">
<div class="card mapcard"><div id="map" role="region" aria-label="시군구 버블 지도"></div>
<div class="legend2"><span>안전</span><div class="bar" style="height:10px;width:170px;border-radius:5px;background:linear-gradient(90deg,rgb(45,110,190),rgb(232,230,222),rgb(214,69,65))"></div><span>위험</span></div><div class="hint" id="tilenote" style="margin:2px 4px 0;color:var(--neg)"></div><div class="hint" style="margin:2px 4px 4px">버블 크기 = 점포 수 · 점선 회색 = 표본 30개 미만 · 시군구 내 점포 좌표의 중앙값에 표시 · 휠/＋－로 확대</div></div>
<div class="card panel" id="panel"><p class="hint">지도의 버블을 누르거나 위 입력창에 <b>지역 + 업종</b>(예: 동탄 서양음식)을 적어 보세요. 형식은 입력창 아래에 있습니다.<br><br>“왜”는 Cox 모형(M3L)의 선형예측자를 요인별로 정확히 쪼갠 값입니다. 붉은 막대는 위험을 높이는 요인, 푸른 막대는 낮추는 요인이며, 요인들을 곱하면 위험 배수가 됩니다.</p></div>
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
<li><b>지도:</b> 시군구 경계가 아니라 시군구 내 점포 좌표의 중앙값(EPSG:5174를 위·경도로 변환, 오차 수백 m)에 놓은 버블입니다. 배경 지도는 CARTO 타일(OpenStreetMap 데이터, 오른쪽 위 버튼으로 스타일 변경)이며 인터넷 연결이 필요합니다(끊겨도 버블·패널은 동작). 2026년 개편 지역명을 그대로 씁니다. 그룹당 점포가 30개 미만이면 실제 폐업률이 불안정해 회색 점선으로 표시합니다.</li>
<li><b>설명 문장:</b> 규칙으로 만든 문장이며 LLM을 쓰지 않습니다. 숫자는 모두 위 분해 결과에서 옵니다.</li>
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
const SHOW=[
 {label:'영업연수',idx:[0]},{label:'프랜차이즈',idx:[1]},{label:'사업장 특성',idx:[3]},{label:'이웃·자기 폐업 이력',idx:[5]},
 {label:'BC 연령 구성 †',idx:[7]},{label:'BC 성별 구성',idx:[6]},{label:'업종 기본 위험',idx:[8]},{label:'기타(입지 등)',idx:[2,4]}];
const factors=x=>SHOW.map(s=>({label:s.label,m:s.idx.reduce((a,i)=>a*x[i],1)}));
const GI=new Map(); D.groups.forEach((g,i)=>GI.set(g.r*10+g.b,i));
const S={biz:-1,mode:'mult',sel:null};
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
// 배경 타일은 외부(CARTO/OpenStreetMap)에서 불러온다. 타일을 못 불러와도 버블과 패널은 그대로 동작한다.
const dark=window.matchMedia&&window.matchMedia('(prefers-color-scheme: dark)').matches&&document.documentElement.dataset.theme!=='light';
const map=L.map('map',{minZoom:6,maxZoom:14,zoomSnap:0.5,preferCanvas:true,attributionControl:false});
// Leaflet 접두('Leaflet | ' + 국기)는 빼고(라이선스상 제거 허용), 타일 제공처 크레딧(OSM/Esri)은 유지한다(OSM 이용 정책상 지도 위에 보여야 함).
L.control.attribution({prefix:false,position:'bottomright'}).addTo(map);
// 배경 타일: CARTO(OSM 데이터 기반, 데이터 오버레이용으로 설계된 절제된 스타일)를 기본으로 쓰고, 오른쪽 위 버튼으로 스타일을 바꿔 볼 수 있다.
// 기본은 밝은 화면이면 'Positron', 다크 화면이면 'Dark Matter'. 못 불러오면 OpenStreetMap -> Esri 순으로 자동 대체한다.
const cartoA='© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors © <a href="https://carto.com/attributions">CARTO</a>';
const carto=p=>L.tileLayer('https://{s}.basemaps.cartocdn.com/'+p+'/{z}/{x}/{y}{r}.png',{subdomains:'abcd',maxZoom:19,attribution:cartoA});
const bLight=carto('light_all'),bDark=carto('dark_all'),bVoy=carto('rastertiles/voyager');
const osm=L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,className:'tile-gray',attribution:'© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'});
const esri=L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}',{maxZoom:15,className:'tile-gray',attribution:'Tiles © Esri — Esri, HERE, Garmin, © OpenStreetMap contributors'});
const qtiles=new URLSearchParams(location.search).get('tiles');
const pick={light:bLight,dark:bDark,voyager:bVoy,osm:osm,esri:esri};
let terr=0;
function tileNote(t){$('#tilenote').textContent=t;}
[bLight,bDark,bVoy,osm,esri].forEach(l=>{
  l.on('tileload',()=>{if(map.hasLayer(l))terr=0;});
  l.on('tileerror',()=>{if(!map.hasLayer(l))return;
    if(l===esri){if(++terr>=6)tileNote('배경 지도를 불러오지 못했습니다(인터넷 연결이나 차단을 확인하세요). 버블은 좌표 기준으로 표시됩니다.');return;}
    if(++terr>=3){terr=0;map.removeLayer(l);const nx=l===osm?esri:osm;nx.addTo(map);tileNote((l===osm?'OpenStreetMap':'선택한 배경')+' 타일을 불러오지 못해 대체 배경('+(nx===osm?'OpenStreetMap':'Esri')+')을 쓰고 있습니다.');}});});
L.control.layers({'밝은 지도(기본)':bLight,'다크':bDark,'컬러(Voyager)':bVoy,'OpenStreetMap(회색조)':osm},null,{position:'topright',collapsed:true}).addTo(map);
(pick[qtiles]||(dark?bDark:bLight)).addTo(map);
map.fitBounds([[33.0,125.0],[38.7,130.8]]);
const order=D.regions.map((r,i)=>i).sort((a,b)=>D.regions[b].n-D.regions[a].n);   // 큰 버블을 먼저 그려 작은 버블이 위에 오게 한다
const markers={};
const tipHtml=i=>{const v=val(i,S.biz),R=D.regions[i];
  return '<b>'+R.sido.replace(/특별시|광역시|특별자치도|특별자치시/,'')+' '+R.name+'</b>'+(S.biz>=0?' · '+BIZ[S.biz]:'')+'<br>'+(v?'위험 ×'+v.mult.toFixed(2)+' · 폐업률 '+pct(v.rate)+' · 점포 '+v.n.toLocaleString():'해당 업종 점포 없음');};
order.forEach(i=>{const R=D.regions[i];
  const m=L.circleMarker([R.lat,R.lon],{radius:5,weight:.8,color:'rgba(0,0,0,.45)',fillOpacity:.86}).addTo(map);
  m.on('click',()=>select(i)); m.bindTooltip(()=>tipHtml(i),{sticky:true,direction:'top',opacity:.95}); markers[i]=m;});
const ZF=()=>Math.max(0.75,Math.min(3.2,Math.pow(1.28,map.getZoom()-7)));      // 확대할수록 버블을 키워 겹침을 줄인다
const nbLayer=L.layerGroup().addTo(map);
function update(){
  const zf=ZF();
  order.forEach(i=>{const m=markers[i],v=val(i,S.biz);
    if(!v){m.setStyle({opacity:0,fillOpacity:0,radius:0.1});return;}
    const k=S.biz<0?0.055:0.09,small=S.biz>=0&&v.n<30,sel=i===S.sel;
    m.setStyle({radius:(2.2+k*Math.sqrt(v.n))*zf,fillColor:small?'#9aa0a6':colorOf(v),fillOpacity:small?0.35:0.86,color:sel?'#111':'rgba(0,0,0,.45)',weight:sel?3:0.8,opacity:1,dashArray:small?'2 2':null});
    if(sel)m.bringToFront();});
  drawLinks();
}
map.on('zoomend',update);
function drawLinks(){
  nbLayer.clearLayers(); if(S.sel===null) return; const a=D.regions[S.sel];
  a.nb.forEach(j=>{const b=D.regions[j];L.polyline([[a.lat,a.lon],[b.lat,b.lon]],{color:dark?'#ddd':'#222',weight:1.3,dashArray:'4 4',opacity:.75,interactive:false}).addTo(nbLayer);});
  if(D.regions[S.sel]&&!map.getBounds().contains([a.lat,a.lon])) map.panTo([a.lat,a.lon]);
}

// ---------- 패널 ----------
function whyChart(x){
  const f=factors(x).sort((a,b)=>Math.abs(Math.log(b.m))-Math.abs(Math.log(a.m)));
  const Wd=480,lw=150,bh=19,gap=6,half=(Wd-lw-56)/2,cx=lw+half+8,mx=Math.log(1.6);
  let s='<svg viewBox="0 0 '+Wd+' '+(f.length*(bh+gap)+6)+'" class="chart"><line x1="'+cx+'" x2="'+cx+'" y1="0" y2="'+(f.length*(bh+gap)+4)+'" class="axis"/>';
  f.forEach((d,i)=>{const y=4+i*(bh+gap),l=Math.log(d.m),w=Math.min(Math.abs(l)/mx,1)*half,x0=l>=0?cx:cx-w;
    s+='<text x="'+(lw-6)+'" y="'+(y+13.5)+'" text-anchor="end" class="lbl">'+d.label+'</text>'+
       '<rect x="'+x0.toFixed(1)+'" y="'+y+'" width="'+Math.max(w,1.5).toFixed(1)+'" height="'+bh+'" rx="3" class="bar '+(l>=0?'neg':'pos')+(d.label.includes('†')?' soft':'')+'"/>'+
       '<text x="'+(l>=0?cx+w+5:cx-w-5).toFixed(1)+'" y="'+(y+13.5)+'" text-anchor="'+(l>=0?'start':'end')+'" class="val">×'+d.m.toFixed(2)+'</text>';});
  return s+'</svg>';
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
  const AGEL='BC 연령 구성 †', ageF=f.find(d=>d.label===AGEL), core=f.filter(d=>d.label!==AGEL);
  const up=core.filter(d=>d.m>=1.03).sort((a,b)=>b.m-a.m), dn=core.filter(d=>d.m<=0.97).sort((a,b)=>a.m-b.m);
  const chg=v.mult>=1?((v.mult-1)*100).toFixed(0)+'% 높':((1-v.mult)*100).toFixed(0)+'% 낮';
  const phrase=(d,isUp)=>{
    const a=g?g.age_yr:R.age_yr, fr=g?g.fr:R.fr;
    switch(d.label){
      case '영업연수': return isUp?'영업 기간이 짧은 점포가 많고(평균 '+a.toFixed(1)+'년, 전국 '+NAT.age_yr.toFixed(1)+'년)':'오래 영업한 점포가 많고(평균 '+a.toFixed(1)+'년, 전국 '+NAT.age_yr.toFixed(1)+'년)';
      case '프랜차이즈': return isUp?'프랜차이즈 비중이 낮고('+pct(fr)+', 전국 '+pct(NAT.fr)+')':'프랜차이즈 비중이 높고('+pct(fr)+', 전국 '+pct(NAT.fr)+')';
      case '사업장 특성': return isUp?'점포 규모·다중이용 등 점포 특성이 위험 쪽이고':'점포 규모·다중이용 등 점포 특성이 안정 쪽이고';
      case '이웃·자기 폐업 이력': return g?(isUp?'이 시군구('+pct(g.reg_hist)+')와 이웃 지역('+pct(g.nb_hist)+')의 직전 1년 폐업률이 높고':'이 시군구('+pct(g.reg_hist)+')와 이웃 지역('+pct(g.nb_hist)+')의 직전 1년 폐업률이 낮고'):(isUp?'이 지역과 이웃 지역의 직전 1년 폐업률이 높고':'이 지역과 이웃 지역의 직전 1년 폐업률이 낮고');
      case 'BC 연령 구성 †': return '고객 연령 구성이 '+(isUp?'폐업 위험이 높은':'폐업 위험이 낮은')+' 지역 유형과 닮았고(지역 유형 신호이며 같은 지역 안의 원인이라는 근거는 없음)';
      case 'BC 성별 구성': return '고객 성별 구성이 '+(isUp?'위험 쪽이고':'안정 쪽이고');
      case '업종 기본 위험': return isUp?'업종 자체의 기본 위험이 평균보다 높고':'업종 자체의 기본 위험이 평균보다 낮고';
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
  let h='<h3>'+nm+'</h3><div class="sub2">'+(b>=0?BIZ[b]:'전체 7개 업종')+' · 점포 '+(v?v.n.toLocaleString():0)+'개</div>';
  if(!v){$('#panel').innerHTML=h+'<p class="hint">이 시군구에는 해당 업종 점포가 없습니다.</p>'+bizRows(r);return;}
  h+='<div class="big"><b style="color:'+(v.mult>=1?'var(--neg)':'var(--pos)')+'">×'+v.mult.toFixed(2)+'</b><span>평균 점포 대비 위험 배수</span></div>';
  h+='<div class="sub2">실제 폐업률 '+pct(v.rate)+' <span class="hint">(전국 '+pct(NAT.rate)+')</span></div>';
  if(b>=0&&v.n<30) h+='<div class="warn">점포가 30개 미만이라 실제 폐업률은 우연 변동이 큽니다. 배수는 모형 기반이라 상대적으로 안정적입니다.</div>';
  h+='<div class="blk"><h4>왜 그런가 — 요인별 배수 (붉음: 위험 ↑, 푸름: 위험 ↓)</h4>'+whyChart(v.x)+'<p class="hint" style="margin:2px 0 0">† 옅게 표시한 BC 연령 구성은 같은 시군구 안에서 예측에 기여하지 않았습니다. 위험의 원인이 아니라 지역 유형 신호로 읽으세요.</p></div>';
  h+='<div class="blk why"><h4>한 줄 해설</h4>'+explain(r,b)+'</div>';
  if(v.g){const g=v.g;
    h+='<div class="blk"><h4>BC카드 소비 구성 (2026-01~06, 맥락 정보)</h4><div class="two"><div>'+barsMini(g.age,AGE,x=>pct(x,0))+'<p class="hint" style="margin:2px 0 6px">연령 코드별 소비액 비중</p>'+barsMini(g.gen,GEN,x=>pct(x,0))+'</div><div>'+spark(g.amt)+'</div></div></div>';
    h+='<div class="blk"><h4>상권 프로필</h4><div class="kp"><div><b>'+g.age_yr.toFixed(1)+'년</b><span>평균 영업연수 (전국 '+NAT.age_yr.toFixed(1)+')</span></div><div><b>'+pct(g.fr)+'</b><span>프랜차이즈 (전국 '+pct(NAT.fr)+')</span></div><div><b>'+pct(g.reg_hist)+' / '+pct(g.nb_hist)+'</b><span>직전 1년 폐업률 자기 / 이웃</span></div><div><b>'+g.n.toLocaleString()+'개</b><span>경쟁 점포(같은 업종)</span></div></div></div>';
  } else h+=bizRows(r);
  h+='<div class="blk"><h4>모형이 참고하는 가까운 이웃 5곳(지도의 점선)</h4><div class="nb">'+R.nb.map(j=>{const z=val(j,b);return '<button data-r="'+j+'">'+D.regions[j].name+(z?' ×'+z.mult.toFixed(2):'')+'</button>';}).join('')+'</div></div>';
  p.innerHTML=h; p.querySelectorAll('.nb button').forEach(x=>x.addEventListener('click',()=>select(+x.dataset.r)));
  p.querySelectorAll('tr[data-b]').forEach(x=>x.addEventListener('click',()=>{setBiz(+x.dataset.b);}));
}
function bizRows(r){
  let s='<div class="blk"><h4>업종별 (누르면 그 업종으로 전환)</h4><table class="tbl"><thead><tr><th>업종</th><th class="num">점포</th><th class="num">폐업률</th><th class="num">위험 배수</th></tr></thead><tbody>';
  BIZ.forEach((nm,b)=>{const v=val(r,b);if(!v)return;s+='<tr data-b="'+b+'" style="cursor:pointer"><td>'+nm+'</td><td class="num">'+v.n.toLocaleString()+'</td><td class="num">'+pct(v.rate)+'</td><td class="num"><b style="color:'+(v.mult>=1?'var(--neg)':'var(--pos)')+'">×'+v.mult.toFixed(2)+'</b></td></tr>';});
  return s+'</tbody></table></div>';
}
function select(i){S.sel=i;update();renderPanel();}
function setBiz(b){S.biz=b;document.querySelectorAll('#bizbar .chip-b').forEach(x=>x.classList.toggle('on',+x.dataset.b===b));update();renderPanel();}
// 업종 필터
(function(){const bar=$('#bizbar');bar.innerHTML='<span class="hint">업종</span>'+['전체'].concat(BIZ).map((nm,i)=>'<button class="chip-b'+(i===0?' on':'')+'" data-b="'+(i-1)+'">'+nm+'</button>').join('');
  bar.querySelectorAll('.chip-b').forEach(x=>x.addEventListener('click',()=>setBiz(+x.dataset.b)));})();
$('#mode').addEventListener('change',e=>{S.mode=e.target.value;update();});

// ---------- 규칙 기반 질문 (LLM 아님: 정해진 형태만 이해한다) ----------
const BIZKEY={'한식':0,'일식':1,'회집':1,'횟집':1,'중국':2,'중식':2,'서양':3,'양식':3,'스넥':4,'스낵':4,'분식':4,'제과':5,'빵':5,'베이커리':5,'편의점':6};
const UNSUP=['치킨','카페','커피','피자','술집','호프','주점','고기','삼겹','미용','학원','약국','세탁'];
const SIDOALIAS={'경남':'경상남도','경북':'경상북도','충남':'충청남도','충북':'충청북도','전남':'전라남도','전북':'전북특별자치도','강원':'강원특별자치도','제주':'제주특별자치도','세종':'세종특별자치시'};
const SIDOS=[...new Set(D.regions.map(r=>r.sido))];
const sidoOf=t=>SIDOALIAS[t]||SIDOS.find(x=>t.length>=2&&x.includes(t));
const rname=i=>D.regions[i].sido.replace(/특별시|광역시|특별자치도|특별자치시/,'')+' '+D.regions[i].name;
function say(html){$('#panel').innerHTML=html;$('#panel').querySelectorAll('[data-r]').forEach(x=>x.addEventListener('click',()=>{if(x.dataset.b!==undefined)setBizQuiet(+x.dataset.b);select(+x.dataset.r);}));}
const HELP='<div class="hint"><b>이렇게 물어보세요</b><ul style="margin:6px 0 0 18px;padding:0"><li><b>지역 + 업종</b> — 동탄 서양음식 · 합천 한식 · 마포구 제과점</li><li><b>지역만</b> — 강남구 (전체 업종 요약과 업종별 표)</li><li><b>순위</b> — 한식 위험한 곳 · 서울 제과점 안전한 곳 · 경남 한식 위험한 곳</li></ul>'+
 '<p style="margin:8px 0 0">지역은 시군구 이름의 일부만 써도 됩니다(동탄, 합천). 업종은 한식·일식·중식·서양(양식)·스낵(분식)·제과점(빵)·편의점 7개만 있습니다. 카페·치킨 등 다른 업종, 두 지역 비교, 시점별 추세, 예측 질문은 지원하지 않습니다. “왜”는 지역+업종을 고르면 나오는 요인 분해가 답입니다.</p></div>';
function ask(){
  const q=$('#ask').value.replace(/\s+/g,' ').trim(); if(!q) return;
  const esc=q.replace(/</g,'&lt;');
  if(UNSUP.some(k=>q.includes(k))){say('<p>“'+esc+'”: 이 사이트는 7개 업종(한식·일식·중식·서양음식·스낵·제과점·편의점)만 다룹니다.</p>'+HELP);return;}
  let b=-1;for(const k in BIZKEY){if(q.includes(k)){b=BIZKEY[k];break;}}
  const intent=/(위험한|위험 ?높|폐업 ?많|많이 ?망|취약)/.test(q)?'hi':(/(안전|위험 ?낮|덜 ?망|안정)/.test(q)?'lo':null);
  const toks=q.split(/[ ,?]+/).filter(t=>t.length>=2&&!Object.keys(BIZKEY).some(k=>t.includes(k))&&!/(왜|위험|해줘|알려|어때|설명|곳|안전|폐업|많이|제일|가장)/.test(t));
  if(intent){ // 순위 질문: 업종(선택) + 시도(선택)
    let sido=null;for(const t of toks){const x=sidoOf(t);if(x){sido=x;break;}}
    let rows;
    if(b>=0) rows=D.groups.filter(g=>g.b===b&&g.n>=300&&(!sido||D.regions[g.r].sido===sido)).map(g=>({r:g.r,m:g.mult,rate:g.rate,n:g.n}));
    else rows=D.regions.map((R,i)=>({r:i,m:R.mult,rate:R.rate,n:R.n})).filter(x=>x.n>=2000&&(!sido||D.regions[x.r].sido===sido));
    rows.sort((x,y)=>intent==='hi'?y.m-x.m:x.m-y.m); rows=rows.slice(0,8);
    if(!rows.length){say('<p>조건에 맞는 지역이 없습니다(점포 수가 충분한 곳만 순위에 넣습니다).</p>'+HELP);return;}
    setBizQuiet(b);S.sel=null;update();
    say('<h3>'+(sido?sido.replace(/특별시|광역시|특별자치도|특별자치시/,'')+' ':'전국 ')+(b>=0?BIZ[b]:'전체 업종')+' — 위험이 '+(intent==='hi'?'높은':'낮은')+' 곳 상위 '+rows.length+'</h3><p class="hint">점포 '+(b>=0?300:2000)+'개 이상인 곳만 순위에 넣었습니다. 누르면 설명이 열립니다.</p><div class="nb" style="flex-direction:column;align-items:stretch">'+
      rows.map(x=>'<button data-r="'+x.r+'" data-b="'+b+'" style="text-align:left">'+rname(x.r)+' · <b style="color:'+(x.m>=1?'var(--neg)':'var(--pos)')+'">×'+x.m.toFixed(2)+'</b> · 폐업률 '+pct(x.rate)+' · 점포 '+x.n.toLocaleString()+'</button>').join('')+'</div>');
    return;
  }
  let cand=[];
  for(const t of toks){const t2=t.replace(/(시|군|구)$/,'');
    cand=D.regions.map((r,i)=>i).filter(i=>{const full=D.regions[i].sido+' '+D.regions[i].name;return full.includes(t)||(t2.length>=2&&full.includes(t2));});
    if(cand.length) break;}
  if(!cand.length){say('<p>“'+esc+'”에서 시군구를 찾지 못했습니다.</p>'+HELP);return;}
  setBizQuiet(b);
  if(cand.length>1){S.sel=null;update();say('<p>여러 시군구가 맞습니다. 선택해 주세요.</p><div class="nb">'+cand.slice(0,14).map(i=>'<button data-r="'+i+'">'+D.regions[i].sido+' '+D.regions[i].name+'</button>').join('')+'</div>');return;}
  select(cand[0]);
}
function setBizQuiet(b){S.biz=b;document.querySelectorAll('#bizbar .chip-b').forEach(x=>x.classList.toggle('on',+x.dataset.b===b));}
$('#askbtn').addEventListener('click',ask);$('#ask').addEventListener('keydown',e=>{if(e.key==='Enter')ask();});
document.querySelectorAll('#askhelp [data-q]').forEach(x=>x.addEventListener('click',()=>{$('#ask').value=x.dataset.q;ask();}));

// ---------- 상권 분석 ----------
const RL=$('#rlist');D.regions.forEach((r,i)=>{const o=document.createElement('option');o.value=r.sido+' '+r.name;RL.appendChild(o);});
function areaShow(){
  const q=$('#areaq').value.trim();const i=D.regions.findIndex(r=>(r.sido+' '+r.name)===q)>=0?D.regions.findIndex(r=>(r.sido+' '+r.name)===q):D.regions.findIndex(r=>r.name.includes(q)&&q.length>=2);
  if(i<0){$('#areaout').innerHTML='<p class="hint">일치하는 시군구가 없습니다.</p>';return;}
  const R=D.regions[i];let s='<h3 style="margin:0">'+R.sido+' '+R.name+'</h3><div class="kp"><div><b>'+R.n.toLocaleString()+'개</b><span>점포(7개 업종)</span></div><div><b>'+pct(R.rate)+'</b><span>180일 폐업률 (전국 '+pct(NAT.rate)+')</span></div><div><b style="color:'+(R.mult>=1?'var(--neg)':'var(--pos)')+'">×'+R.mult.toFixed(2)+'</b><span>위험 배수(지역 평균)</span></div><div><b>'+R.age_yr.toFixed(1)+'년</b><span>평균 영업연수 (전국 '+NAT.age_yr.toFixed(1)+')</span></div><div><b>'+pct(R.fr)+'</b><span>프랜차이즈 (전국 '+pct(NAT.fr)+')</span></div></div>';
  s+='<div class="scroll"><table class="tbl"><thead><tr><th>업종</th><th class="num">점포</th><th>실제 폐업률</th><th>위험 배수</th><th class="num">평균 영업연수</th><th class="num">프랜차이즈</th><th class="num">BC 월평균 소비(백만원)</th><th class="num">점포당(백만원)</th></tr></thead><tbody>';
  BIZ.forEach((nm,b)=>{const g=GI.has(i*10+b)?D.groups[GI.get(i*10+b)]:null;if(!g)return;const am=g.amt.filter(v=>v!==null),mean=am.length?am.reduce((a,c)=>a+c,0)/am.length:null;
    s+='<tr><td>'+nm+'</td><td class="num">'+g.n.toLocaleString()+'</td><td class="b1"><span class="mb" style="width:'+Math.min(g.rate/0.09*90,100).toFixed(0)+'px;background:var(--ref)"></span>'+pct(g.rate)+'</td><td class="b1"><span class="mb" style="width:'+Math.min(g.mult/2*90,100).toFixed(0)+'px;background:'+(g.mult>=1?'var(--neg)':'var(--pos)')+'"></span>×'+g.mult.toFixed(2)+'</td><td class="num">'+g.age_yr.toFixed(1)+'</td><td class="num">'+pct(g.fr)+'</td><td class="num">'+(mean===null?'-':Math.round(mean).toLocaleString())+'</td><td class="num">'+(mean===null?'-':(mean/g.n).toFixed(2))+'</td></tr>';});
  s+='</tbody></table></div><p class="cap">BC 소비는 시군구×업종 집계이며 점포당 값은 (월평균 소비 ÷ 1/1 영업 점포 수)입니다. <a href="#" id="tomap" style="color:var(--acc)">지도에서 보기 →</a></p>';
  $('#areaout').innerHTML=s;$('#tomap').addEventListener('click',ev=>{ev.preventDefault();tab('map');select(i);});
}
$('#areaq').addEventListener('change',areaShow);$('#areaq').addEventListener('input',()=>{if(D.regions.some(r=>(r.sido+' '+r.name)===$('#areaq').value.trim()))areaShow();});
const RB=$('#rankbiz');RB.innerHTML=BIZ.map((n,i)=>'<option value="'+i+'">'+n+'</option>').join('');
function rank(){
  const b=+RB.value,gs=D.groups.filter(g=>g.b===b&&g.n>=300).sort((a,c)=>c.mult-a.mult);
  const row=g=>{const R=D.regions[g.r],f=factors(g.x).filter(d=>!d.label.includes('†')).sort((a,c)=>Math.abs(Math.log(c.m))-Math.abs(Math.log(a.m)))[0];
    return '<tr><td>'+R.sido.replace(/특별시|광역시|특별자치도|특별자치시/,'')+' '+R.name+'</td><td class="num"><b style="color:'+(g.mult>=1?'var(--neg)':'var(--pos)')+'">×'+g.mult.toFixed(2)+'</b></td><td class="num">'+pct(g.rate)+'</td><td class="num">'+g.n.toLocaleString()+'</td><td>'+f.label.replace(' †','')+' ×'+f.m.toFixed(2)+'</td></tr>';};
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
update();
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
