"""
A basic struct-like Stable Pose class to make accessing pose probability and rotation matrix easier

Author: Matt Matl and Nikhil Sharma
"""
import numpy as np

from alan.core import RigidTransform

class StablePose(object):
    """A representation of a mesh's stable pose.

    Attributes
    ----------
    p : float
        Probability associated with this stable pose.
    r : :obj:`numpy.ndarray` of :obj`numpy.ndarray` of float
        3x3 rotation matrix that rotates the mesh into the stable pose from
        standardized coordinates.
    x0 : :obj:`numpy.ndarray` of float
        3D point in the mesh that is resting on the table.
    stp_id : :obj:`str`
        A string identifier for the stable pose
    T_obj_table : :obj:`RigidTransform`
        A RigidTransform representation of the pose's rotation matrix.
    """
    def __init__(self, p, r, x0, stp_id=-1):
        """Create a new stable pose object.

        Parameters
        ----------
        p : float
            Probability associated with this stable pose.
        r : :obj:`numpy.ndarray` of :obj`numpy.ndarray` of float
            3x3 rotation matrix that rotates the mesh into the stable pose from
            standardized coordinates.
        x0 : :obj:`numpy.ndarray` of float
            3D point in the mesh that is resting on the table.
        stp_id : :obj:`str`
            A string identifier for the stable pose
        """
        self.p = p
        self.r = r
        self.x0 = x0
        self.id = stp_id

        # fix stable pose bug
        if np.abs(np.linalg.det(self.r) + 1) < 0.01:
            self.r[1,:] = -self.r[1,:]

    @property
    def T_obj_table(self):
        R_obj_stp = self.r
        return RigidTransform(rotation=self.r, from_frame='obj', to_frame='table')
