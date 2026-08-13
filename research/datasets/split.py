"""แบ่ง train/test แบบ paired

★ กับดักที่ทำให้ผลการทดลองผิดบ่อยที่สุด:
  ถ้า cover ของภาพ X อยู่ใน train แต่ stego ของภาพ X อยู่ใน test
  detector จะเรียนรู้ "ภาพนี้หน้าตายังไง" แทนที่จะเรียนรู้ "ร่องรอยการฝัง"
  ทำให้ตัวเลขดูดีเกินจริงมาก
"""

from __future__ import annotations

from pathlib import Path


def paired_split(paths: list[Path], ratio: float,
                 seed: int) -> tuple[list[Path], list[Path]]:
    """cover/stego ของภาพเดียวกันต้องอยู่ฝั่งเดียวกันเสมอ"""
    raise NotImplementedError("PROJECT_STRUCTURE.md 4.11")
