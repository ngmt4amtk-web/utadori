"""歌入りの音源から旋律の譜面データを作る。

出力は tick 単位（1拍=12tick）の音符列。16分と3連8分を同じ格子に乗せる。
"""
import numpy as np,librosa
from . import f0 as F
TPB=12;LO=36;HI=96
MAJ=np.array([6.35,2.23,3.48,2.33,4.38,4.09,2.52,5.19,2.39,3.66,2.29,2.88]);MIN=np.array([6.33,2.68,3.52,5.38,2.60,3.53,2.54,4.75,3.98,2.69,3.34,3.17])

def to_midi(fq):
    m=np.full(len(fq),np.nan);v=fq>0;m[v]=69+12*np.log2(fq[v]/440);return m

def viterbi(m,conf,switch=14.0,enter=8.0,sigma=.55):
    """音高列を音符の段へ。状態0=休符、1..=半音。ビブラートでは段が変わらない重みにする。"""
    st=np.arange(LO,HI+1);K=len(st)+1;T=len(m);e=np.zeros((T,K))
    v=~np.isnan(m);d=np.zeros((T,K-1));d[v]=((m[v,None]-st)/sigma)**2/2
    e[:,1:]=d;e[v,0]=4.0;e[~v,1:]=4.0
    D=e[0].copy();B=np.zeros((T,K),np.int16)
    for t in range(1,T):
        best=np.argmin(D);alt=D[best]+switch
        r=D[0]+enter;  # 休符から
        n=D.copy();b=np.arange(K)
        c=alt<n;n[c]=alt;b[c]=best
        c=(r<n);c[0]=False;n[c]=r;b[c]=0
        q=np.min(D[1:])+2.0
        if q<n[0]:n[0]=q;b[0]=1+np.argmin(D[1:])
        D=n+e[t];B[t]=b
    p=np.zeros(T,int);p[-1]=int(np.argmin(D))
    for t in range(T-2,-1,-1):p[t]=B[t+1,p[t+1]]
    return p

def segments(m,conf,minlen=.07):
    p=viterbi(m,conf);out=[];i=0;T=len(p)
    while i<T:
        j=i
        while j<T and p[j]==p[i]:j+=1
        if p[i]>0 and (j-i)*.01>=minlen:
            k=p[i]+LO-1;g=m[i:j];ok=~np.isnan(g)
            c=float(np.mean(conf[i:j]));dev=float(np.nanmedian(np.abs(g[ok]-k))) if ok.any() else 1.
            out.append(dict(t0=i*.01,t1=j*.01,p=int(k),conf=c,dev=dev))
        i=j
    return out

def beats(y22,sr=22050,bpm=None,meter=4):
    h,pc=librosa.effects.hpss(y22)
    oe=librosa.onset.onset_strength(y=pc,sr=sr)
    kw=dict(start_bpm=bpm,tightness=800) if bpm else dict(tightness=300)
    t,b=librosa.beat.beat_track(onset_envelope=oe,sr=sr,units="time",**kw)
    if len(b)<8:
        raise ValueError("拍を検出できませんでした。テンポを指定してください")
    ibi=np.median(np.diff(b));tempo=60*(len(b)-1)/(b[-1]-b[0])
    # 拍の刻みを前後へ延ばす
    pre=np.arange(b[0]-ibi,-ibi,-ibi)[::-1];post=np.arange(b[-1]+ibi,len(y22)/sr+ibi*2,ibi)
    bb=np.r_[pre,b,post]
    lo=librosa.onset.onset_strength(S=librosa.feature.melspectrogram(y=pc,sr=sr,fmax=150,n_mels=16),sr=sr)
    fr=librosa.time_to_frames(bb,sr=sr);fr=np.clip(fr,0,len(lo)-1);val=lo[fr]
    ph=int(np.argmax([val[i::meter].mean() for i in range(meter)]))
    return bb,float(tempo),ph

def quantize(segs,bb,ph,grid=3):
    """tick へ丸める。grid=3 で16分。"""
    idx=np.arange(len(bb))
    tk=lambda t:np.interp(t,bb,idx)*TPB
    notes=[]
    for s in segs:
        a=int(round((tk(s["t0"])-ph*TPB)/grid))*grid;e=int(round((tk(s["t1"])-ph*TPB)/grid))*grid
        if e<=a:e=a+grid
        notes.append(dict(s,on=a,dur=e-a))
    # 重なりは前の音を詰め、同じ位置は短い方を捨てる
    r=[]
    for n in sorted(notes,key=lambda x:(x["on"],-x["dur"])):
        if r and n["on"]<=r[-1]["on"]:continue
        if r and r[-1]["on"]+r[-1]["dur"]>n["on"]:r[-1]["dur"]=n["on"]-r[-1]["on"]
        r.append(n)
    # 短い隙間は前の音を伸ばす（歌の子音の切れ目）
    for a,b in zip(r,r[1:]):
        g=b["on"]-a["on"]-a["dur"]
        if 0<g<=grid:a["dur"]+=g
    return r

def key_of(notes):
    h=np.zeros(12)
    for n in notes:h[n["p"]%12]+=n["dur"]
    if h.sum()==0:return dict(tonic=0,mode="major",score=0.)
    best=max(((float(np.corrcoef(h,np.roll(pf,i))[0,1]),i,md) for md,pf in (("major",MAJ),("minor",MIN)) for i in range(12)))
    return dict(tonic=best[1],mode=best[2],score=best[0])

def key_of_audio(y22,notes,sr=22050):
    """伴奏の響きと旋律を合わせて調を推定する。旋律だけより終わりの音に引きずられにくい。"""
    c=librosa.feature.chroma_cqt(y=librosa.effects.harmonic(y22),sr=sr,bins_per_octave=36).mean(1)
    h=np.zeros(12)
    for n in notes:h[n["p"]%12]+=n["dur"]
    v=c/max(c.sum(),1e-9)+.5*h/max(h.sum(),1e-9)
    best=max(((float(np.corrcoef(v,np.roll(pf,i))[0,1]),i,md) for md,pf in (("major",MAJ),("minor",MIN)) for i in range(12)))
    return dict(tonic=best[1],mode=best[2],score=round(best[0],3))

def flag(n):
    """機械の自信が低い音に印を付ける。"""
    return n["conf"]<.55 or n["dev"]>.45

def run(path,meter=4,bpm=None,grid=3,sess=None,progress=lambda s:None):
    progress("読み込み")
    y=F.load(path);y22,_=librosa.load(path,sr=22050,mono=True)
    progress("歌の音高");sess=sess or F.session();sal=F.infer(sess,y);fq,conf=F.decode(sal);m=to_midi(fq)
    progress("音符へ分割");segs=split_repeats(segments(m,conf),harmonic_env(y,fq),fq)
    progress("拍の検出");bb,tempo,ph=beats(y22,bpm=bpm,meter=meter)
    ns=quantize(segs,bb,ph,grid);k=key_of_audio(y22,ns)
    for i,n in enumerate(ns):
        n["id"]=i;n["unsure"]=bool(flag(n));n["lyric"]=""
    b=[{k2:(round(v,3) if isinstance(v,float) else v) for k2,v in n.items()} for n in ns]
    return dict(version=1,tpb=TPB,meter=meter,grid=grid,tempo=round(tempo,1),beat_offset=ph,beats=[round(float(x),3) for x in bb],key=k,notes=b,duration=round(len(y)/16000,2))

def harmonic_env(y,fq,sr=16000,hop=160):
    """検出した音高の倍音だけを足した音量。伴奏があっても歌の音の切れ目が出やすい。"""
    S=np.abs(librosa.stft(y,n_fft=1024,hop_length=hop,win_length=1024,center=True));T=min(S.shape[1],len(fq));e=np.zeros(len(fq))
    binhz=sr/1024
    for t in range(T):
        f=fq[t]
        if f<=0:continue
        k=[int(round(h*f/binhz)) for h in range(1,7) if h*f<sr/2-50]
        e[t]=sum(S[max(0,i-1):i+2,t].max() for i in k)
    return 20*np.log10(e+1e-3)

def split_repeats(segs,env,fq,depth=5.0,minlen=.09):
    """同じ高さの連続を、歌の音量の谷で分ける。"""
    from scipy.signal import find_peaks,medfilt
    out=[];E=medfilt(env,5)
    for s in segs:
        a=int(s["t0"]*100);b=int(s["t1"]*100);g=E[a:b]
        unv=np.flatnonzero(fq[a:b]<=0)
        cuts=set()
        if len(g)>=20:
            pk,_=find_peaks(-g,prominence=depth,distance=int(minlen*100))
            cuts|={a+int(i) for i in pk}
        if len(unv):
            r=np.split(unv,np.flatnonzero(np.diff(unv)>1)+1)
            cuts|={a+int(x[len(x)//2]) for x in r if len(x)>=2}
        cs=sorted(c for c in cuts if a+minlen*100<=c<=b-minlen*100)
        prev=a
        for c in cs+[b]:
            if (c-prev)*.01>=minlen:out.append(dict(s,t0=prev*.01,t1=c*.01));prev=c
    return out
