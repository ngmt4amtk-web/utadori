"""譜面データ（tick単位の音符列）を MusicXML と SVG へ変える。"""
from xml.sax.saxutils import escape
import os,threading,verovio
RES=os.path.join(os.path.dirname(verovio.__file__),"data")
LOCK=threading.Lock()
VALS=[(48,"whole",0),(36,"half",1),(24,"half",0),(18,"quarter",1),(12,"quarter",0),(9,"eighth",1),(6,"eighth",0),(3,"16th",0)]
FIFTHS={(0,"major"):0,(7,"major"):1,(2,"major"):2,(9,"major"):3,(4,"major"):4,(11,"major"):5,(6,"major"):6,(1,"major"):-5,(8,"major"):-4,(3,"major"):-3,(10,"major"):-2,(5,"major"):-1}
def fifths(key):
    if isinstance(key.get("fifths"),int) and -7<=key["fifths"]<=7:return key["fifths"]
    t=key["tonic"]
    if key["mode"]=="minor":t=(t+3)%12
    return FIFTHS[(t,"major")]
SH=[("C",0),("C",1),("D",0),("D",1),("E",0),("F",0),("F",1),("G",0),("G",1),("A",0),("A",1),("B",0)]
FL=[("C",0),("D",-1),("D",0),("E",-1),("E",0),("F",0),("G",-1),("G",0),("A",-1),("A",0),("B",-1),("B",0)]
def spell(p,fif):
    s,a=(SH if fif>=0 else FL)[p%12];return s,a,p//12-1
def pieces(pos,dur,bar):
    """小節の中の位置 pos から dur を書ける音価に分ける。半端な位置では拍で区切る。"""
    out=[]
    while dur>0:
        for v,t,d in VALS:
            if v<=dur and pos%(12 if v>=12 else v if v in(3,6) else 6)==0 and (pos%bar)+v<=bar:
                out.append((v,t,d));pos+=v;dur-=v;break
        else:
            raise ValueError(f"書けない長さ pos={pos} dur={dur}")
    return out
def validate(sc):
    """保存前の検査。grid の外れと音の重なりは譜面が黙って変わるので受け取らない。"""
    g=sc.get("grid",3)
    ns=sorted(sc["notes"],key=lambda n:n["on"]);last=None
    for n in ns:
        for k in("on","dur","p"):
            if not isinstance(n.get(k),int):raise ValueError(f"{k} が整数ではありません")
        if n["dur"]<=0 or n["dur"]%g or n["on"]%g:raise ValueError("音の位置か長さが刻みに合っていません")
        if not 0<=n["p"]<=127:raise ValueError("音の高さが範囲外です")
        if last is not None and n["on"]<last:raise ValueError("音が重なっています")
        last=n["on"]+n["dur"]
def clean(notes):
    r=[];last=None
    for n in sorted(notes,key=lambda x:x["on"]):
        n=dict(n);n["on"]=int(n["on"]);n["dur"]=int(n["dur"])
        if n["dur"]<=0:continue
        if last is not None and n["on"]<last["on"]+last["dur"]:last["dur"]=n["on"]-last["on"]
        r.append(n);last=n
    return [n for n in r if n["dur"]>0]
def to_musicxml(sc,title="無題"):
    m=sc["meter"];bar=m*12;fif=fifths(sc["key"]);ns=clean(sc["notes"])
    if not ns:raise ValueError("音符がありません")
    b0=ns[0]["on"]//bar;nb=(ns[-1]["on"]+ns[-1]["dur"]-1)//bar-b0+1
    mea=[[] for _ in range(nb)]
    def push(i,x):mea[i].append(x)
    cur=b0*bar
    def rest(a,z):
        while a<z:
            e=min(z,(a//bar+1)*bar);i=a//bar-b0
            for v,t,d in pieces(a%bar,e-a,bar):
                push(i,f'<note><rest/><duration>{v}</duration><voice>1</voice><type>{t}</type>{"<dot/>" if d else ""}</note>')
            a=e
    for n in ns:
        rest(cur,n["on"]);a=n["on"];z=a+n["dur"];first=True;seg=[]
        while a<z:
            e=min(z,(a//bar+1)*bar)
            for pi in pieces(a%bar,e-a,bar):seg.append((a//bar-b0,pi))
            a=e
        s,al,oc=spell(n["p"],fif)
        for k,(i,(v,t,d)) in enumerate(seg):
            tie="";nt=""
            if k>0:tie+='<tie type="stop"/>';nt+='<tied type="stop"/>'
            if k<len(seg)-1:tie+='<tie type="start"/>';nt+='<tied type="start"/>'
            col=' color="#C62828"' if n.get("unsure") else ""
            ly=""
            if k==0 and n.get("lyric"):ly=f'<lyric number="1"><syllabic>single</syllabic><text>{escape(n["lyric"])}</text></lyric>'
            alt=f"<alter>{al}</alter>" if al else ""
            push(i,f'<note{col}><pitch><step>{s}</step>{alt}<octave>{oc}</octave></pitch><duration>{v}</duration>{tie}<voice>1</voice><type>{t}</type>{"<dot/>" if d else ""}{"<notations>"+nt+"</notations>" if nt else ""}{ly}</note>')
        cur=z
    rest(cur,(b0+nb)*bar)
    x=[f'<?xml version="1.0" encoding="UTF-8"?><score-partwise version="4.0"><work><work-title>{escape(title)}</work-title></work><part-list><score-part id="P1"><part-name>旋律</part-name></score-part></part-list><part id="P1">']
    for i,c in enumerate(mea):
        at=""
        if i==0:at=f'<attributes><divisions>12</divisions><key><fifths>{fif}</fifths></key><time><beats>{m}</beats><beat-type>4</beat-type></time><clef><sign>G</sign><line>2</line></clef></attributes><direction placement="above"><direction-type><metronome><beat-unit>quarter</beat-unit><per-minute>{round(sc["tempo"])}</per-minute></metronome></direction-type></direction>'
        x.append(f'<measure number="{i+1}">{at}{"".join(c)}</measure>')
    x.append("</part></score-partwise>");return "".join(x)
def to_svg(xml,width=1000):
    with LOCK:
        tk=verovio.toolkit();tk.setResourcePath(RES)
        tk.setOptions({"pageWidth":width,"pageHeight":1400,"scale":45,"adjustPageHeight":False,"footer":"none","header":"none","breaks":"auto"})
        if not tk.loadData(xml):raise ValueError("譜面を読み込めません")
        return [tk.renderToSVG(i+1) for i in range(tk.getPageCount())]
