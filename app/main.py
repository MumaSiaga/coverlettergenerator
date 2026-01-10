import os
import re
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import httpx
import PyPDF2

app = FastAPI(title="Cover Letter Generator API")

# CORS (lock this down later)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API key
API_KEY = os.getenv("OPENROUTER_API_KEY")
if not API_KEY:
    raise RuntimeError("OPENROUTER_API_KEY environment variable not set")


def extract_text_from_pdf(file: UploadFile) -> str:
    try:
        reader = PyPDF2.PdfReader(file.file)
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        return text.strip()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read CV PDF: {e}")


async def generate_cover_letter(
    job_title: str,
    company_name: str,
    job_description: str,
    tone: str,
    cv_text: str | None,
) -> str:
    prompt = f"""
You are an expert career assistant.

Write a professional cover letter with a **{tone}** tone.

Job Title: {job_title}
Company: {company_name}

Job Description:
{job_description}

Candidate CV:
{cv_text if cv_text else "No CV provided."}

Rules:
- Keep it 3–4 paragraphs
- No emojis
- Sound human and natural
- Do not invent experience
- Use only information from CV
- Give only the letter as the response
"""

    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json",
            },
                        json={
                "model": "xiaomi/mimo-v2-flash:free",
                "messages": [
                    {"role": "system", "content": "You are a professional cover letter writing assistant."},
                    {"role": "user", "content": prompt}
                ],
            }
,
        )

    if response.status_code != 200:
        raise HTTPException(
            status_code=500,
            detail=f"Grok API error: {response.text}",
        )

    result = response.json()
    content = result.get("choices", [{}])[0].get("message", {}).get("content", "")

    if not content:
        raise HTTPException(status_code=500, detail="Empty response from model")

    return content.strip()


@app.post("/generate")
async def generate(
    jobTitle: str = Form(...),
    companyName: str = Form(...),
    jobDescription: str = Form(...),
    tone: str = Form(...),
    cv: UploadFile | None = File(None),
):
    cv_text = None

    if cv:
        if cv.content_type != "application/pdf":
            raise HTTPException(status_code=400, detail="CV must be a PDF")
        cv_text = extract_text_from_pdf(cv)

    letter = await generate_cover_letter(
        job_title=jobTitle,
        company_name=companyName,
        job_description=jobDescription,
        tone=tone,
        cv_text=cv_text,
    )

    return JSONResponse(
        content={
            "cover_letter": letter,
        }
    )


@app.get("/healthcheck", include_in_schema=False)
async def healthcheck():
    return {"status": "OK"}
