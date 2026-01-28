import json
import base64
from typing import Optional, Dict, Any
from datetime import datetime
from pathlib import Path
import uuid

from PIL import Image
import traceback
import io

import boto3
from botocore.exceptions import ClientError, BotoCoreError

# Local imports
from logger import get_logger
import settings

logger = get_logger(__name__)

MICRO_INSTRUCTION = """
You are a metadata extractor. Given a single book-cover image, return exactly
one valid JSON object (no surrounding text, no markdown) with the keys:
title, author, isbn, publisher, published_year, description

- title/author/publisher/description: strings ("" if unknown)
- isbn: digits only (strip hyphens/spaces), "" if not found
- published_year: 4-digit integer or null

Return only the JSON object and nothing else.
"""

def _get_bedrock_client():
	"""Get or create a Bedrock Runtime client instance."""
	try:
		client = boto3.client(
			'bedrock-runtime',
			region_name=settings.AWS_REGION,
			aws_access_key_id=settings.AWS_ACCESS_KEY_ID if settings.AWS_ACCESS_KEY_ID else None,
			aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY if settings.AWS_SECRET_ACCESS_KEY else None
		)
		logger.info(f"Bedrock client initialized in region: {settings.AWS_REGION}")
		return client
	except Exception as e:
		logger.error(f"Failed to initialize Bedrock client: {e}")
		raise

def extract_book_metadata(image_path: str) -> Optional[Dict[str, Any]]:
	"""Extract metadata from `image_path` using AWS Bedrock Claude 3 Haiku.
	
	Uses Claude 3 Haiku vision model to analyze book cover images and extract
	metadata such as title, author, ISBN, publisher, and description.
	
	Args:
		image_path: Path to the book cover image file
		
	Returns:
		Dictionary with keys: id, filename, processed_at, title, author, isbn, 
		publisher, published_year, description
		Returns None if extraction fails.
	"""
	try:
		# Verify image exists
		full_file_path = Path(image_path)
		if not full_file_path.exists() or not full_file_path.is_file():
			logger.warning("Image not found for Bedrock extraction: %s", image_path)
			return None
		
		# Prepare image data
		image_data = image_to_resized_jpeg_bytes(full_file_path, 1024)
		if not image_data:
			logger.warning('Failed to create resized JPEG bytes for %s', image_path)
			return None
		
		# Encode image to base64
		image_base64 = base64.b64encode(image_data).decode('utf-8')
		
		# Get Bedrock client
		bedrock = _get_bedrock_client()
		
		# Construct the request body for Claude 3
		request_body = {
			"anthropic_version": "bedrock-2023-05-31",
			"max_tokens": 1024,
			"messages": [
				{
					"role": "user",
					"content": [
						{
							"type": "image",
							"source": {
								"type": "base64",
								"media_type": "image/jpeg",
								"data": image_base64
							}
						},
						{
							"type": "text",
							"text": MICRO_INSTRUCTION
						}
					]
				}
			]
		}
		
		logger.debug(f"Calling Bedrock with model: {settings.BEDROCK_MODEL_ID}")
		
		# Invoke the model
		response = bedrock.invoke_model(
			modelId=settings.BEDROCK_MODEL_ID,
			body=json.dumps(request_body)
		)
		
		# Parse response
		response_body = json.loads(response['body'].read())
		
		# Extract the text from Claude's response
		if 'content' in response_body and len(response_body['content']) > 0:
			response_text = response_body['content'][0]['text']
			logger.debug(f"Bedrock response: {response_text}")
			
			# Parse metadata from response
			metadata = _parse_bedrock_response(response_text)
			metadata = _ensure_metadata_defaults(metadata, full_file_path.name)
			
			logger.info(f"Successfully extracted metadata for: {full_file_path.name}")
			return metadata
		else:
			logger.warning("Unexpected Bedrock response structure")
			return None
			
	except ClientError as e:
		logger.error(f"Bedrock ClientError: {e}")
		return None
	except BotoCoreError as e:
		logger.error(f"Bedrock BotoCoreError: {e}")
		return None
	except Exception as e:
		logger.error("Failed to extract metadata using Bedrock: %s", e)
		traceback.print_exc()
		return None

def _parse_bedrock_response(response_text: str) -> Dict[str, Any]:
	"""Parse Bedrock Claude response into metadata dictionary."""
	metadata = {
		'title': '',
		'author': '',
		'publisher': '',
		'description': '',
		'isbn': '',
		'published_year': None,
	}
	
	# Claude should return JSON directly based on our instruction
	try:
		# Try to parse as JSON first
		parsed = json.loads(response_text.strip())
		for key in metadata.keys():
			if key in parsed:
				metadata[key] = parsed[key]
		logger.debug(f"Successfully parsed JSON response: {metadata}")
		return metadata
	except json.JSONDecodeError:
		logger.warning("Response was not valid JSON, attempting to extract from text")
		logger.debug(f"Response text: {response_text}")
		
		# Fallback: try to find JSON object in the text
		try:
			# Look for JSON object pattern
			start = response_text.find('{')
			end = response_text.rfind('}') + 1
			if start >= 0 and end > start:
				json_str = response_text[start:end]
				parsed = json.loads(json_str)
				for key in metadata.keys():
					if key in parsed:
						metadata[key] = parsed[key]
				logger.debug(f"Extracted JSON from text: {metadata}")
				return metadata
		except (json.JSONDecodeError, ValueError) as e:
			logger.warning(f"Could not extract JSON from response: {e}")
	
	return metadata

def image_to_resized_jpeg_bytes(src: str | Path, max_dim: int = 1024, quality: int = 90) -> Optional[bytes]:
	"""Open `src`, resize to fit within `max_dim` x `max_dim`, and return JPEG bytes.

	Returns None on failure.
	"""
	p = Path(src)
	if not p.exists() or not p.is_file():
		return None
	try:
		with Image.open(str(p)) as im:
			im = im.convert('RGB')
			im.thumbnail((max_dim, max_dim), Image.LANCZOS)
			buf = io.BytesIO()
			im.save(buf, format='JPEG', quality=quality)
			return buf.getvalue()
	except Exception:
		logger.debug('image_to_resized_jpeg_bytes failed for %s', str(p), exc_info=True)
		return None

def _ensure_metadata_defaults(meta: Dict[str, Any], filename: str) -> Dict[str, Any]:
	"""Ensure metadata has required default fields."""
	if 'id' not in meta or not meta.get('id'):
		meta['id'] = str(uuid.uuid4())
	if 'filename' not in meta or not meta.get('filename'):
		meta['filename'] = filename
	if 'processed_at' not in meta or not meta.get('processed_at'):
		meta['processed_at'] = datetime.utcnow().isoformat() + 'Z'
	return meta
