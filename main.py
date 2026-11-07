
import os
import uuid
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

app = FastAPI(
    title="SSh AI Video Studio",
    description="AI Video Studio Backend API",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = Path("uploads")
OUTPUT_DIR = Path("outputs")

UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

jobs = {}

@app.get("/")
def home():
    return {
        "app": "SSh AI Video Studio",
        "status": "Running",
        "version": "1.0.0"
    }

@app.get("/health")
def health():
    return {"status": "healthy"}

@app.post("/upload")
async def upload_video(file: UploadFile = File(...)):
    allowed = {".mp4", ".mov", ".jpg", ".jpeg", ".png"}

    ext = Path(file.filename or "").suffix.lower()

    if ext not in allowed:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file format"
        )

    filename = str(uuid.uuid4()) + ext
    filepath = UPLOAD_DIR / filename

    data = await file.read()

    if len(data) > 100 * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail="File too large (100MB maximum)"
        )

    filepath.write_bytes(data)

    return {
        "success": True,
        "filename": filename,
        "download_url": f"/files/{filename}"
    }

class Subtitle(BaseModel):
    start: float
    end: float
    text: str

class SubtitleRequest(BaseModel):
    subtitles: list[Subtitle]

def to_srt_time(seconds):
    ms = int(seconds * 1000)
    hours = ms // 3600000
    minutes = (ms % 3600000) // 60000
    secs = (ms % 60000) // 1000
    millis = ms % 1000

    return (
        f"{hours:02}:{minutes:02}:"
        f"{secs:02},{millis:03}"
    )

@app.post("/subtitles")
def create_subtitles(request: SubtitleRequest):
    if len(request.subtitles) > 1000:
        raise HTTPException(400, "Too many subtitles")

    lines = []

    for index, sub in enumerate(request.subtitles, 1):
        if sub.start < 0 or sub.end <= sub.start:
            raise HTTPException(400, "Invalid subtitle timing")

        lines.extend([
            str(index),
            f"{to_srt_time(sub.start)} --> "
            f"{to_srt_time(sub.end)}",
            sub.text,
            ""
        ])

    filename = str(uuid.uuid4()) + ".srt"
    filepath = OUTPUT_DIR / filename

    filepath.write_text(
        "\n".join(lines),
        encoding="utf-8-sig"
    )

    return {
        "success": True,
        "filename": filename,
        "download_url": f"/files/{filename}"
    }

@app.get("/files/{filename}")
def download_file(filename: str):
    if Path(filename).name != filename:
        raise HTTPException(400, "Invalid filename")

    for folder in [UPLOAD_DIR, OUTPUT_DIR]:
        filepath = folder / filename

        if filepath.is_file():
            return FileResponse(
                filepath,
                filename=filename
            )

    raise HTTPException(404, "File not found")

@app.post("/jobs")
def create_job():
    job_id = str(uuid.uuid4())

    jobs[job_id] = {
        "status": "pending",
        "progress": 0,
        "message": "Waiting for AI processing"
    }

    return {
        "job_id": job_id,
        **jobs[job_id]
    }

@app.get("/jobs/{job_id}")
def get_job(job_id: str):
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")

    return {
        "job_id": job_id,
        **jobs[job_id]
    }
