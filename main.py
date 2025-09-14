from fastapi import FastAPI, File, UploadFile
from pyresparser import ResumeParser
from google.cloud import storage, firestore
import shutil
import os
import nltk
from spacy.lang.en import English
import uuid
import json

# Download required NLTK data
try:
    nltk.data.find('corpora/stopwords')
except nltk.downloader.DownloadError:
    nltk.download('stopwords')
try:
    nltk.data.find('corpora/words')
except nltk.downloader.DownloadError:
    nltk.download('words')

# Load English tokenizer, tagger, parser, NER and word vectors
nlp = English()
nlp.add_pipe("sentencizer")


app = FastAPI()

# GCS configuration
BUCKET_NAME = "cvanalyzer_resumes"

def upload_to_gcs(file_path, file_name):
    """Uploads a file to the bucket."""
    storage_client = storage.Client()
    bucket = storage_client.bucket(BUCKET_NAME)
    blob = bucket.blob(file_name)

    blob.upload_from_filename(file_path)

    # Return the GCS URI
    return f"gs://{BUCKET_NAME}/{file_name}"


def parse_resume(file_path):
    data = ResumeParser(file_path).get_extracted_data()
    return data

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


        # Parse the resume
        parsed_data = parse_resume(file_path)
        if gcs_uri:
            parsed_data['resume_uri'] = gcs_uri

        # Save to Firestore
        if parsed_data:
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
