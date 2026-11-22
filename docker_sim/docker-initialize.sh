: "${__ARG__USER_NAME:?}"

Main() {
  # Docker related
  rm -f /etc/apt/apt.conf.d/docker-clean

  apt-get update

  # Install basic packages
  apt-get install -y --no-install-recommends \
    ca-certificates curl gpg git tzdata locales sudo

  # Install Python
  apt-get install -y --no-install-recommends \
    python3 python-is-python3 python3-pip python3-venv python3-dev python3-yaml

  # Install C++ and C-Python bindings
  apt-get install -y --no-install-recommends \
    cmake ninja-build g++ make pybind11-dev

  # Remove the old user
  local OldUser && OldUser=$(getent passwd 1000 | cut -d: -f1 || true)
  if [ -n "$OldUser" ]; then userdel -r "$OldUser"; fi

  # Create a new user
  useradd -m -s /bin/bash -u 1000 "$__ARG__USER_NAME"
  echo "$__ARG__USER_NAME ALL=(ALL) NOPASSWD:ALL" >"/etc/sudoers.d/$__ARG__USER_NAME"
}

Main
