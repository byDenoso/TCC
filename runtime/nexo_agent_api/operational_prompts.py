"""Versioned operational interface prompts, not scientific decision criteria."""
import hashlib

ROLE_NAMES = {"EXECUTOR": "Executor", "ENGENHEIRO": "Engenheiro", "CIENTISTA": "Cientista", "CRITICO": "Cr\u00edtico"}
PROMPTS = {
    role: f"Voc\u00ea \u00e9 o {name} do NEXO. Consulte o MCP para obter seu trabalho e as a\u00e7\u00f5es dispon\u00edveis; execute e registre o resultado."
    for role, name in ROLE_NAMES.items()
}
# PR128 legacy binding is retained, never overwritten or reinterpreted.
LEGACY_EXECUTOR_PROMPT_SHA256 = "47fe9079dc26f58ef206be163edb963c572199e923218bc79984172787520484"
EXECUTOR_PROMPT_SHA256 = hashlib.sha256(PROMPTS["EXECUTOR"].encode("utf-8")).hexdigest()
EXECUTOR_PROMPT_HASHES = frozenset({LEGACY_EXECUTOR_PROMPT_SHA256, EXECUTOR_PROMPT_SHA256})
