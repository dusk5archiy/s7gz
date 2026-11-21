Main() {
  local ParentDir && ParentDir=$(dirname "${BASH_SOURCE[0]}")
  . "$ParentDir/host--env.sh"

  docker logs -f "$__HOST_SIM__CONTAINER_NAME"
}

Main
