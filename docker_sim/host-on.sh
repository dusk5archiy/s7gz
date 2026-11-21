Main() {
  local ParentDir && ParentDir=$(dirname "${BASH_SOURCE[0]}")
  . "$ParentDir/host--env.sh"

  python -m src_host.sim_container_launchers
}

Main
