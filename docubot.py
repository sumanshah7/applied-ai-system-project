"""
Core DocuBot class responsible for:
- Loading documents from the docs/ folder
- Building a simple retrieval index (Phase 1)
- Retrieving relevant snippets (Phase 1)
- Supporting retrieval only answers
- Supporting RAG answers when paired with Gemini (Phase 2)
"""

import os
import glob
import re

def normalize(word):
    """
    Collapse simple plurals to a common root so 'tokens' matches 'token'.
    Deliberately minimal: handle the two most common English endings and
    leave short words alone to avoid mangling them (e.g. 'is', 'has').
    """
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"   # libraries -> library
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]         # tokens -> token, users -> user
    return word


def tokenize(text):
    """
    Split text into lowercase, plural-normalized word tokens, stripping
    punctuation. Shared by indexing and scoring so both agree on what a
    'word' is (and both normalize plurals the same way).
    """
    return [normalize(w) for w in re.findall(r"[a-z0-9_]+", text.lower())]


# Very common words that carry little meaning for retrieval. Dropping these
# keeps scoring focused on the words that actually identify a topic. Normalized
# through the same function as tokens so the membership check stays consistent.
STOPWORDS = {
    normalize(w)
    for w in {
        "the", "a", "an", "is", "are", "was", "were", "be", "to", "of", "in",
        "on", "for", "and", "or", "how", "do", "i", "what", "where", "which",
        "does", "this", "that", "these", "those", "there", "any", "mention",
        "docs", "doc", "documentation",
    }
}


class DocuBot:
    def __init__(self, docs_folder="docs", llm_client=None, extra_folders=None):
        """
        docs_folder: primary directory containing project documentation files.
        llm_client:  optional Gemini client for LLM based answers.
        extra_folders: optional list of additional documentation sources
                       (RAG enhancement). Every folder is indexed together so a
                       single query can be answered from multiple data sources.
        """
        # RAG enhancement: retrieve across one or more documentation sources.
        self.docs_folders = [docs_folder]
        if extra_folders:
            self.docs_folders.extend(extra_folders)

        # Kept for backward compatibility with earlier single-folder code.
        self.docs_folder = docs_folder
        self.llm_client = llm_client

        # Load documents into memory
        self.documents = self.load_documents()  # List of (filename, text)

        # Build a retrieval index (implemented in Phase 1)
        self.index = self.build_index(self.documents)

    # -----------------------------------------------------------
    # Document Loading
    # -----------------------------------------------------------

    def load_documents(self):
        """
        Loads all .md and .txt files from every configured documentation
        source. Returns a list of tuples: (filename, text).

        Filenames are prefixed with their source folder when more than one
        folder is configured, so identical basenames from different sources do
        not collide and the answer can cite where a snippet came from.
        """
        docs = []
        multiple_sources = len(self.docs_folders) > 1
        for folder in self.docs_folders:
            if not os.path.isdir(folder):
                continue
            pattern = os.path.join(folder, "*.*")
            for path in sorted(glob.glob(pattern)):
                if path.endswith(".md") or path.endswith(".txt"):
                    with open(path, "r", encoding="utf8") as f:
                        text = f.read()
                    basename = os.path.basename(path)
                    filename = f"{folder}/{basename}" if multiple_sources else basename
                    docs.append((filename, text))
        return docs

    # -----------------------------------------------------------
    # Index Construction (Phase 1)
    # -----------------------------------------------------------

    def build_index(self, documents):
        """
        TODO (Phase 1):
        Build a tiny inverted index mapping lowercase words to the documents
        they appear in.

        Example structure:
        {
            "token": ["AUTH.md", "API_REFERENCE.md"],
            "database": ["DATABASE.md"]
        }

        Keep this simple: split on whitespace, lowercase tokens,
        ignore punctuation if needed.
        """
        index = {}
        for filename, text in documents:
            # Use a set so each word maps to a filename only once per file.
            for word in set(tokenize(text)):
                index.setdefault(word, []).append(filename)
        return index

    # -----------------------------------------------------------
    # Scoring and Retrieval (Phase 1)
    # -----------------------------------------------------------

    def score_document(self, query, text):
        """
        TODO (Phase 1):
        Return a simple relevance score for how well the text matches the query.

        Suggested baseline:
        - Convert query into lowercase words
        - Count how many appear in the text
        - Return the count as the score
        """
        query_words = [w for w in tokenize(query) if w not in STOPWORDS]
        text_words = set(tokenize(text))

        # Count how many distinct meaningful query words appear in the text.
        return sum(1 for w in set(query_words) if w in text_words)

    def retrieve(self, query, top_k=3):
        """
        Phase 1 + Phase 3:
        Select the top_k most relevant *snippets* for the query.

        - Uses the inverted index to find only the files that mention a
          meaningful query word (avoids scanning irrelevant files).
        - Splits those files into paragraphs so we return small, focused
          snippets instead of whole documents.
        - Drops any snippet that scores 0. This is the guardrail: when no
          snippet contains query words, retrieve returns [], and the
          answering modes report "I do not know."

        Return a list of (filename, snippet_text) sorted by score descending.
        """
        scored = self.retrieve_scored(query, top_k=top_k)
        return [(filename, snippet) for _, filename, snippet in scored]

    def retrieve_scored(self, query, top_k=3):
        """
        Same retrieval logic as `retrieve`, but keeps the numeric relevance
        score on each result: a list of (score, filename, snippet_text) sorted
        by score descending. Used by the test harness and the agent's
        self-check as a lightweight confidence signal.
        """
        query_words = [w for w in tokenize(query) if w not in STOPWORDS]

        # Candidate files: any file the index says mentions a query word.
        candidate_files = set()
        for word in query_words:
            candidate_files.update(self.index.get(word, []))

        scored = []
        for filename, text in self.documents:
            if filename not in candidate_files:
                continue
            for snippet in self.split_into_snippets(text):
                score = self.score_document(query, snippet)
                if score > 0:  # guardrail: ignore snippets with no evidence
                    scored.append((score, filename, snippet))

        # Highest score first; keep ordering stable for equal scores.
        scored.sort(key=lambda item: item[0], reverse=True)

        return scored[:top_k]

    def split_into_snippets(self, text):
        """
        Break a document into small, self-contained snippets.
        Strategy: split on blank lines (paragraphs / sections), which keeps
        headings with their content and avoids returning an entire file.
        """
        chunks = re.split(r"\n\s*\n", text)
        return [chunk.strip() for chunk in chunks if chunk.strip()]

    # -----------------------------------------------------------
    # Answering Modes
    # -----------------------------------------------------------

    def answer_retrieval_only(self, query, top_k=3):
        """
        Phase 1 retrieval only mode.
        Returns raw snippets and filenames with no LLM involved.
        """
        snippets = self.retrieve(query, top_k=top_k)

        if not snippets:
            return "I do not know based on these docs."

        formatted = []
        for filename, text in snippets:
            formatted.append(f"[{filename}]\n{text}\n")

        return "\n---\n".join(formatted)

    def answer_rag(self, query, top_k=3):
        """
        Phase 2 RAG mode.
        Uses student retrieval to select snippets, then asks Gemini
        to generate an answer using only those snippets.
        """
        if self.llm_client is None:
            raise RuntimeError(
                "RAG mode requires an LLM client. Provide a GeminiClient instance."
            )

        snippets = self.retrieve(query, top_k=top_k)

        if not snippets:
            return "I do not know based on these docs."

        return self.llm_client.answer_from_snippets(query, snippets)

    # -----------------------------------------------------------
    # Bonus Helper: concatenated docs for naive generation mode
    # -----------------------------------------------------------

    def full_corpus_text(self):
        """
        Returns all documents concatenated into a single string.
        This is used in Phase 0 for naive 'generation only' baselines.
        """
        return "\n\n".join(text for _, text in self.documents)
