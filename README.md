# Papertrail

Local-first PDF question answering with page-aware citations.

## Run it

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --reload
```

Open http://127.0.0.1:8000. PDFs in the project folder are indexed when the server starts. More PDFs can be added from the interface and are re-indexed immediately.

The baseline uses TF-IDF retrieval and extractive answers, so it works without an API key. To add a generative model, replace `answer_with_context` in `rag.py` with a call to the team's preferred OpenAI-compatible endpoint.