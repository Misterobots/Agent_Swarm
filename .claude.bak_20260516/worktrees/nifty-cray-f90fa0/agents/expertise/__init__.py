"""
ExpertiseTemplate system for self-improving agent templates.

Provides versioned templates, performance tracking, and automatic
template evolution based on MarsRL reward signals.
"""

from expertise.template_registry import (
    TemplateRegistry,
    ExpertiseTemplate,
    TemplateVersion,
    PerformanceRecord,
    PerformanceSummary,
    get_template_registry,
)

__all__ = [
    "TemplateRegistry",
    "ExpertiseTemplate",
    "TemplateVersion",
    "PerformanceRecord",
    "PerformanceSummary",
    "get_template_registry",
]
