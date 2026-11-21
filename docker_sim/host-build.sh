Main() {
  local ParentDir && ParentDir=$(dirname "${BASH_SOURCE[0]}")
  . "$ParentDir/host--env.sh"
  local BuildArgs=()
  for var in $(compgen -v | grep -E '^(__ARG__)'); do
    BuildArgs+=(--build-arg "$var=${!var}")
  done

  DOCKER_BUILDKIT=1 docker build -f "$__HOST_SIM__DOCKERFILE" -t "$__HOST_SIM__IMAGE_NAME" "${BuildArgs[@]}" .
}

Main
