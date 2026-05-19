from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class WorkItemType(str, Enum):
    NEW_ARTICLE = "new_article"
    REFRESH = "refresh"
    TECHNICAL = "technical"


class PublishDecision(str, Enum):
    PUBLISH = "publish"
    DRAFT = "draft"
    BLOCK = "block"


@dataclass(frozen=True)
class Opportunity:
    kind: WorkItemType
    keyword: str
    title: str
    score: float
    url: str | None = None
    post_id: int | None = None
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GeneratedContent:
    title: str
    slug: str
    markdown: str
    html: str
    meta_title: str
    meta_description: str
    focus_keyphrase: str
    excerpt: str
    tags: list[str]
    categories: list[str]
    schema_json: dict[str, Any]
    image_prompt: str | None = None
    featured_image_path: str | None = None
    image_alt_text: str | None = None
    rich_blocks: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class AuditReport:
    score: float
    decision: PublishDecision
    issues: list[str]
    warnings: list[str]
    sources: list[str]
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PipelineResult:
    run_id: str
    dry_run: bool
    opportunity: Opportunity
    audit: AuditReport
    content: GeneratedContent
    wordpress_status: str
    wordpress_id: int | None = None
    wordpress_url: str | None = None
