"""Small Vertex AI REST adapter. ADC in Cloud Run; gcloud tokens for indexing.

No credentials are embedded in the image. No automatic application retries.
"""
import os
import re
import subprocess


def setting(name, default=None):
    value = os.getenv(name, default)
    if not value or not re.fullmatch(r"[A-Za-z0-9_.-]+", value):
        raise ValueError(f"Set a valid {name}")
    return value


class Vertex:
    def __init__(self, use_gcloud=False):
        self.project = setting("GOOGLE_CLOUD_PROJECT")
        self.model = setting("MODEL_ID", "gemini-3.5-flash-lite")
        self.location = setting("MODEL_LOCATION", "global")
        self.embedding_model = setting("EMBEDDING_MODEL", "gemini-embedding-001")
        self.embedding_location = setting("EMBEDDING_LOCATION", "us-central1")
        self.dimension = int(os.getenv("EMBEDDING_DIM", "768"))
        if not 1 <= self.dimension <= 3072:
            raise ValueError("EMBEDDING_DIM must be 1..3072")
        self.use_gcloud = use_gcloud

    def post(self, location, model, method, body):
        host = "aiplatform.googleapis.com" if location == "global" else f"{location}-aiplatform.googleapis.com"
        url = (f"https://{host}/v1/projects/{self.project}/locations/{location}"
               f"/publishers/google/models/{model}:{method}")
        if self.use_gcloud:
            import requests
            token = subprocess.check_output(
                ["gcloud", "auth", "print-access-token"], text=True, timeout=20).strip()
            with requests.Session() as session:
                response = session.post(url, json=body, timeout=(5, 30),
                    headers={"Authorization": f"Bearer {token}", "x-goog-user-project": self.project})
        else:
            import google.auth
            from google.auth.transport.requests import AuthorizedSession
            credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
            with AuthorizedSession(credentials, max_refresh_attempts=0) as session:
                response = session.post(url, json=body, timeout=(5, 30), max_allowed_time=40)
        response.raise_for_status()
        return response.json()

    def embed(self, text, task_type):
        if task_type not in {"RETRIEVAL_DOCUMENT", "RETRIEVAL_QUERY"}:
            raise ValueError("Unsupported embedding task")
        response = self.post(self.embedding_location, self.embedding_model, "predict", {
            "instances": [{"content": text, "task_type": task_type}],
            "parameters": {"autoTruncate": False, "outputDimensionality": self.dimension}})
        embedding = response["predictions"][0]["embeddings"]
        if embedding.get("statistics", {}).get("truncated"):
            raise ValueError("Embedding text was truncated")
        values = embedding["values"]
        if len(values) != self.dimension:
            raise ValueError("Embedding dimension differs from configuration")
        return values

    def generate(self, contents, system, phase, declaration=None):
        config = {"temperature": 0.2, "maxOutputTokens": 2048}
        body = {"systemInstruction": {"parts": [{"text": system}]},
                "contents": contents, "generationConfig": config}
        if phase == "plan":
            body["tools"] = [{"functionDeclarations": [declaration]}]
            body["toolConfig"] = {"functionCallingConfig": {
                "mode": "ANY", "allowedFunctionNames": [declaration["name"]]}}
        if phase == "answer":
            # The controller independently rejects any unexpected function call.
            config.update(responseMimeType="application/json", responseSchema={
                "type": "OBJECT", "properties": {
                    "answer": {"type": "STRING"},
                    "source_ids": {"type": "ARRAY", "items": {"type": "STRING"}},
                    "insufficient_evidence": {"type": "BOOLEAN"}},
                "required": ["answer", "source_ids", "insufficient_evidence"]})
        return self.post(self.location, self.model, "generateContent", body)
