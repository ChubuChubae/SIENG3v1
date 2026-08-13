# SIENG2 analyzer backend — packages binwalk/exiftool (Linux-only CLI tools the
# analyzer depends on) so the Windows GUI can run steganalysis via `docker run`
# instead of requiring these tools installed natively. See docker_bridge.py.
FROM python:3.12-slim-bookworm

# binwalk / libimage-exiftool-perl: external CLI tools analyzer/external_tools/* shells out to.
# libgl1 / libglib2.0-0: shared libs opencv-python (used by avi_handler.py) needs.
# ruby: runtime for the zsteg gem (installed below) - LSB extraction/enumeration for PNG & BMP.
# binutils: provides the GNU `strings` CLI (printable-text extraction from raw bytes).
RUN apt-get update && apt-get install -y --no-install-recommends \
    binwalk \
    libimage-exiftool-perl \
    libgl1 \
    libglib2.0-0 \
    ruby \
    file \
    binutils \
    p7zip-full \
    unzip \
    pngcheck \
    mediainfo \
    && rm -rf /var/lib/apt/lists/*

# zsteg: de-facto tool for detecting/extracting LSB steganography in PNG/BMP
# (pure-Ruby deps, no build toolchain needed).
RUN gem install zsteg --no-document

WORKDIR /app

COPY docker/requirements-analyzer.txt .
RUN pip install --no-cache-dir -r requirements-analyzer.txt

# เอาเฉพาะส่วนที่ analyzer ต้องใช้ ไม่ต้องลาก pipeline/crypto/ui เข้ามา
COPY src/sieng/__init__.py       src/sieng/__init__.py
COPY src/sieng/common/           src/sieng/common/
COPY src/sieng/analyzer/         src/sieng/analyzer/
COPY src/sieng/ui/__init__.py    src/sieng/ui/__init__.py
COPY src/sieng/ui/cli/           src/sieng/ui/cli/

ENV PYTHONPATH=/app/src

# รันเป็น non-root - input คือไฟล์ที่เราไม่ไว้ใจ
RUN useradd --uid 65532 --create-home --shell /usr/sbin/nologin analyzer
USER 65532

ENTRYPOINT ["python", "-m", "sieng.ui.cli.analyze"]
