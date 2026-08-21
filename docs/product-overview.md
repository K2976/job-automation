# Product overview

## Problem
Applying to different roles means manually rewriting one master résumé each time —
reframing projects, reordering experience, foregrounding the skills a given JD cares about,
without lying. It's slow and easy to get wrong (or to over-claim).

## Target user
A candidate with a broad background (e.g. iOS-heavy, but with Python/SQL/backend/ML/edge-AI
experience) who applies to varied roles (Data Engineer, AI Engineer, Backend, …).

## Core idea
Treat the candidate's experience as a **living knowledge base**, and treat each tailored
résumé as a **view/transformation** of that base for a specific role — never a replacement
for the master profile.

## User journey (V1)
1. **Ingest** a master résumé (or the bundled sample) → structured, provenance-tagged KB.
2. **Paste a JD** → structured requirements.
3. **See the match**: strong/partial/weak/missing per requirement, with evidence.
4. **Review suggestions**: project rewrites and skill additions — accept / edit / reject.
   Nothing is applied without approval; you only confirm skills you actually have.
5. **Generate** a role-specific résumé built from approved evidence.
6. **Trust it**: a validator traces every claim to evidence; a JD-alignment report scores
   coverage; a comparison shows what changed vs the master.

## V1 boundaries
In scope: the full analyze → approve → generate → validate loop, offline-capable.
Out of scope (by design): job discovery, application automation, browser automation,
multi-agent systems. See [roadmap](roadmap.md).

## First principle
Optimise for *a believable end-to-end RAG workflow that works on real résumés and JDs* —
not feature count.
