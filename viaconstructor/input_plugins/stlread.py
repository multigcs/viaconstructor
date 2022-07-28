"""dxf reading."""

import argparse

import meshcut
import numpy as np
import stl
from OpenGL import GL

from ..calc import calc_distance  # pylint: disable=E0402


class StlReader:
    def __init__(self, filename: str, args: argparse.Namespace = None):
        """slicing and converting stl into single segments."""
        self.filename = filename
        self.segments: list[dict] = []

        meshdata = stl.mesh.Mesh.from_file(self.filename)
        self.verts_3d = meshdata.vectors.reshape(-1, 3)
        min_z = self.verts_3d[0][2]
        max_z = min_z
        for vert in self.verts_3d:
            value_z = vert[2]
            min_z = min(min_z, value_z)
            max_z = max(max_z, value_z)
        self.faces_3d = np.arange(len(self.verts_3d)).reshape(-1, 3)
        verts, faces = meshcut.merge_close_vertices(self.verts_3d, self.faces_3d)
        mesh = meshcut.TriangleMesh(verts, faces)
        self.diff_z = max_z - min_z

        print(f"STL: INFO: z_min={min_z}, z_max={max_z}")

        slice_z = None
        if args.zslice:  # type: ignore
            if args.zslice.endswith("%"):  # type: ignore
                percent = float(args.zslice[:-1])  # type: ignore
                slice_z = min_z + (self.diff_z * percent / 100.0)
            else:
                slice_z = float(args.zslice)  # type: ignore

        if slice_z is None:
            slice_z = min_z + (self.diff_z / 2.0)

        if slice_z > max_z:
            slice_z = max_z
        elif slice_z < min_z:
            slice_z = min_z

        print(f"STL: INFO: slicing stl at z={slice_z}")
        plane = meshcut.Plane((0, 0, slice_z), (0, 0, 1))
        objects = meshcut.cross_section_mesh(mesh, plane)

        for obj in objects:
            last_x = None
            last_y = None
            for point in obj:
                if last_x is not None:
                    self.add_line((last_x, last_y), (point[0], point[1]))
                last_x = point[0]
                last_y = point[1]

            self.add_line((last_x, last_y), (obj[0][0], obj[0][1]))

        self.min_max = [0.0, 0.0, 10.0, 10.0]
        for seg_idx, segment in enumerate(self.segments):
            for point in ("start", "end"):
                if seg_idx == 0:
                    self.min_max[0] = segment[point][0]
                    self.min_max[1] = segment[point][1]
                    self.min_max[2] = segment[point][0]
                    self.min_max[3] = segment[point][1]
                else:
                    self.min_max[0] = min(self.min_max[0], segment[point][0])
                    self.min_max[1] = min(self.min_max[1], segment[point][1])
                    self.min_max[2] = max(self.min_max[2], segment[point][0])
                    self.min_max[3] = max(self.min_max[3], segment[point][1])

        self.size = []
        self.size.append(self.min_max[2] - self.min_max[0])
        self.size.append(self.min_max[3] - self.min_max[1])

    def add_line(self, start, end, layer="0") -> None:
        dist = round(calc_distance(start, end), 6)
        if dist > 0.0:
            self.segments.append(
                {
                    "type": "LINE",
                    "object": None,
                    "layer": layer,
                    "start": start,
                    "end": end,
                    "bulge": 0.0,
                }
            )

    def get_segments(self) -> list[dict]:
        return self.segments

    def get_minmax(self) -> list[float]:
        return self.min_max

    def get_size(self) -> list[float]:
        return self.size

    def draw(self, draw_function, user_data=()) -> None:
        for segment in self.segments:
            draw_function(segment["start"], segment["end"], *user_data)

    def draw_3d(self):
        GL.glColor4f(1.0, 1.0, 1.0, 0.3)
        GL.glBegin(GL.GL_TRIANGLES)
        for face in self.faces_3d:
            coords = self.verts_3d[face[0]].tolist()
            GL.glVertex3f(coords[0], coords[1], coords[2] - self.diff_z)
            coords = self.verts_3d[face[1]].tolist()
            GL.glVertex3f(coords[0], coords[1], coords[2] - self.diff_z)
            coords = self.verts_3d[face[2]].tolist()
            GL.glVertex3f(coords[0], coords[1], coords[2] - self.diff_z)
        GL.glEnd()

    def save_tabs(self, tabs: list) -> None:
        pass

    @staticmethod
    def suffix() -> list[str]:
        return ["stl"]
