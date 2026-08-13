"""สถิติที่ต้องรายงานคู่กับ P_E เสมอ"""

from __future__ import annotations


def p_error(y_true, y_score) -> float:
    """minimal total probability of error under equal priors
    ยิ่งใกล้ 0.5 ยิ่งดี (detector เดาสุ่ม)
    """
    raise NotImplementedError("PROJECT_STRUCTURE.md 4.11")


def bootstrap_ci(scores, n: int = 2000, alpha: float = 0.05):
    """ความต่างระหว่าง 0.47 กับ 0.49 อาจเป็นแค่ noise
    ถ้าไม่มี CI ตัวเลขนั้นตีความไม่ได้
    """
    raise NotImplementedError


def report(p_e: float, ci: tuple[float, float], n: int, seed: int, **meta) -> str:
    raise NotImplementedError
