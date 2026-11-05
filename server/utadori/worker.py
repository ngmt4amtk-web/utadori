"""1曲を別プロセスで処理する。終われば終了するのでモデルのメモリが残らない。"""
import json,subprocess,sys,pathlib
from . import transcribe
def main(d,meter,bpm,grid):
    d=pathlib.Path(d);st=d/"status.json"
    def put(**k):
        t=st.with_suffix(".tmp");t.write_text(json.dumps(k,ensure_ascii=False),encoding="utf-8");t.replace(st)
    try:
        put(state="running",step="音源の変換")
        src=next(p for p in d.iterdir() if p.stem=="source")
        subprocess.run(["ffmpeg","-v","error","-y","-i",str(src),"-ac","1","-ar","44100",str(d/"audio.wav")],check=True,timeout=300)
        subprocess.run(["ffmpeg","-v","error","-y","-i",str(d/"audio.wav"),"-c:a","aac","-b:a","96k",str(d/"audio.m4a")],check=True,timeout=300)
        sc=transcribe.run(str(d/"audio.wav"),meter=meter,bpm=bpm,grid=grid,progress=lambda s:put(state="running",step=s))
        (d/"score.json").write_text(json.dumps(sc,ensure_ascii=False),encoding="utf-8")
        (d/"auto.json").write_text(json.dumps(sc,ensure_ascii=False),encoding="utf-8")
        put(state="done",step="完了")
    except Exception as e:
        put(state="error",step=str(e)[:300])
if __name__=="__main__":
    main(sys.argv[1],int(sys.argv[2]),float(sys.argv[3]) or None,int(sys.argv[4]))
