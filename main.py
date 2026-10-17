"""
اجرا:  uvicorn main:app --host 0.0.0.0 --port 8000
نیازمندی‌ها: pip install fastapi uvicorn python-multipart faster-whisper
و نصب ffmpeg روی سرور. فونت Vazirmatn را در backend/fonts بگذارید.
برای مقیاس‌پذیری: BackgroundTasks را با Celery/RQ + Redis و ذخیره فایل‌ها را با S3 جایگزین کنید.
"""
import json
import subprocess
import uuid
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from faster_whisper import WhisperModel
from pydantic import BaseModel

from subtitles import Style, words_to_ass

DATA = Path("data")
DATA.mkdir(exist_ok=True)
FONTS = Path("fonts")

app = FastAPI(title="Captions API")
# روی CPU:  WhisperModel("medium", device="cpu", compute_type="int8")
model = WhisperModel("large-v3", device="cuda", compute_type="float16")
JOBS: dict[str, dict] = {}  # در تولید: Redis / DB


def vdir(video_id: str) -> Path:
    p = DATA / video_id
    if not p.exists():
        raise HTTPException(404, "video not found")
    return p


@app.post("/videos")
async def upload(file: UploadFile = File(...)):
    vid = uuid.uuid4().hex
    d = DATA / vid
    d.mkdir()
    with open(d / "input.mp4", "wb") as f:
        while chunk := await file.read(1 << 20):
            f.write(chunk)
    return {"video_id": vid}


def run_transcribe(job_id: str, vid: str, lang: str | None):
    try:
        d = DATA / vid
        JOBS[job_id]["status"] = "extracting_audio"
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(d / "input.mp4"), "-vn", "-ac", "1", "-ar", "16000", str(d / "audio.wav")],
            check=True, capture_output=True,
        )
        JOBS[job_id]["status"] = "transcribing"
        segments, info = model.transcribe(
            str(d / "audio.wav"), language=lang, word_timestamps=True, vad_filter=True
        )
        words = [
            {"w": w.word.strip(), "s": round(w.start, 2), "e": round(w.end, 2)}
            for seg in segments for w in (seg.words or []) if w.word.strip()
        ]
        (d / "captions.json").write_text(json.dumps(words, ensure_ascii=False))
        JOBS[job_id].update(status="done", language=info.language, words=words)
    except Exception as e:  # noqa
        JOBS[job_id].update(status="error", error=str(e))


@app.post("/videos/{vid}/transcribe")
def transcribe(vid: str, bg: BackgroundTasks, lang: str | None = None):
    vdir(vid)
    job_id = uuid.uuid4().hex
    JOBS[job_id] = {"status": "queued"}
    bg.add_task(run_transcribe, job_id, vid, lang)  # lang="fa" برای فارسی
    return {"job_id": job_id}


@app.get("/jobs/{job_id}")
def job(job_id: str):
    return JOBS.get(job_id) or HTTPException(404)


class Captions(BaseModel):
    words: list[dict]


@app.put("/videos/{vid}/captions")
def save_captions(vid: str, body: Captions):
    (vdir(vid) / "captions.json").write_text(json.dumps(body.words, ensure_ascii=False))
    return {"ok": True}


class ExportReq(BaseModel):
    words: list[dict]
    style: dict = {}


def run_export(job_id: str, vid: str, req: ExportReq):
    try:
        d = DATA / vid
        JOBS[job_id]["status"] = "rendering"
        (d / "sub.ass").write_text(words_to_ass(req.words, Style(**req.style)), encoding="utf-8")
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(d / "input.mp4"),
             "-vf", f"ass={d / 'sub.ass'}:fontsdir={FONTS}",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
             "-c:a", "copy", str(d / "output.mp4")],
            check=True, capture_output=True,
        )
        JOBS[job_id]["status"] = "done"
    except Exception as e:  # noqa
        JOBS[job_id].update(status="error", error=str(e))


@app.post("/videos/{vid}/export")
def export(vid: str, req: ExportReq, bg: BackgroundTasks):
    vdir(vid)
    job_id = uuid.uuid4().hex
    JOBS[job_id] = {"status": "queued"}
    bg.add_task(run_export, job_id, vid, req)
    return {"job_id": job_id}


@app.get("/videos/{vid}/download")
def download(vid: str):
    return FileResponse(vdir(vid) / "output.mp4", media_type="video/mp4", filename="captioned.mp4")
