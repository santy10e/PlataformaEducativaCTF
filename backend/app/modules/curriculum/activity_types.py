"""Activity type registry (SPEC §5). New activity kinds are added by registering a type here.

Each type owns three things: validating its `config`, producing the learner-safe view of that config
(answers and solutions never leave the server) and grading a learner submission.
"""

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Protocol
from urllib.parse import urlparse
from uuid import uuid4


@dataclass
class Outcome:
    status: str
    score: int | None
    max_score: int | None
    auto_graded: bool
    feedback: str = ""
    details: dict[str, Any] = field(default_factory=dict)


class ActivityType(Protocol):
    key: str
    label: str
    submittable: bool

    def validate_config(self, config: dict[str, Any]) -> dict[str, Any]: ...

    def student_config(self, config: dict[str, Any]) -> dict[str, Any]: ...

    def grade(self, config: dict[str, Any], points: int, payload: dict[str, Any]) -> Outcome: ...


def _int(config: dict[str, Any], key: str, low: int, high: int, default: int | None) -> int | None:
    value = config.get(key, default)
    if value is None:
        return None
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{key} must be an integer between {low} and {high}")
    return value


def _only(config: dict[str, Any], allowed: set[str]) -> None:
    unknown = set(config) - allowed
    if unknown:
        raise ValueError(f"unsupported config keys: {', '.join(sorted(unknown))}")


def normalize_answer(value: str, case_sensitive: bool) -> str:
    text = " ".join(unicodedata.normalize("NFC", value).split())
    return text if case_sensitive else text.casefold()


def _text_list(values: object, name: str, *, minimum: int, maximum: int, length: int) -> list[str]:
    if not isinstance(values, list) or not minimum <= len(values) <= maximum:
        raise ValueError(f"{name} must contain {minimum} to {maximum} entries")
    cleaned = []
    for item in values:
        if not isinstance(item, str) or not item.strip() or len(item) > length:
            raise ValueError(f"every {name} entry must be 1 to {length} characters")
        cleaned.append(item.strip())
    return cleaned


class LessonRead:
    key = "lesson_read"
    label = "Lectura de la lección"
    submittable = True

    def validate_config(self, config: dict[str, Any]) -> dict[str, Any]:
        _only(config, set())
        return {}

    def student_config(self, config: dict[str, Any]) -> dict[str, Any]:
        return {}

    def grade(self, config: dict[str, Any], points: int, payload: dict[str, Any]) -> Outcome:
        return Outcome("APPROVED", points, points, auto_graded=True)


class Quiz:
    key = "quiz"
    label = "Cuestionario autocorregido"
    submittable = True

    def validate_config(self, config: dict[str, Any]) -> dict[str, Any]:
        _only(config, {"questions", "max_attempts"})
        raw = config.get("questions")
        if not isinstance(raw, list) or not 1 <= len(raw) <= 50:
            raise ValueError("a quiz needs 1 to 50 questions")
        questions: list[dict[str, Any]] = []
        seen: set[str] = set()
        for index, item in enumerate(raw, start=1):
            if not isinstance(item, dict):
                raise ValueError(f"question {index} is invalid")  # noqa: TRY004 - user input; mapped to 422, not a programming error
            _only(item, {"id", "prompt", "kind", "options", "correct", "accepted", "points"})
            question_id = str(item.get("id") or uuid4().hex[:12])
            if not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", question_id) or question_id in seen:
                raise ValueError(f"question {index} has an invalid or duplicated id")
            seen.add(question_id)
            prompt = item.get("prompt")
            if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 2000:
                raise ValueError(f"question {index} needs a prompt of up to 2000 characters")
            kind = item.get("kind")
            weight = _int(item, "points", 1, 100, 1)
            question: dict[str, Any] = {"id": question_id, "prompt": prompt.strip(), "kind": kind, "points": weight}
            if kind in {"single", "multiple"}:
                options = _text_list(item.get("options"), f"question {index} options", minimum=2, maximum=10, length=500)
                correct = item.get("correct")
                if not isinstance(correct, list) or not correct or any(type(c) is not int or not 0 <= c < len(options) for c in correct) or len(set(correct)) != len(correct):
                    raise ValueError(f"question {index} must mark valid correct options")
                if kind == "single" and len(correct) != 1:
                    raise ValueError(f"question {index} is single choice and needs exactly one correct option")
                question |= {"options": options, "correct": sorted(correct)}
            elif kind == "text":
                question["accepted"] = _text_list(item.get("accepted"), f"question {index} accepted answers", minimum=1, maximum=20, length=200)
            else:
                raise ValueError(f"question {index} kind must be single, multiple or text")
            questions.append(question)
        return {"questions": questions, "max_attempts": _int(config, "max_attempts", 1, 20, None)}

    def student_config(self, config: dict[str, Any]) -> dict[str, Any]:
        return {
            "max_attempts": config.get("max_attempts"),
            "questions": [
                {key: value for key, value in question.items() if key in {"id", "prompt", "kind", "options", "points"}}
                for question in config.get("questions", [])
            ],
        }

    def grade(self, config: dict[str, Any], points: int, payload: dict[str, Any]) -> Outcome:
        answers = payload.get("answers")
        if not isinstance(answers, dict):
            raise ValueError("answers must map question ids to responses")  # noqa: TRY004 - user input; mapped to 422, not a programming error
        questions = config.get("questions", [])
        total = sum(int(q["points"]) for q in questions) or 1
        earned = 0
        results: dict[str, bool] = {}
        for question in questions:
            answer = answers.get(question["id"])
            if question["kind"] == "text":
                ok = isinstance(answer, str) and normalize_answer(answer, False) in {normalize_answer(a, False) for a in question["accepted"]}
            else:
                chosen = [answer] if type(answer) is int else answer
                ok = isinstance(chosen, list) and all(type(c) is int for c in chosen) and sorted(set(chosen)) == question["correct"]
            results[question["id"]] = ok
            earned += int(question["points"]) if ok else 0
        score = round(points * earned / total)
        return Outcome("APPROVED", score, points, auto_graded=True, feedback=f"{earned}/{total} puntos de preguntas", details={"results": results})


class Exercise:
    key = "exercise"
    label = "Ejercicio de respuesta"
    submittable = True

    def validate_config(self, config: dict[str, Any]) -> dict[str, Any]:
        _only(config, {"accepted_answers", "case_sensitive", "max_attempts"})
        accepted = config.get("accepted_answers", [])
        accepted = _text_list(accepted, "accepted_answers", minimum=0, maximum=20, length=500) if accepted else []
        case_sensitive = config.get("case_sensitive", False)
        if type(case_sensitive) is not bool:
            raise ValueError("case_sensitive must be a boolean")
        return {"accepted_answers": accepted, "case_sensitive": case_sensitive, "max_attempts": _int(config, "max_attempts", 1, 50, None)}

    def student_config(self, config: dict[str, Any]) -> dict[str, Any]:
        return {"max_attempts": config.get("max_attempts"), "review": "manual" if not config.get("accepted_answers") else "automatic"}

    def grade(self, config: dict[str, Any], points: int, payload: dict[str, Any]) -> Outcome:
        answer = payload.get("answer")
        if not isinstance(answer, str) or not answer.strip() or len(answer) > 5000:
            raise ValueError("answer must be 1 to 5000 characters")
        accepted = config.get("accepted_answers") or []
        if not accepted:
            return Outcome("PENDING_REVIEW", None, points, auto_graded=False)
        sensitive = bool(config.get("case_sensitive"))
        if normalize_answer(answer, sensitive) in {normalize_answer(item, sensitive) for item in accepted}:
            return Outcome("APPROVED", points, points, auto_graded=True, feedback="Respuesta correcta.")
        return Outcome("IN_PROGRESS", None, points, auto_graded=True, feedback="La respuesta no coincide. Revisa la lección e inténtalo de nuevo.")


class Project:
    key = "project"
    label = "Proyecto evaluado por el docente"
    submittable = True

    def validate_config(self, config: dict[str, Any]) -> dict[str, Any]:
        _only(config, {"accept"})
        accept = config.get("accept", ["text", "url"])
        if not isinstance(accept, list) or not accept or any(item not in {"text", "url"} for item in accept) or len(set(accept)) != len(accept):
            # TODO(fase-11): file submissions share the validated upload pipeline built for external evidence.
            raise ValueError("accept must list text and/or url")
        return {"accept": accept}

    def student_config(self, config: dict[str, Any]) -> dict[str, Any]:
        return {"accept": config.get("accept", ["text", "url"])}

    def grade(self, config: dict[str, Any], points: int, payload: dict[str, Any]) -> Outcome:
        accept = config.get("accept", ["text", "url"])
        text = payload.get("text")
        url = payload.get("url")
        if text is not None and ("text" not in accept or not isinstance(text, str) or len(text) > 20000):
            raise ValueError("text is not accepted or exceeds 20000 characters")
        if url is not None:
            parsed = urlparse(url) if isinstance(url, str) else None
            if "url" not in accept or parsed is None or parsed.scheme not in {"http", "https"} or not parsed.netloc or len(url) > 1000:
                raise ValueError("url must be an http(s) address of up to 1000 characters")
        if not (isinstance(text, str) and text.strip()) and not url:
            raise ValueError("send a text or a link")
        return Outcome("PENDING_REVIEW", None, points, auto_graded=False)


class CtfChallenge:
    """References an existing CTF challenge (decision D2); progress comes from the CTF engine."""

    key = "ctf_challenge"
    label = "Reto CTF propio"
    submittable = False

    def validate_config(self, config: dict[str, Any]) -> dict[str, Any]:
        _only(config, {"challenge_id"})
        challenge_id = config.get("challenge_id")
        if type(challenge_id) is not int or challenge_id < 1:
            raise ValueError("challenge_id is required")
        return {"challenge_id": challenge_id}

    def student_config(self, config: dict[str, Any]) -> dict[str, Any]:
        return {}

    def grade(self, config: dict[str, Any], points: int, payload: dict[str, Any]) -> Outcome:
        raise ValueError("CTF challenges are solved in the challenge itself")


REGISTRY: dict[str, ActivityType] = {kind.key: kind for kind in (LessonRead(), Quiz(), Exercise(), Project(), CtfChallenge())}


def get_type(key: str) -> ActivityType:
    kind = REGISTRY.get(key)
    if kind is None:
        raise ValueError("unknown activity type")
    return kind
