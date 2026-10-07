const { chromium } = require('playwright'); const { spawn } = require('child_process');
(async()=>{
  const FPS=30, DUR=24, NF=FPS*DUR;
  const b=await chromium.launch(); const p=await b.newPage({viewport:{width:1920,height:1080}});
  await p.goto('file://'+__dirname+'/video.html'); await p.evaluate(()=>window.ready);
  const ff=spawn('ffmpeg',['-y','-loglevel','error','-f','image2pipe','-framerate',String(FPS),'-c:v','png','-i','-',
    '-c:v','libx264','-preset','slow','-crf','16','-pix_fmt','yuv420p',__dirname+'/silent.mp4'],{stdio:['pipe','inherit','inherit']});
  for(let i=0;i<NF;i++){ await p.evaluate(t=>render(t), i/FPS);
    const buf=await p.screenshot({type:'png'});
    if(!ff.stdin.write(buf)) await new Promise(r=>ff.stdin.once('drain',r));
    if(i%90===0) console.log('frame',i); }
  ff.stdin.end(); await new Promise(r=>ff.on('close',r)); await b.close();
})();
