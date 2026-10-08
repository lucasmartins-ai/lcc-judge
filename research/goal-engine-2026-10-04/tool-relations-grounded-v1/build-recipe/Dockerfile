FROM python@sha256:3dd7cc108ec1493442514f5c2a871af6af0ec31d768ff6e378a93340c3b3db5f
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY deps/ /opt/lcc-tool-deps/
COPY install-deps.py /opt/install-deps.py
RUN ["python", "/opt/install-deps.py"]
COPY tool_relation_worker.py tool_measurement_worker.py /usr/local/lib/python3.13/site-packages/research/
LABEL lcc.tool-relations.source-sha256="d90d831f2d25ddbcb9ac02166d6274f5166581734c7bfb3aacf547697ad65224" lcc.tool-relations.dependency-sha256="255600482631fdd1a04f299af2f0f1e748d783caafa896bdee322fce18f099bf"
USER 65534:65534
