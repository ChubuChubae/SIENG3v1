# Fuzzing targets

รัน 60 วินาที/target ใน CI (`fuzz-smoke`) และ 1 ชม./target ตอน nightly

| target | สิ่งที่ป้อน |
|---|---|
| `fuzz_jpeg.py` | JPEG ที่ผิดรูป -> `JpegCarrier.load()` |
| `fuzz_header.py` | bit ที่ถอดมาจากภาพที่ไม่มีข้อมูล -> `Header.unpack()` |
| `fuzz_envelope.py` | `.sess` ที่ถูกดัดแปลง |
| `fuzz_stc.py` | cost/bits ที่ผิดรูป |
| `fuzz_pipeline.py` | YAML ที่เป็นอันตราย |
| `fuzz_state.py` | state file ที่เสียหาย |

เกณฑ์: ห้ามเกิด crash · hang · memory ระเบิด · secret รั่วออก error · state ผิด · output ผิด
crash ทุกตัวที่เจอต้องเก็บเข้า `corpus/` เป็น regression test ถาวร

## ข้อจำกัดที่รู้ตัว

ช่องโหว่ระดับ memory corruption ไม่ได้อยู่ในโค้ด Python แต่อยู่ใน
libjpeg-turbo ที่ `carrier/image/jpeg.py` เรียกผ่าน binding
atheris ทดสอบชั้น Python ได้ แต่จะไม่พบ heap overflow ในชั้น C
การครอบคลุมจริงต้องใช้ libFuzzer/AFL++ ที่ระดับ C (Phase 2)
