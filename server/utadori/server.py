"""うたどり: 歌の旋律の下書きを作り、人が直すためのサーバー。Tailscale内だけで使う。"""
import json,os,pathlib,re,shutil,subprocess,sys,tempfile,threading,queue,time,uuid
from fastapi import FastAPI,File,Form,HTTPException,UploadFile,Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse,JSONResponse,Response
from fastapi.staticfiles import StaticFiles
from . import music
ROOT=pathlib.Path(__file__).resolve().parent.parent;DATA=pathlib.Path(os.environ.get("UTADORI_DATA",ROOT/"data"));DATA.mkdir(exist_ok=True)
CHROME=os.path.expanduser("~/.hermes/tools/chromium-1208/chrome-linux64/chrome")
MAXB=200*1024*1024;EXT={".mp3",".m4a",".wav",".aac",".flac",".ogg",".opus",".mp4",".mov"}
q=queue.Queue()
def loop():
    while True:
        i,m,b,g=q.get()
        try:
            subprocess.run([sys.executable,"-m","utadori.worker",str(DATA/i),str(m),str(b or 0),str(g)],cwd=ROOT,timeout=1800)
        except Exception as e:
            st=DATA/i/"status.json";st.write_text(json.dumps(dict(state="error",step=f"処理を止めました: {type(e).__name__}"),ensure_ascii=False),encoding="utf-8")
        finally:
            q.task_done()
threading.Thread(target=loop,daemon=True).start()
app=FastAPI(title="うたどり")
app.add_middleware(CORSMiddleware,allow_origins=["https://ngmt4amtk-web.github.io"],allow_methods=["GET","POST","PUT"],allow_headers=["Content-Type"],expose_headers=["Content-Disposition"])
def jd(i):
    if not re.fullmatch(r"[0-9a-f]{12}",i) or not (DATA/i).is_dir():raise HTTPException(404,"見つかりません")
    return DATA/i
def meta(d):return json.loads((d/"meta.json").read_text(encoding="utf-8"))
@app.post("/api/jobs")
async def create(file:UploadFile=File(...),title:str=Form(""),meter:int=Form(4),bpm:float=Form(0),grid:int=Form(3)):
    ext=pathlib.Path(file.filename or "").suffix.lower()
    if ext not in EXT:raise HTTPException(400,"音声か動画のファイルを選んでください")
    if meter not in(2,3,4) or grid not in(3,6) or not(0==bpm or 30<=bpm<=260):raise HTTPException(400,"設定の値が範囲外です")
    i=uuid.uuid4().hex[:12];d=DATA/i;d.mkdir();n=0
    with open(d/f"source{ext}","wb") as w:
        while c:=await file.read(1<<20):
            n+=len(c)
            if n>MAXB:
                w.close();shutil.rmtree(d);raise HTTPException(413,"200MBまでです")
            w.write(c)
    (d/"meta.json").write_text(json.dumps(dict(id=i,title=title or pathlib.Path(file.filename).stem,created=time.time()),ensure_ascii=False),encoding="utf-8")
    (d/"status.json").write_text(json.dumps(dict(state="queued",step="順番待ち"),ensure_ascii=False),encoding="utf-8")
    q.put((i,meter,bpm,grid));return dict(id=i)
@app.get("/api/jobs")
def jobs():
    r=[]
    for d in DATA.iterdir():
        if (d/"meta.json").exists():r.append({**meta(d),**json.loads((d/"status.json").read_text(encoding="utf-8"))})
    return sorted(r,key=lambda x:-x["created"])
@app.get("/api/jobs/{i}")
def job(i:str):
    d=jd(i);return {**meta(d),**json.loads((d/"status.json").read_text(encoding="utf-8"))}
@app.get("/api/jobs/{i}/score")
def score(i:str):
    p=jd(i)/"score.json"
    if not p.exists():raise HTTPException(409,"まだできていません")
    return JSONResponse(json.loads(p.read_text(encoding="utf-8")),headers={"Cache-Control":"no-store"})
@app.put("/api/jobs/{i}/score")
async def save(i:str,req:Request):
    d=jd(i);sc=await req.json()
    if not isinstance(sc.get("notes"),list) or sc.get("meter") not in(2,3,4):raise HTTPException(400,"形が違います")
    try:
        music.validate(sc)
        if sc["notes"]:music.to_musicxml(sc)
    except (ValueError,KeyError,TypeError) as e:
        raise HTTPException(400,f"保存できません: {e}")
    t=d/"score.tmp";t.write_text(json.dumps(sc,ensure_ascii=False),encoding="utf-8");t.replace(d/"score.json");return dict(ok=True)
@app.post("/api/jobs/{i}/reset")
def reset(i:str):
    d=jd(i);shutil.copy(d/"auto.json",d/"score.json");return dict(ok=True)
@app.get("/api/jobs/{i}/audio")
def audio(i:str):return FileResponse(jd(i)/"audio.m4a",media_type="audio/mp4")
def xml(d):
    return music.to_musicxml(json.loads((d/"score.json").read_text(encoding="utf-8")),meta(d)["title"])
@app.get("/api/jobs/{i}/svg")
def svg(i:str):return dict(pages=music.to_svg(xml(jd(i))))
def fname(d,ext):
    from urllib.parse import quote
    return {"Content-Disposition":"attachment; filename*=UTF-8''"+quote(meta(d)["title"]+ext)}
@app.get("/api/jobs/{i}/musicxml")
def mx(i:str):
    d=jd(i);return Response(xml(d),media_type="application/vnd.recordare.musicxml+xml",headers=fname(d,".musicxml"))
@app.get("/api/jobs/{i}/pdf")
def pdf(i:str):
    d=jd(i);pages=music.to_svg(xml(d),width=1000)
    with tempfile.TemporaryDirectory() as t:
        h=pathlib.Path(t)/"p.html";o=pathlib.Path(t)/"o.pdf"
        h.write_text("<!doctype html><meta charset=utf-8><style>@page{size:A4;margin:10mm}body{margin:0}div{break-after:page}svg{width:100%;height:auto}</style>"+"".join(f"<div>{p}</div>" for p in pages),encoding="utf-8")
        subprocess.run([CHROME,"--headless","--no-sandbox","--disable-gpu","--no-pdf-header-footer",f"--print-to-pdf={o}",f"file://{h}"],check=True,timeout=90,capture_output=True)
        return Response(o.read_bytes(),media_type="application/pdf",headers=fname(d,".pdf"))
WEB=ROOT/"web" if (ROOT/"web").is_dir() else ROOT.parent/"docs"
app.mount("/",StaticFiles(directory=WEB,html=True),name="web")
