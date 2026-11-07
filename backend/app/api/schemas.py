from pydantic import BaseModel


class ApplicationResponse(BaseModel):
    job_title: str
    company: str
    language: str
    photo_used: bool
    cv_pdf_base64: str
    letter_pdf_base64: str
