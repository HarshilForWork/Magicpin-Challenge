#!/usr/bin/env python3
"""
magicpin AI Challenge - LLM-Powered Judge Simulator (Expanded Dataset)

Replica of judge_simulator with:
- Hardcoded configuration
- Expanded dataset loader (dataset/expanded)
- Expanded evaluation over test_pairs
"""

# =============================================================================
# CONFIGURATION - HARD CODED
# =============================================================================

# Your bot's URL (where your bot is running)
BOT_URL = "http://localhost:8080"

# Choose your LLM provider: "openai", "anthropic", "gemini", "deepseek", "groq", "ollama", "openrouter"
LLM_PROVIDER = "groq"

# Your API key (optional for Groq if GROQ_API_KEY is set in .env)
LLM_API_KEY = ""

# Model to use (leave empty to use provider default)
LLM_MODEL = "llama-3.1-8b-instant"

# Which test to run by default
TEST_SCENARIO = "expanded"

# Expanded dataset size (0 = all pairs)
EXPANDED_LIMIT = 0

# Tick batch size for expanded/full evaluation
TRIGGER_BATCH_SIZE = 5

# =============================================================================
# END OF CONFIGURATION - DON'T EDIT BELOW THIS LINE
# =============================================================================

import os
import sys
import json
import time
import re
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple
from pathlib import Path
from urllib import request as urlrequest, error as urlerror
from abc import ABC, abstractmethod

from dotenv import load_dotenv

_BASE_DIR = Path(__file__).parent
load_dotenv(_BASE_DIR / ".env", override=True)
load_dotenv(_BASE_DIR / "vera_bot" / ".env", override=True)

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
LLM_API_KEY = os.getenv("LLM_API_KEY", LLM_API_KEY)

# Prefer GROQ_API_KEY for Groq provider.
if LLM_PROVIDER == "groq" and GROQ_API_KEY:
    LLM_API_KEY = GROQ_API_KEY

# Constants
TIMEOUT_LLM = 45
DATASET_DIR = _BASE_DIR / "dataset" / "expanded"

# =============================================================================
# TERMINAL OUTPUT
# =============================================================================

class Colors:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    MAGENTA = "\033[35m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"


def print_header(text: str):
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*70}{Colors.RESET}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text.center(70)}{Colors.RESET}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*70}{Colors.RESET}\n")


def print_section(text: str):
    print(f"\n{Colors.CYAN}{Colors.BOLD}--- {text} ---{Colors.RESET}\n")


def print_success(text: str):
    print(f"{Colors.GREEN}[PASS]{Colors.RESET} {text}")


def print_fail(text: str):
    print(f"{Colors.RED}[FAIL]{Colors.RESET} {text}")


def print_warn(text: str):
    print(f"{Colors.YELLOW}[WARN]{Colors.RESET} {text}")


def print_info(text: str):
    print(f"{Colors.BLUE}[INFO]{Colors.RESET} {text}")


def print_llm(text: str):
    print(f"{Colors.MAGENTA}[LLM]{Colors.RESET} {text}")


def print_score_bar(dimension: str, score: int, max_score: int = 10):
    bar_filled = int((score / max_score) * 20)
    bar_empty = 20 - bar_filled
    color = Colors.GREEN if score >= 7 else Colors.YELLOW if score >= 4 else Colors.RED
    bar = "#" * bar_filled + "-" * bar_empty
    print(
        f"  {dimension:22} "
        f"[{color}{bar}{Colors.RESET}] "
        f"{color}{score:2}/{max_score}{Colors.RESET}"
    )


def print_reason(text: str):
    wrapped = text[:200] + "..." if len(text) > 200 else text
    print(f"    {Colors.DIM}{wrapped}{Colors.RESET}")


def print_hint(hint: str):
    print(f"\n  {Colors.YELLOW}Hint:{Colors.RESET} {hint}")

# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class ScoreResult:
    specificity: int = 0
    specificity_reason: str = ""
    category_fit: int = 0
    category_fit_reason: str = ""
    merchant_fit: int = 0
    merchant_fit_reason: str = ""
    decision_quality: int = 0
    decision_quality_reason: str = ""
    engagement_compulsion: int = 0
    engagement_reason: str = ""
    penalties: int = 0
    penalty_reasons: List[str] = field(default_factory=list)
    hint: str = ""

    @property
    def total(self) -> int:
        return max(
            0,
            self.specificity
            + self.category_fit
            + self.merchant_fit
            + self.decision_quality
            + self.engagement_compulsion
            - self.penalties,
        )

# =============================================================================
# LLM PROVIDERS
# =============================================================================

class LLMProvider(ABC):
    @abstractmethod
    def complete(self, prompt: str, system: str = None) -> str:
        pass

    @abstractmethod
    def name(self) -> str:
        pass


class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = ""):
        self.api_key = api_key
        self.model = model or "gpt-4o-mini"

    def name(self) -> str:
        return f"OpenAI ({self.model})"

    def complete(self, prompt: str, system: str = None) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        body = json.dumps({
            "model": self.model,
            "messages": messages,
            "temperature": 0,
            "max_tokens": 1500,
        }).encode("utf-8")

        req = urlrequest.Request(
            "https://api.openai.com/v1/chat/completions",
            data=body,
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
        )
        resp = urlrequest.urlopen(req, timeout=TIMEOUT_LLM)
        data = json.loads(resp.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"]


class AnthropicProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = ""):
        self.api_key = api_key
        self.model = model or "claude-3-5-sonnet-20241022"

    def name(self) -> str:
        return f"Anthropic ({self.model})"

    def complete(self, prompt: str, system: str = None) -> str:
        body_dict = {
            "model": self.model,
            "max_tokens": 1500,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            body_dict["system"] = system

        req = urlrequest.Request(
            "https://api.anthropic.com/v1/messages",
            data=json.dumps(body_dict).encode("utf-8"),
            headers={
                "x-api-key": self.api_key,
                "Content-Type": "application/json",
                "anthropic-version": "2023-06-01",
            },
        )
        resp = urlrequest.urlopen(req, timeout=TIMEOUT_LLM)
        data = json.loads(resp.read().decode("utf-8"))
        return data["content"][0]["text"]


class GeminiProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = ""):
        self.api_key = api_key
        self.model = model or "gemini-1.5-flash"

    def name(self) -> str:
        return f"Gemini ({self.model})"

    def complete(self, prompt: str, system: str = None) -> str:
        full_prompt = f"{system}\n\n{prompt}" if system else prompt
        body = json.dumps({
            "contents": [{"parts": [{"text": full_prompt}]}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 1500},
        }).encode("utf-8")

        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent?key={self.api_key}"
        )
        req = urlrequest.Request(url, data=body, headers={"Content-Type": "application/json"})
        resp = urlrequest.urlopen(req, timeout=TIMEOUT_LLM)
        data = json.loads(resp.read().decode("utf-8"))
        return data["candidates"][0]["content"]["parts"][0]["text"]


class DeepSeekProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = ""):
        self.api_key = api_key
        self.model = model or "deepseek-chat"

    def name(self) -> str:
        return f"DeepSeek ({self.model})"

    def complete(self, prompt: str, system: str = None) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        req = urlrequest.Request(
            "https://api.deepseek.com/v1/chat/completions",
            data=json.dumps({
                "model": self.model,
                "messages": messages,
                "temperature": 0.2,
                "max_tokens": 1500,
            }).encode("utf-8"),
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
        )
        resp = urlrequest.urlopen(req, timeout=TIMEOUT_LLM)
        data = json.loads(resp.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"]


class GroqProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = ""):
        self.api_key = api_key
        self.model = model or "llama-3.1-70b-versatile"

    def name(self) -> str:
        return f"Groq ({self.model})"

    def complete(self, prompt: str, system: str = None) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        from groq import Groq

        client = Groq(api_key=self.api_key)
        resp = client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.2,
            max_completion_tokens=1500,
        )
        return resp.choices[0].message.content


class OllamaProvider(LLMProvider):
    def __init__(self, model: str = "", api_url: str = ""):
        self.model = model or "llama3"
        self.api_url = api_url or "http://localhost:11434"

    def name(self) -> str:
        return f"Ollama ({self.model})"

    def complete(self, prompt: str, system: str = None) -> str:
        full_prompt = f"{system}\n\n{prompt}" if system else prompt
        req = urlrequest.Request(
            f"{self.api_url}/api/generate",
            data=json.dumps({
                "model": self.model,
                "prompt": full_prompt,
                "stream": False,
                "options": {"temperature": 0.2},
            }).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        resp = urlrequest.urlopen(req, timeout=90)
        data = json.loads(resp.read().decode("utf-8"))
        return data["response"]


class OpenRouterProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = ""):
        self.api_key = api_key
        self.model = model or "anthropic/claude-3-haiku"

    def name(self) -> str:
        return f"OpenRouter ({self.model})"

    def complete(self, prompt: str, system: str = None) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        req = urlrequest.Request(
            "https://openrouter.ai/api/v1/chat/completions",
            data=json.dumps({
                "model": self.model,
                "messages": messages,
                "temperature": 0.2,
                "max_tokens": 1500,
            }).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://magicpin.com",
            },
        )
        resp = urlrequest.urlopen(req, timeout=TIMEOUT_LLM)
        data = json.loads(resp.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"]


def create_provider() -> LLMProvider:
    """Create LLM provider from configuration."""
    providers = {
        "openai": lambda: OpenAIProvider(LLM_API_KEY, LLM_MODEL),
        "anthropic": lambda: AnthropicProvider(LLM_API_KEY, LLM_MODEL),
        "gemini": lambda: GeminiProvider(LLM_API_KEY, LLM_MODEL),
        "deepseek": lambda: DeepSeekProvider(LLM_API_KEY, LLM_MODEL),
        "groq": lambda: GroqProvider(LLM_API_KEY, LLM_MODEL),
        "ollama": lambda: OllamaProvider(LLM_MODEL, os.getenv("OLLAMA_URL", "http://localhost:11434")),
        "openrouter": lambda: OpenRouterProvider(LLM_API_KEY, LLM_MODEL),
    }

    if LLM_PROVIDER not in providers:
        print_fail(f"Unknown provider: {LLM_PROVIDER}")
        print_info(f"Available: {', '.join(providers.keys())}")
        sys.exit(1)

    return providers[LLM_PROVIDER]()

# =============================================================================
# DATASET & BOT CLIENT
# =============================================================================

class ExpandedDatasetLoader:
    def __init__(self, dataset_dir: Path):
        self.dataset_dir = dataset_dir
        self.categories: Dict[str, Dict] = {}
        self.merchants: Dict[str, Dict] = {}
        self.customers: Dict[str, Dict] = {}
        self.triggers: Dict[str, Dict] = {}
        self.test_pairs: List[Dict] = []

    def load(self) -> bool:
        try:
            cat_dir = self.dataset_dir / "categories"
            if cat_dir.exists():
                for f in cat_dir.glob("*.json"):
                    data = json.load(open(f))
                    self.categories[data.get("slug", f.stem)] = data

            for f in (self.dataset_dir / "merchants").glob("*.json"):
                data = json.load(open(f))
                mid = data.get("merchant_id", f.stem)
                self.merchants[mid] = data

            for f in (self.dataset_dir / "customers").glob("*.json"):
                data = json.load(open(f))
                cid = data.get("customer_id", f.stem)
                self.customers[cid] = data

            for f in (self.dataset_dir / "triggers").glob("*.json"):
                data = json.load(open(f))
                tid = data.get("id", f.stem)
                self.triggers[tid] = data

            pairs_path = self.dataset_dir / "test_pairs.json"
            if pairs_path.exists():
                data = json.load(open(pairs_path))
                self.test_pairs = data.get("pairs", [])

            return True
        except Exception as e:
            print_fail(f"Expanded dataset load error: {e}")
            return False


class BotClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def _request(
        self,
        method: str,
        path: str,
        timeout: int = 30,
        body_dict: Dict = None,
    ) -> Tuple[Optional[Dict], Optional[str], float]:
        url = f"{self.base_url}{path}"
        start = time.time()
        body = json.dumps(body_dict).encode("utf-8") if body_dict else None
        headers = {"Content-Type": "application/json"}
        req = urlrequest.Request(url, data=body, method=method, headers=headers)

        try:
            resp = urlrequest.urlopen(req, timeout=timeout)
            return json.loads(resp.read().decode("utf-8")), None, (time.time() - start) * 1000
        except urlerror.HTTPError as e:
            latency = (time.time() - start) * 1000
            if e.code == 401:
                return None, "Unauthorized", latency
            try:
                return json.loads(e.read().decode("utf-8")), None, latency
            except Exception:
                return None, f"HTTP {e.code}", latency
        except Exception as e:
            return None, str(e), (time.time() - start) * 1000

    def healthz(self):
        return self._request("GET", "/v1/healthz", 5)

    def metadata(self):
        return self._request("GET", "/v1/metadata", 5)

    def push_context(self, scope, cid, version, payload):
        return self._request("POST", "/v1/context", 10, {
            "scope": scope,
            "context_id": cid,
            "version": version,
            "payload": payload,
            "delivered_at": datetime.utcnow().isoformat() + "Z",
        })

    def tick(self, triggers):
        return self._request("POST", "/v1/tick", 15, {
            "now": datetime.utcnow().isoformat() + "Z",
            "available_triggers": triggers,
        })

    def reply(self, conv_id, merchant_id, message, turn):
        return self._request("POST", "/v1/reply", 15, {
            "conversation_id": conv_id,
            "merchant_id": merchant_id,
            "customer_id": None,
            "from_role": "merchant",
            "message": message,
            "received_at": datetime.utcnow().isoformat() + "Z",
            "turn_number": turn,
        })

# =============================================================================
# LLM SCORING ENGINE
# =============================================================================

class LLMScorer:
    """Scores messages using LLM and provides detailed reasoning."""

    SYSTEM = """You are a STRICT judge for the magicpin AI Challenge. You score merchant engagement messages.

SCORING DIMENSIONS (0-10 each, be strict - 5 is average, 7+ is good, 9+ is excellent):

1. SPECIFICITY: Does the message have VERIFIABLE facts?
   - Numbers (percentages, counts, prices)
   - Dates/times
   - Source citations
   - Concrete claims vs vague statements

2. CATEGORY FIT: Does the voice match the business type?
   - Dentists: clinical, peer-to-peer, technical OK, use "Dr." prefix
   - Salons: warm, friendly, practical
   - Restaurants: operator-to-operator
   - Gyms: coaching, motivational
   - Pharmacies: trustworthy, precise

3. MERCHANT FIT: Is it personalized to THIS merchant?
   - Uses their name/owner name correctly
   - References their actual data (not fabricated)
   - Honors language preference

4. TRIGGER RELEVANCE: Does it connect to WHY NOW?
   - Clear reason for this specific message
   - Uses data from the trigger payload
   - Not a generic nudge

5. ENGAGEMENT COMPULSION: Would they reply?
   - Loss aversion, curiosity, social proof
   - Clear CTA
   - Low friction ask

PENALTIES:
- Fabricating data not in context: -2
- Exposing internal jargon to merchant: -1

RESPOND ONLY WITH THIS EXACT JSON FORMAT:
{
  "specificity": <0-10>,
  "specificity_reason": "<why this score, 1-2 sentences>",
  "category_fit": <0-10>,
  "category_fit_reason": "<why this score>",
  "merchant_fit": <0-10>,
  "merchant_fit_reason": "<why this score>",
  "decision_quality": <0-10>,
  "decision_quality_reason": "<why this score>",
  "engagement_compulsion": <0-10>,
  "engagement_reason": "<why this score>",
  "hint": "<one sentence guidance for improvement, cryptic not direct>"
}"""

    def __init__(self, llm: LLMProvider, dataset: ExpandedDatasetLoader):
        self.llm = llm
        self.dataset = dataset

    def score(
        self,
        action: Dict,
        category: Dict,
        merchant: Dict,
        trigger: Dict,
        customer: Dict = None,
    ) -> ScoreResult:
        """Score a message and return detailed results."""

        body = action.get("body", "")

        prompt = f"""SCORE THIS MESSAGE:

=== CONTEXT PROVIDED TO BOT ===
Category: {category.get('slug', 'unknown')}
Voice: {category.get('voice', {}).get('tone', 'unknown')}
Taboos: {category.get('voice', {}).get('vocab_taboo', [])[:5]}

Merchant: {merchant.get('identity', {}).get('name', 'unknown')}
Owner: {merchant.get('identity', {}).get('owner_first_name', 'unknown')}
Locality: {merchant.get('identity', {}).get('locality', 'unknown')}
Languages: {merchant.get('identity', {}).get('languages', [])}
Performance: views={merchant.get('performance', {}).get('views', '?')}, calls={merchant.get('performance', {}).get('calls', '?')}, ctr={merchant.get('performance', {}).get('ctr', '?')}
Signals: {merchant.get('signals', [])}
Active Offers: {[o.get('title') for o in merchant.get('offers', []) if o.get('status') == 'active']}

Trigger Kind: {trigger.get('kind', 'unknown')}
Trigger Payload: {json.dumps(trigger.get('payload', {}))}
Trigger Urgency: {trigger.get('urgency', '?')}

Customer: {json.dumps(customer.get('identity', {})) if customer else 'None (merchant-facing)'}

=== BOT'S MESSAGE ===
Body ({len(body)} chars): "{body}"
CTA: {action.get('cta', 'none')}
Send As: {action.get('send_as', 'vera')}

Score each dimension 0-10 with clear reasoning. Be STRICT."""

        try:
            print_llm("Analyzing message...")
            response = self.llm.complete(prompt, self.SYSTEM)
            return self._parse_response(response, action)
        except Exception as e:
            print_warn(f"LLM error: {e}")
            return self._fallback_score(action)

    def _parse_response(self, response: str, action: Dict) -> ScoreResult:
        """Parse LLM JSON response."""
        match = re.search(r"\{[\s\S]*\}", response)
        if not match:
            return self._fallback_score(action)

        try:
            data = json.loads(match.group())
            result = ScoreResult(
                specificity=min(10, max(0, int(data.get("specificity", 5)))),
                specificity_reason=data.get("specificity_reason", ""),
                category_fit=min(10, max(0, int(data.get("category_fit", 5)))),
                category_fit_reason=data.get("category_fit_reason", ""),
                merchant_fit=min(10, max(0, int(data.get("merchant_fit", 5)))),
                merchant_fit_reason=data.get("merchant_fit_reason", ""),
                decision_quality=min(
                    10,
                    max(0, int(data.get("decision_quality", data.get("trigger_relevance", 5)))),
                ),
                decision_quality_reason=data.get(
                    "decision_quality_reason",
                    data.get("trigger_relevance_reason", ""),
                ),
                engagement_compulsion=min(10, max(0, int(data.get("engagement_compulsion", 5)))),
                engagement_reason=data.get("engagement_reason", ""),
                hint=data.get("hint", ""),
            )
            return result
        except Exception as e:
            print_warn(f"Parse error: {e}")
            return self._fallback_score(action)

    def _fallback_score(self, action: Dict) -> ScoreResult:
        """Basic fallback scoring."""
        body = action.get("body", "").lower()
        nums = len(re.findall(r"\d+", body))
        return ScoreResult(
            specificity=min(10, 3 + nums * 2),
            specificity_reason="Fallback: counted numbers in message",
            category_fit=5,
            category_fit_reason="Could not evaluate",
            merchant_fit=5,
            merchant_fit_reason="Could not evaluate",
            decision_quality=5,
            decision_quality_reason="Could not evaluate",
            engagement_compulsion=5,
            engagement_reason="Could not evaluate",
            hint="LLM scoring failed - using basic heuristics",
        )

# =============================================================================
# MAIN JUDGE
# =============================================================================

class JudgeSimulator:
    def __init__(self, llm: LLMProvider):
        self.llm = llm
        self.client = BotClient(BOT_URL)
        self.dataset = ExpandedDatasetLoader(DATASET_DIR)
        self.scorer: Optional[LLMScorer] = None
        self.all_scores: List[ScoreResult] = []

    def run(self, scenario: str) -> bool:
        print_header(f"LLM JUDGE - {scenario.upper()}")
        print_info(f"Bot: {BOT_URL}")
        print_info(f"LLM: {self.llm.name()}")

        if not self.dataset.load():
            print_fail("Dataset load failed")
            return False

        self.scorer = LLMScorer(self.llm, self.dataset)
        print_info(
            f"Loaded: {len(self.dataset.categories)} categories, "
            f"{len(self.dataset.merchants)} merchants, "
            f"{len(self.dataset.triggers)} triggers"
        )

        scenarios = {
            "warmup": self._warmup,
            "phase2_short": self._phase2_short,
            "auto_reply_hell": self._auto_reply,
            "intent_transition": self._intent,
            "hostile": self._hostile,
            "expanded": self._expanded,
            "all": self._all,
            "full_evaluation": self._full,
        }

        if scenario not in scenarios:
            print_fail(f"Unknown scenario: {scenario}")
            print_info(f"Available: {', '.join(scenarios.keys())}")
            return False

        success = scenarios[scenario]()
        self._final_summary()
        return success

    def _warmup(self) -> bool:
        print_section("WARMUP")

        data, err, lat = self.client.healthz()
        if err:
            print_fail(f"healthz: {err}")
            return False
        print_success(f"healthz ({lat:.0f}ms)")

        data, err, lat = self.client.metadata()
        if err:
            print_warn(f"metadata: {err}")
        else:
            print_success(f"metadata - Team: {data.get('team_name', '?')}, Model: {data.get('model', '?')}")

        print_section("CONTEXT PUSH")
        for slug, cat in self.dataset.categories.items():
            data, err, _ = self.client.push_context("category", slug, 1, cat)
            status = "PASS" if data and data.get("accepted") else "FAIL"
            print(f"  [{status}] category/{slug}")

        for mid, m in list(self.dataset.merchants.items())[:5]:
            data, err, _ = self.client.push_context("merchant", mid, 1, m)
            status = "PASS" if data and data.get("accepted") else "FAIL"
            short_id = mid.split("_")[1] if "_" in mid else mid[:10]
            print(f"  [{status}] merchant/{short_id}")

        return True

    def _phase2_short(self) -> bool:
        if not self._warmup():
            return False

        print_section("TICK TEST")

        trigs = list(self.dataset.triggers.keys())[:3]
        for tid in trigs:
            self.client.push_context("trigger", tid, 1, self.dataset.triggers[tid])

        data, err, lat = self.client.tick(trigs)
        if err:
            print_fail(f"tick: {err}")
            return False

        actions = data.get("actions", [])
        print_info(f"Bot returned {len(actions)} action(s) ({lat:.0f}ms)")

        if not actions:
            print_warn("No actions - bot chose not to send")
            return True

        for action in actions:
            self._score_and_display(action)

        return True

    def _auto_reply(self) -> bool:
        print_section("AUTO-REPLY DETECTION")

        data, err, _ = self.client.healthz()
        if err:
            print_fail(f"Bot unreachable: {err}")
            return False

        mid = list(self.dataset.merchants.keys())[0] if self.dataset.merchants else "m_test"
        auto_msg = "Thank you for contacting us! Our team will respond shortly."

        for i in range(1, 5):
            print_info(f"Turn {i}: Sending auto-reply...")
            data, err, _ = self.client.reply(f"conv_auto_{i}", mid, auto_msg, i + 1)

            if err:
                print_fail(f"Error: {err}")
                return False

            action = data.get("action", "?")

            if action == "end":
                print_success(f"Turn {i}: Bot ENDED - detected auto-reply pattern!")
                return True
            if action == "wait":
                wait_s = data.get("wait_seconds", "?")
                print_success(f"Turn {i}: Bot WAITING {wait_s}s")
            else:
                body = data.get("body", "")[:50]
                print_warn(f"Turn {i}: Bot sent: \"{body}...\"")

        print_warn("Bot never ended after 4 auto-replies")
        return True

    def _intent(self) -> bool:
        print_section("INTENT TRANSITION")

        data, err, _ = self.client.healthz()
        if err:
            print_fail(f"Bot unreachable: {err}")
            return False

        mid = list(self.dataset.merchants.keys())[0] if self.dataset.merchants else "m_test"
        commitment = "Ok lets do it. Whats next?"

        print_info(f"Merchant: \"{commitment}\"")
        data, err, _ = self.client.reply("conv_intent_1", mid, commitment, 2)

        if err:
            print_fail(f"Error: {err}")
            return False

        action = data.get("action", "?")
        body = data.get("body", "")

        print_info(f"Bot action: {action}")
        if body:
            print_info(f"Bot body: \"{body[:100]}{'...' if len(body) > 100 else ''}\"")

        qualifying = ["would you", "do you", "can you tell", "what if", "how about"]
        actioning = ["done", "sending", "draft", "here", "confirm", "proceed", "next"]

        body_lower = body.lower()
        if any(w in body_lower for w in actioning) and not any(w in body_lower for w in qualifying):
            print_success("Bot correctly switched to ACTION mode")
        elif any(w in body_lower for w in qualifying):
            print_fail("Bot is STILL QUALIFYING after commitment")
        else:
            print_warn("Response unclear")

        return True

    def _hostile(self) -> bool:
        print_section("HOSTILE HANDLING")

        data, err, _ = self.client.healthz()
        if err:
            print_fail(f"Bot unreachable: {err}")
            return False

        mid = list(self.dataset.merchants.keys())[0] if self.dataset.merchants else "m_test"
        hostile = "Stop messaging me. This is useless spam."

        print_info(f"Merchant (hostile): \"{hostile}\"")
        data, err, _ = self.client.reply("conv_hostile", mid, hostile, 2)

        if err:
            print_fail(f"Error: {err}")
            return False

        action = data.get("action", "?")
        body = data.get("body", "")

        print_info(f"Bot action: {action}")

        if action == "end":
            print_success("Bot correctly ENDED on hostile message")
        elif action == "send" and any(w in body.lower() for w in ["sorry", "apolog", "won't"]):
            print_success("Bot apologized gracefully")
        else:
            print_fail("Bot didn't handle hostility well")

        return True

    def _suppression(self) -> bool:
        print_section("SUPPRESSION CHECK")

        data, err, _ = self.client.healthz()
        if err:
            print_fail(f"Bot unreachable: {err}")
            return False

        trigger_id = None
        trigger = None
        for tid, t in self.dataset.triggers.items():
            if t.get("merchant_id"):
                trigger_id = tid
                trigger = t
                break

        if not trigger or not trigger_id:
            print_warn("No trigger with merchant_id found; skipping suppression check")
            return True

        merchant_id = trigger.get("merchant_id")
        merchant = self.dataset.merchants.get(merchant_id)
        if not merchant:
            print_warn("Merchant not found for suppression check")
            return True

        category_slug = merchant.get("category_slug")
        category = self.dataset.categories.get(category_slug)
        if category:
            self.client.push_context("category", category_slug, 1, category)

        self.client.push_context("merchant", merchant_id, 1, merchant)
        self.client.push_context("trigger", trigger_id, 1, trigger)

        data, err, _ = self.client.tick([trigger_id])
        if err:
            print_fail(f"tick: {err}")
            return False

        actions = data.get("actions", [])
        if not actions:
            print_warn("No actions returned; cannot test suppression")
            return True

        action = actions[0]
        reject_msg = "Stop messaging me."
        data, err, _ = self.client.reply(action.get("conversation_id"), merchant_id, reject_msg, 2)
        if err:
            print_fail(f"reply: {err}")
            return False

        if data.get("action") != "end":
            print_warn("Reject did not end conversation; suppression may not be set")

        next_trigger_id = None
        for tid, t in self.dataset.triggers.items():
            if t.get("merchant_id") == merchant_id and tid != trigger_id:
                next_trigger_id = tid
                break

        if not next_trigger_id:
            print_warn("No second trigger for same merchant; skipping suppression verify")
            return True

        self.client.push_context("trigger", next_trigger_id, 2, self.dataset.triggers[next_trigger_id])
        data, err, _ = self.client.tick([next_trigger_id])
        if err:
            print_fail(f"tick: {err}")
            return False

        if data.get("actions"):
            print_fail("Suppression check failed: actions returned for suppressed merchant")
            return False

        print_success("Suppression check passed (no actions after reject)")
        return True

    def _expanded(self) -> bool:
        if not self._warmup():
            return False

        if not self._auto_reply():
            print_warn("Auto-reply check failed")
        if not self._suppression():
            print_warn("Suppression check failed")

        print_section("EXPANDED EVALUATION")

        if not self.dataset.test_pairs:
            print_fail("Expanded test_pairs.json is empty")
            return False

        if EXPANDED_LIMIT <= 0:
            limit = len(self.dataset.test_pairs)
        else:
            limit = max(1, min(EXPANDED_LIMIT, len(self.dataset.test_pairs)))

        pairs = self.dataset.test_pairs[:limit]
        run_id = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        run_version = int(time.time())

        print_info(
            f"Expanded pairs: {limit} of {len(self.dataset.test_pairs)}"
        )

        pushed_categories = set()
        pushed_triggers = set()

        for pair in pairs:
            trigger_id = pair.get("trigger_id")
            merchant_id = pair.get("merchant_id")
            customer_id = pair.get("customer_id")

            trigger = self.dataset.triggers.get(trigger_id)
            merchant = self.dataset.merchants.get(merchant_id)

            if not trigger or not merchant:
                print_warn(f"Missing data for pair {pair.get('test_id', '?')}")
                continue

            category_slug = merchant.get("category_slug")
            category = self.dataset.categories.get(category_slug)
            if category and category_slug not in pushed_categories:
                self.client.push_context("category", category_slug, 1, category)
                pushed_categories.add(category_slug)

            self.client.push_context("merchant", merchant_id, 1, merchant)

            if customer_id:
                customer = self.dataset.customers.get(customer_id)
                if customer:
                    self.client.push_context("customer", customer_id, 1, customer)
                else:
                    print_warn(f"Customer missing: {customer_id}")

            if trigger_id and trigger_id not in pushed_triggers:
                trigger_payload = json.loads(json.dumps(trigger))
                base_key = trigger_payload.get("suppression_key", "")
                trigger_payload["suppression_key"] = f"{base_key}:exp:{run_id}:{pair.get('test_id', '')}"
                self.client.push_context("trigger", trigger_payload["id"], run_version, trigger_payload)
                pushed_triggers.add(trigger_id)

        trigger_ids = []
        seen = set()
        for pair in pairs:
            trigger_id = pair.get("trigger_id")
            if trigger_id and trigger_id in self.dataset.triggers and trigger_id not in seen:
                trigger_ids.append(trigger_id)
                seen.add(trigger_id)

        if not trigger_ids:
            print_fail("No triggers found for expanded pairs")
            return False

        print_section("SCORING COMPOSITIONS")
        for i in range(0, len(trigger_ids), TRIGGER_BATCH_SIZE):
            batch = trigger_ids[i:i + TRIGGER_BATCH_SIZE]
            data, err, lat = self.client.tick(batch)

            if err:
                print_warn(f"Tick failed: {err}")
                continue

            actions = data.get("actions", [])
            print_info(f"Batch {i // TRIGGER_BATCH_SIZE + 1}: {len(actions)} actions ({lat:.0f}ms)")

            for action in actions:
                self._score_and_display(action, verbose=False)

        return True

    def _all(self) -> bool:
        results = []
        for name, fn in [
            ("warmup", self._warmup),
            ("auto_reply", self._auto_reply),
            ("intent", self._intent),
            ("hostile", self._hostile),
            ("suppression", self._suppression),
            ("expanded", self._expanded),
        ]:
            try:
                results.append((name, fn()))
            except Exception as e:
                print_fail(f"{name} crashed: {e}")
                results.append((name, False))

        print_section("SCENARIO RESULTS")
        for name, passed in results:
            (print_success if passed else print_fail)(name)

        return all(p for _, p in results)

    def _full(self) -> bool:
        if not self._warmup():
            return False

        print_section("FULL EVALUATION")

        for mid, m in self.dataset.merchants.items():
            self.client.push_context("merchant", mid, 1, m)
        for tid, t in self.dataset.triggers.items():
            self.client.push_context("trigger", tid, 1, t)

        print_success("All contexts pushed")

        print_section("SCORING COMPOSITIONS")
        tids = list(self.dataset.triggers.keys())

        for i in range(0, len(tids), TRIGGER_BATCH_SIZE):
            batch = tids[i:i + TRIGGER_BATCH_SIZE]
            data, err, lat = self.client.tick(batch)

            if err:
                print_warn(f"Tick failed: {err}")
                continue

            actions = data.get("actions", [])
            print_info(f"Batch {i // TRIGGER_BATCH_SIZE + 1}: {len(actions)} actions ({lat:.0f}ms)")

            for action in actions:
                self._score_and_display(action, verbose=False)

        return True

    def _score_and_display(self, action: Dict, verbose: bool = True):
        tid = action.get("trigger_id", "")
        mid = action.get("merchant_id", "")
        cid = action.get("customer_id")

        trigger = self.dataset.triggers.get(tid, {})
        merchant = self.dataset.merchants.get(mid, {})
        customer = self.dataset.customers.get(cid) if cid else None
        category = self.dataset.categories.get(merchant.get("category_slug", ""), {})

        score = self.scorer.score(action, category, merchant, trigger, customer)
        self.all_scores.append(score)

        body = action.get("body", "")[:50]
        print(f"\n{Colors.CYAN}Message:{Colors.RESET} \"{body}...\"")

        print_score_bar("Specificity", score.specificity)
        if verbose and score.specificity_reason:
            print_reason(score.specificity_reason)

        print_score_bar("Category Fit", score.category_fit)
        if verbose and score.category_fit_reason:
            print_reason(score.category_fit_reason)

        print_score_bar("Merchant Fit", score.merchant_fit)
        if verbose and score.merchant_fit_reason:
            print_reason(score.merchant_fit_reason)

        print_score_bar("Decision Quality", score.decision_quality)
        if verbose and score.decision_quality_reason:
            print_reason(score.decision_quality_reason)

        print_score_bar("Engagement", score.engagement_compulsion)
        if verbose and score.engagement_reason:
            print_reason(score.engagement_reason)

        if score.penalties:
            print(f"  {Colors.RED}Penalties: -{score.penalties}{Colors.RESET}")
            for r in score.penalty_reasons:
                print_reason(r)

        print(f"\n  {Colors.BOLD}TOTAL: {score.total}/50{Colors.RESET}")

        if verbose and score.hint:
            print_hint(score.hint)

    def _final_summary(self):
        if not self.all_scores:
            return

        print_section("FINAL SUMMARY")

        n = len(self.all_scores)
        avg = ScoreResult(
            specificity=sum(s.specificity for s in self.all_scores) // n,
            category_fit=sum(s.category_fit for s in self.all_scores) // n,
            merchant_fit=sum(s.merchant_fit for s in self.all_scores) // n,
            decision_quality=sum(s.decision_quality for s in self.all_scores) // n,
            engagement_compulsion=sum(s.engagement_compulsion for s in self.all_scores) // n,
            penalties=sum(s.penalties for s in self.all_scores),
        )

        print_info(f"Messages scored: {n}\n")

        print_score_bar("Avg Specificity", avg.specificity)
        print_score_bar("Avg Category Fit", avg.category_fit)
        print_score_bar("Avg Merchant Fit", avg.merchant_fit)
        print_score_bar("Avg Decision Quality", avg.decision_quality)
        print_score_bar("Avg Engagement", avg.engagement_compulsion)

        total = avg.total
        pct = (total / 50) * 100

        print(f"\n{Colors.BOLD}  AVERAGE SCORE: {total}/50 ({pct:.0f}%){Colors.RESET}")

        if pct >= 80:
            print(f"\n  {Colors.GREEN}EXCELLENT{Colors.RESET}")
        elif pct >= 60:
            print(f"\n  {Colors.YELLOW}GOOD{Colors.RESET}")
        elif pct >= 40:
            print(f"\n  {Colors.YELLOW}NEEDS IMPROVEMENT{Colors.RESET}")
        else:
            print(f"\n  {Colors.RED}BELOW EXPECTATIONS{Colors.RESET}")

# =============================================================================
# ENTRY POINT
# =============================================================================

def main():
    print_header("magicpin AI Challenge - LLM Judge (Expanded)")

    # Validate configuration
    if LLM_PROVIDER != "ollama" and not LLM_API_KEY:
        print_fail("LLM_API_KEY is not set!")
        print_info("Set your API key in .env or the configuration section at the top of this file")
        sys.exit(1)

    # Create LLM provider
    try:
        llm = create_provider()
        print_info(f"LLM Provider: {llm.name()}")
    except Exception as e:
        print_fail(f"Failed to create LLM provider: {e}")
        sys.exit(1)

    # Test LLM connection
    print_info("Testing LLM connection...")
    try:
        test_response = llm.complete("Say 'ready' if you can hear me.", "You are a test assistant.")
        if test_response:
            print_success("LLM connected successfully")
        else:
            print_fail("LLM returned empty response")
            sys.exit(1)
    except Exception as e:
        print_fail(f"LLM connection failed: {e}")
        print_info("Check your API key and internet connection")
        sys.exit(1)

    # Run the judge
    judge = JudgeSimulator(llm)
    success = judge.run(TEST_SCENARIO)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
