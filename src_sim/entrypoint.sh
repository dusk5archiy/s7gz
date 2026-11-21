set -e

: "${__ARG__ROS_DISTRO:?}"

Main() {
  local GzSetupBash="/opt/ros/${__ARG__ROS_DISTRO}/setup.bash"

  if [ -f "$GzSetupBash" ]; then
    # shellcheck source=/dev/null
    . "$GzSetupBash"
  else
    echo "[-- error --] Gazebo setup at $GzSetupBash does not exist" >&2
    exit 1
  fi

  export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-xcb}"
  export QT_X11_NO_MITSHM="${QT_X11_NO_MITSHM:-1}"

  local NvidiaVendorJson
  for NvidiaVendorJson in \
    /usr/share/glvnd/egl_vendor.d/10_nvidia.json \
    /etc/glvnd/egl_vendor.d/10_nvidia.json; do
    if [ -f "$NvidiaVendorJson" ]; then
      export __EGL_VENDOR_LIBRARY_FILENAMES="${__EGL_VENDOR_LIBRARY_FILENAMES:-$NvidiaVendorJson}"
      export __NV_PRIME_RENDER_OFFLOAD="${__NV_PRIME_RENDER_OFFLOAD:-1}"
      export __GLX_VENDOR_LIBRARY_NAME="${__GLX_VENDOR_LIBRARY_NAME:-nvidia}"
      break
    fi
  done

  exec python -m src_sim.stage_run "$@"
}

Main "$@"
