"""stl reading."""

import argparse

import numpy as np
from OpenGL import GL

from ..ext import stl
from ..ext.meshcut import meshcut
from ..input_plugins_base import DrawReaderBase


def load_ply(fileobj):
    """Same as load_ply, but takes a file-like object"""

    def nextline():
        """Read next line, skip comments"""
        while True:
            line = fileobj.readline()
            assert line != ""  # eof
            if not line.startswith("comment"):
                return line.strip()

    assert nextline() == "ply"
    assert nextline() == "format ascii 1.0"
    line = nextline()
    assert line.startswith("element vertex")
    nverts = int(line.split()[2])
    # print "nverts : ", nverts
    assert nextline() == "property float x"
    assert nextline() == "property float y"
    assert nextline() == "property float z"
    line = nextline()

    assert line.startswith("element face")
    nfaces = int(line.split()[2])
    # print "nfaces : ", nfaces
    assert nextline() == "property list uchar int vertex_indices"
    line = nextline()
    has_texcoords = line == "property list uchar float texcoord"
    if has_texcoords:
        assert nextline() == "end_header"
    else:
        assert line == "end_header"

    # Verts
    verts = np.zeros((nverts, 3))
    for i in range(nverts):
        vals = nextline().split()
        verts[i, :] = [float(v) for v in vals[:3]]
    # Faces
    faces = []
    faces_uv = []
    for _i in range(nfaces):
        vals = nextline().split()
        assert int(vals[0]) == 3
        faces.append([int(v) for v in vals[1:4]])
        if has_texcoords:
            assert len(vals) == 11
            assert int(vals[4]) == 6
            faces_uv.append(
                [
                    (float(vals[5]), float(vals[6])),
                    (float(vals[7]), float(vals[8])),
                    (float(vals[9]), float(vals[10])),
                ]
            )
            # faces_uv.append([float(v) for v in vals[5:]])
        else:
            assert len(vals) == 4
    return verts, faces, faces_uv


class DrawReader(DrawReaderBase):
    @staticmethod
    def arg_parser(parser) -> None:
        parser.add_argument(
            "--stlread-zslice",
            help="stlread: slice at postion z (stl)",
            type=str,
            default=None,
        )

    @staticmethod
    def preload_setup(filename: str, args: argparse.Namespace):  # pylint: disable=W0613
        from PyQt5.QtWidgets import (  # pylint: disable=E0611,C0415
            QDialog,
            QDialogButtonBox,
            QDoubleSpinBox,
            QLabel,
            QVBoxLayout,
        )

        dialog = QDialog()
        dialog.setWindowTitle("STL-Reader")

        dialog.buttonBox = QDialogButtonBox(QDialogButtonBox.Ok)
        dialog.buttonBox.accepted.connect(dialog.accept)

        dialog.layout = QVBoxLayout()
        message = QLabel("Import-Options")
        dialog.layout.addWidget(message)

        label = QLabel("Height")
        dialog.layout.addWidget(label)
        stlread_zslice = QDoubleSpinBox()
        stlread_zslice.setDecimals(4)
        stlread_zslice.setSingleStep(0.1)
        stlread_zslice.setMinimum(0.0)
        stlread_zslice.setMaximum(1.0)
        stlread_zslice.setValue(0.5)
        dialog.layout.addWidget(stlread_zslice)

        dialog.layout.addWidget(dialog.buttonBox)
        dialog.setLayout(dialog.layout)

        if dialog.exec():
            args.stlread_zslice = str(stlread_zslice.value())

    def __init__(self, filename: str, args: argparse.Namespace = None):
        """slicing and converting stl into single segments."""
        self.filename = filename
        self.segments: list[dict] = []
        if self.filename.lower().endswith(".stl"):
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
        elif self.filename.lower().endswith(".ply"):
            with open(self.filename) as file_d:
                verts, faces, _ = load_ply(file_d)
                self.faces_3d = faces
                self.verts_3d = verts
                min_z = self.verts_3d[0][2]
                max_z = min_z
                for vert in self.verts_3d:
                    value_z = vert[2]
                    min_z = min(min_z, value_z)
                    max_z = max(max_z, value_z)

        """
        zlayers = {}
        for vert in verts:
            #print(vert[2])
            if vert[2] not in zlayers:
                zlayers[vert[2]] = 0
            zlayers[vert[2]] += 1

        for h, n in zlayers.items():
            if n > 2:
                print("### ", h, n)
        """

        mesh = meshcut.TriangleMesh(verts, faces)
        self.diff_z = max_z - min_z

        print(f"STL: INFO: z_min={min_z}, z_max={max_z}")

        slice_z = None
        if args.stlread_zslice:  # type: ignore
            if args.stlread_zslice.endswith("%"):  # type: ignore
                percent = float(args.stlread_zslice[:-1])  # type: ignore
                slice_z = min_z + (self.diff_z * percent / 100.0)
            else:
                slice_z = float(args.stlread_zslice)  # type: ignore

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
                    self._add_line((last_x, last_y), (point[0], point[1]))
                last_x = point[0]
                last_y = point[1]

            self._add_line((last_x, last_y), (obj[0][0], obj[0][1]))

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

    @staticmethod
    def suffix(args: argparse.Namespace = None) -> list[str]:  # pylint: disable=W0613
        return ["stl", "ply"]
