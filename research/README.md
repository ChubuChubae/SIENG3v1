# research/

กรอบการวัดผล - ตอบคำถามเดียว: "detector ปัจจุบันจับได้ไหม และจับได้แค่ไหน"

**กฎเหล็ก:** `torch` อยู่ที่นี่เท่านั้น ห้ามปรากฏใน `src/sieng/`
ถ้า GUI ต้อง import torch แปลว่ามีคนวางโค้ดผิดชั้น

## รายงานผลต้องครบสี่มิติ

| มิติ | config |
|---|---|
| payload 0.05 / 0.1 / 0.2 / 0.4 bpnzAC | `experiments/payload_sweep.yaml` |
| JPEG quality QF 50-95 | `experiments/quality_sweep.yaml` |
| cross-dataset BOSS <-> ALASKA | `experiments/cross_dataset.yaml` |
| cover-source mismatch | `experiments/cover_source_mismatch.yaml` |

## รูปแบบที่บังคับ - ห้ามเขียนแค่ P_E = 0.47

```
P_E = 0.47   95% CI [0.44, 0.50]   N = 5,000 pairs
detector = SRNet (seed 42, 3 runs)   dataset = BOSSbase QF75
payload = 0.10 bpnzAC   embedding = J-UNIWARD + STC(h=10)
commit = a1b2c3d   dataset_sha256 = ...
```

ถ้าไม่มี CI และ N ตัวเลขนั้นตีความไม่ได้
