"""
Text chunking module - splits documents into overlapping chunks
for better embedding quality on large documents.
"""

import re

CHUNK_SIZE = 2000       # ~512 tokens target
CHUNK_OVERLAP = 200     # overlap between chunks for context continuity


def chunk_text(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    """
    Split text into overlapping chunks, breaking at paragraph/sentence boundaries.
    Returns list of {text, chunk_index, total_chunks}.
    """
    text = text.strip()
    if not text:
        return []

    # If text fits in one chunk, return as-is
    if len(text) <= chunk_size:
        return [{"text": text, "chunk_index": 0, "total_chunks": 1}]

    # Split into paragraphs first
    paragraphs = re.split(r'\n\s*\n', text)

    chunks = []
    current_chunk = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        # If adding this paragraph exceeds chunk size
        if len(current_chunk) + len(para) + 2 > chunk_size:
            if current_chunk:
                chunks.append(current_chunk.strip())

                # Start next chunk with overlap from end of current
                overlap_text = _get_overlap(current_chunk, overlap)
                current_chunk = overlap_text + "\n\n" + para if overlap_text else para
            else:
                # Single paragraph exceeds chunk size - split by sentences
                sentence_chunks = _split_long_paragraph(para, chunk_size, overlap)
                if sentence_chunks:
                    chunks.extend(sentence_chunks[:-1])
                    current_chunk = sentence_chunks[-1]
                else:
                    current_chunk = para
        else:
            if current_chunk:
                current_chunk += "\n\n" + para
            else:
                current_chunk = para

    # Don't forget the last chunk
    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    total = len(chunks)
    return [
        {"text": c, "chunk_index": i, "total_chunks": total}
        for i, c in enumerate(chunks)
    ]


def _get_overlap(text, overlap_chars):
    """Get the last overlap_chars of text, breaking at a sentence boundary."""
    if len(text) <= overlap_chars:
        return text

    tail = text[-overlap_chars:]
    # Try to break at sentence boundary
    sentence_break = re.search(r'[.!?]\s+', tail)
    if sentence_break:
        return tail[sentence_break.end():]
    # Fall back to word boundary
    word_break = tail.find(' ')
    if word_break != -1:
        return tail[word_break + 1:]
    return tail


def _split_long_paragraph(text, chunk_size, overlap):
    """Split a single long paragraph by sentence boundaries."""
    # Split into sentences
    sentences = re.split(r'(?<=[.!?])\s+', text)

    chunks = []
    current = ""

    for sentence in sentences:
        if len(current) + len(sentence) + 1 > chunk_size:
            if current:
                chunks.append(current.strip())
                overlap_text = _get_overlap(current, overlap)
                current = overlap_text + " " + sentence if overlap_text else sentence
            else:
                # Single sentence exceeds chunk size - hard split
                for i in range(0, len(sentence), chunk_size - overlap):
                    chunks.append(sentence[i:i + chunk_size])
                current = ""
        else:
            current = current + " " + sentence if current else sentence

    if current.strip():
        chunks.append(current.strip())

    return chunks
