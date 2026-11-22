"""Cut a clip down to the kept segments and remap word timings onto the new timeline.

Usage: python cut.py src.mp4 edit.json out_dir
edit.json needs "segments": [[start,end],...] in source seconds and "words": [{w,s,e}] in source seconds.
Writes out_dir/cut.mp4 (1080x1920, loudness-normalised) and out_dir/timeline.json (words in output seconds).
"""
import json, subprocess, sys, os

def main(src, edit_path, out):
    ed = json.load(open(edit_path))
    segs = ed["segments"]
    os.makedirs(out, exist_ok=True)
    parts = []
    for i, (s, e) in enumerate(segs):
        d = e - s
        parts.append(f"[0:v]trim={s}:{e},setpts=PTS-STARTPTS[v{i}];"
                     f"[0:a]atrim={s}:{e},asetpts=PTS-STARTPTS,afade=t=in:d=0.02,afade=t=out:st={max(d-0.03,0)}:d=0.03[a{i}];")
    cat = "".join(f"[v{i}][a{i}]" for i in range(len(segs))) + f"concat=n={len(segs)}:v=1:a=1[v][a0];[a0]loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000[a]"
    fc = "".join(parts) + cat
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", src, "-filter_complex", fc, "-map", "[v]", "-map", "[a]",
                    "-r", "30", "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-c:a", "aac", "-b:a", "192k",
                    os.path.join(out, "cut.mp4")], check=True)
    # remap words
    out_words, offset, seg_index = [], 0.0, []
    for i, (s, e) in enumerate(segs):
        for w in ed["words"]:
            mid = (w["s"] + w["e"]) / 2
            if s <= mid < e:
                out_words.append({**w, "s": round(max(w["s"], s) - s + offset, 3), "e": round(min(w["e"], e) - s + offset, 3), "seg": i})
        seg_index.append([round(offset, 3), round(offset + e - s, 3)])
        offset += e - s
    json.dump({"duration": round(offset, 3), "segments": seg_index, "words": out_words}, open(os.path.join(out, "timeline.json"), "w"), indent=1)
    print("duration", round(offset, 2), "words", len(out_words))

if __name__ == "__main__":
    main(*sys.argv[1:4])
