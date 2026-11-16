"""Citation extraction and dual-phase (deterministic + semantic) verification pipeline."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from app.core.config import CitationSettings
from app.rag.retrieval.bm25 import tokenize_text
from app.schemas.domain import (
    Citation,
    CitationVerificationResult,
    RetrievedChunk,
    VerifiedCitation,
)

if TYPE_CHECKING:
    from app.repositories.document_repository import DocumentRepository

logger = logging.getLogger(__name__)


class CitationVerifier:
    """Verifies citation authenticity, student data ownership, page existence, and claim grounding."""

    # Matches: [Source: notes.pdf, p. 3], [Source: notes.pdf, page 3], [notes.pdf, p. 3], [Source: notes.pdf]
    CITATION_REGEX = re.compile(
        r"\[(?:Source:\s*)?([A-Za-z0-9_\-\.\s]+?)(?:,\s*(?:p(?:age|\.)\s*)(\d+))?(?:,\s*sec(?:tion)?:\s*([^\]]+))?\]",
        re.IGNORECASE,
    )

    def __init__(
        self,
        document_repo: DocumentRepository,
        settings: CitationSettings,
    ) -> None:
        self.document_repo = document_repo
        self.settings = settings

    def extract_citations(self, text: str) -> list[Citation]:
        """Extract all bracketed citations and their immediate sentence claims."""
        citations: list[Citation] = []
        if not text:
            return citations

        # Mask citations in a copy of the text to prevent punctuation inside citations
        # (like 'p. 2') from triggering sentence split boundaries
        masked_chars = list(text)
        for m in self.CITATION_REGEX.finditer(text):
            for i in range(m.start(), m.end()):
                if masked_chars[i] != "\n":
                    masked_chars[i] = " "
        masked_str = "".join(masked_chars)

        # Sentence boundaries in masked_str (clean sentence starts and ends)
        boundaries = [0]
        for m in re.finditer(r"[\.\!\?]\s+|\n+", masked_str):
            boundaries.append(m.end())
        boundaries.append(len(text))

        for cit_m in self.CITATION_REGEX.finditer(text):
            source_name = cit_m.group(1).strip()
            page_num = int(cit_m.group(2)) if cit_m.group(2) else None
            sec_title = cit_m.group(3).strip() if cit_m.group(3) else None

            # Find boundary slice that contains this citation
            s_start = 0
            s_end = len(text)
            for i in range(len(boundaries) - 1):
                if boundaries[i] <= cit_m.start() < boundaries[i + 1]:
                    s_start = boundaries[i]
                    s_end = boundaries[i + 1]
                    break

            raw_sent = text[s_start:s_end].strip()
            claim = self.CITATION_REGEX.sub("", raw_sent).strip()
            claim = re.sub(r"[\.\!\?\,]+$", "", claim).strip()

            citations.append(
                Citation(
                    document_id="",  # Will be resolved during ownership check
                    source=source_name,
                    page=page_num,
                    section_title=sec_title,
                    claim=claim,
                )
            )
        return citations

    def compute_claim_support(self, claim: str, passage: str) -> float:
        """Calculate lexical-semantic grounding score between claim and passage."""
        claim_tokens = set(tokenize_text(claim))
        if not claim_tokens:
            return 1.0  # Empty claim has nothing to disprove

        # Filter out trivial stop words for support checking
        stop_words = {
            "the",
            "a",
            "an",
            "is",
            "are",
            "was",
            "were",
            "this",
            "that",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "and",
            "or",
            "by",
            "with",
            "as",
            "it",
        }
        substantive_tokens = claim_tokens - stop_words
        if not substantive_tokens:
            substantive_tokens = claim_tokens

        passage_tokens = set(tokenize_text(passage))
        overlap = substantive_tokens.intersection(passage_tokens)
        support_ratio = len(overlap) / len(substantive_tokens)
        return round(support_ratio, 4)

    def verify_turn(
        self,
        text: str,
        student_id: str,
        retrieved_chunks: list[RetrievedChunk],
    ) -> CitationVerificationResult:
        """Execute full deterministic and semantic verification over all citations in the response."""
        if not self.settings.enabled:
            return CitationVerificationResult(all_valid=True)

        extracted = self.extract_citations(text)
        if not extracted:
            # If no citations were generated, report as clean
            return CitationVerificationResult(all_valid=True, citations=[])

        # 1. Fetch authorized student documents
        student_docs = self.document_repo.list_for_student(student_id)
        doc_filename_map = {d.filename.lower(): d for d in student_docs}
        doc_id_map = {d.id: d for d in student_docs}

        verified_list: list[VerifiedCitation] = []
        unsupported_count = 0

        for cit in extracted[: self.settings.max_claims_per_verification]:
            norm_source = cit.source.lower()
            doc_record = doc_filename_map.get(norm_source) or doc_id_map.get(cit.source)

            # Check 1: Ownership and Document Existence
            if not doc_record:
                # Document does not belong to this student or does not exist
                verified_list.append(
                    VerifiedCitation(
                        citation=cit,
                        is_valid=False,
                        ownership_verified=False,
                        page_verified=False,
                        support_score=0.0,
                        reason=f"Document {cit.source!r} does not belong to student {student_id} or does not exist",
                    )
                )
                continue

            cit.document_id = doc_record.id

            # Check 2: Page Existence
            matching_chunks = [
                c
                for c in retrieved_chunks
                if (c.source.lower() == norm_source or c.document_id == doc_record.id)
            ]

            page_valid = True
            if cit.page is not None and matching_chunks:
                available_pages = {c.page for c in matching_chunks if c.page is not None}
                if available_pages and cit.page not in available_pages:
                    page_valid = False

            if not page_valid:
                verified_list.append(
                    VerifiedCitation(
                        citation=cit,
                        is_valid=False,
                        ownership_verified=True,
                        page_verified=False,
                        support_score=0.0,
                        reason=f"Cited page {cit.page} was not found in retrieved chunks for {cit.source}",
                    )
                )
                continue

            # Check 3: Semantic Grounding against retrieved passages
            best_support = 0.0
            candidate_texts = [
                c.content for c in matching_chunks if cit.page is None or c.page == cit.page
            ] or [c.content for c in retrieved_chunks]

            for passage in candidate_texts:
                sup = self.compute_claim_support(cit.claim, passage)
                if sup > best_support:
                    best_support = sup

            is_supported = best_support >= self.settings.verification_threshold
            if not is_supported:
                unsupported_count += 1

            verified_list.append(
                VerifiedCitation(
                    citation=cit,
                    is_valid=is_supported,
                    ownership_verified=True,
                    page_verified=True,
                    support_score=best_support,
                    reason=""
                    if is_supported
                    else "Claim lacks sufficient grounding in cited passage",
                )
            )

        valid_count = sum(1 for v in verified_list if v.is_valid)
        correctness = round(valid_count / max(len(verified_list), 1), 4)

        return CitationVerificationResult(
            citations=verified_list,
            all_valid=(unsupported_count == 0 and valid_count == len(verified_list)),
            citation_correctness=correctness,
            citation_completeness=1.0 if verified_list else 0.0,
            unsupported_claim_count=unsupported_count,
        )
