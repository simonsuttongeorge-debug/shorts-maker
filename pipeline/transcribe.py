import json,sys
from faster_whisper import WhisperModel
m=WhisperModel(sys.argv[2] if len(sys.argv)>2 else "small.en",device="cpu",compute_type="int8")
import numpy as np, subprocess
aud=np.frombuffer(subprocess.run(["ffmpeg","-v","error","-i",sys.argv[1],"-f","s16le","-ac","1","-ar","16000","-"],capture_output=True).stdout,np.int16).astype(np.float32)/32768
segs,info=m.transcribe(aud,word_timestamps=True,vad_filter=False,initial_prompt="Local Tenerife, Los Cristianos, Adeje, Arona, Santa Cruz, La Laguna, Puerto de la Cruz, Teide.")
words=[]
for s in segs:
    for w in s.words: words.append({"w":w.word.strip(),"s":round(w.start,3),"e":round(w.end,3),"p":round(w.probability,2)})
json.dump(words,open("words.json","w"),indent=0)
print(" ".join(w["w"] for w in words))
