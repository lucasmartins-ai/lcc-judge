FROM python@sha256:3dd7cc108ec1493442514f5c2a871af6af0ec31d768ff6e378a93340c3b3db5f
COPY requirements.txt /opt/requirements.txt
RUN python -m pip install --no-cache-dir "https://download-r2.pytorch.org/whl/cpu/torch-2.12.0%2Bcpu-cp313-cp313-manylinux_2_28_aarch64.whl#sha256=68b7ddd4db4603a03e106e74c7098c8d8c8943d33c1e5ada009ca4cd885759c3"
RUN python -m pip install --no-cache-dir -r /opt/requirements.txt
COPY *.whl /opt/wheels/
RUN python -m pip install --no-deps /opt/wheels/*.whl
COPY hf /opt/hf
COPY checkpoint /opt/checkpoint
COPY model-manifest.json smoke.py /opt/
ENV HF_HOME=/opt/hf HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PYTHONDONTWRITEBYTECODE=1
USER 65534:65534
WORKDIR /tmp
ENTRYPOINT ["python", "/opt/smoke.py"]
