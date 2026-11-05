"""著作権切れの唱歌「ふるさと」(1914) を合成した正解付き試験音源を作る。"""
import json,sys,numpy as np,soundfile as sf
from scipy.signal import lfilter
sr=44100; bpm=float(sys.argv[2]) if len(sys.argv)>2 else 96; beat=60/bpm; key=int(sys.argv[3]) if len(sys.argv)>3 else 0
# (MIDI,拍)。ヘ長調3/4
m=[(65,1),(65,1),(65,1),(67,1.5),(69,.5),(67,1),(69,1),(69,1),(70,1),(72,3),
   (70,1),(70,1),(69,1),(67,2),(65,1),(67,3),(67,1),(67,1),(67,1),
   (69,1.5),(70,.5),(69,1),(65,1),(65,1),(67,1),(69,3)]
# 区切り調整: 合計は問わない
m=[(p+key,d) for p,d in m]
def formant(x,fs,sr):
    y=np.zeros_like(x)
    for f,b,g in fs:
        r=np.exp(-np.pi*b/sr);t=2*np.pi*f/sr
        y+=g*lfilter([1-r],[1,-2*r*np.cos(t),r*r],x)
    return y
V=[[(800,90,1),(1150,110,.6),(2900,160,.25)],[(300,60,1),(2300,120,.4),(3000,160,.2)],[(450,80,1),(800,90,.5),(2830,160,.2)],[(350,70,1),(1300,120,.4),(2500,160,.2)],[(500,80,1),(1700,110,.5),(2500,160,.2)]]
rng=np.random.default_rng(1);t0=beat*3;total=t0+sum(d for _,d in m)*beat+2
N=int(total*sr);v=np.zeros(N);notes=[];t=t0
for i,(p,d) in enumerate(m):
    D=d*beat;n=int(D*.92*sr);tt=np.arange(n)/sr
    f=440*2**((p-69)/12)*2**((.35*np.sin(2*np.pi*5.5*tt)*np.clip(tt/.3-.5,0,1)+ .25*np.exp(-tt/.06)*-1)/12)
    ph=np.cumsum(f)/sr;s=np.zeros(n)
    for h in range(1,26):
        s+=np.sin(2*np.pi*h*ph)/h**1.1*(h*f<sr/2)
    s+=rng.normal(0,.05,n)
    s=formant(s,V[i%5],sr)
    e=np.minimum(tt/.03,1)*np.minimum((n/sr-tt)/.05,1)
    a=int(t*sr);v[a:a+n]+=s*e;notes.append({"on":t,"off":t+D,"p":p});t+=D
v/=np.abs(v).max()
# 伴奏: 3拍子の和音とベース、打楽器
acc=np.zeros(N);ch=[[53,60,65,69],[58,62,65,70],[60,64,67,70]]
T=t0;i=0;tot=sum(d for _,d in m)*beat
while T<t0+tot:
    c=ch[(i//3)%3] if (i%3) else ch[(i//3)%3]
    for q,pp in enumerate(c if i%3 else c[:1]):
        fr=440*2**((pp+key-69)/12);n=int(beat*.9*sr);tt=np.arange(n)/sr
        s=sum(np.sin(2*np.pi*fr*h*tt)/h**1.5 for h in range(1,7))*np.exp(-tt*2.5)
        a=int(T*sr);acc[a:a+n]+=s*.5
    a=int(T*sr);n=int(.12*sr);acc[a:a+n]+=rng.normal(0,.7,n)*np.exp(-np.arange(n)/sr*40)*(.5 if i%3 else 1)
    T+=beat;i+=1
acc/=np.abs(acc).max()
for name,g in [("vocal",0),("mix0",.5),("mix6",1.0)]:
    x=v+g*acc;x/=np.abs(x).max()*1.05;sf.write(f"{sys.argv[1]}_{name}.wav",x,sr,subtype="PCM_16")
json.dump({"bpm":bpm,"t0":t0,"beats_per_bar":3,"notes":notes},open(f"{sys.argv[1]}_truth.json","w"))
print(len(notes),round(total,1))
