import numpy as np, wave
SR=44100; DUR=24.0; N=int(SR*DUR)
rng=np.random.default_rng(7)
L=np.zeros(N); R=np.zeros(N)
def mtof(m): return 440*2**((m-69)/12)
def add(sig,t0,gain=1.0,pan=0.0):
    i=int(t0*SR); j=min(N,i+len(sig)); s=sig[:j-i]*gain
    L[i:j]+=s*np.sqrt((1-pan)/2)*1.414; R[i:j]+=s*np.sqrt((1+pan)/2)*1.414
def env(n,a,d,sus=0.0,rel=None):
    t=np.arange(n)/SR; e=np.minimum(1,t/max(a,1e-4))*np.exp(-np.maximum(0,t-a)/d)
    return e*(1-sus)+sus*np.minimum(1,t/max(a,1e-4))
def lp(x,fc):  # static FFT lowpass (smooth rolloff)
    X=np.fft.rfft(x); f=np.fft.rfftfreq(len(x),1/SR); X*=1/np.sqrt(1+(f/fc)**4); return np.fft.irfft(X,len(x))
def hp(x,fc):
    X=np.fft.rfft(x); f=np.fft.rfftfreq(len(x),1/SR); X*=1/np.sqrt(1+(fc/np.maximum(f,1))**4); return np.fft.irfft(X,len(x))
def bp(x,lo,hi): return hp(lp(x,hi),lo)
def tone(f,dur,harm=(1,),amps=(1,),det=0.0):
    t=np.arange(int(dur*SR))/SR; s=np.zeros_like(t)
    for h,a in zip(harm,amps):
        s+=a*np.sin(2*np.pi*f*h*t)
        if det: s+=a*np.sin(2*np.pi*f*h*(1+det)*t)
    return s
BEAT=0.5
# chords per 2s bar (A minor): Am F C G
prog={0:[57,60,64],1:[53,57,60],2:[48,55,60,64],3:[55,59,62]}
roots={0:45,1:41,2:48,3:43}
def bar_idx(t): return int((t-5.5)//2)%4 if t>=5.5 else 0

# ---------- hook 0-3: drone, ticks, log blips, riser ----------
d=tone(55,3.2,(1,2,3),(1,.4,.15),det=.003); d*=np.minimum(1,np.arange(len(d))/SR/1.2)*np.exp(-np.maximum(0,np.arange(len(d))/SR-3.0)*8)
add(lp(d,400),0,0.22)
for k in range(24):           # 8th-note ticks accelerating to 16ths
    t0=k*0.125
    n=rng.standard_normal(int(.03*SR))*env(int(.03*SR),.001,.008)
    add(hp(n,7000),t0,0.05+0.04*(k/24),pan=0.3*(-1)**k)
penta=[69,72,74,76,79,81,84]
for k in range(40):           # log-line blips
    t0=0.05+k*0.07+rng.uniform(0,.03); m=penta[rng.integers(len(penta))]+12
    b=tone(mtof(m),.08)*env(int(.08*SR),.002,.02); add(b,t0,0.025,pan=rng.uniform(-.7,.7))
for t0 in (0.95,):            # "12,000 failed." low hit
    b=tone(55,1.2,(1,2),(1,.3))*env(int(1.2*SR),.003,.35); add(b,t0,0.35)
    n=rng.standard_normal(int(.25*SR))*env(int(.25*SR),.001,.06); add(lp(n,900),t0,0.12)
riser=rng.standard_normal(int(1.2*SR)); tr=np.arange(len(riser))/SR
riser=bp(riser,800,6000)*(tr/1.2)**2.5
add(riser,1.8,0.10)
# ---------- drop at 3.0 ----------
boom=tone(41.2,2.0,(1,2),(1,.25))*env(int(2*SR),.002,.6)
boom*=1+0*np.arange(len(boom))
add(boom,3.0,0.45)
pad_notes=[(3.0,[57,60,64,71],2.5)]
def pad(t0,notes,dur,g=0.06):
    n=int(dur*SR); t=np.arange(n)/SR; s=np.zeros(n)
    for m in notes:
        f=mtof(m)
        for h,a in ((1,1),(2,.35),(3,.18),(4,.08)):
            s+=a*(np.sin(2*np.pi*f*h*t)+np.sin(2*np.pi*f*h*1.004*t+1.3))
    e=np.minimum(1,t/0.35)*np.minimum(1,(dur-t)/0.4).clip(0,1)
    add(lp(s*e,2200),t0,g,0); 
pad(3.0,[57,60,64,71],2.6,0.05)
pad(5.5,[53,57,60,64],0.0001+2.0,0.035)
# ---------- groove 5.5-21 ----------
def kick(t0,g=0.5):
    n=int(.35*SR); t=np.arange(n)/SR; f=48+90*np.exp(-t*35)
    s=np.sin(2*np.pi*np.cumsum(f)/SR)*np.exp(-t*9); add(s,t0,g)
def hat(t0,g=0.04,pan=0.2):
    n=int(.05*SR); s=rng.standard_normal(n)*env(n,.001,.012); add(hp(s,8000),t0,g,pan)
for bar in range(8):          # 5.5 .. 21.5
    b0=5.5+bar*2; ci=bar%4
    if b0>=21: break
    pad(b0,prog[ci]+[prog[ci][0]+12],2.05,0.028)
    for q in range(4):
        tq=b0+q*BEAT
        if tq<21: kick(tq,0.42 if tq>=5.5 else 0)
        if tq+.25<21: hat(tq+.25,0.035,pan=.25)
    for e8 in range(8):       # bass 8ths
        tq=b0+e8*.25
        if tq>=21: break
        f=mtof(roots[ci]-12 if e8%2==0 else roots[ci])
        n=int(.24*SR); s=tone(f,.24,(1,2,3),(1,.5,.2))*env(n,.004,.09); add(lp(s,700),tq,0.12)
    arp=prog[ci]+[prog[ci][1]+12]
    for s16 in range(16):     # pluck arp with echo
        tq=b0+s16*.125
        if tq>=21: break
        m=arp[s16%4]+12; n=int(.3*SR)
        p=tone(mtof(m),.3,(1,2,3),(1,.3,.1))*env(n,.002,.07)
        g=0.03 if s16%2==0 else 0.018
        add(p,tq,g,pan=-.35); add(p,tq+.375,g*.35,pan=.35)
# ---------- sfx in key ----------
def blip(t0,m,g=0.05,dec=.06,pan=0):
    n=int(.4*SR); b=tone(mtof(m),.4,(1,2,4),(1,.25,.08))*env(n,.002,dec); add(b,t0,g,pan)
def whoosh(t0,g=0.06,dur=.45):
    n=int(dur*SR); t=np.arange(n)/SR; s=rng.standard_normal(n)
    e=np.sin(np.pi*t/dur)**2; add(bp(s,500,4000)*e,t0,g)
for t0 in (5.3,8.9,12.9,17.4,20.85): whoosh(t0)
# click on "Use Bundled Sample"
blip(6.52,81,0.07,.03); n=int(.01*SR); add(hp(rng.standard_normal(n)*env(n,.0005,.002),3000),6.52,0.05)
# KPI count ticks
for k in range(10): blip(7.15+k*.085,76+[0,3,5,7,10][k%5],0.018,.02,pan=.3)
# SHAP bars: rising pentatonic plucks
sc=[57,60,62,64,67,69,72,74,76,79]
for i in range(10): blip(9.3+i*.09,sc[i]+12,0.022,.05,pan=-.2+.04*i)
blip(10.9,69,0.05,.25)    # highlight top bar
# fingerprint rows
for i in range(7): blip(13.2+i*.08,[64,67,69,72,74,76,79][i]+12,0.016,.03,pan=.2)
blip(14.3,76,0.05,.4); blip(14.5,88,0.04,.5,pan=.2)   # row + ring
# "A real RTL bug." impact
b=tone(55,1.6,(1,2,3),(1,.35,.1))*env(int(1.6*SR),.003,.5); add(b,15.0,0.32)
for m in (57,64,69,72): blip(15.0,m+12,0.035,.7)
# recommendations
for i in range(3): blip(18.5+i*.12,[69,72,76][i]+12,0.022,.05)
for m in (69,76,81): blip(19.35,m,0.03,.6)
# ---------- outro 21-24 ----------
boom2=tone(55,3,(1,2),(1,.2))*env(int(3*SR),.003,.9); add(boom2,21.0,0.3)
pad(21.0,[57,64,69,71,72],3.0,0.05)
for k,m in enumerate([69,72,76,79,81,84]): blip(21.0+k*.125,m+12,0.028,.25,pan=-.3+.12*k)
# ---------- reverb + master ----------
ir_n=int(1.8*SR); tt=np.arange(ir_n)/SR
ir=rng.standard_normal(ir_n)*np.exp(-tt*3.2); ir=lp(ir,5000); ir/=np.sqrt(np.sum(ir**2))
def conv(x):
    m=len(x)+ir_n; F=np.fft.rfft(x,m)*np.fft.rfft(ir,m); return np.fft.irfft(F,m)[:len(x)]
L=L+0.22*conv(L); R=R+0.22*conv(R)
L=hp(L,30); R=hp(R,30)
# fade tail
t=np.arange(N)/SR; fade=np.clip((24.0-t)/0.9,0,1); L*=fade; R*=fade
peak=max(np.abs(L).max(),np.abs(R).max()); g=0.89/peak
L=np.tanh(L*g*1.1)/np.tanh(1.1); R=np.tanh(R*g*1.1)/np.tanh(1.1)
st=(np.stack([L,R],1)*32767*0.95).astype(np.int16)
with wave.open('music.wav','wb') as w: w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(st.tobytes())
print('ok',peak)
