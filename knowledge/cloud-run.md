# Cloud Run application notes

Cloud Run hosts this application as a container. The container listens on the PORT environment variable and accepts HTTP requests. Cloud Run can create or remove container instances as demand changes. A container image packages Python code, libraries and the read-only FAISS index. The Gemini model weights are hosted by the model provider and are not stored in this image.

The human caller uses a short-lived identity token and needs permission to invoke the Cloud Run service. The running application uses its dedicated runtime service account to call the Vertex AI APIs. The build service account builds the image. These three identities have separate responsibilities. Service-account keys do not belong in the container or browser.

Cloud Run local files and process memory belong to an instance. This demo loads an immutable index from its image on each instance. Editing a file on one running instance would not update all replicas or persist across replacement. Updating the knowledge base therefore requires rebuilding the index and deploying a new image revision.
