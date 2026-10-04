#!/usr/bin/env python3
"""Build deterministic, original SVG ingredient illustrations from catalog names.

These are deliberately stylized botanical/culinary illustrations, not photographs,
measurements, verified cultivar portraits, or evidence for ingredient identity.
No remote image service is used. Exact source IDs are never changed.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
import random
import re
import subprocess
from collections import Counter
from pathlib import Path
import xml.etree.ElementTree as ET
ET.register_namespace('', 'http://www.w3.org/2000/svg')

BASE = Path(__file__).resolve().parents[1]
OUT = BASE / 'assets' / 'ingredients'
PAPER = '#f5f1e8'
STYLE = 'original_native_svg_editorial_botanical_v1'


def esc(s): return html.escape(str(s), quote=True)
def fmt(v): return f'{v:.2f}'.rstrip('0').rstrip('.') if isinstance(v, float) else str(v)
def attrs(**kw): return ' '.join(f'{k.replace("_", "-")}="{esc(fmt(v))}"' for k,v in kw.items() if v is not None)
def el(tag, **kw): return f'<{tag} {attrs(**kw)}/>'
def circle(x,y,r,fill,**kw): return el('circle',cx=x,cy=y,r=r,fill=fill,**kw)
def ellipse(x,y,rx,ry,fill,**kw): return el('ellipse',cx=x,cy=y,rx=rx,ry=ry,fill=fill,**kw)
def path(d,fill='none',**kw): return el('path',d=d,fill=fill,**kw)
def line(x1,y1,x2,y2,stroke,**kw): return el('line',x1=x1,y1=y1,x2=x2,y2=y2,stroke=stroke,**kw)
def rect(x,y,w,h,fill,**kw): return el('rect',x=x,y=y,width=w,height=h,fill=fill,**kw)
def group(body,**kw): return f'<g {attrs(**kw)}>{body}</g>'
def move(body,x=0,y=0,s=1,r=0): return group(body,transform=f'translate({x} {y}) rotate({r}) scale({s})')
def has(n,*xs): return any(x in n for x in xs)
def poly(points,fill,**kw): return el('polygon',points=' '.join(f'{fmt(x)},{fmt(y)}' for x,y in points),fill=fill,**kw)
def points(cx,cy,r,num,start=0): return [(cx+math.cos(start+i*math.tau/num)*r,cy+math.sin(start+i*math.tau/num)*r) for i in range(num)]
def star(cx,cy,r1,r2,num=5,fill='#567145',rotate=-math.pi/2,**kw):
    ps=[]
    for i in range(num*2):
        r=r1 if i%2==0 else r2;a=rotate+math.pi*i/num;ps.append((cx+r*math.cos(a),cy+r*math.sin(a)))
    return poly(ps,fill,**kw)

def leaf(x=0,y=0,size=1,rot=0,color='url(#leaf)'):
    s=path('M0 0 C-28-19-31-58 1-91 C29-61 29-26 0 0Z',color)
    s+=path('M0-3 Q4-47 1-83',stroke='#bdc589',stroke_width=1.2,opacity=.6)
    for j in [22,37,52,65]:
        s+=path(f'M2 {-j} Q-8 {-j-4} -15 {-j-14} M2 {-j} Q12 {-j-6} 17 {-j-16}',stroke='#c7ce96',stroke_width=.75,opacity=.33)
    return move(s,x,y,size,rot)

def speckles(rng,cx,cy,rx,ry,num,color,lo=.65,hi=1.6,opacity=.36):
    out=[]
    for _ in range(num):
        a=rng.random()*math.tau;r=math.sqrt(rng.random());x=cx+math.cos(a)*r*rx;y=cy+math.sin(a)*r*ry
        out.append(ellipse(x,y,rng.uniform(lo,hi),rng.uniform(lo,hi)*.68,color,opacity=opacity))
    return ''.join(out)

DEFS='''<defs>
<radialGradient id="red" cx="30%" cy="21%" r="83%"><stop stop-color="#f68667"/><stop offset=".39" stop-color="#d84937"/><stop offset=".83" stop-color="#ae2d2b"/><stop offset="1" stop-color="#7c272c"/></radialGradient>
<radialGradient id="berry" cx="30%" cy="23%" r="80%"><stop stop-color="#a4abc5"/><stop offset=".4" stop-color="#68738f"/><stop offset=".82" stop-color="#42475e"/><stop offset="1" stop-color="#282e45"/></radialGradient>
<radialGradient id="purple" cx="25%" cy="20%" r="87%"><stop stop-color="#b690ad"/><stop offset=".45" stop-color="#755273"/><stop offset="1" stop-color="#3e334c"/></radialGradient>
<linearGradient id="leaf" x1="0" y1="0" x2="1" y2=".65"><stop stop-color="#9aaa66"/><stop offset=".43" stop-color="#6f864e"/><stop offset="1" stop-color="#3f6449"/></linearGradient>
<radialGradient id="green" cx="28%" cy="25%" r="84%"><stop stop-color="#c6cb6d"/><stop offset=".42" stop-color="#94ad58"/><stop offset="1" stop-color="#527846"/></radialGradient>
<radialGradient id="gold" cx="26%" cy="20%" r="89%"><stop stop-color="#f9d991"/><stop offset=".52" stop-color="#dea94e"/><stop offset="1" stop-color="#a86632"/></radialGradient>
<radialGradient id="orange" cx="29%" cy="20%" r="87%"><stop stop-color="#ffd795"/><stop offset=".4" stop-color="#edab55"/><stop offset="1" stop-color="#ce7341"/></radialGradient>
<radialGradient id="brown" cx="26%" cy="23%" r="80%"><stop stop-color="#c6976c"/><stop offset=".45" stop-color="#946948"/><stop offset="1" stop-color="#624633"/></radialGradient>
<radialGradient id="cream" cx="26%" cy="18%" r="87%"><stop stop-color="#fffdf1"/><stop offset=".5" stop-color="#ece3c5"/><stop offset="1" stop-color="#c4b28d"/></radialGradient>
<linearGradient id="milk" x1="0" y1="0" x2="1" y2=".3"><stop stop-color="#e2dbca"/><stop offset=".3" stop-color="#fffdf2"/><stop offset=".74" stop-color="#f7f2e4"/><stop offset="1" stop-color="#d9d1bf"/></linearGradient>
<linearGradient id="glass" x1="0" y1="0" x2="1" y2="0"><stop stop-color="#bfd0c8" stop-opacity=".45"/><stop offset=".2" stop-color="#fffef6" stop-opacity=".8"/><stop offset=".5" stop-color="#e5eadb" stop-opacity=".1"/><stop offset=".83" stop-color="#cad5c6" stop-opacity=".35"/><stop offset="1" stop-color="#9dafa4" stop-opacity=".5"/></linearGradient>
<linearGradient id="fish" x1="0" y1="0" x2="0" y2="1"><stop stop-color="#536f75"/><stop offset=".4" stop-color="#9caea7"/><stop offset=".69" stop-color="#e6e1c8"/><stop offset="1" stop-color="#b0afa0"/></linearGradient>
<linearGradient id="salmon" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#f6b091"/><stop offset=".5" stop-color="#dc826b"/><stop offset="1" stop-color="#b85d4f"/></linearGradient>
<linearGradient id="meat" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#cc8b7e"/><stop offset=".4" stop-color="#a64f4c"/><stop offset="1" stop-color="#70393a"/></linearGradient>
<radialGradient id="roast" cx="26%" cy="20%" r="80%"><stop stop-color="#d49a60"/><stop offset=".4" stop-color="#a66c3e"/><stop offset="1" stop-color="#6c4331"/></radialGradient>
<radialGradient id="oil" cx="29%" cy="20%" r="84%"><stop stop-color="#ecd78b"/><stop offset=".57" stop-color="#b3a150"/><stop offset="1" stop-color="#74703b"/></radialGradient>
<filter id="ground" x="-60%" y="-200%" width="220%" height="500%"><feGaussianBlur stdDeviation="9"/></filter>
<filter id="soft" x="-20%" y="-20%" width="140%" height="150%"><feDropShadow dx="0" dy="5" stdDeviation="4" flood-color="#685438" flood-opacity=".13"/></filter>
<filter id="paper"><feTurbulence type="fractalNoise" baseFrequency=".69" numOctaves="2" stitchTiles="stitch"/><feColorMatrix type="saturate" values="0"/><feComponentTransfer><feFuncA type="linear" slope=".042"/></feComponentTransfer><feBlend in="SourceGraphic" mode="multiply"/></filter>
</defs>'''

def strawberry(rng,n):
    def berry(x,y,s,r):
        body=path('M-1-64 C-20-85-73-76-81-28 C-92 28-35 95 0 123 C32 100 88 25 80-28 C73-73 30-85-1-64Z','url(#red)',stroke='#a8342c',stroke_width=1)
        for row in range(8):
            yy=-43+row*20;ww=68*(1-(max(0,yy+5)/150)**1.6)
            for j in range(-3,4):
                xx=j*19+(9 if row%2 else 0)
                if abs(xx)<ww:
                    body+=move(ellipse(0,0,2.2,4.8,'#f7d791',stroke='#a64732',stroke_width=.8),xx,yy,1,-10+xx*.23)
                    body+=ellipse(xx-1,yy-1,1,2.5,'#fff0bd',opacity=.7)
        body+=star(0,-64,54,12,7,'url(#leaf)',rotate=-1.55)
        body+=path('M0-66 Q10-94 22-102',stroke='#587345',stroke_width=7,stroke_linecap='round')
        return move(group(body,filter='url(#soft)'),x,y,s,r)
    body=berry(178,211,.86,-20)+berry(284,244,.95,18)
    body+=leaf(163,145,.45,-60)
    return body

def blueberries(rng,n):
    body=leaf(160,194,.94,-54)+leaf(291,180,.63,42)
    coords=[(210,185,38),(276,193,41),(155,241,41),(222,243,45),(307,258,45),(190,310,41),(260,325,40),(336,320,34),(127,311,33)]
    if has(n,'枸杞'):
        return ''.join(move(ellipse(0,0,12,31,'url(#red)',stroke='#b44737',stroke_width=1),rng.uniform(132,346),rng.uniform(181,323),1,rng.uniform(-50,60)) for _ in range(24))
    for x,y,r in coords:
        body+=circle(x,y,r,'url(#berry)',stroke='#5e6680',stroke_width=.6)
        body+=ellipse(x-12,y-15,r*.45,r*.2,'#d6d6dd',opacity=.18,transform=f'rotate(-29 {x-12} {y-15})')
        body+=star(x+r*.14,y-r*.3,r*.23,r*.11,5,'#556078',rotate=.1,stroke='#9ba0b6',stroke_width=1.2)
        body+=speckles(rng,x,y,r*.87,r*.87,18,'#dbdce1',.4,.85,.23)
    return body

def bramble(rng,n):
    dark=has(n,'黑莓','黑覆盆','桑','巴西莓');color='url(#purple)' if dark else 'url(#red)'
    body=leaf(200,206,1,-28)+leaf(296,175,.7,47)
    for cx,cy,scale in [(166,244,.93),(284,258,1.05),(249,335,.65)]:
        s=''
        for row in range(6):
            num=6-int(row*.65)
            for j in range(num):
                x=(j-(num-1)/2)*18+rng.uniform(-2,2);y=row*18-44
                s+=circle(x,y,13,color,stroke='#693f4a' if dark else '#9f3b3c',stroke_width=.6)
                s+=ellipse(x-3,y-5,3,1.7,'#f8c6bb',opacity=.27)
        s+=star(0,-59,31,11,5,'url(#leaf)')
        body+=move(s,cx,cy,scale,-13 if cx<200 else 16)
    return body

def apple(rng,n):
    green=has(n,'青苹果','金冠');gold=has(n,'金冠','五爪');color='url(#green)' if green else 'url(#gold)' if gold else 'url(#red)'
    body=path('M225 152 C173 115 108 164 109 239 C109 311 157 352 207 340 Q233 334 251 341 C300 354 351 314 353 240 C356 165 291 121 242 152 Q233 159 225 152Z',color,stroke='#9e6c48',stroke_width=1)
    body+=path('M230 158 Q219 125 237 103',stroke='#765844',stroke_width=9,stroke_linecap='round')+leaf(236,139,.76,55)
    body+=path('M231 165 Q235 177 234 187',stroke='#803c38',stroke_width=2,opacity=.55)
    body+=speckles(rng,231,245,105,87,150,'#f7db98',.5,1.3,.35)
    body+=ellipse(160,203,15,35,'#ffead1',opacity=.14,transform='rotate(25 160 203)')
    if has(n,'汁'): return juice(rng,n)
    return body

def pear(rng,n):
    color='url(#brown)' if has(n,'博斯','会议') else 'url(#gold)' if has(n,'亚洲') else 'url(#green)'
    b=path('M216 136 C186 142 207 189 162 225 C115 263 119 330 173 354 C227 379 296 353 313 305 C329 266 311 240 285 215 C254 184 262 128 230 132Z',color,stroke='#879052',stroke_width=1)
    b+=path('M224 140 Q213 110 237 88',stroke='#775840',stroke_width=8,stroke_linecap='round')+leaf(229,135,.71,54)
    b+=speckles(rng,224,286,78,62,130,'#765d37',.45,1.2,.38)
    b+=path('M164 269 Q148 309 182 330',stroke='#f6ebba',stroke_width=10,stroke_linecap='round',opacity=.15)
    return b

def peach(rng,n):
    b=leaf(273,159,.9,41)+path('M235 157 C165 113 102 176 115 253 C127 329 189 366 242 340 C302 365 364 303 360 237 C355 171 297 121 235 157Z','url(#orange)',stroke='#c98d58',stroke_width=1)
    b+=path('M245 158 C211 203 246 280 239 337',stroke='#c87053',stroke_width=3,opacity=.67)
    b+=ellipse(165,212,34,49,'#c8564c',opacity=.22,transform='rotate(25 165 212)')+ellipse(300,271,36,47,'#c76853',opacity=.19)
    b+=path('M236 160 Q231 143 239 128',stroke='#846043',stroke_width=6,stroke_linecap='round')
    b+=speckles(rng,235,248,98,78,170,'#ffe6bf',.4,1.1,.29)
    return b

def mango(rng,n):
    b=path('M160 149 C203 113 292 139 319 214 C349 293 292 367 207 359 C149 354 122 308 127 243 C132 201 131 174 160 149Z','url(#orange)',stroke='#bd8042',stroke_width=1)
    b+=path('M161 149 C177 126 191 145 204 134',stroke='#737248',stroke_width=5)+leaf(171,150,.65,-42)
    b+=path('M142 205 Q172 140 230 151 C192 172 170 219 173 293 C141 276 134 244 142 205Z','#b66659',opacity=.35)
    b+=speckles(rng,212,259,69,87,75,'#f6db91',.5,1.1,.43)
    cut=ellipse(0,0,62,101,'#e9b157',stroke='#c9a34e',stroke_width=4)+ellipse(0,0,54,92,'#f3c96d')
    for x in [-28,0,28]:cut+=path(f'M{x} -78 Q{x-4} 0 {x} 78',stroke='#dca449',stroke_width=2,opacity=.65)
    for y in [-49,-13,23,59]:cut+=path(f'M-48 {y} Q0 {y+5} 48 {y}',stroke='#dca449',stroke_width=2,opacity=.65)
    return b+move(cut,328,302,.73,27)

def citrus(rng,n):
    lime=has(n,'莱姆','青柠','酢橘','酸橘');lemon=has(n,'柠檬','佛手');blood=has(n,'血橙');grape=has(n,'葡萄柚')
    rind='#75854a' if lime else '#e9c950' if lemon else '#e19a46';flesh='#c3ca79' if lime else '#f4dfa0' if lemon else '#bd5750' if blood else '#edab94' if grape else '#f1b45d'
    if lemon:
        b=path('M110 232 C126 171 205 154 258 179 L279 184 L284 206 C303 260 247 306 195 306 C147 308 112 294 106 257 L95 246Z','url(#gold)',stroke=rind,stroke_width=2)
    else:b=ellipse(191,230,93,88,'url(#green)' if lime else 'url(#orange)',stroke=rind,stroke_width=1)
    b+=leaf(181,152,.76,60)+speckles(rng,184,230,77,72,170,'#996b36',.4,1.3,.17)
    cx,cy,rr=292,295,83
    b+=circle(cx,cy,rr,rind)+circle(cx,cy,rr-6,'#faf2d6')
    for i in range(10):
        a=math.tau*i/10;b0=a+.07;b1=a+math.tau/10-.07
        p0=(cx+math.cos(b0)*7,cy+math.sin(b0)*7);p1=(cx+math.cos(b0)*69,cy+math.sin(b0)*69);p2=(cx+math.cos(b1)*69,cy+math.sin(b1)*69);p3=(cx+math.cos(b1)*7,cy+math.sin(b1)*7)
        b+=path(f'M{p0[0]} {p0[1]} L{p1[0]} {p1[1]} A69 69 0 0 1 {p2[0]} {p2[1]} L{p3[0]} {p3[1]}Z',flesh)
        for j in range(8):
            aa=b0+(b1-b0)*(j+.5)/8;dist=rng.uniform(28,46)
            b+=line(cx+math.cos(aa)*dist,cy+math.sin(aa)*dist,cx+math.cos(aa)*64,cy+math.sin(aa)*64,'#fff8d9',stroke_width=.85,opacity=.32)
    b+=circle(cx,cy,6,'#faf2d6')
    return b

def banana(rng,n):
    b=''
    for dx,dy,rot in [(0,0,-8),(24,7,1),(39,21,12)]:
        q=path('M136 164 C132 252 188 305 310 278 Q333 278 343 265 Q325 325 255 340 C150 362 90 261 109 186Z','url(#gold)',stroke='#c59f4b',stroke_width=1.5)
        q+=path('M122 183 C121 276 191 338 299 302',stroke='#fff0a8',stroke_width=4,opacity=.59)
        q+=path('M137 167 L124 145 L109 158 L110 185Z','#a89550')+path('M311 278 L339 264 L347 269 L334 283Z','#796345')
        q+=speckles(rng,184,306,32,9,7,'#93683e',1,2,.65)
        b+=move(q,dx,dy,.9,rot)
    return b

def grapes(rng,n):
    green=has(n,'白葡萄','绿葡萄');col='url(#green)' if green else 'url(#purple)'
    b=leaf(196,170,1.07,-49)+leaf(235,153,.72,60)+path('M239 131 Q251 153 245 194',stroke='#7d7350',stroke_width=6)
    for row in range(5):
        num=[3,4,4,3,1][row]
        for j in range(num):
            x=239+(j-(num-1)/2)*44+rng.uniform(-5,5);y=185+row*39+rng.uniform(-3,3)
            b+=ellipse(x,y,27,31,col,stroke='#748357' if green else '#69536e',stroke_width=.6)
            b+=ellipse(x-8,y-12,6,3,'#e5dbe3',opacity=.27,transform=f'rotate(-35 {x-8} {y-12})')
    return b

def pineapple(rng,n):
    b=''
    for i in range(9):
        a=(i-4)*13
        b+=move(path('M0 35 C-24-5-19-69-13-119 Q17-65 4 35Z','url(#leaf)',stroke='#677746',stroke_width=1),234,169,1,a)
    b+=ellipse(234,272,92,112,'url(#gold)',stroke='#9e893f',stroke_width=2)
    for row in range(7):
        yy=184+row*30;ww=math.sqrt(max(0,1-((yy-272)/112)**2))*88
        for j in range(-3,4):
            xx=234+j*30+(15 if row%2 else 0)
            if abs(xx-234)<ww-5:
                b+=poly([(xx,yy-14),(xx+14,yy),(xx,yy+14),(xx-14,yy)],'none',stroke='#a78b49',stroke_width=1.5)
                b+=path(f'M{xx-4} {yy+3} l4-7 5 7',stroke='#9e8045',stroke_width=2)
    return b

def kiwi(rng,n):
    b=ellipse(182,218,84,100,'url(#brown)',transform='rotate(-32 182 218)',stroke='#896d4c',stroke_width=2)
    for _ in range(180):
        a=rng.random()*math.tau;t=math.sqrt(rng.random());x=182+math.cos(a)*t*77;y=220+math.sin(a)*t*86
        b+=line(x,y,x+3,y-5,'#d4b181',stroke_width=.7,opacity=.55)
    cx,cy=292,294
    b+=ellipse(cx,cy,88,82,'#987544')+ellipse(cx,cy,82,76,'#b1bc60')+ellipse(cx,cy,73,67,'#a8c373')
    for i in range(44):
        a=i*math.tau/44;x=cx+math.cos(a)*63;y=cy+math.sin(a)*58
        b+=line(cx,cy,x,y,'#e1e6aa',stroke_width=1,opacity=.7)
        if i%2==0:b+=move(ellipse(0,0,2.1,4,'#333d29'),cx+math.cos(a)*42,cy+math.sin(a)*38,1,a*180/math.pi-90)
    b+=ellipse(cx,cy,21,30,'#e7e5b6',transform=f'rotate(18 {cx} {cy})')
    return b

def avocado(rng,n):
    b=path('M154 144 C194 106 220 154 217 193 C255 234 263 293 229 337 C207 369 148 371 119 332 C90 293 115 222 136 194 C130 169 137 150 154 144Z','url(#green)',stroke='#486347',stroke_width=3)
    b+=speckles(rng,173,284,53,68,220,'#374c37',.7,2,.37)
    cut=path('M0-108 C42-121 39-48 56-14 C97 60 55 110 0 107 C-62 106-90 61-53-13 C-37-49-33-106 0-108Z','#71804b',stroke='#506f3e',stroke_width=3)
    cut+=path('M0-101 C34-112 31-40 48-10 C83 53 50 99 0 98 C-52 98-77 53-46-11 C-29-47-27-100 0-101Z','#dadb91')
    cut+=ellipse(0,39,37,44,'#c7ca7d')+ellipse(0,35,32,38,'url(#brown)')+ellipse(-10,22,10,12,'#d6ac7e',opacity=.4)
    return b+move(cut,304,267,1,17)

def coconut(rng,n):
    b=ellipse(183,215,86,87,'url(#brown)',stroke='#6f5138',stroke_width=2)
    for i in range(80):
        a=rng.uniform(0,math.tau);rr=rng.uniform(20,80);x=183+math.cos(a)*rr;y=215+math.sin(a)*rr
        b+=path(f'M{x} {y} q12 -8 22-9',stroke='#d3ae78',stroke_width=.9,opacity=.4)
    for x,y in [(166,169),(187,164),(179,187)]:b+=ellipse(x,y,6,7,'#533f2d')
    b+=ellipse(296,295,93,75,'#765438',transform='rotate(-18 296 295)')+ellipse(296,283,90,63,'#e1d6b8',transform='rotate(-18 296 283)')+ellipse(296,282,73,48,'#fffbee',transform='rotate(-18 296 282)')+ellipse(296,286,47,27,'#e9e8d8',transform='rotate(-18 296 286)')
    return b

def cutfruit(rng,n,kind):
    if kind=='watermelon':
        b=path('M99 308 L271 124 L385 318 Q250 411 99 308Z','#4e7449',stroke='#3d6041',stroke_width=2)
        b+=path('M110 306 L270 141 L371 313 Q247 393 110 306Z','#dce0a3')+path('M120 301 L270 153 L358 308 Q244 376 120 301Z','#d87469')
        for x,y,r in [(210,251,20),(242,215,13),(286,261,-16),(251,296,10),(188,304,24),(316,307,-17)]:b+=move(ellipse(0,0,3.5,7,'#594039'),x,y,1,r)
        return b
    if kind=='papaya':outer='#c68e36';inner='#eeae60';pit='#454739';shape='M0-112 C78-127 98 79 18 112 C-63 141-100-77 0-112Z'
    elif kind=='fig':outer='#67505e';inner='#c9827b';pit='#eacfa4';shape='M0-111 C26-72 72-26 74 37 C72 89 27 112-19 103 C-73 90-84 32-44-25 C-29-49-22-91 0-111Z'
    elif kind=='dragon':outer='#c75568';inner='#f1e9d4';pit='#42413b';shape='M0-112 C91-114 101 100 8 116 C-98 122-102-103 0-112Z'
    elif kind=='passion':outer='#705167';inner='#d5b85b';pit='#494831';shape='M0-88 C118-92 114 92 0 93 C-114 90-117-87 0-88Z'
    elif kind=='guava':outer='#b0b56b';inner='#d99a92';pit='#eee0ab';shape='M0-104 C88-109 108 93 8 111 C-91 107-93-100 0-104Z'
    else:outer='#d0b665';inner='#e1d2a0';pit='#ac8b58';shape='M0-103 C94-109 104 99 0 109 C-102 103-103-97 0-103Z'
    b=ellipse(173,226,84,96,outer,stroke='#857754',stroke_width=1)+leaf(177,142,.65,34)
    cut=path(shape,outer,stroke='#8a765a',stroke_width=1)+group(path(shape,inner),transform='scale(.9)')
    if kind=='papaya':
        cut+=ellipse(0,0,26,81,'#d18d4d')
        for i in range(60):
            a=rng.random()*math.tau;t=math.sqrt(rng.random());x=math.cos(a)*t*22;y=math.sin(a)*t*75
            cut+=circle(x,y,rng.uniform(3,5),pit,stroke='#797352',stroke_width=.7)
    elif kind=='fig':
        cut+=path('M0-79 Q-2-27-41 20 Q-40 82 0 86 Q47 75 45 26 Q26-16 0-79Z','#b7676c')
        cut+=speckles(rng,0,28,37,55,180,'#eed6a5',.9,1.8,.95)
    else:
        cut+=speckles(rng,0,0,59,kind=='passion' and 62 or 78,100,pit,1,kind=='passion' and 3 or 1.8,.9)
    return b+move(cut,299,279,.93,18)

def cherry(rng,n):
    b=leaf(255,143,.8,66)
    col='url(#gold)' if has(n,'白樱桃') else 'url(#purple)' if has(n,'黑','李子') else 'url(#red)'
    for x,y,rr in [(172,276,49),(284,306,54),(324,231,46)]:
        b+=path(f'M{x} {y-rr+7} Q{x+8} 176 253 141',stroke='#807247',stroke_width=4,stroke_linecap='round')
        b+=ellipse(x,y,rr,rr*.9,col,stroke='#8b4243',stroke_width=.6)+ellipse(x-14,y-17,8,4,'#f3d3c3',opacity=.35,transform=f'rotate(-35 {x-14} {y-17})')
        b+=path(f'M{x-6} {y-rr+10} q8 6 15 0',stroke='#733e3a',stroke_width=2)
    return b

def exotic(rng,n,kind):
    if kind=='pomegranate':
        b=ellipse(184,237,88,88,'url(#red)')+star(182,144,24,11,6,'#b2734f')
        b+=ellipse(289,292,87,77,'#c98461')+ellipse(289,287,81,71,'#efddb3')
        for _ in range(110):
            a=rng.random()*math.tau;t=math.sqrt(rng.random());x=289+math.cos(a)*t*69;y=287+math.sin(a)*t*58
            b+=ellipse(x,y,6,7,'#a53f49',stroke='#d88981',stroke_width=1)
        for a in [0,2.1,4.2]:b+=line(289,287,289+math.cos(a)*68,287+math.sin(a)*58,'#f1e2bd',stroke_width=5)
        return b
    if kind=='lychee':
        b=leaf(208,169,.9,-47)
        for x,y,r in [(159,240,54),(257,240,58),(223,325,50)]:
            b+=circle(x,y,r,'#b97563',stroke='#996448',stroke_width=1)
            for _ in range(95):
                a=rng.random()*math.tau;t=math.sqrt(rng.random());xx=x+math.cos(a)*t*(r-5);yy=y+math.sin(a)*t*(r-5)
                b+=path(f'M{xx-2} {yy+2} l3-4 3 4',stroke='#ebaf8c',stroke_width=1.3,opacity=.63)
        b+=ellipse(327,310,42,44,'url(#cream)')+ellipse(332,312,16,24,'#69503d')
        return b
    if kind=='durian':
        b=ellipse(216,251,110,124,'#9a9a57',transform='rotate(-18 216 251)')
        for y in range(145,365,20):
            for x in range(117,324,21):
                if ((x-216)/108)**2+((y-251)/123)**2<.91:
                    b+=poly([(x-9,y+8),(x+3,y-10),(x+10,y+7)],'#c4bd79',stroke='#818443',stroke_width=.8)
        b+=path('M321 228 C381 218 395 339 332 358 C283 360 278 263 321 228Z','#e7ddbd')
        b+=path('M327 244 C353 229 379 275 367 315 C342 350 304 345 310 307 C303 278 311 256 327 244Z','#e2c781')
        return b
    if kind=='starfruit':
        b=path('M103 272 L202 161 L285 150 L371 268 L284 346 L177 350Z','url(#gold)',stroke='#aeb55d',stroke_width=3)
        for a in [(105,270,284,345),(202,162,285,346),(284,151,177,349)]:b+=line(*a,'#c3b956',stroke_width=4)
        b+=star(315,310,75,32,5,'#f0d97e',rotate=-1.58,stroke='#a7b45b',stroke_width=4)+star(315,310,45,15,5,'#f2e6b1',rotate=-1.58)
        return b
    return cutfruit(rng,n,'melon')


def specific_fruit(rng,n,kind):
    if kind=='mangosteen':
        b=ellipse(183,224,81,81,'url(#purple)',stroke='#644354',stroke_width=2)+star(182,149,49,19,4,'url(#leaf)',rotate=.14)
        b+=path('M183 150 Q187 127 199 116',stroke='#7f7850',stroke_width=8,stroke_linecap='round')
        b+=ellipse(293,295,88,73,'#7e5365',stroke='#5f4356',stroke_width=3)+ellipse(293,293,75,61,'#b07587')
        for i in range(6):
            a=i*60;q=ellipse(0,-25,19,34,'url(#milk)',stroke='#dbceb4',stroke_width=1)
            b+=move(q,293,293,1,a)
        b+=circle(293,293,8,'#eee3c9')
        return b
    if kind=='custard_apple':
        b=path('M230 147 C146 139 108 217 125 287 C139 348 209 369 258 356 C319 354 365 289 341 218 C324 161 271 142 230 147Z','#98ac70',stroke='#7d8d59',stroke_width=2)
        for row in range(7):
            y=170+row*27
            for j in range(7):
                x=147+j*28+(14 if row%2 else 0)
                if ((x-235)/104)**2+((y-253)/105)**2<.87:
                    b+=path(f'M{x-14} {y} Q{x} {y-17} {x+14} {y} Q{x+12} {y+15} {x} {y+19} Q{x-15} {y+12} {x-14} {y}Z','#b5c38b',stroke='#82985f',stroke_width=1.5)
        b+=path('M230 155 Q231 128 250 115',stroke='#7a7850',stroke_width=8,stroke_linecap='round')+leaf(237,151,.66,57)
        return b
    if kind in ['raisins','barberry']:
        b=''
        for _ in range(40 if kind=='raisins' else 49):
            a=rng.random()*math.tau;t=math.sqrt(rng.random());x=237+math.cos(a)*t*115;y=264+math.sin(a)*t*86
            q=ellipse(0,0,kind=='raisins' and 13 or 8,kind=='raisins' and 17 or 19,'#695243' if kind=='raisins' else '#a55342',stroke='#574737' if kind=='raisins' else '#864837',stroke_width=.8)
            for i in [-7,0,7]:q+=path(f'M{i} -11 q-5 9 0 24',stroke='#ac8860' if kind=='raisins' else '#d29466',stroke_width=.8,opacity=.65)
            b+=move(q,x,y,1,rng.uniform(-180,180))
        return b
    if kind=='loquat':
        b=leaf(198,185,1.08,-28)+leaf(278,177,.85,58)
        for x,y,s in [(174,254,.85),(270,232,1),(290,329,.73)]:
            q=ellipse(0,0,47,57,'url(#orange)',stroke='#ba9157',stroke_width=1)+star(0,46,10,4,5,'#77654b')+speckles(rng,0,0,38,43,55,'#d5b074',.7,1.2,.4)
            b+=move(q,x,y,s,12)
        b+=ellipse(191,332,40,43,'#e5b975',stroke='#c99158',stroke_width=3)+ellipse(190,332,16,27,'#79563c')+ellipse(177,326,11,20,'#9b7250')
        return b
    if kind=='persimmon':
        b=path('M125 210 C138 157 196 147 232 163 C278 142 337 170 350 217 C375 282 318 357 239 353 C159 360 101 280 125 210Z','url(#orange)',stroke='#c28b4d',stroke_width=1.3)
        b+=star(237,173,49,19,4,'#7b8451',rotate=.2)+path('M237 173 Q231 155 242 137',stroke='#736947',stroke_width=7,stroke_linecap='round')
        b+=path('M160 217 Q138 277 174 309',stroke='#ffe0a6',stroke_width=9,stroke_linecap='round',opacity=.24)
        return b
    if kind=='waxapple':
        b=leaf(236,160,.78,45)
        for x,y,s,r in [(183,223,1,-15),(299,255,.85,16)]:
            q=path('M-25-77 C-42-52-18-6-61 50 C-90 84-47 106 1 91 C55 109 92 78 63 48 C22-4 40-52 26-75Z','url(#red)',stroke='#ac655c',stroke_width=1)
            q+=path('M-17-51 Q-17 21-43 65',stroke='#f4c7aa',stroke_width=8,stroke_linecap='round',opacity=.37)+path('M-47 78 Q0 61 48 79',stroke='#a94948',stroke_width=2)
            b+=move(q,x,y,s,r)
        return b
    if kind=='tamarind':
        b=''
        for x,y,s,r in [(154,196,1,-22),(266,195,.9,24),(262,327,.63,64)]:
            q=path('M-12-59 C17-78 38-37 20-15 C48 0 41 34 27 40 C48 63 30 107 3 99 C-24 100-29 68-22 53 C-41 29-33 5-24-7 C-43-36-32-57-12-59Z','#bb9a6a',stroke='#967c54',stroke_width=2)
            for yy in [-23,20,61]:q+=path(f'M-20 {yy} q18 7 42 0',stroke='#957b56',stroke_width=2)
            q+=speckles(rng,0,19,20,66,65,'#846647',.6,1.2,.36)
            b+=move(q,x,y,s,r)
        return b
    if kind=='quince':
        return pear(rng,'亚洲梨')+speckles(rng,225,280,56,49,65,'#ede6b3',.4,.8,.6)
    if kind=='dried_fruit':
        b=''
        for x,y,s,r in [(174,226,1,-17),(288,251,.95,23),(210,329,.78,1)]:
            q=ellipse(0,0,61,47,'#aa8259',stroke='#8c6d49',stroke_width=1.5)
            for i in range(18):
                a=i*math.tau/18;q+=path(f'M{math.cos(a)*12} {math.sin(a)*10} Q{math.cos(a+.2)*35} {math.sin(a+.2)*30} {math.cos(a)*55} {math.sin(a)*42}',stroke='#755a3f',stroke_width=1.5,opacity=.72)
            q+=circle(0,0,7,'#c1a477')
            b+=move(q,x,y,s,r)
        return b
    if kind=='burger':
        b=ellipse(237,318,125,42,'url(#gold)',stroke='#b18452',stroke_width=2)+ellipse(237,289,126,28,'#66503b')+path('M116 276 L143 263 L164 280 L191 261 L217 279 L247 262 L270 278 L300 261 L323 278 L358 267 L355 290 L119 291Z','#91a36a')+ellipse(237,254,122,24,'#ca7560')
        b+=path('M110 253 C118 132 351 130 367 253 Q237 287 110 253Z','url(#gold)',stroke='#ba8d54',stroke_width=2)+speckles(rng,237,218,104,38,63,'#f2e0ae',1,3,.95)
        return b
    return identity_unresolved(rng,n)

def carrot(rng,n):
    purple=has(n,'紫');white=has(n,'防风','萝卜','白','香芹根') and not has(n,'胡萝卜');color='#ab6c84' if purple else '#e7ddbd' if white else '#db985e'
    b=''
    for dx,rot in [(0,-20),(70,9)]:
        root=path('M-28-59 C-42-72-27-94 0-93 C33-94 43-68 28-47 L-3 151 Q-13 179-17 143Z',color,stroke='#a28665',stroke_width=1)
        for i in range(12):
            y=-69+i*17;w=max(4,24-i*1.4);root+=path(f'M{-w} {y} q{w*.5} 5 {w} 2',stroke='#957554' if white else '#ac673d',stroke_width=1.3,opacity=.48)
        root+=leaf(0,-86,.9,-20)+leaf(4,-89,1.03,13)+leaf(-4,-86,.66,-45)
        b+=move(root,199+dx,226,1,rot)
    return b

def tomato(rng,n):
    b=''
    c='url(#orange)' if has(n,'橘色','黄') else 'url(#red)'
    for x,y,s in [(179,234,1),(305,277,.78)]:
        q=ellipse(0,0,86,72,c,stroke='#b5633e',stroke_width=.8)
        for xx in [-35,36]:q+=path(f'M{xx/2}-62 Q{xx*1.7} 0 {xx/2} 63',stroke='#ca6b49',stroke_width=2,opacity=.35)
        q+=star(0,-57,43,10,6,'url(#leaf)',rotate=-1.3)+path('M0-57 Q6-81 16-83',stroke='#627741',stroke_width=5,stroke_linecap='round')
        q+=ellipse(-30,-25,13,7,'#ffd0a3',opacity=.29,transform='rotate(-30 -30 -25)')
        b+=move(q,x,y,s,-15 if x<200 else 19)
    return b

def pepper(rng,n):
    green=has(n,'青','绿');yellow=has(n,'黄');fill='url(#green)' if green else 'url(#gold)' if yellow else 'url(#red)'
    if has(n,'甜椒','哈瓦那','罗可多'):
        b=path('M222 153 C159 118 120 159 126 208 C113 251 131 343 186 344 C210 360 238 356 255 346 C309 361 339 313 340 237 C350 180 310 128 265 148Z',fill,stroke='#875338',stroke_width=1)
        b+=path('M217 165 C179 195 193 307 188 338 M259 162 C290 219 248 307 257 338',stroke='#ffe5b5',stroke_width=2,opacity=.3)
        b+=path('M218 155 Q225 116 247 100 L265 111 Q242 132 247 160Z','url(#leaf)')
        return b
    b=''
    for x,y,s,r in [(195,145,1,-22),(283,170,.94,13),(340,223,.63,49)]:
        q=path('M0 0 C-36 41-45 133-10 180 Q20 220 59 203 C-17 203 10 107 23 52 Q29 5 0 0Z',fill,stroke='#8c513e',stroke_width=1)
        q+=path('M1 13 Q13-18 32-28',stroke='#56713d',stroke_width=7,stroke_linecap='round')+path('M-9 29 Q-22 99-10 135',stroke='#ffeac0',stroke_width=3,opacity=.35)
        b+=move(q,x,y,s,r)
    return b

def onion(rng,n):
    garlic=has(n,'蒜');red=has(n,'红葱','紫');col='#c3a39c' if red else '#d5bb85'
    if garlic:
        b=path('M212 134 L243 137 L256 196 C337 214 360 280 315 326 C267 365 188 358 145 314 C115 272 144 217 201 199Z','url(#cream)',stroke='#b7a68d',stroke_width=1)
        for x in [176,202,228,252,280]:b+=path(f'M223 196 Q{x-30} 269 {x} 337',stroke='#c1ad9b',stroke_width=1.5,opacity=.6)
        b+=path('M217 197 L215 137 M231 196 L233 139',stroke='#bca486',stroke_width=2)
        for i in range(11):b+=path(f'M{209+i*4} 342 q{rng.uniform(-15,15)} 11 {rng.uniform(-15,15)} 22',stroke='#bfa586',stroke_width=1)
        return b
    b=path('M229 143 C208 184 143 201 129 267 C112 341 190 372 246 357 C324 361 365 303 324 241 C302 204 262 186 250 143Z',col,stroke='#a18a69',stroke_width=1)
    for x in [155,186,219,252,285,314]:b+=path(f'M237 167 Q{x} 219 {x} 292 Q{x} 337 238 355',stroke='#f0e0bd' if not red else '#e0c5c0',stroke_width=2,opacity=.6)
    b+=path('M230 154 L219 113 L227 91 M239 156 L249 96 M248 151 L265 118',stroke='#a6976c',stroke_width=6,stroke_linecap='round')
    b+=ellipse(330,309,48,49,'#eadfc4',stroke='#ad9180',stroke_width=4)
    for r in [36,27,16,7]:b+=ellipse(330,309,r,r*1.03,'none',stroke='#b393a0' if red else '#c0b391',stroke_width=2)
    return b

def eggplant(rng,n):
    q=path('M189 140 C231 130 308 158 328 219 C353 294 302 369 220 366 C158 364 114 316 128 261 C146 199 154 169 189 140Z','url(#purple)',stroke='#4d4552',stroke_width=1)
    q+=star(202,159,53,20,6,'url(#leaf)',rotate=.1)+path('M210 145 Q222 116 246 107',stroke='#65754b',stroke_width=11,stroke_linecap='round')
    q+=path('M173 208 Q141 272 167 311',stroke='#cfb8c6',stroke_width=10,stroke_linecap='round',opacity=.22)
    return q

def cucumber(rng,n):
    b=move(ellipse(0,0,45,139,'url(#green)',stroke='#557b49',stroke_width=2),214,231,1,39)
    for i in range(12):
        y=148+i*15;x=290-(y-148)*.71
        b+=circle(x+rng.uniform(-18,18),y,2.2,'#436940',opacity=.65)
    for x,y,s,r in [(295,306,1,22),(330,334,.83,29)]:
        q=ellipse(0,0,46,35,'#61864d')+ellipse(0,0,40,30,'#d3d7a4')+ellipse(0,0,29,24,'#e7e6c3')
        for a in range(0,360,40):q+=move(ellipse(0,0,2.5,5,'#c5c698'),math.cos(math.radians(a))*18,math.sin(math.radians(a))*15,1,a)
        b+=move(q,x,y,s,r)
    return b

def squash(rng,n):
    b='';orange=not has(n,'冬瓜');col='#d39455' if orange else '#99af86'
    for dx,s in [(-66,.72),(-34,.92),(0,1),(34,.9),(65,.68)]:b+=ellipse(238+dx,275,60*s,95*s,col,stroke='#b2834f' if orange else '#748b6c',stroke_width=2)
    b+=path('M225 185 Q219 154 243 132 L261 141 Q244 161 247 190Z','#7e7752')
    return b

def potato(rng,n):
    purple=has(n,'紫','甜菜');sweet=has(n,'番薯','红番','番𫉄');color='#9d7a88' if purple else '#b18065' if sweet else '#c9ae7c'
    b=''
    for x,y,rx,ry,r in [(177,229,79,98,-35),(286,288,85,58,18)]:
        q=ellipse(0,0,rx,ry,color,stroke='#9d805c',stroke_width=1.2)
        q+=speckles(rng,0,0,rx*.86,ry*.87,95,'#796349',.6,1.6,.27)
        for _ in range(9):
            xx=rng.uniform(-rx*.7,rx*.7);yy=rng.uniform(-ry*.7,ry*.7);q+=path(f'M{xx-3} {yy} q3 3 6 0',stroke='#8d7351',stroke_width=1.3)
        b+=move(q,x,y,1,r)
    if has(n,'甜菜'):b+=leaf(192,145,.9,-27)+leaf(215,154,1,35)
    return b

def greens(rng,n):
    if has(n,'甘蓝','花椰','青花'):
        if has(n,'花椰','青花'):
            b=path('M210 350 L214 260 L251 262 L271 350Z','#b5c194')
            c='#dddcc0' if has(n,'花椰') else '#658251'
            for x,y,r in [(150,228,43),(187,189,42),(243,180,49),(296,213,46),(221,242,53),(320,253,34)]:
                b+=circle(x,y,r,c)
                for _ in range(28):
                    a=rng.random()*math.tau;t=math.sqrt(rng.random());xx=x+math.cos(a)*t*r;yy=y+math.sin(a)*t*r
                    b+=circle(xx,yy,rng.uniform(3,7),'#f1eed7' if has(n,'花椰') else '#7f9661',opacity=.8)
            return b
        b=ellipse(235,260,112,106,'#71865c' if not has(n,'红') else '#8d718b')
        for i in range(10):
            a=i*math.tau/10;x=235+math.cos(a)*65;y=263+math.sin(a)*60
            b+=path(f'M235 347 Q{x-60} {y+20} {x} {y-50} Q{x+60} {y-20} 238 340','none',stroke='#b7c396' if not has(n,'红') else '#baa4b4',stroke_width=2,opacity=.6)
        return b
    b=''
    for j in range(8):
        a=-65+j*18;x=222+rng.uniform(-18,18);y=332+rng.uniform(-9,8)
        b+=leaf(x,y,rng.uniform(1.4,2.1),a,'#8e6284' if has(n,'红菊','红酸','紫') else 'url(#leaf)')
    b+=path('M218 326 L233 362 M230 329 L231 362 M244 323 L235 362',stroke='#cad19f',stroke_width=7,stroke_linecap='round')
    return b

def asparagus(rng,n):
    b='';white=has(n,'白')
    for i in range(6):
        x=151+i*31;y=114+rng.uniform(-7,27);w=10
        q=path(f'M{x-w} 357 L{x-8} {y+38} Q{x-17} {y+13} {x} {y-9} Q{x+17} {y+13} {x+8} {y+38} L{x+w} 357Z','#dddcc0' if white else '#92a765',stroke='#aab38b' if white else '#728d55',stroke_width=1)
        for yy in range(int(y+16),338,25):q+=path(f'M{x-8} {yy} l8 6 8-6',stroke='#b7b894' if white else '#668555',stroke_width=1.3)
        b+=q
    return b

def peas(rng,n):
    b='';color='#d9bd8d' if has(n,'鹰嘴') else '#8eae66' if has(n,'豌','蚕','毛豆','绿') else '#966c5c' if has(n,'红','斑') else '#4c4842' if has(n,'黑') else '#ded3a7'
    if has(n,'四季','豌豆','毛豆','蚕豆'):
        pod=path('M117 170 C212 145 331 203 355 311 C253 313 147 264 117 170Z','#83a15c',stroke='#638449',stroke_width=3)
        pod+=path('M126 176 Q203 185 345 302',stroke='#c2ce8d',stroke_width=2)
        for x,y,r in [(163,193,19),(206,215,22),(252,244,24),(299,276,24)]:pod+=circle(x,y,r,'url(#green)',stroke='#7b9b55',stroke_width=1)
        b+=pod
    for _ in range(20):
        x=rng.uniform(128,351);y=rng.uniform(281,366)
        if has(n,'鹰嘴'):b+=path(f'M{x-11} {y} q-5-12 8-13 l9-5 2 8 q15 7 3 21 q-13 10-22-11Z',color,stroke='#b59c76',stroke_width=.7)
        else:b+=ellipse(x,y,rng.uniform(9,14),rng.uniform(7,10),color,stroke='#867c56',stroke_width=.65,transform=f'rotate({rng.uniform(-90,90)} {x} {y})')
    return b

def herb(rng,n):
    fine=has(n,'迷迭','莳萝','茴香','松针','百里','龙蒿','香茅','细香','韭','葱','班兰');purple=has(n,'紫苏','紫鼠')
    b=''
    if has(n,'香茅','韭','葱','班兰'):
        for i in range(10):
            x=205+i*7;end=105+i*25
            b+=path(f'M{x} 358 Q{x-55} 257 {end} 95 Q{x+2} 243 {x+7} 355Z','url(#leaf)',stroke='#8c9b67',stroke_width=.6)
        return b
    for j in range(5):
        x0=217+j*10;y0=362;xe=112+j*55;ye=121+rng.uniform(-18,31)
        b+=path(f'M{x0} {y0} Q{xe+17} 228 {xe} {ye}',stroke='#7f8c57',stroke_width=3,stroke_linecap='round')
        for i in range(7):
            t=(i+1)/8;x=x0+(xe-x0)*t;y=y0+(ye-y0)*t
            if fine:
                for side in [-1,1]:b+=path(f'M{x} {y} Q{x+side*22} {y-3} {x+side*31} {y-31}',stroke='#73894f',stroke_width=has(n,'莳萝','茴香') and 1.4 or 3,stroke_linecap='round')
                if has(n,'莳萝','茴香'):
                    for side in [-1,1]:b+=path(f'M{x+side*17} {y-17} l{side*12}-1 m-4-5 l{side*10}-7',stroke='#879969',stroke_width=.8)
            else:
                for side in [-1,1]:b+=leaf(x,y,.38+(1-t)*.13,side*55,'#8b667c' if purple else 'url(#leaf)')
    return b

def flower(rng,n):
    rose=has(n,'玫瑰');lavender=has(n,'薰衣','蕾香','墓香');yellow=has(n,'万寿','金盏','千日');purple=has(n,'紫罗','木槿','琉璃');white=has(n,'茉莉','洋甘','母菊','橙花','接骨','油菜')
    b=''
    if lavender:
        for j in range(7):
            x=155+j*28;y=131+rng.uniform(-13,44)
            b+=path(f'M239 371 Q{x} 260 {x} {y}',stroke='#7d8e60',stroke_width=2)
            for i in range(10):
                yy=y+i*9;xx=x+(-1 if i%2 else 1)*5
                b+=ellipse(xx,yy,5,8,'#a38ea9',transform=f'rotate({-25 if i%2 else 25} {xx} {yy})')
        return b
    colors=['#eee4d0','#fff3dc'] if white else ['#edbe64','#dca052'] if yellow else ['#bca4c2','#8e85ac'] if purple else ['#d9a0a4','#b97887']
    for cx,cy,s in [(172,224,1),(296,196,.93),(272,309,.76)]:
        b+=path(f'M239 366 Q{cx-15} 294 {cx} {cy}',stroke='#7f8d59',stroke_width=3)+leaf(cx-7,cy+67,.55,-60)
        if rose:
            q=''
            for layer in range(4,0,-1):
                for i in range(7):
                    a=i*math.tau/7+layer*.35;x=math.cos(a)*layer*9;y=math.sin(a)*layer*9
                    q+=ellipse(x,y,19,13,colors[layer%2],stroke='#b07b86',stroke_width=.6,transform=f'rotate({a*180/math.pi+90} {x} {y})')
            q+=circle(0,0,8,'#ad7885')
        else:
            q='';num=11 if white else 7
            for i in range(num):q+=move(ellipse(0,-24,white and 10 or 18,28,colors[i%2],stroke='#d2c7ac' if white else colors[1],stroke_width=.6),0,0,1,i*360/num)
            q+=circle(0,0,white and 14 or 11,'#c9a65a')+speckles(rng,0,0,9,9,25,'#806a3a',.7,1.4,.6)
        b+=move(q,cx,cy,s)
    return b

def mushroom(rng,n):
    if has(n,'松露'):
        b=''
        for cx,cy,rr in [(178,245,79),(293,281,80)]:
            col='#8e7859' if has(n,'白') else '#675b4c';b+=circle(cx,cy,rr,col,stroke='#594e40',stroke_width=2)
            for _ in range(160):
                a=rng.random()*math.tau;t=math.sqrt(rng.random());x=cx+math.cos(a)*t*rr*.92;y=cy+math.sin(a)*t*rr*.92
                b+=poly([(x-3,y+2),(x+2,y-4),(x+5,y+2)],'#b6a38a' if has(n,'白') else '#88765f',stroke='#534b3b',stroke_width=.7)
        return b
    b=''
    for cx,cy,s in [(177,216,1),(307,258,.83),(241,322,.48)]:
        q=path('M-20 11 Q-15 60-30 116 C-14 132 12 132 25 118 Q11 58 20 8Z','url(#cream)',stroke='#c7b798',stroke_width=1)
        if has(n,'羊肚'):
            q+=path('M-56 12 C-61-90 19-151 49-71 Q80-15 54 15Z','url(#brown)',stroke='#6a5741',stroke_width=2)
            for y in range(-80,9,19):
                for x in range(-35,45,20):q+=ellipse(x,y,7,11,'#67533d',stroke='#b0956a',stroke_width=3)
        else:
            col='#d4c9ad' if has(n,'白蘑','金针') else '#d6a967' if has(n,'鸡油') else 'url(#brown)'
            q+=ellipse(0,14,85,24,'#a39273')
            for x in range(-70,71,12):q+=path(f'M0 4 L{x} 26',stroke='#d1bea1',stroke_width=1)
            q+=path('M-87 10 C-81-93 60-101 88 12 C51 28-56 31-87 10Z',col,stroke='#a58b68',stroke_width=1)
            q+=speckles(rng,0,-22,63,24,45,'#e1c7a3',.7,2,.48)
            if has(n,'香菇'):q+=path('M-24-42 L16-8 M-8-46 L-23-9 M-30-17 L24-34',stroke='#ded0b1',stroke_width=5,stroke_linecap='round')
        b+=move(q,cx,cy,s,-13 if cx<200 else 18)
    return b

def nuts(rng,n):
    seed=has(n,'籽','芝麻','孜然','香菜籽','亚麻','奇亚','种草');walnut=has(n,'核桃','胡桃') and not has(n,'澳洲');cashew=has(n,'腰果');pistachio=has(n,'开心');peanut=has(n,'花生');hazel=has(n,'榛果');almond=has(n,'杏仁','巴西');black=has(n,'黑')
    b=''
    if seed:
        for _ in range(70):
            a=rng.random()*math.tau;rr=math.sqrt(rng.random());x=237+math.cos(a)*rr*127;y=260+math.sin(a)*rr*92
            c='#58524b' if black or has(n,'奇亚','罂粟') else '#83936b' if has(n,'南瓜') else '#ba9c72' if has(n,'葵花') else '#d5c69f'
            size=15 if has(n,'葵花','南瓜') else 7 if has(n,'芹','茴','孜') else 4.5
            q=path(f'M0 {-size} Q{size*.7} 0 0 {size} Q{-size*.7} 0 0 {-size}Z',c,stroke='#8e8269',stroke_width=.75)+line(0,-size*.7,0,size*.6,'#f1e5c9',stroke_width=.9,opacity=.65)
            b+=move(q,x,y,1,rng.uniform(-180,180))
        return b
    coords=[(151,203,.87,-25),(250,178,.78,20),(332,238,.83,-22),(193,283,1,34),(278,316,.82,10),(124,325,.6,-5)]
    for cx,cy,s,r in coords:
        if cashew:
            q=path('M-35-34 C23-68 61-25 43 23 C33 45-9 48-19 27 C-24 13 3 15 4-4 C4-19-21-9-33-9 C-47-8-48-24-35-34Z','url(#cream)',stroke='#b6a080',stroke_width=2)
        elif walnut:
            q=ellipse(0,0,44,38,'#bca07a',stroke='#8f7454',stroke_width=2)
            for side in [-1,1]:
                for y in [-23,-7,9,23]:q+=path(f'M{side*5} {y-7} C{side*28} {y-18} {side*43} {y+11} {side*20} {y+12}',stroke='#876c4f',stroke_width=5,stroke_linecap='round')
            q+=line(0,-32,0,32,'#715e47',stroke_width=2)
        elif peanut:
            q=path('M-25-42 C8-64 39-28 20-4 C40 19 11 55-18 36 C-42 16-26 1-30-10 C-44-25-40-34-25-42Z','#c9ad7d',stroke='#aa8c60',stroke_width=1)
            for y in range(-35,37,9):q+=path(f'M-26 {y} q19 5 49 0',stroke='#a68962',stroke_width=.8)
            for x in [-17,-7,4,14]:q+=path(f'M{x}-40 Q{x+8} 0 {x} 37',stroke='#a68a64',stroke_width=.8)
        elif pistachio:
            q=ellipse(0,0,31,42,'#e8dbb3',stroke='#bfa983',stroke_width=1.5)+path('M0-37 C-24-20-16 26 0 37 C27 18 21-15 0-37Z','#9aaa68',stroke='#877a55',stroke_width=1)
        elif almond:
            q=path('M0-48 C37-28 42 29 1 50 C-38 29-39-26 0-48Z','url(#brown)',stroke='#9d7854',stroke_width=1)
            for x in [-17,-8,4,15]:q+=path(f'M0-40 Q{x*2} 0 0 41',stroke='#d4ad7c',stroke_width=.9,opacity=.65)
        else:
            q=ellipse(0,0,35,37,'url(#brown)',stroke='#8b6441',stroke_width=1)+ellipse(0,22,23,14,'#c5a16a')
            q+=speckles(rng,0,0,27,27,32,'#e4c390',.6,1.3,.4)
        b+=move(q,cx,cy,s,r)
    return b

def spice(rng,n):
    if has(n,'姜','山葵','辣根'):
        c='#d4b58a' if not has(n,'姜黄') else '#d69a4c';b=''
        for x,y,rx,ry,r in [(227,273,82,34,-18),(177,237,30,67,-24),(276,228,28,64,31),(304,295,47,23,22)]:b+=ellipse(x,y,rx,ry,c,stroke='#b4946b',stroke_width=1.3,transform=f'rotate({r} {x} {y})')
        for i in range(14):
            x=rng.uniform(160,299);y=rng.uniform(227,295);b+=path(f'M{x} {y} q8 7 18 0',stroke='#a88c65',stroke_width=1,opacity=.7)
        return b+ellipse(307,313,33,24,'#ecdaa0',stroke='#b4946b',stroke_width=4)
    if has(n,'肉桂','桂皮'):
        b=''
        for x,y,r in [(158,185,-28),(228,177,-15),(305,206,7)]:
            q=rect(-17,0,42,157,'#a67551',rx=5,stroke='#80563d',stroke_width=1)+ellipse(4,0,21,13,'#b89366',stroke='#855d41',stroke_width=3)+ellipse(5,0,12,7,'#765039')+ellipse(8,0,5,4,'#b28b60')
            for xx in [-8,0,12,19]:q+=path(f'M{xx} 20 Q{xx-3} 90 {xx} 143',stroke='#c49669',stroke_width=1,opacity=.7)
            b+=move(q,x,y,1,r)
        return b
    if has(n,'八角','大茴香'):
        b=''
        for x,y,s,r in [(179,234,1,14),(304,274,.85,-8),(220,342,.55,32)]:
            q=''
            for i in range(8):
                petal=path('M0-9 C-23-29-21-49 0-65 C22-48 22-29 0-9Z','url(#brown)',stroke='#795237',stroke_width=1)+ellipse(0,-38,8,15,'#5f4632')+ellipse(0,-36,5,11,'#b7824d')
                q+=move(petal,0,0,1,i*45)
            b+=move(q,x,y,s,r)
        return b
    if has(n,'香草','零陵香'):
        b=''
        for i in range(6):b+=path(f'M{132+i*16} {149+i*8} C{107+i*25} 244 {213+i*23} 330 {250+i*13} 350',stroke='#514439',stroke_width=9,stroke_linecap='round')+path(f'M{132+i*16} {152+i*8} Q{145+i*25} 278 {250+i*13} 348',stroke='#95806a',stroke_width=1,opacity=.55)
        return b
    if has(n,'丁香'):
        return ''.join(move(path('M-3-9 L-2 39 L4 42 L6-9Z','#79523c')+circle(1,-12,8,'#8c6343')+path('M-5-15 L0-25 L6-15Z','#ad865e'),rng.uniform(130,349),rng.uniform(173,323),1,rng.uniform(-180,180)) for _ in range(20))
    color='#ded4bb' if has(n,'白胡椒') else '#b77374' if has(n,'粉红') else '#74845a' if has(n,'绿胡椒') else '#565044'
    b=''
    for _ in range(68):
        a=rng.random()*math.tau;t=math.sqrt(rng.random());x=237+math.cos(a)*t*114;y=263+math.sin(a)*t*89;rr=rng.uniform(6,11)
        b+=circle(x,y,rr,color,stroke='#8c7c60',stroke_width=.7)+path(f'M{x-rr*.45} {y-rr*.45} q{rr*.5} {-rr*.4} {rr} 0',stroke='#c4b69a',stroke_width=1,opacity=.3)
    return b

def bread(rng,n):
    if has(n,'米','麦谷','麦粒','藜麦','荞麦','苔','翡麦','麦芽','燕麦','斯佩尔','卡姆','单粒') and not has(n,'面包','饼','米浆','饮'):
        b=ellipse(237,286,141,74,'#d4c7ac')+ellipse(237,275,135,67,'#f1e8d4')
        dark=has(n,'黑米','野米');brown=has(n,'糙','麦');col='#514845' if dark else '#c6af85' if brown else '#e6ddbd'
        for _ in range(210):
            a=rng.random()*math.tau;t=math.sqrt(rng.random());x=237+math.cos(a)*t*118;y=270+math.sin(a)*t*53
            b+=ellipse(x,y,4 if has(n,'藜','苔') else 3,4 if has(n,'藜','苔') else 9,col,stroke='#a08d70',stroke_width=.35,transform=f'rotate({rng.uniform(-90,90)} {x} {y})')
        return b
    if has(n,'义大利面','荞麦面'):
        b=ellipse(237,288,142,78,'#ece2cb',stroke='#cabea6',stroke_width=1)
        for _ in range(40):
            x=rng.uniform(142,308);y=rng.uniform(220,325)
            b+=path(f'M{x} {y} q{rng.uniform(12,35)} -28 41 2 t35 0',stroke='#bba879' if has(n,'荞') else '#dfc183',stroke_width=7,stroke_linecap='round')
        return b
    if has(n,'可颂'):
        b=path('M102 292 C113 177 325 146 375 292 L323 287 L298 327 L256 338 L210 329 L178 296Z','url(#gold)',stroke='#b78956',stroke_width=2)
        for x in [157,190,228,267,304]:b+=path(f'M{x} 202 Q{x-15} 273 {x+20} 319',stroke='#a77543',stroke_width=3)
        return b
    if has(n,'贝果'):
        b=ellipse(238,252,128,104,'url(#gold)',stroke='#a87e48',stroke_width=2)+ellipse(238,252,36,30,PAPER,stroke='#ae844e',stroke_width=4)
        return b+speckles(rng,238,252,111,90,120,'#f8e0ad',1,2.3,.8)
    if has(n,'饼','薄脆','千层','塔'):
        b=''
        for x,y,s in [(192,247,1),(293,285,.86),(229,330,.73)]:
            q=circle(0,0,72,'url(#gold)',stroke='#bb925e',stroke_width=2)+speckles(rng,0,0,63,63,70,'#8c6847',1,2,.3)
            if has(n,'巧克力'):
                for _ in range(14):q+=rect(rng.uniform(-44,36),rng.uniform(-41,40),9,7,'#664b38',rx=2)
            b+=move(q,x,y,s)
        return b
    b=path('M108 257 C110 158 321 136 371 245 L366 317 Q240 359 115 315Z','url(#gold)',stroke='#a87543',stroke_width=2)
    for x in [157,207,257,307]:b+=path(f'M{x} 214 q-20 26-17 57',stroke='#f3dca4',stroke_width=10,stroke_linecap='round')+path(f'M{x-3} 215 q-21 27-17 53',stroke='#b38550',stroke_width=2)
    b+=speckles(rng,240,276,111,40,140,'#f5dfb0',.6,1.6,.53)
    return b

def cheese(rng,n):
    if has(n,'奶油乳酪','马斯卡','茅屋','莫札','菲达'):
        b=ellipse(239,315,130,39,'#e0d4be')+ellipse(239,302,124,35,'#f6efdc')
        if has(n,'莫札'):
            b+=ellipse(208,245,76,62,'url(#milk)')+ellipse(289,286,64,53,'url(#milk)')
        else:
            b+=path('M145 275 C134 222 193 215 211 186 C240 232 296 197 322 244 C354 279 302 308 250 304 C200 311 157 306 145 275Z','url(#milk)',stroke='#d6cbb5',stroke_width=1)
            b+=path('M178 272 Q217 232 269 251 M208 278 Q252 261 304 281',stroke='#fffdf4',stroke_width=6,stroke_linecap='round')
        return b
    white=has(n,'布里','卡蒙','山羊','软质','圣莫尔');blue=has(n,'蓝纹','洛克福','史帝','古冈');orange=has(n,'切达','高达','艾曼','葛瑞')
    top='#ede6ca' if white or blue else '#e4bf72' if orange else '#e4d49b';side='#d8cb9f' if white or blue else '#c99f5e'
    b=path('M116 263 L316 171 L365 229 L167 325Z',top,stroke='#bbaa80',stroke_width=1)+path('M116 263 L167 325 L365 229 L362 312 L172 390 L117 328Z',side,stroke='#b09b72',stroke_width=1)
    b+=path('M116 263 L316 171 L324 181 L124 273Z','#f3e9cc')
    if white:b+=path('M117 268 L129 279 L129 329 L172 376 L361 302 L362 313 L172 390 L117 328Z','#f0ebd8')
    if blue:
        for _ in range(27):
            x=rng.uniform(169,310);y=rng.uniform(236,312)
            b+=path(f'M{x} {y} l-8 7 5 6 -9 5',stroke='#819489',stroke_width=rng.uniform(1,3),opacity=.77)
    elif not white:
        for x,y,rx,ry in [(177,271,13,8),(245,237,12,7),(303,220,8,5),(199,333,12,15),(271,308,15,12),(325,285,8,11)]:b+=ellipse(x,y,rx,ry,'#b99558',stroke='#e8ca8e',stroke_width=2)
    return move(b,0,-21)

def dairy(rng,n):
    if has(n,'蛋') and not has(n,'蛋糕'):
        b=ellipse(188,228,75,98,'url(#cream)',transform='rotate(-27 188 228)',stroke='#c7bca2',stroke_width=1)
        b+=ellipse(296,298,84,61,'#f8f2df',transform='rotate(17 296 298)',stroke='#d4cbb4',stroke_width=2)+ellipse(297,297,47,40,'url(#gold)',transform='rotate(17 297 297)')
        return b
    if has(n,'奶油') and not has(n,'鲜','酸'):
        b=ellipse(239,330,140,36,'#ded5bf')+ellipse(239,318,135,32,'#f4ebd6')
        b+=path('M145 240 L281 211 L337 249 L201 283Z','#f2dda0')+path('M145 240 L201 283 L201 324 L145 282Z','#d6bb7e')+path('M201 283 L337 249 L336 287 L201 324Z','#e7ce8f')
        b+=path('M231 253 q20-46 48-31 q-1 22-27 30Z','#f8e9b9',stroke='#d6bc83',stroke_width=1)
        return b
    if has(n,'优格','鲜奶油','酸奶油','酱','克菲'):
        return bowl(rng,n,'#eee8d6','milk')
    return bottle(rng,n,'milk')

def meat(rng,n):
    cooked=has(n,'烤','煎','熟','炖','熏','清炖');fill='url(#roast)' if cooked else 'url(#meat)'
    if has(n,'香肠','萨拉米','乔利佐'):
        b=''
        for x,y,r in [(163,198,-22),(229,215,-14)]:
            q=rect(-22,0,57,153,fill,rx=27,stroke='#875946',stroke_width=2)+path('M-12 18 Q-15 87-8 131',stroke='#e6af8f',stroke_width=3,opacity=.4)
            b+=move(q,x,y,1,r)
        for x,y in [(292,280),(322,326)]:
            b+=ellipse(x,y,43,32,'#a5635a',stroke='#794d42',stroke_width=4)+speckles(rng,x,y,32,23,36,'#e0c5a4',1.5,4,.95)
        return b
    if has(n,'培根','五花'):
        b=''
        for i in range(4):
            q=path('M0 0 C33-17 53 17 88 5 Q113-3 146 9 L151 52 Q103 35 72 57 C45 63 20 43-3 54Z','#bd8170',stroke='#a06c56',stroke_width=1)
            q+=path('M0 12 C36-3 55 31 90 20 Q117 10 149 23 L150 34 Q112 19 85 38 C53 45 29 17-1 26Z','#e5c8a7')
            b+=move(q,127+i*15,184+i*39,1,-12)
        return b
    if has(n,'鸡','鸭','鹅','鸽','鹌鹑','火鸡','斑鸠') and not has(n,'胸','肝'):
        b=ellipse(225,254,101,84,fill,transform='rotate(-17 225 254)',stroke='#8d613f',stroke_width=2)
        b+=path('M159 273 C111 287 106 337 142 350 C174 357 191 318 181 298Z',fill,stroke='#966947',stroke_width=2)+path('M148 342 L137 367 M137 367 Q120 373 123 359 M137 367 Q143 381 150 367',stroke='#e1d4b9',stroke_width=11,stroke_linecap='round')
        b+=path('M275 221 C326 203 355 234 333 275 Q308 296 298 273',fill,stroke='#956039',stroke_width=2)
        b+=speckles(rng,223,253,79,58,85,'#704b33',.7,1.4,.2)
        return b
    b=path('M119 232 C133 171 209 149 267 170 C317 157 372 192 370 247 C389 302 340 342 284 339 C249 370 179 347 163 324 C120 317 100 273 119 232Z',fill,stroke='#b69c82' if not cooked else '#775039',stroke_width=9,stroke_linejoin='round')
    for d in ['M141 249 Q176 209 211 231 T277 238 T346 263','M180 191 Q203 224 194 262 Q208 303 191 323','M232 180 Q264 213 244 265 T279 330','M143 286 Q195 279 235 298 T328 302']:
        b+=path(d,stroke='#e3bea5' if not cooked else '#b48358',stroke_width=3 if cooked else 4,opacity=.77)
    if cooked:
        for x in [153,193,233,273,313]:b+=path(f'M{x} 206 l-13 87',stroke='#5a4030',stroke_width=7,stroke_linecap='round',opacity=.41)
    return b

def seafood(rng,n):
    if has(n,'虾'):
        b=''
        for x,y,s,r in [(198,236,1,-19),(301,276,.81,19)]:
            q=path('M-6-77 C-92-55-88 58-20 79 C21 92 67 67 53 35 C42 12 15 20 5 36 C-13 55-44 15-32-14 C-24-35-4-39 21-33 L35-61Z','url(#salmon)',stroke='#be826b',stroke_width=1.4)
            for a in range(-125,91,27):
                aa=math.radians(a);xx=-15+math.cos(aa)*49;yy=math.sin(aa)*59
                q+=path(f'M{xx-7} {yy-9} l17 12',stroke='#f0c7a8',stroke_width=3)
            q+=path('M16-53 L48-78 L58-42 L28-32Z','#d08b70')+circle(27,-60,3,'#58483b')+path('M38-69 Q101-100 92-151 M40-62 Q113-59 133-111',stroke='#a58c6b',stroke_width=1.5)
            q+=path('M40 43 l32-8 -9 31 -29-3Z','#d89579')
            b+=move(q,x,y,s,r)
        return b
    if has(n,'蟹'):
        b=''
        for side in [-1,1]:
            for yy in [-30,3,34]:b+=path(f'M{239+side*57} {267+yy} l{side*61} -19 {side*28} -39',stroke='#b78364',stroke_width=14,stroke_linecap='round')
            b+=path(f'M{239+side*60} 235 l{side*38}-43 {side*22}-49',stroke='#ae7657',stroke_width=19,stroke_linecap='round')
            b+=move(path('M-12 7 Q-45-29-16-66 L-7-22 Q17-56 34-51 Q33-14 12 8Z','#c38f6d',stroke='#9a6e50',stroke_width=2),239+side*113,152,1,side*28)
        b+=ellipse(239,269,94,69,'url(#roast)',stroke='#946847',stroke_width=2)+speckles(rng,239,258,76,44,80,'#d6ac7d',1,2,.44)
        b+=circle(211,207,6,'#3f4337')+circle(268,207,6,'#3f4337')
        return b
    if has(n,'贝','蛤','牡','淡菜','蚝'):
        b=''
        for x,y,s,r in [(183,233,1,-20),(307,293,.88,26)]:
            if has(n,'淡菜'):
                q=path('M0-96 C76-71 81 83 14 102 C-48 105-58-58 0-96Z','#626d69',stroke='#3f514a',stroke_width=4)+path('M0-80 C58-65 65 77 13 87 C-32 91-45-50 0-80Z','#d1c1a1')+ellipse(14,15,30,60,'#d6a577')
            else:
                q=path('M-9-80 C-31-112-95-48-92 9 C-85 78-13 110 38 81 C109 44 80-54 19-85Z','#d5c7ad',stroke='#aa9c84',stroke_width=3)
                for i in range(12):
                    a=-2.7+i*.24;xx=math.cos(a)*79;yy=math.sin(a)*80
                    q+=path(f'M0 84 Q{xx*.7} 10 {xx} {yy}',stroke='#b9a58b',stroke_width=1.5,opacity=.65)
                q+=ellipse(0,18,has(n,'扇贝') and 41 or 55,43,'url(#cream)')
                if has(n,'牡','蚝'):q+=path('M-34 12 Q-42-15-8-22 Q40-30 43 16 Q27 43-9 27Z','#b9b79b',stroke='#a6a38d',stroke_width=2)
            b+=move(q,x,y,s,r)
        return b
    if has(n,'乌贼','章鱼'):
        b=ellipse(246,183,65,88,'#bcae9c',stroke='#a19481',stroke_width=2)
        for i in range(8):b+=path(f'M{222+i*7} 249 Q{98+i*38} 338 {129+i*33} 353 Q{128+i*34} 318 {152+i*28} 302',stroke='#b2a391',stroke_width=11,stroke_linecap='round')
        return b
    if has(n,'鱼排','鲑鱼','鲔鱼'):
        c='url(#salmon)' if has(n,'鲑') else '#a46b65' if has(n,'鲔') else '#e0d5ba'
        b=path('M106 254 L220 179 L360 220 L352 307 L198 352 L117 313Z',c,stroke='#ac8c75',stroke_width=2)
        for i in range(8):b+=path(f'M{127+i*24} {241-i*3} Q{174+i*24} 277 {159+i*24} 330',stroke='#eed4b6',stroke_width=4,opacity=.72)
        b+=path('M117 313 L198 352 L352 307 L353 322 L198 366 L118 328Z','#6c7975')
        return b
    b=path('M107 248 C170 145 289 161 347 236 L390 194 L379 249 L394 300 L345 264 C280 335 164 332 107 248Z','url(#fish)',stroke='#768377',stroke_width=1.5)
    b+=path('M182 187 L217 152 L255 180 M193 309 L239 338 L270 303','#80958c',stroke='#687d70',stroke_width=1)
    b+=circle(145,238,10,'#ded6b9')+circle(144,238,6,'#3f4b46')+circle(142,235,2,'#f8f2d8')
    b+=path('M176 198 Q204 251 177 301',stroke='#778a7e',stroke_width=2)+path('M109 249 L130 255',stroke='#6b7e72',stroke_width=2)
    for y in range(202,299,13):
        for x in range(198,327,17):
            if ((x-245)/103)**2+((y-252)/69)**2<.85:b+=path(f'M{x-5} {y} q5 7 10 0',stroke='#dfdac1',stroke_width=.9,opacity=.5)
    return b

def bowl(rng,n,color=None,kind=None):
    if color is None:
        color='#747c4c' if has(n,'青酱','酪梨','绿','开心') else '#a26148' if has(n,'番茄','辣','红','草莓') else '#d0b87b' if has(n,'美乃','芝麻','花生','杏仁','奶油','鹰嘴') else '#675144' if has(n,'巧克','鱼露','酱油','味噌') else '#b08c59'
    b=ellipse(238,336,113,24,'#b8ab92',opacity=.4)
    b+=path('M107 234 C115 384 360 386 372 234Z','#ded6c3',stroke='#bdb49d',stroke_width=1)
    b+=ellipse(239,235,132,62,'#f7efdb',stroke='#c7bca1',stroke_width=2)+ellipse(239,234,117,49,color)
    b+=path('M151 231 Q207 190 307 225 Q337 246 255 263',stroke='#fff4d6' if kind=='milk' else '#dcc396',stroke_width=4,stroke_linecap='round',opacity=.32)
    if has(n,'子酱'):
        for _ in range(180):
            a=rng.random()*math.tau;t=math.sqrt(rng.random());x=239+math.cos(a)*t*104;y=233+math.sin(a)*t*40
            b+=circle(x,y,rng.uniform(3,5),'#53544b',stroke='#838171',stroke_width=.7)
    else:b+=speckles(rng,239,235,105,39,75,'#6d5c3e',.5,1.4,.2)
    if has(n,'汤','高汤'):b+=leaf(210,248,.32,-52)+ellipse(279,248,7,3,'#c49754',opacity=.6)
    return b

def bottle(rng,n,kind=None):
    milk=kind=='milk';oil=kind=='oil';dark=has(n,'红酒','波特','黑','巴萨米','酱油','咖啡','可可');green=has(n,'绿','薄荷','查特');clear=has(n,'伏特','琴酒','白兰地' if False else '烧酒','清酒','白色兰姆')
    liquid='#f3ebd7' if milk else '#a6a665' if oil else '#758863' if green else '#795653' if dark else '#e2d9b6' if clear else '#bc9660'
    shape='M209 123 L270 123 L270 169 Q306 197 307 227 L307 348 Q307 369 240 370 Q174 369 174 348 L174 227 Q174 197 209 169Z'
    b=path(shape,'url(#glass)',stroke='#aab5a6',stroke_width=1.5)
    b+=path('M181 232 L300 232 L300 344 Q299 361 240 363 Q183 360 181 344Z',liquid,opacity=milk and .95 or .78)
    b+=ellipse(240,232,59,12,liquid,opacity=.88)
    b+=rect(208,111,64,29,'#a58a68' if not milk else '#c9c0ae',rx=5,stroke='#9b927e',stroke_width=1)
    for x in range(213,269,6):b+=line(x,116,x,132,'#d6c8a9',stroke_width=1,opacity=.5)
    b+=path('M194 224 L194 338',stroke='#fffef6',stroke_width=6,stroke_linecap='round',opacity=.5)
    if oil:b+=leaf(306,303,.76,57)+leaf(304,319,.59,-35)+ellipse(311,327,12,17,'#738651')
    else:
        b+=ellipse(324,339,45,11,'#c1bdac',opacity=.35)+path('M286 268 L361 268 L354 338 Q324 352 294 338Z','url(#glass)',stroke='#b5bcaf',stroke_width=1)+ellipse(324,269,37,9,liquid)+path('M293 273 L298 332 Q323 341 350 332 L355 273Z',liquid,opacity=.7)
    return b

def juice(rng,n):
    col='#be787a' if has(n,'莓','樱桃','石榴','红','李子','醋栗','葡萄') else '#bdc695' if has(n,'奇异','梨','莱姆','青苹果') else '#e1b170' if has(n,'橙','芒果','凤梨','百香','杏','柠') else '#e6d1a3'
    b=path('M151 153 L320 153 L303 357 Q235 382 170 357Z','url(#glass)',stroke='#b6baac',stroke_width=2)+path('M160 193 L311 193 L294 348 Q235 366 178 348Z',col,opacity=.88)+ellipse(235,193,75,15,col)+ellipse(235,153,84,18,'#e5e3d6',fill_opacity=.4,stroke='#bbc0b1',stroke_width=1)
    b+=path('M174 198 L185 334',stroke='#fff8e7',stroke_width=6,stroke_linecap='round',opacity=.4)
    b+=speckles(rng,235,191,65,9,45,'#fff5d7',1,2.2,.6)
    return b

def beverage(rng,n):
    coffee=has(n,'咖啡');matcha=has(n,'抹茶');green=has(n,'绿茶','煎茶','龙井','杏仁')
    if has(n,'咖啡豆'):
        b=''
        for _ in range(32):
            a=rng.random()*math.tau;t=math.sqrt(rng.random());x=237+math.cos(a)*t*113;y=260+math.sin(a)*t*80
            q=ellipse(0,0,14,19,'url(#brown)',stroke='#674c37',stroke_width=1)+path('M0-15 Q-6 0 1 15',stroke='#5c442e',stroke_width=2)
            b+=move(q,x,y,1,rng.uniform(-90,90))
        return b
    if matcha:return bowl(rng,n,'#a1ac68')
    b=ellipse(231,337,132,32,'#e5dcc8',stroke='#c8bea7',stroke_width=1)+ellipse(231,330,104,23,'#f2ead7')
    b+=path('M326 225 C396 210 390 300 326 290',stroke='#cfc4ad',stroke_width=20)+path('M326 225 C396 210 390 300 326 290',stroke='#ebe2cb',stroke_width=12)
    b+=path('M120 207 L336 207 Q326 327 229 334 Q132 327 120 207Z','url(#milk)',stroke='#c4b99f',stroke_width=1.5)
    b+=ellipse(228,206,109,36,'#f8f0db',stroke='#c5b99d',stroke_width=1)+ellipse(228,208,96,28,'#685141' if coffee else '#aaba75' if green else '#b58d57')
    b+=ellipse(219,206,61,16,'#d4ba85',opacity=coffee and .12 or .2)
    b+=path('M204 153 Q181 132 205 107 M254 142 Q281 114 258 88',stroke='#c1bbac',stroke_width=2.5,stroke_linecap='round',opacity=.3)
    return b

def chocolate(rng,n):
    white=has(n,'白巧');gold=has(n,'金黄','奶油焦糖');col='#eee1b9' if white else '#c59b62' if gold else '#8b6950' if has(n,'牛奶') else '#5d4b3e'
    b=''
    for dx,dy,r in [(0,0,-12),(37,59,12)]:
        q=path('M137 172 L300 172 L337 293 L175 293Z',col,stroke='#705b45' if not white else '#c7b990',stroke_width=2)+path('M175 293 L337 293 L335 309 L173 309Z','#4d4034' if not white else '#c3b38f')
        for i in range(3):
            for j in range(3):
                x=144+i*48+j*11;y=180+j*35
                q+=path(f'M{x} {y} h39 l8 27 h-39Z',col,stroke='#aa8f69' if not white else '#faf0d1',stroke_width=2)
        b+=move(q,dx,dy,1,r)
    return b

def powder(rng,n):
    color='#8b6241' if has(n,'可可','肉桂') else '#c47c50' if has(n,'红椒','辣') else '#a1aa70' if has(n,'抹茶','芒果') else '#d6c7a3'
    b=bowl(rng,n,color)
    b+=speckles(rng,239,227,99,40,220,'#6e5437',.3,.9,.22)
    return b

def honey(rng,n):
    b=path('M150 197 Q235 171 316 198 L315 345 Q237 377 151 344Z','url(#glass)',stroke='#b8b5a0',stroke_width=2)+path('M159 236 Q235 216 308 236 L307 337 Q234 361 160 337Z','#bb9150',opacity=.8)+ellipse(233,235,74,17,'#d3ad61')
    b+=ellipse(233,197,83,24,'#ddd3b8',stroke='#a7a38a',stroke_width=2)+ellipse(233,197,69,15,'#c6a86b')
    b+=path('M273 150 L331 260',stroke='#a98554',stroke_width=11,stroke_linecap='round')
    for i in range(5):b+=move(rect(-22,-5,44,10,'#b99a61',rx=5,stroke='#927344',stroke_width=1),278+i*6,167+i*12,1,-27)
    b+=path('M308 218 Q331 248 322 274',stroke='#d4ad59',stroke_width=5,stroke_linecap='round',opacity=.8)
    return b

def seaweed(rng,n):
    b=''
    for i in range(7):
        x=120+i*32
        b+=path(f'M{x} 350 C{x-36} 287 {x+21} 235 {x-8} 166 Q{x+1} 135 {x+18} 155 C{x+46} 227 {x-4} 287 {x+22} 354Z','#697960',stroke='#4e654c',stroke_width=1.5)
        b+=path(f'M{x+10} 339 Q{x-9} 246 {x+5} 172',stroke='#a8af77',stroke_width=1,opacity=.7)
    return b

def identity_unresolved(rng,n):
    # A specimen card explicitly marks uncertainty; no food shape is asserted.
    b=rect(119,139,241,205,'#eae3d4',rx=9,stroke='#c5bba7',stroke_width=1.5)
    b+=rect(134,152,211,178,'#f8f4e9',rx=5,stroke='#d8cebb',stroke_width=1)
    b+=circle(239,231,42,'none',stroke='#c2b49a',stroke_width=1.5,stroke_dasharray='3 6')
    b+=path('M225 218 C221 198 255 196 255 215 C256 225 239 227 239 240',stroke='#ad9677',stroke_width=4,stroke_linecap='round')+circle(239,253,2.5,'#ad9677')
    b+='<text x="239" y="296" text-anchor="middle" fill="#9a8063" font-family="PingFang SC,Microsoft YaHei,sans-serif" font-size="15" letter-spacing="2">待核食材身份</text>'
    b+=circle(142,162,3,'#b9a184')+circle(336,162,3,'#b9a184')
    return b

def classify(ing):
    n=ing.get('displayName') or ing['name'];fam=ing.get('visualFamily','other')
    if ing.get('nameNeedsReview'): return 'identity_unresolved'
    if has(n,'干无花果'): return 'dried_fruit'
    if has(n,'无花果'): return 'fig'
    if has(n,'番荔枝','释迦'): return 'custard_apple'
    if has(n,'山竹'): return 'mangosteen'
    if has(n,'葡萄干','西梅干'): return 'raisins'
    if has(n,'枇杷'): return 'loquat'
    if has(n,'干小檗'): return 'barberry'
    if has(n,'榅桲'): return 'quince'
    if has(n,'桑椹','桑葚'): return 'bramble'
    if has(n,'桉树','蜜树','茴藿香'): return 'herb'
    if has(n,'马萨拉普','美乃滋','酸菜','泡菜','天贝'): return 'bowl'
    if has(n,'味醂','老抽'): return 'bottle'
    if has(n,'熟苦荞','千层酥皮'): return 'bread'
    if has(n,'汉堡'): return 'burger'
    if has(n,'青花菜'): return 'greens'
    if has(n,'柿子'): return 'persimmon'
    if has(n,'莲雾'): return 'waxapple'
    if has(n,'罗望子'): return 'tamarind'
    if has(n,'干无花果'): return 'dried_fruit'
    # Processed forms precede the raw ingredient; context keywords precede family.
    if has(n,'烟熏','木烟') and not has(n,'鱼','鲑','肉','培根','红茶'): return 'smoke'
    if has(n,'花') and not has(n,'花生','花椰','青花','五花','葵花','椰菜','藏花','花椒','花蜜','花酱','花酒','花茶','花水','花油','啤酒花'):return 'flower'
    if has(n,'啤酒花','蛇麻草芽','草叶','肉桂叶','山葵叶','鸭儿芹','莳萝','茴香草','茴香叶','芹菜叶'):return 'herb'
    if has(n,'高汤','肉汁','鸡汤','蔬菜汤','肉清汤','牛肉汤','豆腐乳'):return 'bowl'
    if has(n,'酱','味噌','豆腐乳','子酱') and not has(n,'酱油','油醋'):return 'bowl'
    if has(n,'酱油','鱼露','醋') and not has(n,'醋栗'):return 'bottle'
    if has(n,'蜂蜜','糖浆','糖蜜','树蜜','莱姆蜜','荞麦蜜','菜籽蜜'):return 'honey'
    if has(n,'巧克力') and not has(n,'饼','抹酱','牛奶饮'):return 'chocolate'
    if has(n,'香甜酒','白兰地','威士','威土','兰姆','琴酒','伏特','波特','龙舌兰','雪莉','气泡酒','香槟','清酒','米酒','西打','苦艾酒','梅酒') or fam=='alcohol' and not has(n,'啤酒花','蛇麻','樱桃'):return 'bottle'
    if has(n,'咖啡','茶','汽水','苏打','通宁'):return 'beverage'
    if has(n,'汁','泥') and not has(n,'蒜','姜','辣根','山葵'):
        return 'juice' if has(n,'汁') else 'bowl'
    if has(n,'粉','末') and not has(n,'粉红','木末'):return 'powder'
    if has(n,'油') and not has(n,'油桃','奶油','酱油','鸡油','油菜','油烤'):return 'oil'
    if has(n,'乳酪','乳酪蛋糕'):return 'cheese'
    if has(n,'奶','蛋','克菲尔','优格') and not has(n,'奶油菇','奶油菌','奶油生菜','奶油莴','奶油萵','奶油万苣','奶油黄','奶油菖','奶油蒿','奶油高','奶油髙','饼','蛋糕','椰奶','燕麦饮'):return 'dairy'
    if has(n,'椰奶','豆浆','燕麦饮','米浆'):return 'milk'
    if has(n,'草莓') and not has(n,'番石榴'):return 'strawberry'
    if has(n,'蓝莓','接骨木莓','山桑','枸杞','醋栗','越橘','蔓越','五味子','沙棘'):return 'blueberries'
    if has(n,'覆盆','黑莓','罗甘','波森','云莓','桑椹','桑葚'):return 'bramble'
    if has(n,'苹果') and not has(n,'地苹果'):return 'apple'
    if has(n,'梨','莎梨') and not has(n,'酪梨','凤梨','腰果梨'):return 'pear'
    if has(n,'桃','杏','油桃') and not has(n,'核桃','胡桃','樱桃','香桃','杏仁'):return 'peach'
    if has(n,'芒果') and not has(n,'籽'):return 'mango'
    if has(n,'蕉'):return 'banana'
    if has(n,'凤梨','菠萝') and not has(n,'菠萝蜜'):return 'pineapple'
    if has(n,'奇异'):return 'kiwi'
    if has(n,'葡萄') and not has(n,'葡萄柚','葡萄叶','葡萄藤'):return 'grapes'
    if has(n,'樱桃','李子','梅子','梅干','西梅','李杏','枣子'):return 'cherry'
    if has(n,'柠檬','青柠','橘','橙','柑','莱姆','柚','日向夏'):return 'citrus'
    if has(n,'酪梨'):return 'avocado'
    if has(n,'椰子'):return 'coconut'
    if has(n,'石榴'):return 'pomegranate'
    if has(n,'百香','香槟果'):return 'passion'
    if has(n,'番石榴','斐济果'):return 'guava'
    if has(n,'木瓜'):return 'papaya'
    if has(n,'火龙'):return 'dragon'
    if has(n,'无花果'):return 'fig'
    if has(n,'荔枝','龙眼','红毛丹'):return 'lychee'
    if has(n,'榴莲','榴梿','榴梗','榴樋','榴机','菠萝蜜'):return 'durian'
    if has(n,'杨桃'):return 'starfruit'
    if has(n,'西瓜'):return 'watermelon'
    if has(n,'瓜','香瓜茄') and not has(n,'南瓜','黄瓜','栉瓜','佛手瓜','冬瓜'):return 'melon'
    if has(n,'菇','蘑','菌','松露','松茸'):return 'mushroom'
    if has(n,'肉桂','桂皮','八角','大茴香','丁香','姜','山葵','辣根','香草','零陵香','胡椒','华澄茄','花椒','豆蔻','多香果','盐肤木'):return 'spice'
    if has(n,'坚果','籽','芝麻','杏仁','核桃','胡桃','腰果','开心果','榛果','花生','松子','栗子','杜松子','孜然'):return 'nuts'
    if has(n,'辣椒','甜椒','潘卡'):return 'pepper'
    if has(n,'胡萝卜','防风根','日本萝卜','白冰柱','香芹根'):return 'carrot'
    if has(n,'番茄'):return 'tomato'
    if has(n,'茄子'):return 'eggplant'
    if has(n,'大蒜','黑蒜','蒜末','蒜泥','洋葱','红葱'):return 'onion'
    if has(n,'栉瓜','黄瓜','秋葵'):return 'cucumber'
    if has(n,'南瓜','冬瓜','佛手瓜'):return 'squash'
    if has(n,'马铃薯','番薯','红番','芋','甜菜','木薯','芜菁','大头菜','芹菜根','菊薯','波罗门'):return 'potato'
    if has(n,'芦笋','青花笋','竹笋'):return 'asparagus'
    if has(n,'豆') and not has(n,'豆蔻','香豆','豆腐'):return 'peas'
    if has(n,'豆腐'):return 'tofu'
    if has(n,'薯条','薯片','脆片'):return 'chips'
    if has(n,'海苔','海带','昆布','藻','裙带'):return 'seaweed'
    if has(n,'鱼','虾','蟹','贝','蛤','牡蛎','牡螭','淡菜','海胆','海腊','鳗','乌贼','鲔','鲑','鲈','鲷','鲽') and not has(n,'天贝','鱼子酱'):return 'seafood'
    if has(n,'肉','牛排','猪','牛','鸡','鸭','鹅','鸽','香肠','萨拉米','火腿','肝','兔','鹿','羊','骨髓','安格斯','培根','胸排'):return 'meat'
    if has(n,'面包','面食','吐司','饼','糕','可颂','米','麦','义大利面','苔','藜','斯佩尔','面包糠','面包丁'):return 'bread'
    if has(n,'橄榄'):return 'olives'
    if has(n,'花'):return 'flower'
    if fam in ['herb']:return 'herb'
    if fam=='flowers':return 'flower'
    if fam=='condiment':return 'bowl'
    if fam=='dairy':return 'dairy'
    if fam=='meat':return 'meat'
    if fam=='seafood':return 'seafood'
    if fam=='mushroom':return 'mushroom'
    if fam=='bread_grain':return 'bread'
    if fam=='citrus':return 'citrus'
    if fam in ['vegetable']:return 'greens'
    if fam=='nuts_seeds':return 'nuts'
    if fam=='spice':return 'spice'
    if fam=='fruit':return 'botanical_fruit'
    if fam=='insect':return 'insect'
    if fam=='sweets':return 'honey'
    return 'visual_family'

def extra(rng,n,kind):
    if kind=='olives':
        b=herb(rng,'月桂叶')
        for x,y,r in [(145,206,-12),(210,233,24),(278,267,-20),(317,306,22),(173,306,17)]:b+=ellipse(x,y,19,26,'url(#purple)' if has(n,'黑') else 'url(#green)',stroke='#69724d',stroke_width=1,transform=f'rotate({r} {x} {y})')
        return b
    if kind=='tofu':
        b=''
        for x,y in [(124,212),(223,247),(163,294)]:b+=path(f'M{x} {y} l79-23 50 31-79 26Z','#f0e4c7',stroke='#d4c3a3',stroke_width=1)+path(f'M{x} {y} l50 34 79-26v41l-79 27-50-37Z','#ddcfae',stroke='#cbb99a',stroke_width=1)
        return b
    if kind=='chips':
        b=''
        for _ in range(19):
            x=rng.uniform(144,333);y=rng.uniform(197,333);b+=move(path('M-30-23 C-6-39 38-24 30 9 Q11 41-26 24 Q-45 7-30-23Z','url(#gold)',stroke='#c4a16b',stroke_width=1),x,y,rng.uniform(.65,1),rng.uniform(-100,100))
        return b
    if kind=='smoke':
        b=''
        for x,y,r in [(138,284,-15),(199,304,7),(284,297,-7)]:
            q=rect(0,0,111,24,'#9b7a53',rx=4,stroke='#735c42',stroke_width=1)+path('M4 7 Q53 17 106 6 M7 16 Q59 21 108 16',stroke='#c5a172',stroke_width=1)
            b+=move(q,x,y,1,r)
        for x in [185,236,288]:b+=path(f'M{x} 263 C{x-48} 210 {x+36} 181 {x+6} 129',stroke='#b8b6a9',stroke_width=8,stroke_linecap='round',opacity=.23)
        return b
    if kind=='insect':
        b=''
        for x,y,sc,rot in [(184,230,1,-25),(290,289,.83,24)]:
            q=''
            if has(n,'蚁'):
                for j in [-1,0,1]:
                    for side in [-1,1]:q+=path(f'M{side*7} {j*15} l{side*34} 12 {side*13} 24',stroke='#70503b',stroke_width=3,stroke_linecap='round')
                q+=ellipse(0,35,24,34,'#8b6549')+ellipse(0,-8,16,24,'#7b573f')+ellipse(0,-45,21,23,'#886143')+path('M-9-60 l-17-29 M9-60 l18-29',stroke='#6a4e39',stroke_width=2)
            else:
                for j in range(12):q+=ellipse(math.sin(j*.35)*14,j*10-58,20-j*.7,9,'#bb956b',stroke='#97734e',stroke_width=1)
                q+=circle(0,-66,12,'#926840')
            b+=move(q,x,y,sc,rot)
        return b
    if kind=='visual_family':
        # A neutral illustration reference sheet is not a claim of food identity.
        b=rect(119,139,241,205,'#eae3d4',rx=9,stroke='#c5bba7',stroke_width=1.5)+rect(134,152,211,178,'#f8f4e9',rx=5,stroke='#d8cebb',stroke_width=1)
        b+=leaf(221,261,.75,-28)+path('M221 262 Q251 234 267 204',stroke='#9ea17b',stroke_width=2)
        b+='<text x="239" y="297" text-anchor="middle" fill="#9a8063" font-family="PingFang SC,Microsoft YaHei,sans-serif" font-size="13">名称已保留 · 形态待补</text>'
        return b
    # For uncommon identified fruit, show a botanical family study, and mark
    # that coarser representation in the manifest. Never claim cultivar fidelity.
    b=leaf(228,170,1.05,-52)+leaf(257,167,.76,39)
    for x,y,rx,ry,r in [(190,243,64,78,-19),(292,292,73,63,16)]:b+=ellipse(x,y,rx,ry,'url(#green)',stroke='#788550',stroke_width=1.2,transform=f'rotate({r} {x} {y})')+speckles(rng,x,y,rx*.86,ry*.86,65,'#e4d99a',.5,1.6,.38)
    return b

DRAWERS={k:v for k,v in globals().copy().items() if callable(v) and k in ['strawberry','blueberries','bramble','apple','pear','peach','mango','citrus','banana','grapes','pineapple','kiwi','avocado','coconut','cherry','carrot','tomato','pepper','onion','eggplant','cucumber','squash','potato','greens','asparagus','peas','herb','flower','mushroom','nuts','spice','bread','cheese','dairy','meat','seafood','bowl','bottle','juice','beverage','chocolate','powder','honey','seaweed','identity_unresolved']}


def render(ing):
    name=ing.get('displayName') or ing['name'];kind=classify(ing)
    seed=int(hashlib.sha256(ing['id'].encode()).hexdigest()[:16],16);rng=random.Random(seed)
    if kind in DRAWERS:body=DRAWERS[kind](rng,name)
    elif kind in ['papaya','fig','dragon','passion','guava','melon','watermelon']:body=cutfruit(rng,name,kind)
    elif kind in ['pomegranate','lychee','durian','starfruit']:body=exotic(rng,name,kind)
    elif kind in ['mangosteen','custard_apple','raisins','barberry','loquat','persimmon','waxapple','tamarind','quince','dried_fruit','burger']:body=specific_fruit(rng,name,kind)
    elif kind=='oil':body=bottle(rng,name,'oil')
    elif kind=='milk':body=bottle(rng,name,'milk')
    else:body=extra(rng,name,kind)
    status='identity_unresolved' if kind=='identity_unresolved' else 'family_illustration' if kind in ['botanical_fruit','visual_family'] else 'illustrated'
    preparation=[x for x in ['干','烤','煎','水煮','清炖','烟熏','熟','腌渍','罐头','冷冻','泥','粉','汁'] if x in name]
    # Warm/brown wash is confined to the food artwork, not used as data.
    art_id=ing['id'];meta={'id':art_id,'rawName':ing['name'],'displayName':name,'status':status,'motif':kind,'style':STYLE,'source':'Original procedural SVG drawing, created locally; no external images.','identityBasis':'catalog displayName; nameNeedsReview gates identifiable food depictions','isPhotograph':False,'isSensoryMeasurement':False,'cultivarExactness':'stylized representation; not verified botanical reference','preparationHints':preparation}
    title=f'{name} · '+('身份待核图鉴卡' if status=='identity_unresolved' else '风格化食材插画')
    shadow=ellipse(239,362,119,15,'#8c7b59',opacity=.13,filter='url(#ground)')
    processing=''
    if status!='identity_unresolved' and has(name,'烤','煎','烟熏') and kind not in ['meat','seafood','beverage','bottle','smoke']:
        processing=' style="filter:saturate(.79)"'
    svg=f'''<svg xmlns="http://www.w3.org/2000/svg" width="480" height="480" viewBox="0 0 480 480" role="img" aria-labelledby="title desc">
<title id="title">{esc(title)}</title><desc id="desc">{esc('原创本地矢量插画。以目录食材名称选择形态，图片不代表原书照片、实测成分或精确品种鉴定。'+('此条目身份待核，未描绘确定食材。' if status=='identity_unresolved' else ''))}</desc>
<metadata>{esc(json.dumps(meta,ensure_ascii=False,separators=(',',':')))}</metadata>{DEFS}
<rect width="480" height="480" fill="{PAPER}"/><ellipse cx="237" cy="267" rx="175" ry="163" fill="#faf6ed" opacity=".75"/>{shadow}
<g{processing}>{body}</g><rect width="480" height="480" fill="#968265" filter="url(#paper)" opacity=".023" pointer-events="none"/>
</svg>'''
    ET.fromstring(svg)
    validate_paths(svg)
    return svg,meta


def validate_paths(svg):
    arity={'M':2,'L':2,'H':1,'V':1,'C':6,'S':4,'Q':4,'T':2,'A':7,'Z':0}
    for node in ET.fromstring(svg).iter():
        if not node.tag.endswith('path'):continue
        d=node.get('d','');segments=re.findall(r'([MmLlHhVvCcSsQqTtAaZz])([^MmLlHhVvCcSsQqTtAaZz]*)',d)
        for cmd,args in segments:
            nums=re.findall(r'[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?',args)
            need=arity[cmd.upper()]
            if (need and (not nums or len(nums)%need)) or (not need and nums):raise ValueError(f'Invalid SVG path parameters for {cmd}: {d}')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--catalog',type=Path,default=BASE/'data'/'catalog.json');parser.add_argument('--contact-sheet',action='store_true');args=parser.parse_args()
    catalog=json.loads(args.catalog.read_text());ingredients=catalog['ingredients'];OUT.mkdir(parents=True,exist_ok=True)
    records=[]
    for ing in ingredients:
        svg,meta=render(ing);dest=OUT/f"{ing['id']}.svg";dest.write_text(svg,encoding='utf-8')
        records.append({**meta,'path':str(dest.relative_to(BASE)),'width':480,'height':480,'bytes':dest.stat().st_size,'sha256':hashlib.sha256(svg.encode()).hexdigest()})
    summary={'total':len(records),'statusCounts':dict(Counter(x['status'] for x in records)),'motifCounts':dict(Counter(x['motif'] for x in records)),'xmlValidation':'all files parsed successfully','missingFiles':[]}
    manifest={'schemaVersion':'1.0.0','style':STYLE,'generator':'scripts/build_ingredient_art.py','catalog':str(args.catalog.relative_to(BASE)) if args.catalog.is_relative_to(BASE) else str(args.catalog),'catalogSha256':hashlib.sha256(args.catalog.read_bytes()).hexdigest(),'assetPolicy':'Original local SVG illustrations, not photos. Display names determine motifs. Unresolved identity entries show an explicit pending identity card. Uncommon fruit family art is labeled in each record. Raw IDs remain stable.','summary':summary,'assets':records}
    (BASE/'assets'/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    if args.contact_sheet: contact_sheet(records)


def contact_sheet(records):
    preferred=['草莓','蓝莓','苹果','梨子','桃子','芒果','柠檬','香蕉','葡萄','凤梨','奇异果','酪梨','椰子','石榴','百香果','火龙果','木瓜','樱桃','西瓜','无花果','山竹','番荔枝','葡萄干','枇杷','干小檗','柿子','莲雾','罗望子','胡萝卜','番茄','红甜椒','大蒜','茄子','黄瓜','南瓜','马铃薯','青花菜','绿芦笋','豌豆','罗勒','迷迭香','洋甘菊','薰衣草','香菇','核桃','烤葵花籽','肉桂','八角','面包','熟藜麦','奶油乳酪','切达乳酪','奶油','水煮蛋','肋眼牛排','煎培根','烤鸡','大虾','熟蛤蜊','大西洋鲑鱼排','沙丁鱼','橄榄油','牛奶','红茶','现煮手冲咖啡','蜂蜜','黑巧克力','青酱']
    picks=[];used=set()
    for n in preferred:
        matches=[x for x in records if x['displayName']==n and x['status']!='identity_unresolved'] or [x for x in records if n in x['displayName'] and x['status']!='identity_unresolved']
        if matches:
            item=matches[0]
            if item['id'] not in used:picks.append(item);used.add(item['id'])
    pending=next((x for x in records if x['status']=='identity_unresolved'),None)
    if pending:picks.append(pending)
    cols=8;cell=150;row_h=177;rows=math.ceil(len(picks)/cols)
    # An SVG/HTML contact sheet is always available; raster preview uses cairosvg if present.
    root=ET.Element('{http://www.w3.org/2000/svg}svg',{'width':str(cols*cell),'height':str(rows*row_h+40),'viewBox':f'0 0 {cols*cell} {rows*row_h+40}'})
    ET.SubElement(root,'{http://www.w3.org/2000/svg}rect',{'width':'100%','height':'100%','fill':PAPER})
    # Rewrite all IDs for each embedded source to prevent gradient/filter collisions.
    for i,item in enumerate(picks):
        content=(BASE/item['path']).read_text();prefix=f'art{i}_'
        for ident in ['red','berry','purple','leaf','green','gold','orange','brown','cream','milk','glass','fish','salmon','meat','roast','oil','ground','soft','paper','title','desc']:
            content=content.replace(f'id="{ident}"',f'id="{prefix}{ident}"').replace(f'url(#{ident})',f'url(#{prefix}{ident})')
        nested=ET.fromstring(content);nested.set('x',str(i%cols*cell));nested.set('y',str(i//cols*row_h));nested.set('width',str(cell));nested.set('height',str(cell));root.append(nested)
        label=ET.SubElement(root,'{http://www.w3.org/2000/svg}text',{'x':str(i%cols*cell+cell/2),'y':str(i//cols*row_h+155),'text-anchor':'middle','fill':'#765f49','font-family':'PingFang SC,Microsoft YaHei,sans-serif','font-size':'10'});label.text=item['displayName'][:13]
        label2=ET.SubElement(root,'{http://www.w3.org/2000/svg}text',{'x':str(i%cols*cell+cell/2),'y':str(i//cols*row_h+169),'text-anchor':'middle','fill':'#ac987a','font-family':'sans-serif','font-size':'7'});label2.text=item['motif']
    sheet=BASE/'assets'/'ingredient-art-contact-sheet.svg';ET.ElementTree(root).write(sheet,encoding='utf-8',xml_declaration=True)
    (BASE/'assets'/'ingredient-art-contact-sheet.html').write_text('<!doctype html><meta charset="utf-8"><title>食材插画核看</title><style>body{margin:0;background:#f5f1e8}img{width:1200px;display:block}</style><img src="ingredient-art-contact-sheet.svg" alt="多类别食材插画核看">')
    try:
        runtime=Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/node'
        node=runtime/'bin/node';sharp=runtime/'node_modules/sharp'
        # librsvg (via sharp) preserves SVG gradients; MuPDF's SVG renderer does not.
        js="const sharp=require(process.argv[3]);sharp(process.argv[1],{density:144}).png().toFile(process.argv[2]).then(()=>console.log('Native SVG contact sheet rendered')).catch(e=>{console.error(e);process.exit(1)});"
        subprocess.run([str(node),'-e',js,str(sheet),str(sheet.with_suffix('.png')),str(sharp)],check=True)
        print('Contact sheet:',sheet.with_suffix('.png'))
    except (ImportError,OSError,subprocess.CalledProcessError) as exc:
        print('SVG and HTML contact sheets ready; PNG renderer unavailable:',type(exc).__name__)
    (BASE/'assets'/'contact-sheet-items.json').write_text(json.dumps([{'id':x['id'],'name':x['displayName'],'motif':x['motif']} for x in picks],ensure_ascii=False,indent=2))


if __name__=='__main__': main()
