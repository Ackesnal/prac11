# Retrieval and model service notes

Retrieval-augmented generation supplies selected evidence during inference. The ingestion process splits documents into chunks, creates document embeddings and stores the vectors in FAISS with source identifiers. At query time the application embeds the search query, finds similar chunks and supplies their text to Gemini. This changes the model input without training or changing its weights.

This demo uses FAISS IndexFlatIP with L2-normalised document and query vectors. The inner product then measures cosine similarity. Larger scores indicate more similar vector directions. A score is not the probability that an answer is correct. Top k limits the number of returned passages. A score threshold can remove weak matches but can also remove useful evidence.

A fixed RAG workflow retrieves using the original question before generation. The agent workflow first asks Gemini to propose a search_course_notes call and a search query. The application validates the proposal, executes one retrieval and returns the actual passages to Gemini for a cited answer. Application code enforces the tool allowlist and the two-generation-call budget.
