from typing import Dict, Any, List

class DeterministicGate:
    """Tri-state deterministic gate enforcing code-level invariants."""
    
    @staticmethod
    def evaluate(rule_id: str, assertion: Dict[str, Any], evidence_quote: str, raw_source: str) -> Dict[str, Any]:
        if not evidence_quote:
            return {
                "verdict": "UNDETERMINED",
                "reason": "Missing supporting evidence quote",
                "rule_id": rule_id
            }
        
        # Enforce exact quote-in-source invariant
        if evidence_quote not in raw_source:
            return {
                "verdict": "FAIL",
                "reason": f"Evidence quote does not exist verbatim in raw source",
                "rule_id": rule_id
            }
            
        return {
            "verdict": "PASS",
            "rule_id": rule_id,
            "verified_evidence": evidence_quote
        }
