#!/usr/bin/python3

import rospy
from particle_filter_node import ParticleFilterLocalisationNode

if __name__ == '__main__':
    rospy.init_node("particle_filter_localization")
    node = ParticleFilterLocalisationNode()
    rospy.spin()
