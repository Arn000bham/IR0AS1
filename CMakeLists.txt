cmake_minimum_required(VERSION 3.0.2)
project(particle_filter_localization)

find_package(catkin REQUIRED COMPONENTS
  roscpp
  rospy
  std_msgs
  geometry_msgs
  sensor_msgs
  tf
  nav_msgs
  message_generation
)

catkin_package()

include_directories(
  ${catkin_INCLUDE_DIRS}
)

install(PROGRAMS
  src/pf_localization_node.py
  DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION}
)
