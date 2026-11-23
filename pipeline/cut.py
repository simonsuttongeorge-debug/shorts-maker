"""Cut a clip down to the kept segments and remap word timings onto the new timeline.

Usage: python cut.py src.mp4 edit.json out_dir
edit.json needs "segments": [[start,end],...] in source seconds and "words": [{w,s,e}] in source seconds.
Writes out_dir/cut.mp4 (1080x1920, loudness-normalised) and out_dir/timeline.json (words in output seconds).
"""
import json, subprocess, sys, os

def main(src, edit_path, out):
    ed = json.load(open(edit_path))
    # snap to the 30fps grid so video and audio lengths match exactly (no caption drift)
    segs = [[round(s * 30) / 30, round(e * 30) / 30] for s, e in ed["segments"]]
    os.makedirs(out, exist_ok=True)
    # Render each segment separately, then concat. A single filter graph with many
    # trims of a 1080x1920 source runs out of memory on small machines (SIGKILL).
    tmp = os.path.join(out, "_segs"); os.makedirs(tmp, exist_ok=True)
    lst = []
    for i, (s, e) in enumerate(segs):
        d = e - s
        f = os.path.join(tmp, f"s{i:03d}.mp4")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{s:.3f}", "-i", src, "-t", f"{d:.3f}",
                        "-af", f"afade=t=in:d=0.02,afade=t=out:st={max(d-0.03,0):.3f}:d=0.03",
                        "-r", "30", "-frames:v", str(round(d * 30)), "-c:v", "libx264", "-preset", "veryfast", "-crf", "16",
                        "-c:a", "pcm_s16le", "-ar", "48000", f.replace(".mp4", ".mov")], check=True)
        lst.append(f"file '{os.path.abspath(f.replace('.mp4', '.mov'))}'")
    open(os.path.join(tmp, "list.txt"), "w").write("\n".join(lst) + "\n")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", os.path.join(tmp, "list.txt"),
                    "-c:v", "copy", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000",
                    "-c:a", "aac", "-b:a", "192k", os.path.join(out, "cut.mp4")], check=True)
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
