# syntax=docker/dockerfile:1.7
FROM ubuntu:26.04 AS stage__ubuntu

ENV DEBIAN_FRONTEND=noninteractive
SHELL ["/bin/bash", "-c"]
LABEL container.role=sim

ARG __ARG__USER_NAME

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
  --mount=type=cache,target=/var/lib/apt/lists,sharing=locked  \
  --mount=type=bind,source=docker_sim/docker-initialize.sh,target=/script.sh bash /script.sh

FROM stage__ubuntu AS stage__gazebo

ARG __ARG__ROS_DISTRO

ENV __ARG__ROS_DISTRO=${__ARG__ROS_DISTRO}

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
  --mount=type=cache,target=/var/lib/apt/lists,sharing=locked \
  --mount=type=bind,source=docker_sim/docker-gazebo.sh,target=/script.sh bash /script.sh

FROM stage__gazebo AS stage__runtime
USER 0:0

ARG __ARG__USER_NAME
ARG __ARG__SIM_WS_DIR

WORKDIR ${__ARG__SIM_WS_DIR}
COPY --chown=${__ARG__USER_NAME}:${__ARG__USER_NAME} requirements.txt requirements.txt
RUN pip install --no-cache-dir --break-system-packages -r requirements.txt
COPY --chown=${__ARG__USER_NAME}:${__ARG__USER_NAME} lib lib
COPY --chown=${__ARG__USER_NAME}:${__ARG__USER_NAME} src_common src_common
COPY --chown=${__ARG__USER_NAME}:${__ARG__USER_NAME} src_sim src_sim
RUN mkdir -p "${__ARG__SIM_WS_DIR}/runtime" && chown -R "${__ARG__USER_NAME}:${__ARG__USER_NAME}" "${__ARG__SIM_WS_DIR}"

COPY --chmod=0644 src_sim/entrypoint.sh /usr/local/bin/entrypoint.sh
USER ${__ARG__USER_NAME}
ENTRYPOINT ["bash", "entrypoint.sh"]
