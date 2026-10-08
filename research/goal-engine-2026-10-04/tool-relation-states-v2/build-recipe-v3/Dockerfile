FROM python@sha256:3dd7cc108ec1493442514f5c2a871af6af0ec31d768ff6e378a93340c3b3db5f
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY deps/ /opt/lcc-tool-deps/
COPY install-deps.py /opt/install-deps.py
RUN ["python", "/opt/install-deps.py"]
COPY tool_relation_state_worker.py tool_relation_worker.py tool_measurement_worker.py /usr/local/lib/python3.13/site-packages/research/
LABEL lcc.tool-relation-states.source-sha256="5ded8f3bdf45d3e420c889d15e8dd38b2e95a631b2209eab0ab931f6638717a3" lcc.tool-relation-states.dependency-sha256="255600482631fdd1a04f299af2f0f1e748d783caafa896bdee322fce18f099bf"
USER 65534:65534
