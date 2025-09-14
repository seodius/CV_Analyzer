from fastapi import FastAPI, File, UploadFile
from google.cloud import storage, firestore
import shutil
import os
import uuid
import json
from PyPDF2 import PdfReader
import google.generativeai as genai

app = FastAPI()

# GCS configuration
BUCKET_NAME = "cvanalyzer_resumes"

# Gemini configuration
GEMINI_API_KEY = "AIzaSyAcIgafIFCorKz5bbxhuAsQWAwW3ilXeeo"
genai.configure(api_key=GEMINI_API_KEY)


def upload_to_gcs(file_path, file_name):
    """Uploads a file to the bucket."""
    storage_client = storage.Client()
    bucket = storage_client.bucket(BUCKET_NAME)
    blob = bucket.blob(file_name)

    blob.upload_from_filename(file_path)

    # Return the GCS URI
    return f"gs://{BUCKET_NAME}/{file_name}"

def extract_text_from_pdf(file_path: str) -> str:
    """Extracts text from a PDF file."""
    text = ""
    try:
        with open(file_path, "rb") as f:
            reader = PdfReader(f)
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text
    except Exception as e:
        print(f"Error extracting text from PDF: {e}")
    return text

def parse_resume_with_gemini(resume_text: str) -> dict:
    """Parses resume text using the Gemini API."""
    model = genai.GenerativeModel('gemini-pro')
    prompt = f"""
    You are an expert resume parser.
    Please parse the following resume text and return it in the JSON Resume format.
    The output should be a valid JSON object.
    Do not include any text outside of the JSON object.

    Resume text:
    {resume_text}
    """
    try:
        response = model.generate_content(prompt)
        # The response might have ```json ... ``` markers, so we need to clean it.
        cleaned_json = response.text.strip().replace("```json", "").replace("```", "").strip()
        return json.loads(cleaned_json)
    except Exception as e:
        print(f"Error parsing with Gemini: {e}")
        return {"error": "Failed to parse resume with Gemini."}

def save_to_firestore(data):
    """Saves the parsed resume data to Firestore."""
    db = firestore.Client()
    resumes_collection = db.collection('resumes')
    # We can use the email as the document ID, or a unique ID.
    # For now, we'll use a unique ID.
    doc_ref = resumes_collection.document(str(uuid.uuid4()))

    # Convert any non-serializable types to string
    serializable_data = json.loads(json.dumps(data, default=str))

    doc_ref.set(serializable_data)
    return doc_ref.id


@app.post("/resume/")
async def create_upload_file(file: UploadFile = File(...)):
    # Create the resumes directory if it doesn't exist
    os.makedirs("resumes", exist_ok=True)

    # Create a unique filename to avoid overwriting
    unique_filename = f"{uuid.uuid4()}_{file.filename}"
    file_path = os.path.join("resumes", unique_filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    gcs_uri = None
    parsed_data = {}
    firestore_id = None

    try:
        # Upload to GCS
        try:
            gcs_uri = upload_to_gcs(file_path, unique_filename)
        except Exception as e:
            print(f"Error uploading to GCS: {e}")

        # Extract text from PDF
        resume_text = extract_text_from_pdf(file_path)

        # Parse with Gemini
        parsed_data = parse_resume_with_gemini(resume_text)

        if gcs_uri:
            parsed_data['resume_uri'] = gcs_uri

        # Save to Firestore
        if parsed_data and "error" not in parsed_data:
            try:
                firestore_id = save_to_firestore(parsed_data)
                parsed_data['firestore_id'] = firestore_id
            except Exception as e:
                print(f"Error saving to Firestore: {e}")

    finally:
        # Clean up the saved file
        os.remove(file_path)

    return parsed_data

@app.get("/")
def read_root():
    return {"Hello": "World"}
