from groq import AsyncGroq
from app.rag.retriever import get_semantic_similarity
from app.rag.embeddings import embed_text, cosine_similarity
from app.utils.skill_normalizer import normalize_skill, expand_synonyms, fuzzy_match

WEIGHTS = {
    "mandatory":  0.40,
    "secondary":  0.20,
    "experience": 0.15,
    "domain":     0.10,
    "education":  0.05,
    "semantic":   0.10,
}

TIERS = [
    (80, "Highly Suitable"),
    (60, "Suitable"),
    (40, "Manual Review"),
    (0,  "Not Suitable"),
]


class ScoringService:
    def __init__(self, openai_client: AsyncGroq):
        self.openai = openai_client

    async def score_candidate(self, candidate: dict, jd: dict) -> dict:
        cand_skills = [normalize_skill(s) for s in (candidate.get("skills_list") or [])]
        syn_map = jd.get("synonym_map") or {}

        mandatory_score, mandatory_matched = self._skill_match(
            cand_skills, jd.get("mandatory_skills") or [], syn_map
        )
        secondary_score, secondary_matched = self._skill_match(
            cand_skills, jd.get("secondary_skills") or [], syn_map
        )
        experience_score = self._experience_score(
            float(candidate.get("total_experience_yrs") or 0),
            float(jd.get("min_experience_yrs") or 0),
        )
        domain_score = await self._domain_score(
            candidate.get("domain_text", ""), jd.get("domain", "")
        )
        education_score = self._education_score(
            candidate.get("education") or [],
            candidate.get("certifications") or [],
            jd.get("education_requirements") or {},
        )
        semantic_raw = await get_semantic_similarity(
            candidate_id=candidate["id"],
            jd_id=jd["id"],
            openai_client=self.openai,
        )
        semantic_score = semantic_raw * 100

        total = (
            mandatory_score  * WEIGHTS["mandatory"]  +
            secondary_score  * WEIGHTS["secondary"]  +
            experience_score * WEIGHTS["experience"] +
            domain_score     * WEIGHTS["domain"]     +
            education_score  * WEIGHTS["education"]  +
            semantic_score   * WEIGHTS["semantic"]
        )

        all_mandatory = set(normalize_skill(s) for s in (jd.get("mandatory_skills") or []))
        missing = list(all_mandatory - set(mandatory_matched))
        risk_flags = self._risk_flags(mandatory_score, experience_score, missing)
        tier = next(t for threshold, t in TIERS if total >= threshold)

        breakdown = {
            "mandatory_skills":  {"raw": round(mandatory_score, 2),  "weighted": round(mandatory_score * WEIGHTS["mandatory"], 2),   "matched": mandatory_matched},
            "secondary_skills":  {"raw": round(secondary_score, 2),  "weighted": round(secondary_score * WEIGHTS["secondary"], 2),   "matched": secondary_matched},
            "experience":        {"raw": round(experience_score, 2), "weighted": round(experience_score * WEIGHTS["experience"], 2)},
            "domain":            {"raw": round(domain_score, 2),     "weighted": round(domain_score * WEIGHTS["domain"], 2)},
            "education":         {"raw": round(education_score, 2),  "weighted": round(education_score * WEIGHTS["education"], 2)},
            "semantic":          {"raw": round(semantic_score, 2),   "weighted": round(semantic_score * WEIGHTS["semantic"], 2)},
        }

        return {
            "total_score": round(total, 2),
            "tier": tier,
            "score_breakdown": breakdown,
            "matched_skills": mandatory_matched + secondary_matched,
            "missing_skills": missing,
            "risk_flags": risk_flags,
        }

    def _skill_match(self, cand_skills: list, jd_skills: list, syn_map: dict) -> tuple:
        if not jd_skills:
            return 100.0, []
        matched = []
        for jd_s in jd_skills:
            variants = expand_synonyms(jd_s, syn_map)
            for cs in cand_skills:
                if any(fuzzy_match(cs, v, threshold=82) for v in variants):
                    matched.append(normalize_skill(jd_s))
                    break
        score = (len(matched) / len(jd_skills)) * 100
        return score, matched

    def _experience_score(self, candidate_yrs: float, required_yrs: float) -> float:
        if required_yrs == 0:
            return 100.0
        ratio = candidate_yrs / required_yrs
        if ratio >= 1.0:  return 100.0
        if ratio >= 0.75: return 75.0
        if ratio >= 0.5:  return 50.0
        return max(0.0, ratio * 50)

    async def _domain_score(self, candidate_domain: str, jd_domain: str) -> float:
        if not candidate_domain or not jd_domain:
            return 50.0
        try:
            v1 = await embed_text(candidate_domain[:500], self.openai)
            v2 = await embed_text(jd_domain[:500], self.openai)
            return cosine_similarity(v1, v2) * 100
        except Exception:
            return 50.0

    def _education_score(self, education: list, certs: list, edu_req: dict) -> float:
        if not edu_req or not edu_req.get("mandatory", False):
            return 100.0
        degree_map = {"phd": 4, "master": 3, "bachelor": 2, "associate": 1, "any": 1}
        required_degree = edu_req.get("degree", "any").lower().split()[0]
        required_level = degree_map.get(required_degree, 1)
        candidate_level = max(
            (degree_map.get((e.get("degree", "") or "").lower().split()[0] if e.get("degree") else "", 0)
             for e in education),
            default=0,
        )
        return 100.0 if candidate_level >= required_level else 40.0

    def _risk_flags(self, mandatory_score: float, experience_score: float, missing: list) -> list:
        flags = []
        if mandatory_score < 50:
            flags.append("Less than 50% mandatory skill match")
        if missing:
            flags.append(f"Missing mandatory skills: {', '.join(missing[:5])}")
        if experience_score < 50:
            flags.append("Significantly under-experienced for this role")
        return flags
