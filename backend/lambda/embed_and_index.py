# Owner: AZ
# EmbedAndIndexLambda — State 6.5 in ExtractionWorkflow
# Reads rawExcerpt text files written by Mohith's write_criteria Lambda,
# embeds them via Titan Embeddings v2, and writes vectors to S3 Vectors.
#
# Step Functions I/O:
#   Input:  { policyDocId, s3Bucket, excerptKeys: [str], ... }
#   Output: { ..., vectorsIndexed: int }

import json
import logging
import os
import re
from typing import Any

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# ── Env vars (validated at cold start) ───────────────────────────────────────

DOCUMENTS_BUCKET_NAME = os.environ.get("DOCUMENTS_BUCKET_NAME", "")
VECTORS_BUCKET_NAME = os.environ.get("VECTORS_BUCKET_NAME", "")
TITAN_MODEL_ARN = os.environ.get("TITAN_MODEL_ARN", "")

for _var, _val in [
    ("DOCUMENTS_BUCKET_NAME", DOCUMENTS_BUCKET_NAME),
    ("VECTORS_BUCKET_NAME", VECTORS_BUCKET_NAME),
    ("TITAN_MODEL_ARN", TITAN_MODEL_ARN),
]:
    if not _val:
        logger.warning(json.dumps({"warning": "missing_env_var", "var": _var}))

# ── Module-level AWS clients (reused across warm invocations) ─────────────────

s3 = boto3.client("s3")
bedrock_runtime = boto3.client("bedrock-runtime", region_name=os.environ.get("REGION", "us-east-1"))
s3vectors_client = boto3.client("s3vectors", region_name=os.environ.get("REGION", "us-east-1"))

_CHUNK_CHAR_LIMIT = 2048  # ~512 tokens at 4 chars/token
_INDEX_NAME = "policy-criteria-index"


def _split_into_chunks(text: str) -> list[str]:
    """Split text at sentence boundaries if it exceeds the token estimate."""
    if len(text) <= _CHUNK_CHAR_LIMIT:
        return [text]

    # Split on sentence boundaries: ". " or newline
    sentences = re.split(r"(?<=\. )|(?<=\n)", text)
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for sentence in sentences:
        if current_len + len(sentence) > _CHUNK_CHAR_LIMIT and current:
            chunks.append("".join(current).strip())
            current = []
            current_len = 0
        current.append(sentence)
        current_len += len(sentence)

    if current:
        chunks.append("".join(current).strip())

    return [c for c in chunks if c]


def _embed_chunk(chunk: str) -> list[float]:
    """Call Titan Embeddings v2 and return the embedding vector."""
    response = bedrock_runtime.invoke_model(
        modelId=TITAN_MODEL_ARN,
        body=json.dumps({"inputText": chunk}),
        contentType="application/json",
        accept="application/json",
    )
    return json.loads(response["body"].read())["embedding"]


def _parse_key(key: str) -> tuple[str, str]:
    """Extract policyDocId and drugIndicationId from key path.

    Expected format: {policyDocId}/excerpts/{drugIndicationId}.txt
    Falls back to key segments if format differs.
    """
    parts = key.split("/")
    policy_doc_id = parts[0] if len(parts) >= 1 else "unknown"
    # drugIndicationId is the filename without extension
    drug_indication_id = parts[-1].replace(".txt", "") if parts else "unknown"
    return policy_doc_id, drug_indication_id


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Embed rawExcerpt text chunks and write vectors to S3 Vectors."""
    if isinstance(event, str):
        try:
            event = json.loads(event)
        except json.JSONDecodeError as exc:
            raise ValueError(f"event is a string and could not be parsed as JSON: {exc}") from exc
    if not isinstance(event, dict):
        raise TypeError(f"Expected event to be a dict, got {type(event).__name__}")
    policy_doc_id = event.get("policyDocId", "unknown")
    logger.info(json.dumps({"state": "EmbedAndIndex", "policyDocId": policy_doc_id}))

    if not VECTORS_BUCKET_NAME or not TITAN_MODEL_ARN:
        logger.warning(json.dumps({"action": "skip_embed", "reason": "missing env vars", "policyDocId": policy_doc_id}))
        return {**event, "vectorsIndexed": 0, "vectorsError": "missing env vars"}

    excerpt_keys: list[str] = event.get("excerptKeys", [])
    bucket = event.get("s3Bucket", DOCUMENTS_BUCKET_NAME)

    # Context metadata passed through from earlier pipeline states
    payer_name = event.get("payerName", "")
    drug_name = event.get("drugName", "")
    indication_name = event.get("indicationName", "")
    effective_date = event.get("effectiveDate", "")

    total_vectors_written = 0

    try:
        for key in excerpt_keys:
            parsed_policy_id, drug_indication_id = _parse_key(key)

            # 1. Read excerpt text from S3
            try:
                obj = s3.get_object(Bucket=bucket, Key=key)
                text = obj["Body"].read().decode("utf-8")
            except Exception as e:
                logger.warning(json.dumps({"action": "skip_key", "key": key, "reason": str(e)}))
                continue

            # 2. Chunk text if over token estimate
            chunks = _split_into_chunks(text)
            logger.info(json.dumps({"action": "chunked", "key": key, "chunks": len(chunks)}))

            for chunk_idx, chunk in enumerate(chunks):
                # 3. Embed via Titan
                try:
                    embedding = _embed_chunk(chunk)
                except Exception as e:
                    logger.warning(json.dumps({"action": "embed_failed", "key": key, "chunk": chunk_idx, "reason": str(e)}))
                    continue

                # 4. Write vector to S3 Vectors
                vector_key = f"{parsed_policy_id}#{drug_indication_id}#{chunk_idx}"
                s3vectors_client.put_vectors(
                    vectorBucketName=VECTORS_BUCKET_NAME,
                    indexName=_INDEX_NAME,
                    vectors=[{
                        "key": vector_key,
                        "data": {"float32": embedding},
                        "metadata": {
                            "policyDocId": parsed_policy_id,
                            "drugIndicationId": drug_indication_id,
                            "payerName": payer_name,
                            "drugName": drug_name,
                            "indicationName": indication_name,
                            "effectiveDate": effective_date,
                            "chunkText": chunk[:256],
                        },
                    }],
                )
                total_vectors_written += 1

        logger.info(json.dumps({"action": "complete", "policyDocId": policy_doc_id, "vectorsIndexed": total_vectors_written}))
        return {**event, "vectorsIndexed": total_vectors_written}

    except Exception as e:
        # ADR: Non-blocking catch | Embedding failures must not fail the extraction pipeline
        logger.warning(json.dumps({"action": "embed_index_error", "policyDocId": policy_doc_id, "reason": str(e)}))
        return {**event, "vectorsIndexed": 0, "vectorsError": "Embedding operation failed"}
