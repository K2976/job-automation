# RAG retrieval evaluation

How the retrieval layer is evaluated, and what the evaluation found. Reproduce with
`python tests/evaluation/run_eval.py --provider <mock|groq|gemini>` (writes
`docs/eval-runs/<provider>.json`); assertions live in `tests/evaluation/`.

## Method
A small human-labelled benchmark (`tests/evaluation/labels.py`) maps key JD requirements
to the candidate entities that *should* be retrieved (e.g. `postgresql → {Parkezy, iOS
Developer at Freelance}`, `1d-cnn → {Setu AI}`). For each we measure **Hit@3 / Hit@5** and
compare three rankings of the same candidate KB: **semantic** (cosine over embeddings),
**keyword** (content-token overlap), and **hybrid** (the fused score the product uses).

## Results (retrieval mechanism — provider-independent)
- **Hit@3 = 100%** for every labelled tech term (PostgreSQL, REST, FastAPI, 1D-CNN,
  Python, feature engineering, edge AI). The retriever surfaces the correct candidate
  project/skill/experience for exact technologies. *Verified* by
  `test_retrieval_hits_labeled_evidence`.
- Retrieval is **provenance-preserving**: every hit carries the entity id, type, status
  and score (no anonymous chunks).

## Hybrid vs semantic vs keyword — the honest caveat
The default embedder is **local TF-IDF** (ADR-004), which is itself *lexical*. So the
"semantic" and "keyword" rankings are highly correlated, and hybrid usually equals both.
This means **the current offline benchmark cannot demonstrate hybrid's main benefit**
(dense-semantic bridging of synonyms/paraphrase) — that needs real dense embeddings
(`EMBEDDING_PROVIDER=gemini`), which is **Not Tested** here.

Where the components *do* diverge, the keyword signal helps. Concrete case —
`feature engineering`:

| mode | top-1 |
|---|---|
| semantic (TF-IDF) | **B.Tech Computer Engineering** ← spurious ("engineering" token) |
| keyword | Setu AI ✓ |
| hybrid | Setu AI ✓ |

The keyword component correctly demotes the degree entry and promotes the project that
actually did feature engineering. This is the intended role of hybrid retrieval for exact
technology terms (CLAUDE.md §12) and it works — but a stronger demonstration awaits dense
embeddings.

## Findings & recommendation
1. Retrieval quality is **strong for exact technology matching** (Hit@3 100%) — no change
   needed. Do **not** replace the numpy/TF-IDF stack (ADR-002/004) on this evidence.
2. To evaluate true semantic retrieval, run the suite with `EMBEDDING_PROVIDER=gemini` and
   re-measure Hit@K on paraphrased requirements. Tracked as a follow-up, not a V1 blocker.
3. A `sentence-transformers` local embedder (opt-in) would let this be measured offline.
