from __future__ import annotations

from typing import Any


class MediaAgenciesPipeline:
    """Self-contained Hugging Face pipeline placeholder.

    The implementation should be adapted from
    `impresso_pipelines.newsagencies.NewsAgenciesPipeline` and must not import
    from the workbench package at runtime.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.args = args
        self.kwargs = kwargs

    def __call__(self, texts: str | list[str], *args: Any, **kwargs: Any) -> dict[str, Any] | list[dict[str, Any]]:
        raise NotImplementedError("HF media-sources pipeline is scaffolded but not implemented yet")


# Compatibility alias for older users while the new pipeline name lands.
NewsAgenciesPipeline = MediaAgenciesPipeline
