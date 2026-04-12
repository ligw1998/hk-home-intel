from __future__ import annotations


DEFAULT_FALLBACK_CHAIN = ("zh-Hant", "zh-Hans", "en")


def build_translation_map(
    *,
    zh_hant: str | None = None,
    zh_hans: str | None = None,
    en: str | None = None,
    existing: dict[str, str] | None = None,
) -> dict[str, str]:
    values = dict(existing or {})
    if zh_hant:
        values["zh-Hant"] = zh_hant
    if zh_hans:
        values["zh-Hans"] = zh_hans
    if en:
        values["en"] = en
    return {key: value for key, value in values.items() if value}


def localize_text(
    translations: dict[str, str] | None,
    preferred_language: str,
    *,
    fallback_chain: tuple[str, ...] = DEFAULT_FALLBACK_CHAIN,
    default: str | None = None,
) -> str | None:
    normalized = {key: value for key, value in (translations or {}).items() if value}
    if not normalized:
        return default

    if preferred_language in normalized:
        return normalized[preferred_language]

    for language in fallback_chain:
        if language in normalized:
            return normalized[language]

    return next(iter(normalized.values()), default)
