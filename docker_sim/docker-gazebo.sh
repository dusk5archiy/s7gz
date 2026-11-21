: "${__ARG__ROS_DISTRO:?}"

Main() {
  mkdir -p /etc/apt/keyrings
  curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key | gpg --dearmor -o /etc/apt/keyrings/ros-archive-keyring.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}") main" \
    >/etc/apt/sources.list.d/ros2.list

  apt-get update

  apt-get install -y --no-install-recommends \
    "ros-$__ARG__ROS_DISTRO-gz-sim-vendor"
}

Main
