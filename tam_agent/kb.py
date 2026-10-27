"""
tam_agent/kb.py - Knowledge Base loader, indexer, and search engine.
"""

import math
import re
from pathlib import Path
from typing import Dict, List, Optional, Any


class KBChunk:
    def __init__(self, doc_path: str, title: str, section_title: str, content: str):
        self.doc_path = doc_path
        self.title = title
        self.section_title = section_title
        self.content = content.strip()
        # Precompute normalized tokens
        self.tokens = self._tokenize(f"{title} {section_title} {content}")

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        return [w for w in re.findall(r"\w+", text.lower()) if len(w) > 2]


class KnowledgeBase:
    def __init__(self, kb_dir: str = "knowledge-base"):
        self.kb_dir = Path(kb_dir)
        self.chunks: List[KBChunk] = []
        self._doc_freq: Dict[str, int] = {}
        self._avg_dl: float = 0.0
        self.load()

    def load(self):
        """Loads and indexes all markdown files across products, troubleshooting, billing, and onboarding."""
        if not self.kb_dir.exists():
            return

        total_length = 0
        for md_file in self.kb_dir.rglob("*.md"):
            try:
                with open(md_file, "r", encoding="utf-8") as f:
                    text = f.read()
            except Exception:
                continue

            rel_path = str(md_file.relative_to(self.kb_dir)).replace("\\", "/")
            lines = text.split("\n")
            doc_title = lines[0].replace("#", "").strip() if lines else md_file.stem

            # Split by markdown sections (## or ---)
            raw_sections = re.split(r"(?:\n---+\n|\n(?=##\s+))", text)
            for section in raw_sections:
                sec_text = section.strip()
                if not sec_text:
                    continue
                # Extract section heading if present
                sec_lines = sec_text.split("\n")
                sec_title = doc_title
                for line in sec_lines:
                    if line.startswith("#"):
                        sec_title = line.replace("#", "").strip()
                        break

                chunk = KBChunk(
                    doc_path=rel_path,
                    title=doc_title,
                    section_title=sec_title,
                    content=sec_text
                )
                self.chunks.append(chunk)
                total_length += len(chunk.tokens)

                # Track document frequency for BM25
                unique_tokens = set(chunk.tokens)
                for t in unique_tokens:
                    self._doc_freq[t] = self._doc_freq.get(t, 0) + 1

        if self.chunks:
            self._avg_dl = total_length / len(self.chunks)

    def search(self, query: str, top_k: int = 3, category_hint: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        BM25-inspired ranking to retrieve top relevant KB snippets for the query.
        """
        query_tokens = KBChunk._tokenize(query)
        if not query_tokens or not self.chunks:
            return []

        N = len(self.chunks)
        k1 = 1.5
        b = 0.75
        scores = []

        for chunk in self.chunks:
            score = 0.0
            doc_len = len(chunk.tokens)
            token_counts: Dict[str, int] = {}
            for t in chunk.tokens:
                token_counts[t] = token_counts.get(t, 0) + 1

            for qt in query_tokens:
                tf = token_counts.get(qt, 0)
                if tf == 0:
                    continue
                df = self._doc_freq.get(qt, 1)
                idf = math.log(1 + (N - df + 0.5) / (df + 0.5))
                # BM25 term weighting
                term_score = idf * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * (doc_len / (self._avg_dl or 1))))
                score += term_score

            # Boost if query tokens appear in title or section title
            for qt in query_tokens:
                if qt in chunk.title.lower() or qt in chunk.section_title.lower():
                    score += 2.0

            if category_hint and category_hint.lower() in chunk.doc_path.lower():
                score += 1.5

            if score > 0:
                scores.append((score, chunk))

        scores.sort(key=lambda x: x[0], reverse=True)
        results = []
        for s, chunk in scores[:top_k]:
            results.append({
                "score": round(s, 2),
                "source": chunk.doc_path,
                "title": chunk.title,
                "section": chunk.section_title,
                "content": chunk.content
            })
        return results

    def get_support_policy(self, plan_tier: Optional[str] = None) -> str:
        """Retrieves support SLA policy from billing-and-plans."""
        results = self.search(f"{plan_tier or 'Enterprise'} support SLA policy", top_k=2)
        if results:
            return "\n\n".join([r["content"] for r in results])
        return "Standard policy: P1 requires immediate TAM notification and 1-hour SLA."
