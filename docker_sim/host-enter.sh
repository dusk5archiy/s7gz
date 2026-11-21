Main() {
  local ParentDir && ParentDir=$(dirname "${BASH_SOURCE[0]}")
  . "$ParentDir/host--env.sh"

  docker exec -it "$__HOST_SIM__CONTAINER_NAME" bash
}

Main
