from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

import numpy as np
import pytesseract
from PIL import Image, ImageFilter, ImageStat
from pytesseract import Output


@dataclass
class OCRResult:
    text: str
    confidence: float | None
    blurry: bool
    reasons: list[str]


def extract_image(raw: bytes) -> OCRResult:
    image = Image.open(BytesIO(raw)).convert("RGB")
    gray = image.convert("L")
    edges = np.asarray(gray.filter(ImageFilter.FIND_EDGES), dtype=np.float32)
    edge_variance = float(edges.var())
    contrast = float(ImageStat.Stat(gray).stddev[0])
    blurry = edge_variance < 180 or contrast < 18
    reasons = []
    if blurry:
        reasons.append("图片清晰度或对比度偏低")
    try:
        data = pytesseract.image_to_data(image, lang="chi_sim+eng", output_type=Output.DICT)
    except pytesseract.TesseractError:
        data = pytesseract.image_to_data(image, lang="eng", output_type=Output.DICT)
        reasons.append("中文 OCR 语言包不可用，已使用英文识别")
    tokens: list[str] = []
    scores: list[float] = []
    for text, conf in zip(data["text"], data["conf"]):
        clean = text.strip()
        try:
            score = float(conf)
        except (TypeError, ValueError):
            score = -1
        if clean:
            tokens.append(clean)
            if score >= 0:
                scores.append(score)
    confidence = round(sum(scores) / len(scores), 1) if scores else None
    if not tokens:
        reasons.append("未识别出有效文字")
    elif confidence is not None and confidence < 60:
        reasons.append(f"OCR 平均置信度较低（{confidence:.1f}）")
    return OCRResult("\n".join(tokens), confidence, blurry, reasons)

