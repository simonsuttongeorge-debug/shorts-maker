# shorts-maker

Turns a raw vertical talking-head clip into a branded short (9:16, 1080x1920) with
pause/retake cuts, word-by-word captions, a title behind the speaker's head, simple
motion graphics, optional b-roll, an end card, and English + Spanish caption versions.

## Pipeline
1. `setup.sh` - install deps, fetch the segmentation model
2. `pipeline/transcribe.py audio.wav small.en` - word timings -> `words.json`
3. `pipeline/cut.py src.mp4 edit.json out/` - keeps `segments`, loudness-normalises, writes `cut.mp4` + `timeline.json`
4. write `out/plan.json` (title, phrases with Spanish text, graphics, b-roll, end card) - see `examples_plan.json`
5. `pipeline/render.py out brands/<id> en|es out.mp4 [--preview]`
6. `pipeline/sheet.py video.mp4 sheet.jpg 1,5,10` - contact sheet for checking frames

## Brands
`brands/<id>/brand.json` holds colours, fonts, logo files and Blotato account IDs.
Current: `tpg` (Tenerife Property Group), `lt` (Local Tenerife).

Fonts are from Google Fonts (SIL Open Font License).
