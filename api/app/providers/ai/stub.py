"""Deterministic offline AI provider.

Returns valid structured content per `task` so the whole pipeline runs with no
API keys. Output is derived from a hash of the prompt so it is stable per input.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Optional

from app.providers.base import AIProvider, AIResult, Usage

_ADJ = ["Surprising", "Hidden", "Untold", "Simple", "Powerful", "Strange", "Essential"]
_NOUN = ["Truth", "History", "Science", "Story", "Method", "Secret", "Reason"]


def _seed(text: str) -> int:
    return int(hashlib.sha256(text.encode()).hexdigest(), 16)


def _subject(prompt: str) -> str:
    m = re.search(r"(?:niche|topic|about|subject)[\s:]+([A-Za-z0-9 ,'-]{3,60})", prompt, re.I)
    if m:
        return m.group(1).strip().rstrip(".,")
    words = re.findall(r"[A-Za-z]{4,}", prompt)
    return " ".join(words[:3]) if words else "the subject"


class StubAI(AIProvider):
    name = "stub"

    def complete(
        self,
        *,
        system: str,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        json_mode: bool = False,
        task: str = "",
    ) -> AIResult:
        s = _seed(prompt + task)
        subject = _subject(prompt + " " + system)
        text = self._dispatch(task, s, subject, prompt)
        usage = Usage(
            provider="stub",
            model=model or "stub",
            operation=task or "complete",
            input_tokens=len(prompt.split()) + len(system.split()),
            output_tokens=len(text.split()),
            est_cost_usd=0.0,
        )
        return AIResult(text=text, usage=usage)

    # -- per-task canned output --
    def _dispatch(self, task: str, s: int, subject: str, prompt: str) -> str:
        if task == "topics":
            return json.dumps(self._topics(s, subject))
        if task == "research_summary":
            return json.dumps(self._research(s, subject))
        if task in ("script", "script_revision"):
            return json.dumps(self._script(s, subject, prompt))
        if task == "script_qa":
            return json.dumps(self._qa(s, prompt))
        if task == "youtube_metadata":
            return json.dumps(self._metadata(s, subject))
        if task == "thumbnail_concepts":
            return json.dumps(self._thumbnails(s, subject))
        # generic
        return f"Stub response about {subject}."

    def _topics(self, s: int, subject: str) -> dict:
        n = 5 + s % 3
        items = []
        for i in range(n):
            adj = _ADJ[(s + i) % len(_ADJ)]
            noun = _NOUN[(s + i * 3) % len(_NOUN)]
            items.append(
                {
                    "title": f"The {adj} {noun} of {subject.title()} (#{i + 1})",
                    "hook": f"What if everything you knew about {subject} was incomplete?",
                    "angle": f"A {adj.lower()} take on {subject} for curious beginners.",
                    "audience": "curious beginners",
                    "estimated_interest": 55 + (s + i * 7) % 40,
                    "uniqueness_score": 40 + (s + i * 11) % 55,
                    "difficulty": 20 + (s + i * 5) % 60,
                    "search_potential": 30 + (s + i * 13) % 65,
                    "retention_potential": 45 + (s + i * 17) % 50,
                    "competition": 15 + (s + i * 19) % 70,
                    "evergreen": (s + i) % 3 != 0,
                }
            )
        return {"topics": items}

    def _research(self, s: int, subject: str) -> dict:
        return {
            "summary": f"Overview of {subject}: three widely-cited facts and two common misconceptions.",
            "facts": [
                {"claim": f"{subject.title()} has a documented history.", "confidence": 0.8},
                {"claim": f"Experts broadly agree on the basics of {subject}.", "confidence": 0.7},
            ],
            "opinions": [f"Many creators find {subject} underrated as a video topic."],
            "assumptions": [f"The audience has no prior knowledge of {subject}."],
        }

    def _script(self, s: int, subject: str, prompt: str) -> dict:
        target = 480
        m = re.search(r"(\d{2,4})\s*(?:seconds|sec|s)\b", prompt)
        if m:
            target = int(m.group(1))
        n_scenes = max(3, min(8, target // 45))
        per = round(target / n_scenes, 1)
        words_per_scene = max(12, int(target * 2.5 / n_scenes))
        scenes = []
        full = []
        _facets = [
            "its origin", "how it works", "why it was overlooked", "a common myth",
            "what changed recently", "how to think about it", "where it leads next",
            "a concrete example",
        ]
        for i in range(n_scenes):
            facet = _facets[(s + i) % len(_facets)]
            sentence = (
                f"Consider {facet} of {subject}: it reframes the whole picture and "
                f"most explanations skip past it entirely, which is exactly why this part matters."
            )
            reps = max(1, words_per_scene // len(sentence.split()))
            narration = " ".join(
                sentence.replace("this part", f"point {i + 1}.{k}") for k in range(reps)
            )
            full.append(narration)
            scenes.append(
                {
                    "scene": i + 1,
                    "narration": narration,
                    "visual_prompt": f"clean editorial illustration representing {subject}, concept {i + 1}",
                    "visual_type": "image",
                    "duration": per,
                    "transition": "fade",
                }
            )
        return {
            "hook": f"The {_ADJ[s % len(_ADJ)].lower()} truth about {subject} in {target // 60} minutes.",
            "intro": f"In this video we break down {subject} from the ground up.",
            "main": " ".join(full),
            "transitions": ["But there is more.", "Here is where it gets interesting."],
            "pattern_interrupts": ["Quick question for you.", "Stay with me."],
            "cta": "Subscribe if this helped and tell me what to cover next.",
            "ending": f"That is {subject}, explained. Thanks for watching.",
            "full_text": f"{subject}. " + " ".join(full),
            "scenes": scenes,
        }

    def _metadata(self, s: int, subject: str) -> dict:
        sub = subject.title()
        titles = [
            f"The {_ADJ[s % len(_ADJ)]} Truth About {sub}",
            f"{sub}: What Nobody Tells You",
            f"Why {sub} Matters More Than You Think",
            f"{sub} Explained in Plain English",
            f"I Studied {sub} So You Don't Have To",
        ]
        title_options = [
            {
                "title": t,
                "reason": "curiosity gap + clarity" if i == 0 else "alternative framing",
                "score": 90 - i * 6 - (s + i) % 5,
            }
            for i, t in enumerate(titles)
        ]
        tags = [
            subject.lower(), f"{subject.lower()} explained", "documentary", "education",
            "how it works", "history", "science", f"learn {subject.lower()}",
        ]
        return {
            "titles": title_options,
            "description": (
                f"A clear, fast-paced breakdown of {subject}. We cover where it came "
                f"from, how it actually works, and why most explanations get it wrong.\n\n"
                f"Chapters are listed below. Subscribe for more."
            ),
            "tags": tags,
            "hashtags": [
                "#" + (
                    [w for w in re.findall(r"[A-Za-z]{3,}", subject.lower())
                     if w not in {"the", "and", "of", "for", "why", "how"}] or ["topic"]
                )[-1],
                "#explained",
                "#learnwithme",
            ],
            "category_id": "27",
            "chapter_titles": [
                "Introduction", "The origin", "How it works", "The common myth",
                "What changed", "How to think about it", "Where it leads", "Recap",
            ],
        }

    def _thumbnails(self, s: int, subject: str) -> dict:
        emotions = ["curiosity", "surprise", "intrigue", "urgency"]
        concepts = []
        for i in range(3):
            concepts.append(
                {
                    "concept": f"Bold close-up representing {subject}, concept {i + 1}",
                    "text": [f"{subject.split()[0].upper()}?", "THE TRUTH", "WATCH THIS"][i % 3],
                    "composition": "subject left third, high contrast, bright rim light, negative space right for text",
                    "target_emotion": emotions[(s + i) % len(emotions)],
                    "image_prompt": (
                        f"high-contrast editorial thumbnail illustration about {subject}, "
                        f"dramatic lighting, bold focal point, minimal background, concept {i + 1}"
                    ),
                }
            )
        return {"concepts": concepts}

    def _qa(self, s: int, prompt: str) -> dict:
        # Fail the first pass ~1/4 of the time so the revision loop is exercised.
        weak = "revision 0" in prompt.lower() or "version 1" in prompt.lower()
        passed = not (weak and s % 4 == 0)
        score = 92 if passed else 61
        issues = [] if passed else ["Hook is generic", "CTA appears twice"]
        return {
            "passed": passed,
            "score": score,
            "issues": issues,
            "recommendations": [] if passed else ["Rewrite the hook with a concrete number"],
        }
