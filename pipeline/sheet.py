import sys, subprocess
from PIL import Image, ImageDraw
vid, out = sys.argv[1], sys.argv[2]; ts=[float(x) for x in sys.argv[3].split(',')]
ims=[]
for t in ts:
    p=f'/tmp/sh_{t}.png'; subprocess.run(['ffmpeg','-y','-v','error','-ss',str(t),'-i',vid,'-frames:v','1','-vf','scale=270:480',p],check=True)
    im=Image.open(p).convert('RGB'); ImageDraw.Draw(im).text((6,6),f'{t:.1f}s',fill=(255,0,0)); ims.append(im)
cols=min(5,len(ims)); rows=(len(ims)+cols-1)//cols
S=Image.new('RGB',(270*cols,480*rows),(20,20,20))
for i,im in enumerate(ims): S.paste(im,((i%cols)*270,(i//cols)*480))
S.save(out)
