ARG BUILD_FROM=ghcr.io/dcnoren/mission-control:latest
FROM ${BUILD_FROM}

ARG BUILD_ARCH
ARG BUILD_VERSION

LABEL \
  io.hass.type="addon" \
  io.hass.version="${BUILD_VERSION}" \
  io.hass.arch="${BUILD_ARCH}"

COPY run.sh /run.sh
RUN chmod a+x /run.sh

CMD ["/run.sh"]