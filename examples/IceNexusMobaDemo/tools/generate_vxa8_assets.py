#!/usr/bin/env python3
# Zero-dependency supersampled VXA8 asset generator for IceNexusMobaDemo.
import math, os, struct

S=4

class Canvas:
    def __init__(self,w,h):
        self.w=w; self.h=h; self.W=w*S; self.H=h*S
        self.p=bytearray(self.W*self.H*4)
    def blend_px(self,x,y,c):
        if x<0 or y<0 or x>=self.W or y>=self.H:return
        r,g,b,a=c
        if a<=0:return
        i=(y*self.W+x)*4
        da=self.p[i+3]
        oa=a + (da*(255-a)+127)//255
        if oa<=0:return
        # premultiplied blend, convert back to straight RGBA
        nr=r*a + (self.p[i]*da*(255-a)+127)//255
        ng=g*a + (self.p[i+1]*da*(255-a)+127)//255
        nb=b*a + (self.p[i+2]*da*(255-a)+127)//255
        self.p[i]=(nr + oa//2)//oa
        self.p[i+1]=(ng + oa//2)//oa
        self.p[i+2]=(nb + oa//2)//oa
        self.p[i+3]=oa
    def ellipse(self,cx,cy,rx,ry,c):
        cx*=S;cy*=S;rx*=S;ry*=S
        x0=max(0,int(cx-rx-1));x1=min(self.W,int(cx+rx+2))
        y0=max(0,int(cy-ry-1));y1=min(self.H,int(cy+ry+2))
        rr=rx*rx*ry*ry
        for y in range(y0,y1):
            dy=(y+0.5-cy)
            for x in range(x0,x1):
                dx=(x+0.5-cx)
                if dx*dx*ry*ry + dy*dy*rx*rx <= rr:
                    self.blend_px(x,y,c)
    def rect(self,x0,y0,x1,y1,c):
        x0=int(x0*S);y0=int(y0*S);x1=int(x1*S);y1=int(y1*S)
        for y in range(max(0,y0),min(self.H,y1)):
            for x in range(max(0,x0),min(self.W,x1)):self.blend_px(x,y,c)
    def poly(self,pts,c):
        q=[(x*S,y*S) for x,y in pts]
        miny=max(0,int(min(y for _,y in q)));maxy=min(self.H-1,int(max(y for _,y in q)))
        for y in range(miny,maxy+1):
            yy=y+0.5; xs=[]
            for i in range(len(q)):
                x1,y1=q[i];x2,y2=q[(i+1)%len(q)]
                if (y1<=yy<y2) or (y2<=yy<y1):
                    xs.append(x1+(yy-y1)*(x2-x1)/(y2-y1))
            xs.sort()
            for k in range(0,len(xs)-1,2):
                a=max(0,int(math.ceil(xs[k])));b=min(self.W,int(math.floor(xs[k+1]))+1)
                for x in range(a,b):self.blend_px(x,y,c)
    def line(self,x0,y0,x1,y1,width,c):
        dx=x1-x0;dy=y1-y0;steps=max(1,int(max(abs(dx),abs(dy))*S))
        rr=max(0.5,width/2)
        for i in range(steps+1):
            t=i/steps;self.ellipse(x0+dx*t,y0+dy*t,rr,rr,c)
    def ring(self,cx,cy,rx,ry,width,outer,inner=None):
        self.ellipse(cx,cy,rx,ry,outer)
        if inner is None:inner=(0,0,0,0)
        self.ellipse(cx,cy,max(.1,rx-width),max(.1,ry-width),inner)
    def outline(self,c,radius=1.0):
        old=self.p[:]
        R=max(1,int(radius*S+0.5))
        cr,cg,cb,ca=c
        new=old[:]
        for y in range(self.H):
            for x in range(self.W):
                i=(y*self.W+x)*4
                if old[i+3]>24: continue
                ma=0
                y0=max(0,y-R);y1=min(self.H-1,y+R)
                x0=max(0,x-R);x1=min(self.W-1,x+R)
                for yy in range(y0,y1+1):
                    for xx in range(x0,x1+1):
                        a=old[(yy*self.W+xx)*4+3]
                        if a>ma: ma=a
                if ma>32:
                    a=(ma*ca+127)//255
                    new[i]=cr;new[i+1]=cg;new[i+2]=cb;new[i+3]=a
        self.p=new
    def write_vxa8(self,path):
        out=bytearray()
        alphas=[]
        pixels=[]
        opaque=True
        n=S*S
        for y in range(self.h):
            for x in range(self.w):
                sa=sr=sg=sb=0
                for yy in range(S):
                    for xx in range(S):
                        i=(((y*S+yy)*self.W)+(x*S+xx))*4
                        a=self.p[i+3];sa+=a
                        sr+=self.p[i]*a;sg+=self.p[i+1]*a;sb+=self.p[i+2]*a
                a=(sa+n//2)//n
                if a<255:opaque=False
                if sa:
                    r=(sr+sa//2)//sa;g=(sg+sa//2)//sa;b=(sb+sa//2)//sa
                else:r=g=b=0
                pixels.append(((r&0xF8)<<8)|((g&0xFC)<<3)|(b>>3))
                alphas.append(a)
        out+=b'VXA8'+struct.pack('<HHBBH',self.w,self.h,1 if opaque else 0,1,12)
        for p in pixels:out+=struct.pack('<H',p)
        if not opaque:out+=bytes(alphas)
        with open(path,'wb') as f:f.write(out)

def ariya():
    c=Canvas(76,88)
    # tails: dark rim then soft white/pink cores
    tails=[(22,51,18,9,-22),(18,60,20,9,-12),(25,69,19,9,8),(50,69,18,8,-5),(58,59,18,8,10),(55,48,16,8,22)]
    for cx,cy,rx,ry,_ in tails:
        c.ellipse(cx,cy,rx+2,ry+2,(107,63,132,255))
        c.ellipse(cx,cy,rx,ry,(239,226,249,255))
        c.ellipse(cx+(2 if cx>38 else -2),cy+1,rx*.48,ry*.55,(248,179,226,220))
    # legs + boots
    c.rect(32,57,37,77,(236,204,197,255));c.rect(42,57,47,77,(236,204,197,255))
    c.rect(30,72,38,80,(96,38,74,255));c.rect(41,72,49,80,(96,38,74,255))
    # robe dark silhouette + layered cloth
    c.poly([(24,42),(52,42),(58,64),(39,72),(19,64)],(95,37,74,255))
    c.poly([(27,41),(49,41),(53,60),(39,68),(22,60)],(245,229,241,255))
    c.poly([(22,46),(37,42),(34,66),(20,59)],(175,49,99,255))
    c.poly([(39,43),(50,45),(53,59),(39,67)],(252,239,247,255))
    c.line(24,53,40,68,1.5,(235,188,68,255));c.line(39,68,52,51,1.5,(235,188,68,255))
    # neck/head hair rim
    c.rect(35,35,42,45,(236,202,195,255))
    c.ellipse(38.5,27,15,16,(116,83,129,255))
    c.ellipse(38.5,27,13.5,14.5,(245,237,249,255))
    # ears
    c.poly([(27,20),(29,4),(36,20)],(115,77,130,255));c.poly([(29,19),(30,7),(35,19)],(244,232,248,255))
    c.poly([(42,18),(50,5),(49,22)],(115,77,130,255));c.poly([(43,18),(48,8),(47,20)],(244,232,248,255))
    # face
    c.ellipse(39,30,8.5,8,(238,205,198,255))
    c.ellipse(35.5,29,1.4,1.7,(119,42,90,255));c.ellipse(42.5,29,1.4,1.7,(119,42,90,255))
    c.line(37,34,41,34,1,(169,77,111,255))
    # hair locks
    c.poly([(27,23),(33,14),(35,36),(29,40)],(248,241,251,255))
    c.poly([(48,20),(44,15),(43,38),(49,34)],(230,215,240,255))
    # arms
    c.line(25,47,14,54,4,(238,205,198,255));c.line(51,47,62,41,4,(238,205,198,255))
    # orb with layered cyan
    c.ellipse(67,37,8,8,(35,121,205,190));c.ellipse(67,37,6.2,6.2,(71,215,255,240));c.ellipse(65,35,2.2,2.2,(225,255,255,255))
    c.outline((62,34,83,220),1.2)
    return c

def nexus():
    c=Canvas(108,108)
    # base shadow/rings
    c.ellipse(54,82,48,19,(18,23,34,210))
    c.ellipse(54,76,48,22,(67,62,59,255))
    c.ellipse(54,74,43,19,(196,153,84,255))
    c.ellipse(54,73,38,16,(24,93,126,255))
    c.ellipse(54,72,32,13,(16,137,185,255))
    c.ellipse(54,71,26,10,(29,177,218,255))
    # outer mechanical brackets
    for x,y in [(15,66),(93,66),(22,91),(86,91)]:
        c.poly([(x-8,y),(x-5,y-12),(x,y-18),(x+5,y-12),(x+8,y),(x+3,y+8),(x-3,y+8)],(70,61,53,255))
        c.line(x-6,y-2,x,y-14,2,(203,160,88,255));c.line(x,y-14,x+6,y-2,2,(203,160,88,255))
        c.ellipse(x,y-13,3.5,5,(42,196,245,255))
    # crystal outline + facets
    c.poly([(54,8),(37,37),(41,72),(54,84),(70,69),(73,36)],(14,85,160,255))
    c.poly([(54,10),(39,38),(44,68),(54,80)],(80,221,247,255))
    c.poly([(54,10),(54,80),(68,67),(71,37)],(18,154,225,255))
    c.poly([(54,10),(47,36),(55,31)],(165,246,255,255))
    c.poly([(47,36),(54,80),(55,31)],(46,196,238,255))
    c.poly([(55,31),(54,80),(68,67)],(23,116,207,255))
    c.line(54,10,54,80,1.2,(220,255,255,255))
    c.line(40,39,63,30,1.2,(150,242,255,230))
    c.line(45,56,67,63,1.2,(114,226,255,220))
    c.outline((8,43,67,220),1.1)
    return c

def floor_atlas():
    c=Canvas(128,16)
    bases=[(52,75,101,255),(58,83,110,255),(47,70,96,255),(45,77,109,255)]
    edges=[(24,43,65,255),(29,49,72,255),(22,39,61,255),(22,47,74,255)]
    for t in range(4):
        ox=t*32
        pts=[(ox+0,8),(ox+16,0),(ox+31,8),(ox+16,15)]
        c.poly(pts,edges[t])
        inner=[(ox+2,8),(ox+16,1.5),(ox+29,8),(ox+16,13.5)]
        c.poly(inner,bases[t])
        c.line(ox+3,7,ox+16,2,0.7,(94,124,151,210))
        c.line(ox+16,2,ox+28,7,0.6,(73,105,135,180))
        if t==1:
            c.line(ox+11,5,ox+16,8,0.8,(25,45,67,255));c.line(ox+16,8,ox+13,12,0.8,(25,45,67,255))
            c.line(ox+16,8,ox+22,10,0.8,(25,45,67,255))
        elif t==2:
            c.line(ox+6,8,ox+13,6,0.7,(30,51,73,255));c.line(ox+13,6,ox+18,10,0.7,(30,51,73,255))
            c.line(ox+18,10,ox+25,8,0.7,(30,51,73,255))
        elif t==3:
            c.poly([(ox+16,3),(ox+20,8),(ox+16,12),(ox+12,8)],(31,127,180,255))
            c.poly([(ox+16,5),(ox+18,8),(ox+16,10),(ox+14,8)],(117,222,244,255))
    return c

def skill_atlas():
    c=Canvas(128,32)
    for i in range(4):
        x=i*32
        c.rect(x+1,1,x+31,31,(5,11,25,255))
        c.rect(x+2,2,x+30,30,(11,22,46,255))
    # Q orb
    c.ellipse(16,16,10,10,(18,85,183,255));c.ellipse(16,16,7,7,(59,207,255,255));c.ellipse(13,12,3,3,(222,255,255,255))
    c.line(7,25,23,7,1.5,(155,243,255,255))
    # W dash petals
    c.poly([(38,23),(43,8),(50,14),(58,5),(57,20),(48,27)],(229,55,178,255))
    c.poly([(42,20),(49,10),(55,16),(48,25)],(255,150,228,255))
    # E charm flower
    for a in range(0,360,72):
        cx=80+math.cos(math.radians(a))*8;cy=16+math.sin(math.radians(a))*8
        c.ellipse(cx,cy,5,3.5,(240,92,190,255))
    c.ellipse(80,16,4,4,(255,225,243,255))
    # R spirit crystal
    c.poly([(112,4),(102,15),(109,28),(121,22),(125,10)],(35,126,232,255))
    c.poly([(112,5),(112,27),(121,21),(123,11)],(65,202,255,255))
    c.line(105,21,121,8,1.5,(216,255,255,255))
    return c

ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT=os.path.join(ROOT,'resources','gen')
os.makedirs(OUT,exist_ok=True)
for name,canvas in [('ariya.vxa8',ariya()),('nexus.vxa8',nexus()),('skills.vxa8',skill_atlas()),('floor.vxa8',floor_atlas())]:
    path=os.path.join(OUT,name);canvas.write_vxa8(path);print(name,os.path.getsize(path))
