"""
Class to render a set of images for a graspable objects
Author: Jeff Mahler
"""
import copy
import logging
import numpy as np
import os
import sys
import time

import meshrender
from alan.rgbd import CameraIntrinsics, BinaryImage, ColorImage, DepthImage, ObjectRender, RenderMode
from alan.core import RigidTransform

class ViewsphereDiscretizer(object):
    """Set of parameters for automatically rendering a set of images from virtual
    cameras placed around a viewing sphere.

    The view sphere indicates camera poses relative to the object.

    Attributes
    ----------
    min_radius : float
        Minimum radius for viewing sphere.
    max_radius : float
        Maximum radius for viewing sphere.
    num_radii  : int
        Number of radii between min_radius and max_radius.
    min_elev : float
        Minimum elevation (angle from z-axis) for camera position.
    max_elev : float
        Maximum elevation for camera position.
    num_elev  : int
        Number of discrete elevations.
    min_az : float
        Minimum azimuth (angle from x-axis) for camera position.
    max_az : float
        Maximum azimuth for camera position.
    num_az  : int
        Number of discrete azimuth locations.
    min_roll : float
        Minimum roll (rotation of camera about axis generated by azimuth and
        elevation) for camera.
    max_roll : float
        Maximum roll for camera.
    num_roll  : int
        Number of discrete rolls.
    """

    def __init__(self, min_radius, max_radius, num_radii,
                 min_elev, max_elev, num_elev,
                 min_az=0, max_az=2*np.pi, num_az=1,
                 min_roll=0, max_roll=2*np.pi, num_roll=1):
        """Initialize a ViewsphereDiscretizer.

        Parameters
        ----------
        min_radius : float
            Minimum radius for viewing sphere.
        max_radius : float
            Maximum radius for viewing sphere.
        num_radii  : int
            Number of radii between min_radius and max_radius.
        min_elev : float
            Minimum elevation (angle from z-axis) for camera position.
        max_elev : float
            Maximum elevation for camera position.
        num_elev  : int
            Number of discrete elevations.
        min_az : float
            Minimum azimuth (angle from x-axis) for camera position.
        max_az : float
            Maximum azimuth for camera position.
        num_az  : int
            Number of discrete azimuth locations.
        min_roll : float
            Minimum roll (rotation of camera about axis generated by azimuth and
            elevation) for camera.
        max_roll : float
            Maximum roll for camera.
        num_roll  : int
            Number of discrete rolls.
        """
        if num_radii < 1 or num_az < 1 or num_elev < 1:
            raise ValueError('Discretization must be at least one in each dimension')
        self.min_radius = min_radius
        self.max_radius = max_radius
        self.num_radii = num_radii
        self.min_az = min_az
        self.max_az = max_az
        self.num_az = num_az
        self.min_elev = min_elev
        self.max_elev = max_elev
        self.num_elev = num_elev
        self.min_roll = min_roll
        self.max_roll = max_roll
        self.num_roll = num_roll

    def object_to_camera_poses(self):
        """Turn the params into a set of object to camera transformations.

        Returns
        -------
        :obj:`list` of :obj:`RigidTransform`
            A list of rigid transformations that transform from object space
            to camera space.
        """
        # compute increments in radial coordinates
        if self.max_radius == self.min_radius:
            radius_inc = 1
        elif self.num_radii == 1:
            radius_inc = self.max_radius - self.min_radius + 1
        else:
            radius_inc = (self.max_radius - self.min_radius) / (self.num_radii - 1)
        az_inc = (self.max_az - self.min_az) / self.num_az
        if self.max_elev == self.min_elev:
            elev_inc = 1
        elif self.num_elev == 1:
            elev_inc = self.max_elev - self.min_elev + 1
        else:
            elev_inc = (self.max_elev - self.min_elev) / (self.num_elev - 1)
        roll_inc = (self.max_roll - self.min_roll) / self.num_roll

        # create a pose for each set of spherical coords
        object_to_camera_poses = []
        radius = self.min_radius
        while radius <= self.max_radius:
            elev = self.min_elev
            while elev <= self.max_elev:
                az = self.min_az
                while az < self.max_az: #not inclusive due to topology (simplifies things)
                    roll = self.min_roll
                    while roll < self.max_roll:

                        # generate camera center from spherical coords
                        camera_center_obj = np.array([ViewsphereDiscretizer.sph2cart(radius, az, elev)]).squeeze()
                        camera_z_obj = -camera_center_obj / np.linalg.norm(camera_center_obj)

                        # find the canonical camera x and y axes
                        camera_x_par_obj = np.array([camera_z_obj[1], -camera_z_obj[0], 0])
                        if np.linalg.norm(camera_x_par_obj) == 0:
                            camera_x_par_obj = np.array([1, 0, 0])
                        camera_x_par_obj = camera_x_par_obj / np.linalg.norm(camera_x_par_obj)
                        camera_y_par_obj = np.cross(camera_z_obj, camera_x_par_obj)
                        camera_y_par_obj = camera_y_par_obj / np.linalg.norm(camera_y_par_obj)
                        if camera_y_par_obj[2] > 0:
                            camera_x_par_obj = -camera_x_par_obj
                            camera_y_par_obj = np.cross(camera_z_obj, camera_x_par_obj)
                            camera_y_par_obj = camera_y_par_obj / np.linalg.norm(camera_y_par_obj)

                        # rotate by the roll
                        R_obj_camera_par = np.c_[camera_x_par_obj, camera_y_par_obj, camera_z_obj]
                        R_camera_par_camera = np.array([[np.cos(roll), -np.sin(roll), 0],
                                                        [np.sin(roll), np.cos(roll), 0],
                                                        [0, 0, 1]])
                        R_obj_camera = R_obj_camera_par.dot(R_camera_par_camera)
                        t_obj_camera = camera_center_obj

                        # create final transform
                        T_obj_camera = RigidTransform(R_obj_camera, t_obj_camera,
                                                      from_frame='camera', to_frame='obj')
                        object_to_camera_poses.append(T_obj_camera.inverse())
                        roll += roll_inc
                    az += az_inc
                elev += elev_inc
            radius += radius_inc
        return object_to_camera_poses

    @staticmethod
    def sph2cart(r, az, elev):
        x = r * np.cos(az) * np.sin(elev)
        y = r * np.sin(az) * np.sin(elev)
        z = r * np.cos(elev)
        return x, y, z

    @staticmethod
    def cart2sph(x, y, z):
        r = np.sqrt(x**2 + y**2 + z**2)
        if x > 0 and y > 0:
            az = np.arctan(y / x)
        elif x > 0 and y < 0:
            az = 2*np.pi - np.arctan(-y / x)
        elif x < 0 and y > 0:
            az = np.pi - np.arctan(-y / x)    
        elif x < 0 and y < 0:
            az = np.pi + np.arctan(y / x)    
        elif x == 0 and y > 0:
            az = np.pi / 2
        elif x == 0 and y < 0:
            az = 3 * np.pi / 2
        elif y == 0 and x > 0:
            az = 0
        elif y == 0 and x < 0:
            az = np.pi
        elev = np.arccos(z / r)
        return r, az, elev

class VirtualCamera(object):
    """A virtualized camera for rendering virtual color and depth images of meshes.

    Rendering is performed by using OSMesa offscreen rendering and boost_numpy.
    """
    def __init__(self, camera_intr):
        """Initialize a virtual camera.

        Parameters
        ----------
        camera_intr : :obj:`CameraIntrinsics`
            The CameraIntrinsics object used to parametrize the virtual camera.

        Raises
        ------
        ValueError
            When camera_intr is not a CameraIntrinsics object.
        """
        if not isinstance(camera_intr, CameraIntrinsics):
            raise ValueError('Must provide camera intrinsics as a CameraIntrinsics object')
        self._camera_intr = camera_intr

    def images(self, mesh, object_to_camera_poses, debug=False):
        """Render images of the given mesh at the list of object to camera poses.

        Parameters
        ----------
        mesh : :obj:`Mesh3D`
            The mesh to be rendered.

        object_to_camera_poses : :obj:`list` of :obj:`RigidTransform`
            A list of object to camera transforms to render from.

        debug : bool
            Whether or not to debug the C++ meshrendering code.

        Returns
        -------
        :obj:`tuple` of `numpy.ndarray`
            A 2-tuple of ndarrays. The first, which represents the color image,
            contains ints (0 to 255) and is of shape (height, width, 3). 
            Each pixel is a 3-ndarray (red, green, blue) associated with a given
            y and x value. The second, which represents the depth image,
            contains floats and is of shape (height, width). Each pixel is a
            single float that represents the depth of the image.
        """
        # get mesh spec as numpy arrays
        vertex_arr = np.array(mesh.vertices)
        tri_arr = np.array(mesh.triangles).astype(np.uint32)

        # generate set of projection matrices
        projections = []
        for T_camera_obj in object_to_camera_poses:
            R = T_camera_obj.rotation
            t = T_camera_obj.translation
            P = self._camera_intr.proj_matrix.dot(np.c_[R, t])
            projections.append(P)

        # render images for each
        render_start = time.time()
        binary_ims, depth_ims = meshrender.render_mesh(projections,
                                                      self._camera_intr.height,
                                                      self._camera_intr.width,
                                                      vertex_arr,
                                                      tri_arr,
                                                      debug)
        render_stop = time.time()
        logging.debug('Rendering took %.3f sec' %(render_stop - render_start))

        return binary_ims, depth_ims

    def images_viewsphere(self, mesh, vs_disc):
        """Render images of the given mesh around a view sphere.

        Parameters
        ----------
        mesh : :obj:`Mesh3D`
            The mesh to be rendered.

        vs_disc : :obj:`ViewsphereDiscretizer`
            A discrete viewsphere from which we draw object to camera
            transforms.

        Returns
        -------
        :obj:`tuple` of `numpy.ndarray`
            A 2-tuple of ndarrays. The first, which represents the color image,
            contains ints (0 to 255) and is of shape (height, width, 3). 
            Each pixel is a 3-ndarray (red, green, blue) associated with a given
            y and x value. The second, which represents the depth image,
            contains floats and is of shape (height, width). Each pixel is a
            single float that represents the depth of the image.
        """
        return self.images(mesh, vs_disc.object_to_camera_poses())

    def wrapped_images(self, mesh, object_to_camera_poses,
                       render_mode, stable_pose=None, debug=False):
        """Create ObjectRender objects of the given mesh at the list of object to camera poses.

        Parameters
        ----------
        mesh : :obj:`Mesh3D`
            The mesh to be rendered.

        object_to_camera_poses : :obj:`list` of :obj:`RigidTransform`
            A list of object to camera transforms to render from.

        render_mode : int
            One of RenderMode.COLOR, RenderMode.DEPTH, or
            RenderMode.SCALED_DEPTH.

        stable_pose : :obj:`StablePose`
            A stable pose to render the object in.

        debug : bool
            Whether or not to debug the C++ meshrendering code.

        Returns
        -------
        :obj:`list` of :obj:`ObjectRender`
            A list of ObjectRender objects generated from the given parameters.
        """
        # pre-multiply the stable pose
        if stable_pose is not None:
            T_obj_stp = RigidTransform(rotation=stable_pose.r,
                                        translation=np.zeros(3),
                                        from_frame='obj',
                                        to_frame='stp')
            stp_to_camera_poses = copy.copy(object_to_camera_poses)
            object_to_camera_poses = []
            for T_stp_camera in stp_to_camera_poses:
                T_stp_camera.from_frame = 'stp'
                object_to_camera_poses.append(T_stp_camera.dot(T_obj_stp))

        # render both image types (doesn't really cost any time)
        binary_ims, depth_ims = self.images(mesh, object_to_camera_poses)

        # convert to image wrapper classes
        images = []
        if render_mode == RenderMode.SEGMASK:
            for binary_im in binary_ims:
                images.append(BinaryImage(binary_im[:,:,0], frame=self._camera_intr.frame))
        elif render_mode == RenderMode.DEPTH:
            for depth_im in depth_ims:
                images.append(DepthImage(depth_im, frame=self._camera_intr.frame))
        elif render_mode == RenderMode.SCALED_DEPTH:
            for depth_im in depth_ims:
                d = DepthImage(depth_im, frame='camera')
                images.append(d.to_color())
        else:
            logging.warning('Render mode %s not supported. Returning None' %(render_mode))
            return None

        # create rendered images
        if stable_pose is not None:
            object_to_camera_poses = copy.copy(stp_to_camera_poses)
        rendered_images = []
        for image, T_obj_camera in zip(images, object_to_camera_poses):
            T_camera_obj = T_obj_camera.inverse()
            rendered_images.append(ObjectRender(image, T_camera_obj))
        return rendered_images

    def wrapped_images_viewsphere(self, mesh, vs_disc, render_mode, stable_pose=None):
        """ Create ObjectRender objects of the given mesh around a viewsphere.
        Parameters
        ----------
        mesh : :obj:`Mesh3D`
            The mesh to be rendered.

        vs_disc : :obj:`ViewsphereDiscretizer`
            A discrete viewsphere from which we draw object to camera
            transforms.

        render_mode : int
            One of RenderMode.COLOR, RenderMode.DEPTH, or
            RenderMode.SCALED_DEPTH.

        stable_pose : :obj:`StablePose`
            A stable pose to render the object in.

        Returns
        -------
        :obj:`list` of :obj:`ObjectRender`
            A list of ObjectRender objects generated from the given parameters.
        """
        return self.wrapped_images(mesh, vs_disc.object_to_camera_poses(), render_mode, stable_pose=stable_pose)

