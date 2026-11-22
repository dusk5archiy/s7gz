. "docker_common/host--env.sh"

__SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

export __HOST_SIM__DOCKERFILE="$__SCRIPT_DIR/Dockerfile"

export __HOST_SIM__IMAGE_NAME=s7gz-sim
export __HOST_SIM__CONTAINER_NAME=s7gz-sim
export __HOST_SIM__USER_NAME="$__ARG__USER_NAME"
export __ARG__SIM_WS_DIR=/ws-s7gz
export __HOST_SIM__SIM_WS_DIR="$__ARG__SIM_WS_DIR"
