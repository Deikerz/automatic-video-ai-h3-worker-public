FROM alpine:3.22.1

RUN apk add --no-cache ca-certificates coreutils curl

ENV H3_MODELS_ROOT=/runpod-volume/models \
    H3_DOWNLOAD_TIMEOUT_SECONDS=7200 \
    H3_DOWNLOAD_ROLE=all

COPY runpod_downloader/h3-models.sha256 /opt/h3-models.sha256
COPY runpod_downloader/download-models.sh /usr/local/bin/download-models.sh
COPY runpod_downloader/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/download-models.sh /usr/local/bin/entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
