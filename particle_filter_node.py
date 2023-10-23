#!/usr/bin/python3

import rospy
from geometry_msgs.msg import PoseStamped, PoseWithCovarianceStamped, PoseArray, Quaternion
from tf.msg import tfMessage
from sensor_msgs.msg import LaserScan
from nav_msgs.msg import OccupancyGrid, Odometry
import pf_localisation
from threading import Lock
import sys
from copy import deepcopy

class ParticleFilterLocalisationNode(object):
    def __init__(self):
        # Initialize your parameters and variables here
        self._PUBLISH_DELTA = rospy.get_param("publish_delta", 0.1)  # Minimum change (m/radians) before publishing new particle cloud and pose

        self._particle_filter = pf_localisation.PFLocaliser()

        self._latest_scan = None
        self._last_published_pose = None
        self._initial_pose_received = False

        # Initialize ROS publishers and subscribers
        self._pose_publisher = rospy.Publisher("/estimatedpose", PoseStamped)
        self._amcl_pose_publisher = rospy.Publisher("/amcl_pose", PoseWithCovarianceStamped)
        self._cloud_publisher = rospy.Publisher("/particlecloud", PoseArray)
        self._tf_publisher = rospy.Publisher("/tf", tfMessage)

        # Wait for a map
        rospy.loginfo("Waiting for a map...")
        try:
            occupancy_map = rospy.wait_for_message("/map", OccupancyGrid, 20)
        except:
            rospy.logerr("Problem getting a map. Check that you have a map_server "
                         "running: rosrun map_server map_server <mapname>")
            sys.exit(1)
        rospy.loginfo("Map received. %d X %d, %f px/m." %
                      (occupancy_map.info.width, occupancy_map.info.height,
                       occupancy_map.info.resolution))
        self._particle_filter.set_map(occupancy_map)

        # Set up ROS subscribers
        self._laser_subscriber = rospy.Subscriber("/base_scan", LaserScan, self._laser_callback, queue_size=1)
        self._initial_pose_subscriber = rospy.Subscriber("/initialpose", PoseWithCovarianceStamped, self._initial_pose_callback)
        self._odometry_subscriber = rospy.Subscriber("/odom", Odometry, self._odometry_callback, queue_size=1)

    def _initial_pose_callback(self, pose):
        # Called when RViz sends a user-supplied initial pose estimate
        self._particle_filter.set_initial_pose(pose)
        self._last_published_pose = deepcopy(self._particle_filter.estimatedpose)
        self._initial_pose_received = True
        self._cloud_publisher.publish(self._particle_filter.particlecloud)

    def _odometry_callback(self, odometry):
        # Odometry received. If the filter is initialized, execute a filter predict step with odometry
        if self._initial_pose_received:
            t_odom = self._particle_filter.predict_from_odometry(odometry)

            t_filter = self._particle_filter.update_filter(self._latest_scan)
            if t_odom + t_filter > 0.1:
                rospy.logwarn("Filter cycle overran timeslot")
                rospy.loginfo("Odometry update: %fs" % t_odom)
                rospy.loginfo("Particle update: %fs" % t_filter)

    def _laser_callback(self, scan):
        # Laser received. Store a reference to the latest scan. If the robot has moved much, republish the latest pose to update RViz
        self._latest_scan = scan
        if self._initial_pose_received:
            if self._sufficientMovementDetected(self._particle_filter.estimatedpose):
                # Publish the new pose
                self._amcl_pose_publisher.publish(self._particle_filter.estimatedpose)
                self._publish_estimated_pose()

                # Update record of previously-published pose
                self._last_published_pose = deepcopy(self._particle_filter.estimatedpose)

                # Get updated particle cloud and publish it
                self._cloud_publisher.publish(self._particle_filter.particlecloud)

                # Get updated transform and publish it
                self._tf_publisher.publish(self._particle_filter.tf_message)

    def _sufficientMovementDetected(self, latest_pose):
        # Compare the last published pose to the current pose. Return true if movement is more than self._PUBLISH_DELTA
        latest_x = latest_pose.pose.pose.position.x
        latest_y = latest_pose.pose.pose.position.y
        prev_x = self._last_published_pose.pose.pose.position.x
        prev_y = self._last_published_pose.pose.pose.position.y
        location_delta = abs(latest_x - prev_x) + abs(latest_y - prev_y)

        latest_rot = latest_pose.pose.pose.orientation
        prev_rot = self._last_published_pose.pose.pose.orientation

        q = rotateQuaternion(Quaternion(w=1.0), getHeading(latest_rot))   # Rotate forward
        q = rotateQuaternion(q, -getHeading(prev_rot))  # Rotate backward
        heading_delta = abs(getHeading(q))

        return location_delta > self._PUBLISH_DELTA or heading_delta > self._PUBLISH_DELTA

    def _publish_estimated_pose(self):
        # Publish the estimated pose
        pose_msg = PoseStamped()
        pose_msg.pose = self._particle_filter.estimatedpose.pose.pose
        pose_msg.header.stamp = rospy.Time.now()
        pose_msg.header.frame_id = "map"
        self._pose_publisher.publish(pose_msg)

if __name__ == '__main__':
    rospy.init_node("pf_localisation")
    node = ParticleFilterLocalisationNode()
    rospy.spin()
