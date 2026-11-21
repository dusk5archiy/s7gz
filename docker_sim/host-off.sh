Main() {
  local ParentDir && ParentDir=$(dirname "${BASH_SOURCE[0]}")
  . "$ParentDir/host--env.sh"

  docker rm -f "$__HOST_SIM__CONTAINER_NAME"
}

Main
