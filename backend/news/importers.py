import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import PurePosixPath
from typing import Iterable
from urllib import robotparser
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from .models import Article, ArticleImage


logger = logging.getLogger(__name__)


@dataclass
class SourceArticle:
    external_id: str
    url: str
    title: str
    description: str = ""
    body: str = ""
    published_at: datetime | None = None
    image_urls: list[str] = field(default_factory=list)


@dataclass
class ImportResult:
    candidates: int = 0
    imported: int = 0
    updated: int = 0
    skipped: int = 0
    article_id: int | None = None
    errors: list[str] = field(default_factory=list)
    dry_run_items: list[dict] = field(default_factory=list)


class NewsImportError(Exception):
    pass


def import_numizmatik_news(
    *,
    limit: int | None = None,
    dry_run: bool = False,
    update_existing: bool = False,
    use_ai: bool = True,
) -> ImportResult:
    limit = max(limit or settings.NEWS_IMPORT_LIMIT, 1)
    session = _session()
    source_url = settings.NEWS_IMPORT_SOURCE_URL
    _ensure_robots_allowed(session, source_url)

    candidates = fetch_numizmatik_news(session=session, limit=limit)
    result = ImportResult(candidates=len(candidates))

    if dry_run:
        for source in candidates:
            result.dry_run_items.append(
                {
                    "external_id": source.external_id,
                    "url": source.url,
                    "title": source.title,
                    "images": len(source.image_urls),
                }
            )
        return result

    if not candidates:
        return result

    aggregate_id = _aggregate_external_id(candidates)
    existing = Article.objects.filter(
        source_site="Numizmatik.ru",
        source_external_id=aggregate_id,
    ).first()
    if existing and not update_existing:
        result.article_id = existing.id
        result.skipped = 1
        return result

    try:
        rewritten = (
            rewrite_collection_with_gemini(candidates)
            if use_ai
            else fallback_collection_rewrite(candidates)
        )
        article, created = save_imported_collection(
            sources=candidates,
            rewritten=rewritten,
            existing=existing,
            session=session,
        )
        result.article_id = article.id
        if created:
            result.imported = 1
        else:
            result.updated = 1
        logger.info(
            "Imported aggregate news article %s from %s source items",
            article.id,
            len(candidates),
        )
    except NewsImportError as exc:
        message = f"{aggregate_id}: {exc}"
        logger.warning("Failed to import aggregate news article: %s", message)
        result.errors.append(message)
    except Exception as exc:
        message = f"{aggregate_id}: {exc}"
        logger.exception("Failed to import aggregate news article: %s", aggregate_id)
        result.errors.append(message)
    return result


def fetch_numizmatik_news(*, session: requests.Session, limit: int) -> list[SourceArticle]:
    response = session.get(settings.NEWS_IMPORT_SOURCE_URL, timeout=settings.NEWS_IMPORT_REQUEST_TIMEOUT)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    cards = soup.select('div[id^="news-"][itemscope][itemtype*="Article"]')
    articles: list[SourceArticle] = []

    for card in cards:
        if len(articles) >= limit:
            break
        source = _source_from_card(card)
        if not source:
            continue
        _ensure_robots_allowed(session, source.url)
        detail = _fetch_detail(session, source)
        articles.append(detail)
    return articles


def rewrite_with_gemini(source: SourceArticle) -> dict[str, str]:
    api_key = settings.GEMINI_API_KEY
    if not api_key:
        raise NewsImportError("GEMINI_API_KEY is not configured")

    prompt = {
        "source_title": source.title,
        "source_description": source.description,
        "source_body": source.body[:12000],
        "source_date": source.published_at.isoformat() if source.published_at else "",
    }
    payload = {
        "systemInstruction": {
            "parts": [
                {
                    "text": (
                        "Ты редактор русскоязычного сайта для коллекционеров. "
                        "Перепиши новость своими словами на русском языке. "
                        "Не копируй исходные предложения и не добавляй факты, которых нет в источнике. "
                        "Сохрани смысл, даты, номиналы, страны и важные детали. "
                        "Верни только JSON без markdown."
                    )
                }
            ]
        },
        "contents": [
            {
                "parts": [
                    {
                        "text": (
                            "Сформируй JSON с полями: "
                            "title (до 140 символов), excerpt (до 300 символов), "
                            "content (4-7 коротких абзацев, разделенных пустой строкой). "
                            f"Исходные данные:\n{json.dumps(prompt, ensure_ascii=False)}"
                        )
                    }
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.55,
            "maxOutputTokens": 2048,
            "responseMimeType": "application/json",
        },
    }
    rewritten, used_model = _generate_gemini_json(
        payload=payload,
        api_key=api_key,
        fallback_title=source.title,
    )
    return {
        "title": _truncate(rewritten.get("title") or source.title, 300),
        "excerpt": _make_excerpt(rewritten.get("excerpt") or rewritten.get("content", ""), 500),
        "content": (rewritten.get("content") or "").strip(),
        "ai_model": used_model,
    }


def rewrite_collection_with_gemini(sources: list[SourceArticle]) -> dict[str, str]:
    api_key = settings.GEMINI_API_KEY
    if not api_key:
        raise NewsImportError("GEMINI_API_KEY is not configured")

    fallback_title = _collection_title(sources)
    prompt = {
        "source_site": "Numizmatik.ru",
        "source_count": len(sources),
        "sources": [
            {
                "id": source.external_id,
                "url": source.url,
                "title": source.title,
                "description": source.description,
                "published_at": source.published_at.isoformat() if source.published_at else "",
                "body": source.body[:6000],
            }
            for source in sources
        ],
    }
    payload = {
        "systemInstruction": {
            "parts": [
                {
                    "text": (
                        "Ты редактор русскоязычной платформы CollectIT для коллекционеров. "
                        "На основе нескольких исходных новостей подготовь один большой обзорный материал. "
                        "Пиши своими словами, не копируй исходные предложения и не добавляй факты, "
                        "которых нет в источниках. Сохраняй важные даты, номиналы, страны, имена, "
                        "названия аукционов и другие проверяемые детали. "
                        "Если темы разные, объедини их в логичные смысловые блоки. "
                        "В начале важных смысловых блоков выделяй короткий смысловой акцент жирным "
                        "через markdown-синтаксис **...**: название темы, страны, выпуска или ключевого события. "
                        "Не выделяй жирным целые абзацы, достаточно 2-7 слов. "
                        "Картинки будут прикреплены отдельно, поэтому не вставляй HTML, ссылки и подписи к изображениям. "
                        "Верни только готовый текст статьи без JSON, служебных полей и заголовка. "
                        "Из markdown разрешен только жирный текст через **...**."
                    )
                }
            ]
        },
        "contents": [
            {
                "parts": [
                    {
                        "text": (
                            "Напиши 8-14 абзацев на русском языке, абзацы разделяй пустой строкой. "
                            "Материал должен читаться как одна крупная редакционная новость, а не как список пересказов. "
                            "Начинай сразу с первого абзаца, без отдельного заголовка. "
                            "В 4-8 местах выдели жирным важные разделы или факты через **...**. "
                            f"Исходные данные:\n{json.dumps(prompt, ensure_ascii=False)}"
                        )
                    }
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.55,
            "maxOutputTokens": 8192,
        },
    }
    rewritten, used_model = _generate_gemini_article(
        payload=payload,
        api_key=api_key,
        fallback_title=fallback_title,
    )
    return {
        "title": _truncate(rewritten.get("title") or fallback_title, 300),
        "excerpt": _make_excerpt(rewritten.get("excerpt") or rewritten.get("content", ""), 500),
        "content": (rewritten.get("content") or "").strip(),
        "ai_model": used_model,
    }


def fallback_rewrite(source: SourceArticle) -> dict[str, str]:
    content = source.body.strip()
    return {
        "title": _truncate(source.title, 300),
        "excerpt": _truncate(source.description or content, 500),
        "content": content,
        "ai_model": "",
    }


def fallback_collection_rewrite(sources: list[SourceArticle]) -> dict[str, str]:
    body_parts = []
    for source in sources:
        date = source.published_at.strftime("%d.%m.%Y") if source.published_at else ""
        heading = f"{source.title} ({date})" if date else source.title
        body_parts.append(f"{heading}\n\n{source.body}".strip())
    content = "\n\n".join(body_parts)
    return {
        "title": _collection_title(sources),
        "excerpt": _truncate(f"Обзор {len(sources)} публикаций с Numizmatik.ru.", 500),
        "content": content,
        "ai_model": "",
    }


def save_imported_article(
    *,
    source: SourceArticle,
    rewritten: dict[str, str],
    existing: Article | None,
    session: requests.Session,
) -> tuple[Article, bool]:
    if not rewritten["content"]:
        raise NewsImportError("Gemini returned empty content")

    published_at = source.published_at or timezone.now()
    now = timezone.now()
    with transaction.atomic():
        article = existing or Article()
        article.title = rewritten["title"]
        article.excerpt = _make_excerpt(rewritten["excerpt"] or rewritten["content"], 500)
        article.content = rewritten["content"]
        article.author = article.author_id and article.author or None
        article.is_published = True
        article.published_at = published_at
        article.source_site = "Numizmatik.ru"
        article.source_url = source.url
        article.source_external_id = source.external_id
        article.source_published_at = source.published_at
        article.imported_at = now
        article.ai_model = rewritten.get("ai_model") or ""
        article.is_ai_generated = bool(rewritten.get("ai_model"))
        article.save()

        if existing:
            article.images.all().delete()

        for order, image_url in enumerate(source.image_urls[: settings.NEWS_IMPORT_MAX_IMAGES]):
            content = _download_image(session, image_url)
            if not content:
                continue
            filename = _image_filename(image_url, content["content_type"])
            ArticleImage.objects.create(
                article=article,
                image=ContentFile(content["body"], name=filename),
                order=order,
            )
    return article, existing is None


def save_imported_collection(
    *,
    sources: list[SourceArticle],
    rewritten: dict[str, str],
    existing: Article | None,
    session: requests.Session,
) -> tuple[Article, bool]:
    if not rewritten["content"]:
        raise NewsImportError("Gemini returned empty content")

    dates = [source.published_at for source in sources if source.published_at]
    published_at = max(dates) if dates else timezone.now()
    source_published_at = min(dates) if dates else None
    image_urls = _unique(
        image_url
        for source in sources
        for image_url in source.image_urls
    )
    now = timezone.now()

    with transaction.atomic():
        article = existing or Article()
        article.title = rewritten["title"]
        article.excerpt = _make_excerpt(rewritten["excerpt"] or rewritten["content"], 500)
        article.content = rewritten["content"]
        article.author = None
        article.is_published = True
        article.published_at = published_at
        article.source_site = "Numizmatik.ru"
        article.source_url = settings.NEWS_IMPORT_SOURCE_URL
        article.source_external_id = _aggregate_external_id(sources)
        article.source_published_at = source_published_at
        article.imported_at = now
        article.ai_model = rewritten.get("ai_model") or ""
        article.is_ai_generated = bool(rewritten.get("ai_model"))
        article.save()

        if existing:
            article.images.all().delete()

        for order, image_url in enumerate(image_urls[: settings.NEWS_IMPORT_MAX_IMAGES]):
            content = _download_image(session, image_url)
            if not content:
                continue
            filename = _image_filename(image_url, content["content_type"])
            ArticleImage.objects.create(
                article=article,
                image=ContentFile(content["body"], name=filename),
                order=order,
            )
    return article, existing is None


def _source_from_card(card) -> SourceArticle | None:
    external_id = str(card.get("id", "")).replace("news-", "").strip()
    link = card.select_one('a.numizmatik-news__name[href]')
    if not external_id or not link:
        return None
    title_node = card.select_one('[itemprop="headline"]') or link
    description_node = card.select_one('[itemprop="description"]')
    date_node = card.select_one('meta[itemprop="datePublished"]')
    image_node = card.select_one('img[itemprop="image"][src], img[src]')
    url = urljoin(settings.NEWS_IMPORT_SOURCE_URL, link.get("href"))
    image_urls = []
    if image_node and image_node.get("src"):
        image_urls.append(urljoin(url, image_node.get("src")))
    return SourceArticle(
        external_id=external_id,
        url=url,
        title=_clean_text(title_node.get_text(" ", strip=True)),
        description=_clean_text(description_node.get_text(" ", strip=True)) if description_node else "",
        published_at=_parse_date(date_node.get("content")) if date_node else None,
        image_urls=image_urls,
    )


def _fetch_detail(session: requests.Session, source: SourceArticle) -> SourceArticle:
    response = session.get(source.url, timeout=settings.NEWS_IMPORT_REQUEST_TIMEOUT)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    headline = soup.select_one('[itemprop="headline"]')
    date_node = soup.select_one('meta[itemprop="datePublished"]')
    body = soup.select_one('[itemprop="articleBody"]')
    if not body:
        raise NewsImportError("articleBody was not found")

    for tag in body.select("script, style, noscript"):
        tag.decompose()

    images = [
        urljoin(source.url, img.get("src"))
        for img in body.select("img[src]")
        if img.get("src")
    ]
    if not images:
        images = source.image_urls

    source.title = _clean_text(headline.get_text(" ", strip=True)) if headline else source.title
    source.published_at = _parse_date(date_node.get("content")) if date_node else source.published_at
    source.body = _clean_multiline(body.get_text("\n", strip=True))
    source.image_urls = _unique(images)
    return source


def _aggregate_external_id(sources: list[SourceArticle]) -> str:
    ids = [source.external_id or hashlib.sha256(source.url.encode("utf-8")).hexdigest()[:8] for source in sources]
    digest_source = "|".join(source.url for source in sources)
    digest = hashlib.sha256(digest_source.encode("utf-8")).hexdigest()[:16]
    visible_ids = ",".join(ids)
    return f"aggregate:{digest}:{visible_ids}"[:120]


def _collection_title(sources: list[SourceArticle]) -> str:
    dates = [source.published_at for source in sources if source.published_at]
    if dates:
        latest = max(dates).strftime("%d.%m.%Y")
        return f"Большой обзор новостей нумизматики за {latest}"
    return "Большой обзор новостей нумизматики"


def _download_image(session: requests.Session, url: str) -> dict | None:
    try:
        response = session.get(url, timeout=settings.NEWS_IMPORT_REQUEST_TIMEOUT)
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("Failed to download image %s: %s", url, exc)
        return None
    content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
    if not content_type.startswith("image/"):
        logger.warning("Skipping non-image URL %s with content-type %s", url, content_type)
        return None
    if len(response.content) > settings.NEWS_IMPORT_IMAGE_MAX_BYTES:
        logger.warning("Skipping too large image %s", url)
        return None
    return {"body": response.content, "content_type": content_type}


def _image_filename(url: str, content_type: str) -> str:
    ext = PurePosixPath(urlparse(url).path).suffix.lower().lstrip(".")
    if not ext:
        ext = {
            "image/jpeg": "jpg",
            "image/png": "png",
            "image/webp": "webp",
            "image/gif": "gif",
        }.get(content_type, "img")
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
    return f"numizmatik-{digest}.{ext}"


def _ensure_robots_allowed(session: requests.Session, url: str) -> None:
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    rp = robotparser.RobotFileParser()
    try:
        response = session.get(robots_url, timeout=settings.NEWS_IMPORT_REQUEST_TIMEOUT)
        response.raise_for_status()
        rp.parse(response.text.splitlines())
    except requests.RequestException as exc:
        raise NewsImportError(f"Cannot read robots.txt: {exc}") from exc
    if not rp.can_fetch(settings.NEWS_IMPORT_USER_AGENT, url):
        raise NewsImportError(f"robots.txt does not allow fetching {url}")


def _session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": settings.NEWS_IMPORT_USER_AGENT})
    return session


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    value = value.strip()
    for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            dt = datetime.strptime(value, fmt)
            return timezone.make_aware(dt, timezone.get_current_timezone())
        except ValueError:
            continue
    return None


def _generate_gemini_json(*, payload: dict, api_key: str, fallback_title: str) -> tuple[dict, str]:
    models = _gemini_model_candidates()
    if not models:
        raise NewsImportError("No Gemini model is configured")

    last_error = None
    plain_text_candidate = ""
    plain_text_model = ""
    for index, model in enumerate(models):
        try:
            endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
            response = requests.post(
                endpoint,
                headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
                json=payload,
                timeout=settings.NEWS_IMPORT_REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            data = response.json()
            text = _gemini_text(data)
            try:
                return _parse_json_text(text), model
            except NewsImportError as exc:
                last_error = exc
                plain_text_candidate = text.strip()
                plain_text_model = model
                logger.warning("Gemini model %s returned non-JSON content: %s", model, exc)
        except (requests.RequestException, ValueError, NewsImportError) as exc:
            last_error = exc
            logger.warning("Gemini model %s failed: %s", model, exc)

    if plain_text_candidate:
        logger.warning("Using plain-text Gemini response from model %s", plain_text_model)
        return _rewrite_from_plain_text(plain_text_candidate, fallback_title), plain_text_model

    raise NewsImportError(f"Gemini failed for all configured models: {last_error}") from last_error


def _generate_gemini_article(*, payload: dict, api_key: str, fallback_title: str) -> tuple[dict, str]:
    models = _gemini_model_candidates()
    if not models:
        raise NewsImportError("No Gemini model is configured")

    last_error = None
    for model in models:
        try:
            endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
            response = requests.post(
                endpoint,
                headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
                json=payload,
                timeout=settings.NEWS_IMPORT_REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            text = _gemini_text(response.json())
            rewritten = _coerce_rewritten_text(text, fallback_title)
            if rewritten["content"]:
                return rewritten, model
        except (requests.RequestException, ValueError, NewsImportError) as exc:
            last_error = exc
            logger.warning("Gemini model %s failed: %s", model, exc)

    raise NewsImportError(f"Gemini failed for all configured models: {last_error}") from last_error


def _gemini_model_candidates() -> list[str]:
    models = []
    for model in (
        settings.GEMINI_MODEL,
        getattr(settings, "GEMINI_FALLBACK_MODEL", "gemini-2.5-flash"),
    ):
        model = (model or "").strip()
        if model and model not in models:
            models.append(model)
    return models


def _rewrite_from_plain_text(text: str, fallback_title: str) -> dict[str, str]:
    return _coerce_rewritten_text(text, fallback_title)


def _coerce_rewritten_text(text: str, fallback_title: str) -> dict[str, str]:
    cleaned = _strip_markdown_fence(text)
    data = None
    try:
        data = _parse_json_text(cleaned)
    except NewsImportError:
        data = _extract_loose_json_fields(cleaned)

    if data:
        title = data.get("title") or fallback_title
        content = (
            data.get("content")
            or data.get("article")
            or data.get("text")
            or data.get("body")
            or data.get("excerpt")
            or ""
        )
        content = _clean_multiline(str(content))
        if not content:
            raise NewsImportError("Gemini returned empty content")
        return {
            "title": _truncate(str(title), 300),
            "excerpt": _make_excerpt(str(data.get("excerpt") or content), 500),
            "content": content,
        }

    content = _clean_multiline(cleaned)
    if not content:
        raise NewsImportError("Gemini returned empty content")
    return {
        "title": _truncate(fallback_title, 300),
        "excerpt": _make_excerpt(content, 500),
        "content": content,
    }


def _gemini_text(data: dict) -> str:
    try:
        parts = data["candidates"][0]["content"]["parts"]
    except (KeyError, IndexError, TypeError) as exc:
        raise NewsImportError("Gemini response does not contain text") from exc
    return "\n".join(part.get("text", "") for part in parts).strip()


def _parse_json_text(text: str) -> dict:
    cleaned = _strip_markdown_fence(text)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        data = _extract_json_object(cleaned)
        if data is None:
            raise NewsImportError("Gemini returned invalid JSON") from exc
    if not isinstance(data, dict):
        raise NewsImportError("Gemini JSON response is not an object")
    return data


def _extract_json_object(text: str) -> dict | None:
    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char != "{":
            continue
        try:
            data, _ = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            return data
    return None


def _extract_loose_json_fields(text: str) -> dict:
    fields = {}
    for key in ("title", "excerpt", "content", "article", "text", "body"):
        pattern = rf'["\']{key}["\']\s*:\s*["“](.*?)(?=["”]\s*,\s*["\'](?:title|excerpt|content|article|text|body)["\']\s*:|["”]\s*}}|\Z)'
        match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
        if match:
            value = match.group(1)
            value = value.replace('\\"', '"').replace("\\n", "\n").strip()
            value = re.sub(r'["”]\s*,?\s*$', "", value).strip()
            if value:
                fields[key] = value
    return fields


def _strip_markdown_fence(text: str) -> str:
    cleaned = (text or "").strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _clean_multiline(value: str) -> str:
    lines = [_clean_text(line) for line in (value or "").splitlines()]
    lines = [line for line in lines if line]
    return "\n\n".join(lines)


def _truncate(value: str, max_length: int) -> str:
    value = _clean_text(value)
    if len(value) <= max_length:
        return value
    return value[: max_length - 1].rstrip() + "…"


def _make_excerpt(value: str, max_length: int = 500) -> str:
    value = _clean_text(value)
    if len(value) <= max_length:
        return value

    sentences = re.split(r"(?<=[.!?…])\s+", value)
    excerpt = ""
    for sentence in sentences:
        candidate = f"{excerpt} {sentence}".strip()
        if len(candidate) > max_length:
            break
        excerpt = candidate

    if excerpt:
        return excerpt

    cut = value[:max_length].rstrip()
    last_space = cut.rfind(" ")
    if last_space > max_length * 0.6:
        cut = cut[:last_space]
    return cut.rstrip(" ,;:-")


def _unique(values: Iterable[str]) -> list[str]:
    result = []
    seen = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
