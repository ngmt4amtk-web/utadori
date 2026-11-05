"""RMVPE(ONNX)で歌の基本周波数を取る。長い音源はメモリを抑えるため区切って流す。"""
import numpy as np,librosa,onnxruntime as ort
SR=16000;HOP=160
_mel=librosa.filters.mel(sr=SR,n_fft=1024,n_mels=128,fmin=30,fmax=8000,htk=True)
_cb=(20*np.arange(360)+1997.3794084376191)
def session(path="models/rmvpe.onnx",threads=4):
    o=ort.SessionOptions();o.intra_op_num_threads=threads;o.inter_op_num_threads=1
    o.enable_cpu_mem_arena=False;o.enable_mem_pattern=False
    return ort.InferenceSession(path,o,providers=["CPUExecutionProvider"])
def logmel(y):
    S=np.abs(librosa.stft(y,n_fft=1024,hop_length=HOP,win_length=1024,window="hann",center=True))
    return np.log(np.maximum(_mel@S,1e-5)).astype(np.float32)
def infer(sess,y,chunk_s=20):
    n=int(chunk_s*SR/HOP);ov=64;M=logmel(y);T=M.shape[1];out=np.zeros((T,360),np.float32);st=0
    while st<T:
        ed=min(T,st+n);L=ed-st;pad=(32-L%32)%32
        x=np.pad(M[:,st:ed],((0,0),(0,pad)),mode="constant",constant_values=np.log(1e-5))[None]
        p=sess.run(None,{"input":x})[0][0][:L]
        keep=0 if st==0 else ov//2
        out[st+keep:ed]=p[keep:];
        if ed==T:break
        st=ed-ov
    return out
def decode(sal,thr=.03):
    c=sal.argmax(1);a=np.clip(c-4,0,None);b=np.minimum(a+9,360)
    idx=np.arange(360)
    f=np.zeros(len(sal));conf=sal.max(1)
    for i in range(len(sal)):
        w=sal[i,a[i]:b[i]];s=w.sum()
        f[i]=10*2**(((w*_cb[a[i]:b[i]]).sum()/s if s>0 else 0)/1200) if conf[i]>thr else 0
    return f,conf
def load(path):
    y,_=librosa.load(path,sr=SR,mono=True);return y.astype(np.float32)
