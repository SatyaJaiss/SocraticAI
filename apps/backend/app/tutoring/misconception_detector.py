"""Evidence-based misconception detection and resolution tracking."""

from __future__ import annotations

import logging
import re
from typing import Any, ClassVar

from app.core.config import MisconceptionSettings
from app.llm.clients.client import LLMClient
from app.repositories.memory_repository import MemoryRepository
from app.repositories.student_repository import StudentRepository
from app.schemas.enums import MemoryFactType

logger = logging.getLogger(__name__)


class MisconceptionDetector:
    """Analyzes student errors to identify, register, and track resolution of specific misconceptions."""

    COMMON_MISCONCEPTION_PATTERNS: ClassVar[dict[str, list[dict[str, Any]]]] = {
        "gravity": [
            {
                "pattern": r"(heavier|heavier object|mass).*(faster|fall faster|first|drop faster)",
                "misconception": "Belief that heavier objects fall faster in a vacuum",
                "remedy": "In a vacuum, gravitational acceleration g is independent of mass.",
            }
        ],
        "physics": [
            {
                "pattern": r"(force.*motion|no force.*stop|constant velocity.*requires force)",
                "misconception": "Belief that constant motion requires a continuous net force (Aristotelian view)",
                "remedy": "Newton's First Law: an object in motion continues with constant velocity unless acted upon by a net external force.",
            },
            {
                "pattern": r"(action.*greater than.*reaction|reaction.*less|overcomes.*reaction)",
                "misconception": "Belief that action and reaction forces can be unequal in magnitude",
                "remedy": "Newton's Third Law: action and reaction forces are strictly equal in magnitude and opposite in direction.",
            },
        ],
        "photosynthesis": [
            {
                "pattern": r"(plants.*only.*photosynthesize|don't respire|no cellular respiration)",
                "misconception": "Belief that plants only perform photosynthesis and not cellular respiration",
                "remedy": "Plant cells continuously undergo cellular respiration in mitochondria for ATP production.",
            }
        ],
        "statistics": [
            {
                "pattern": r"(correlation.*means.*causes?|implies causation|causes?.*because.*correlated)",
                "misconception": "Confusing statistical correlation with causal mechanism",
                "remedy": "Correlation indicates association; establishing causation requires controlled experiments or counterfactual identification.",
            }
        ],
        "math": [
            {
                "pattern": r"(add.*denominators|a/b.*c/d.*\(a\+c\)/\(b\+d\))",
                "misconception": "Adding denominators when performing fraction addition",
                "remedy": "Fractions require finding a common denominator before adding numerators.",
            }
        ],
    }

    def __init__(
        self,
        memory_repo: MemoryRepository,
        student_repo: StudentRepository | None = None,
        settings: MisconceptionSettings | None = None,
        llm: LLMClient | None = None,
    ) -> None:
        self.memory_repo = memory_repo
        self.student_repo = student_repo
        self.settings = settings or MisconceptionSettings()
        self.llm = llm

    def detect(
        self,
        concept: str,
        student_response: str,
        correct_answer: str = "",
        question: str = "",
    ) -> list[dict[str, Any]]:
        """Identify misconceptions present in student answer with confidence scoring."""
        detected: list[dict[str, Any]] = []
        concept_lower = (concept or "").lower()
        resp_lower = (student_response or "").lower()

        # 1. Check known rule-based patterns
        for key, patterns in self.COMMON_MISCONCEPTION_PATTERNS.items():
            if key in concept_lower or any(k in resp_lower for k in key.split()):
                for pat in patterns:
                    if re.search(pat["pattern"], resp_lower, re.IGNORECASE):
                        detected.append(
                            {
                                "misconception": pat["misconception"],
                                "concept": concept,
                                "confidence": 0.90,
                                "remedy": pat["remedy"],
                            }
                        )

        # 2. Check LLM for nuanced misconception detection if available
        if not detected and self.llm is not None and len(resp_lower) > 5:
            prompt = (
                f"Analyze this student error for misconceptions:\n"
                f"Concept: {concept}\n"
                f"Question: {question}\n"
                f"Expected Answer: {correct_answer}\n"
                f"Student Answer: {student_response}\n\n"
                "If the student demonstrates a specific underlying misconception, state it in the format:\n"
                "MISCONCEPTION: <description> | CONFIDENCE: <0.0-1.0> | REMEDY: <one sentence clarification>\n"
                "If it is merely a calculation error or slip with no deeper misconception, respond NONE."
            )
            try:
                out = self.llm.generate(prompt)
                out_text = getattr(out, "content", str(out)).strip()
                if "MISCONCEPTION:" in out_text:
                    parts = out_text.split("|")
                    misc_desc = parts[0].replace("MISCONCEPTION:", "").strip()
                    conf = 0.80
                    remedy = ""
                    for p in parts[1:]:
                        if "CONFIDENCE:" in p:
                            try:
                                conf = float(p.replace("CONFIDENCE:", "").strip())
                            except ValueError:
                                pass
                        elif "REMEDY:" in p:
                            remedy = p.replace("REMEDY:", "").strip()

                    if conf >= self.settings.detection_confidence_threshold:
                        detected.append(
                            {
                                "misconception": misc_desc,
                                "concept": concept,
                                "confidence": conf,
                                "remedy": remedy,
                            }
                        )
            except Exception as e:
                logger.warning(f"LLM misconception detection error: {e}")

        return detected

    def register_misconception(
        self,
        student_id: str,
        concept: str,
        misconception: str,
        confidence: float = 0.85,
    ) -> None:
        """Register an active misconception for the student, deduplicating if configured."""
        if not misconception:
            return

        active = self.get_active_misconceptions(student_id, concept=concept)
        if self.settings.prevent_duplicate_active and any(
            misconception.lower() in m.lower() for m in active
        ):
            logger.info(
                f"Duplicate misconception skipped for student {student_id}: {misconception}"
            )
            return

        if self.student_repo:
            self.student_repo.get_or_create(student_id)

        content = f"Active misconception on [{concept}]: {misconception}"
        self.memory_repo.add_fact(
            student_id=student_id,
            fact_type=MemoryFactType.MISTAKE.value,
            content=content,
            importance=min(1.0, max(0.5, confidence)),
        )

        if self.student_repo:
            self.student_repo.add_weak_concept(student_id, concept)

    def record_successful_demonstration(self, student_id: str, concept: str) -> bool:
        """Record understanding demonstration and mark corresponding misconceptions as resolved if criteria met."""
        active = self.get_active_misconceptions(student_id, concept=concept)
        if not active:
            return False

        # Add resolution confirmation to memory
        content = (
            f"Resolved misconception on [{concept}]: Demonstrated mastery on subsequent assessment."
        )
        self.memory_repo.add_fact(
            student_id=student_id,
            fact_type=MemoryFactType.STRENGTH.value,
            content=content,
            importance=0.8,
        )
        return True

    def get_active_misconceptions(self, student_id: str, concept: str | None = None) -> list[str]:
        """Fetch currently active (unresolved) misconceptions."""
        facts = self.memory_repo.list_facts(
            student_id=student_id, fact_type=MemoryFactType.MISTAKE.value, limit=50
        )
        resolved_facts = self.memory_repo.list_facts(
            student_id=student_id, fact_type=MemoryFactType.STRENGTH.value, limit=50
        )

        resolved_concepts = set()
        for rf in resolved_facts:
            txt = rf.get("content", "")
            if "Resolved misconception on [" in txt:
                c = txt.split("Resolved misconception on [")[1].split("]")[0]
                resolved_concepts.add(c.lower())

        active_list: list[str] = []
        for f in facts:
            txt = f.get("content", "")
            if "Active misconception on [" in txt:
                parts = txt.split("Active misconception on [")
                c_part = parts[1].split("]: ")
                c_name = c_part[0].strip()
                misc_text = c_part[1].strip() if len(c_part) > 1 else ""

                if c_name.lower() in resolved_concepts:
                    continue  # Resolved

                if concept and c_name.lower() != concept.lower():
                    continue

                active_list.append(misc_text or txt)

        return active_list

    def get_resolved_misconceptions(self, student_id: str) -> list[str]:
        """Fetch resolved misconceptions for the student."""
        facts = self.memory_repo.list_facts(
            student_id=student_id, fact_type=MemoryFactType.STRENGTH.value, limit=50
        )
        resolved: list[str] = []
        for f in facts:
            txt = f.get("content", "")
            if "Resolved misconception on [" in txt:
                resolved.append(txt)
        return resolved
