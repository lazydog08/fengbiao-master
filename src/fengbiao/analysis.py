from __future__ import annotations

import math
import re
from typing import Any


# Keep these thresholds aligned with apps/web/src/lib/buckets.ts.
HIGH_RELATIVE_THRESHOLD = 1.5
STEADY_RELATIVE_THRESHOLD = 0.6
LOW_CONFIDENCE_SAMPLE_SIZE = 3


Feature = dict[str, str | bool]
Analysis = dict[str, Any]


def analyze_sample(
    title: str | None,
    cover_dimensions: tuple[int, int] | None,
    cover_changed: bool,
    title_changed: bool,
    relative_to_baseline: float | None,
    sample_size: int,
) -> Analysis:
    normalized_title = title or ""
    features = _title_features(normalized_title)
    bucket = performance_bucket(relative_to_baseline)
    confidence = "low" if bucket == "unknown" or sample_size < LOW_CONFIDENCE_SAMPLE_SIZE else "ok"
    cover = _cover_analysis(cover_dimensions, cover_changed, title_changed)
    return {
        "version": 1,
        "source": "rule",
        "performance": {
            "bucket": bucket,
            "relative_to_baseline": relative_to_baseline,
            "confidence": confidence,
            "basis": "relative-to-creator-baseline",
        },
        "title": {
            "char_len": len(normalized_title.strip()),
            "features": features,
        },
        "cover": cover,
        "explanation": _explanation(features, cover, bucket, confidence),
        "caveats": [
            "本判断基于库内相对表现，不代表真实点击率。",
            "选题、发布时间和受众范围都会影响播放表现。",
        ],
    }


def performance_bucket(relative_to_baseline: float | None) -> str:
    if relative_to_baseline is None:
        return "unknown"
    if math.isnan(relative_to_baseline):
        return "unknown"
    if relative_to_baseline >= HIGH_RELATIVE_THRESHOLD:
        return "high"
    if relative_to_baseline >= STEADY_RELATIVE_THRESHOLD:
        return "steady"
    return "low"


def _title_features(title: str) -> list[Feature]:
    stripped = title.strip()
    checks: list[tuple[str, str, bool]] = [
        ("question", "疑问句式", bool(re.search(r"[?？]|怎么|为什么|如何|吗|能不能|是不是|有没有", stripped))),
        ("number", "含具体数字", bool(re.search(r"\d|[一二三四五六七八九十百千万]+(?:年|天|元|块|次|个|台|款)", stripped))),
        ("comparison", "对比结构", bool(re.search(r"\bvs\b|VS|对比|还是|不如|相比|比.+更", stripped, re.IGNORECASE))),
        ("first_person", "第一人称体验", any(term in stripped for term in ["我", "我们", "亲测", "实测", "自己", "我的"])),
        ("conflict", "冲突/反差词", any(term in stripped for term in ["居然", "竟然", "翻车", "崩", "后悔", "没想到", "真相", "反差", "离谱"])),
        ("specificity", "具体指称", bool(re.search(r"[A-Za-z]+\d*|\d+[A-Za-z]*|《[^》]+》|「[^」]+」|『[^』]+』", stripped))),
    ]
    return [{"id": feature_id, "label": label, "present": present} for feature_id, label, present in checks]


def _cover_analysis(
    cover_dimensions: tuple[int, int] | None,
    cover_changed: bool,
    title_changed: bool,
) -> dict[str, Any]:
    if not cover_dimensions:
        return {
            "has_asset": False,
            "width": None,
            "height": None,
            "aspect_ratio": None,
            "orientation": "unknown",
            "cover_changed": bool(cover_changed),
            "title_changed": bool(title_changed),
        }
    width, height = cover_dimensions
    aspect_ratio = round(width / height, 3) if height > 0 else None
    return {
        "has_asset": True,
        "width": width,
        "height": height,
        "aspect_ratio": aspect_ratio,
        "orientation": _orientation(aspect_ratio),
        "cover_changed": bool(cover_changed),
        "title_changed": bool(title_changed),
    }


def _orientation(aspect_ratio: float | None) -> str:
    if aspect_ratio is None:
        return "unknown"
    if aspect_ratio >= 1.2:
        return "landscape"
    if aspect_ratio <= 0.85:
        return "portrait"
    return "square"


def _explanation(features: list[Feature], cover: dict[str, Any], bucket: str, confidence: str) -> dict[str, str]:
    present_labels = [str(feature["label"]) for feature in features if feature["present"]]
    if present_labels:
        title_part = "标题由" + "、".join(present_labels) + "组成。"
    else:
        title_part = "标题表达相对平铺，主要依赖选题本身传达信息。"

    if cover["has_asset"]:
        cover_part = f"封面为{_orientation_label(str(cover['orientation']))}构图，比例约 {cover['aspect_ratio']}。"
    else:
        cover_part = "当前没有可读取的封面文件，结构分析以标题为主。"
    change_part = _change_part(bool(cover["cover_changed"]), bool(cover["title_changed"]))
    structure = f"{title_part}{cover_part}{change_part}"

    if present_labels:
        features_text = "可见特征集中在" + "、".join(present_labels) + "，适合和同赛道样本对照。"
    else:
        features_text = "可见特征较少，适合作为朴素表达样本和高表现样本做对照。"

    interpretation = _interpretation(bucket, confidence)
    return {
        "structure": structure,
        "features": features_text,
        "interpretation": interpretation,
    }


def _change_part(cover_changed: bool, title_changed: bool) -> str:
    if cover_changed and title_changed:
        return " 收录记录显示封面和标题都发生过变化。"
    if cover_changed:
        return " 收录记录显示封面发生过变化。"
    if title_changed:
        return " 收录记录显示标题发生过变化。"
    return ""


def _orientation_label(orientation: str) -> str:
    labels = {
        "landscape": "横版",
        "portrait": "竖版",
        "square": "近方形",
        "unknown": "未知",
    }
    return labels.get(orientation, "未知")


def _interpretation(bucket: str, confidence: str) -> str:
    uncertainty = " 当前样本量偏少，这个判断需要结合后续收录继续看。" if confidence == "low" else ""
    if bucket == "high":
        return "这个样本高于该创作者库内基线。可以把结构和特征当作候选参考，但不能直接归因为封面或标题单项。" + uncertainty
    if bucket == "steady":
        return "这个样本接近该创作者库内基线。结构可作为常规参考，更适合和同赛道高低样本对照看差异。" + uncertainty
    if bucket == "low":
        return "这个样本低于该创作者库内基线。标题或封面未必有问题，也可能受到选题热度、发布时间和受众范围影响。" + uncertainty
    return "这个样本暂时缺少足够的库内相对表现数据。先记录结构和特征，等后续快照补齐后再判断。" + uncertainty
