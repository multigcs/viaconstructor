import tempfile

import ezdxf
import numpy
from PyQt5.QtCore import QLineF, QRect, Qt  # pylint: disable=E0611
from PyQt5.QtGui import QPainter, QPen, QPixmap  # pylint: disable=E0611
from PyQt5.QtWidgets import (  # pylint: disable=E0611
    QDoubleSpinBox,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from shapely.affinity import rotate, scale
from shapely.geometry import MultiPoint, Point, box
from shapely.ops import unary_union


def rot_matrix(x):
    c, s = numpy.cos(x), numpy.sin(x)
    return numpy.array([[c, -s], [s, c]])


def rotation(X, angle, center=None):
    if center is None:
        return numpy.dot(X, rot_matrix(angle))
    else:
        return numpy.dot(X - center, rot_matrix(angle)) + center


def deg2rad(x):
    return (numpy.pi / 180) * x


def generate(
    teeth_count=20,
    tooth_width=2.0,
    pressure_angle=0.1,
    backlash=0.0,
    frame_count=16,
):
    tooth_width -= backlash
    pitch_circumference = tooth_width * 2 * teeth_count
    pitch_radius = pitch_circumference / (2 * numpy.pi)
    addendum = tooth_width * (2 / numpy.pi)
    dedendum = addendum
    outer_radius = pitch_radius + addendum

    # Tooth profile
    profile = numpy.array(
        [
            [-(0.5 * tooth_width + addendum * numpy.tan(pressure_angle)), addendum],
            [-(0.5 * tooth_width - dedendum * numpy.tan(pressure_angle)), -dedendum],
            [(0.5 * tooth_width - dedendum * numpy.tan(pressure_angle)), -dedendum],
            [(0.5 * tooth_width + addendum * numpy.tan(pressure_angle)), addendum],
        ]
    )

    outer_circle = Point(0.0, 0.0).buffer(outer_radius)
    # print(outer_circle)

    poly_list = []
    prev_X = None
    ll = 2 * tooth_width / pitch_radius
    for theta in numpy.linspace(0, ll, frame_count):
        X = rotation(
            profile + numpy.array((-theta * pitch_radius, pitch_radius)), theta
        )
        if prev_X is not None:
            poly_list.append(
                MultiPoint([x for x in X] + [x for x in prev_X]).convex_hull
            )
        prev_X = X

    def circle_sector(angle, r):
        box_a = rotate(box(0.0, -2 * r, 2 * r, 2 * r), -angle / 2, Point(0.0, 0.0))
        box_b = rotate(box(-2 * r, -2 * r, 0, 2 * r), angle / 2, Point(0.0, 0.0))
        return Point(0.0, 0.0).buffer(r).difference(box_a.union(box_b))

    # Generate a tooth profile
    tooth_poly = unary_union(poly_list)
    tooth_poly = tooth_poly.union(scale(tooth_poly, -1, 1, 1, Point(0.0, 0.0)))

    # Generate the full gear
    gear_poly = Point(0.0, 0.0).buffer(outer_radius)
    for _i in range(0, teeth_count):
        gear_poly = rotate(
            gear_poly.difference(tooth_poly),
            (2 * numpy.pi) / teeth_count,
            Point(0.0, 0.0),
            use_radians=True,
        )

    # Job done
    return gear_poly, pitch_radius


class GearTool(QWidget):
    painter = None

    def __init__(self, app):
        super().__init__()
        self.setWindowTitle("Gear-Tool")
        self.app = app
        layout = QVBoxLayout()
        self.setLayout(layout)

        label = QLabel("Teeth")
        layout.addWidget(label)
        self.gear_teeth = QSpinBox()
        self.gear_teeth.setSingleStep(1)
        self.gear_teeth.setMinimum(3)
        self.gear_teeth.setMaximum(1000)
        self.gear_teeth.setValue(20)
        layout.addWidget(self.gear_teeth)

        label = QLabel("Width")
        layout.addWidget(label)
        self.gear_width = QDoubleSpinBox()
        self.gear_width.setDecimals(3)
        self.gear_width.setSingleStep(0.1)
        self.gear_width.setMinimum(-100000)
        self.gear_width.setMaximum(100000)
        self.gear_width.setValue(2.0)
        layout.addWidget(self.gear_width)

        label = QLabel("Angle")
        layout.addWidget(label)
        self.gear_angle = QDoubleSpinBox()
        self.gear_angle.setDecimals(2)
        self.gear_angle.setSingleStep(1.0)
        self.gear_angle.setMinimum(5)
        self.gear_angle.setMaximum(30)
        self.gear_angle.setValue(20.0)
        layout.addWidget(self.gear_angle)

        label = QLabel("Backlash")
        layout.addWidget(label)
        self.gear_backlash = QDoubleSpinBox()
        self.gear_backlash.setDecimals(2)
        self.gear_backlash.setSingleStep(0.1)
        self.gear_backlash.setMinimum(0.0)
        self.gear_backlash.setMaximum(100)
        self.gear_backlash.setValue(0.1)
        layout.addWidget(self.gear_backlash)

        label = QLabel("Hole")
        layout.addWidget(label)
        self.gear_hole = QDoubleSpinBox()
        self.gear_hole.setDecimals(2)
        self.gear_hole.setSingleStep(1.0)
        self.gear_hole.setMinimum(0.0)
        self.gear_hole.setMaximum(10000)
        self.gear_hole.setValue(4.0)
        layout.addWidget(self.gear_hole)

        self.qimage_label = QLabel()
        layout.addWidget(self.qimage_label)

        def open_gear():
            self.hide()
            teeth = self.gear_teeth.value()
            width = self.gear_width.value()
            angle = self.gear_angle.value()
            backlash = self.gear_backlash.value()
            hole = self.gear_hole.value()

            gpoly, pitch_radius = generate(
                teeth_count=teeth,
                tooth_width=width,
                pressure_angle=deg2rad(angle),
                backlash=backlash,
                frame_count=16,
            )

            temp_file = tempfile.NamedTemporaryFile(
                prefix=f"gear_{teeth}_{width}_{angle}_{backlash}_", suffix=".dxf"
            )
            temp_file.close()
            output_file = temp_file.name
            print(f"saving gear to tempfile: {output_file}")

            doc = ezdxf.new("R2010")
            msp = doc.modelspace()
            doc.units = ezdxf.units.MM

            points = gpoly.exterior.coords
            last = points[-1]
            for point in points:
                msp.add_line(
                    last,
                    point,
                    dxfattribs={"layer": "0"},
                )
                last = point

            circle = msp.add_circle((0, 0), radius=hole / 2, dxfattribs={"layer": "0"})

            for vport in doc.viewports.get_config("*Active"):  # type: ignore
                vport.dxf.grid_on = True
            if hasattr(ezdxf, "zoom"):
                ezdxf.zoom.extents(msp)  # type: ignore
            doc.saveas(output_file)

            if self.app.load_drawing(output_file, no_setup=True):
                pass

        self.gear_teeth.valueChanged.connect(self.preview)  # type: ignore
        self.gear_width.valueChanged.connect(self.preview)  # type: ignore
        self.gear_angle.valueChanged.connect(self.preview)  # type: ignore
        self.gear_backlash.valueChanged.connect(self.preview)  # type: ignore
        self.gear_hole.valueChanged.connect(self.preview)  # type: ignore

        self.button_open = QPushButton("Open")
        self.button_open.clicked.connect(open_gear)
        layout.addWidget(self.button_open)

        self.button_close = QPushButton("Cancel")
        self.button_close.clicked.connect(self.close)
        layout.addWidget(self.button_close)

        self.preview()

    def preview(self, value=0):  # pylint: disable=W0613
        scale = 10
        teeth = self.gear_teeth.value()
        width = self.gear_width.value()
        angle = self.gear_angle.value()
        backlash = self.gear_backlash.value()
        hole = self.gear_hole.value()

        gpoly, pitch_radius = generate(
            teeth_count=teeth,
            tooth_width=width,
            pressure_angle=deg2rad(angle),
            backlash=backlash,
            frame_count=16,
        )

        canvas_w = 400
        canvas_h = 400
        off_x = canvas_w / 2
        off_y = canvas_h / 2

        canvas = QPixmap(canvas_w, canvas_h)
        self.qimage_label.setPixmap(canvas)
        self.qimage_label.adjustSize()
        self.qimage_label.pixmap().fill(Qt.white)
        self.painter = QPainter()
        self.painter.begin(self.qimage_label.pixmap())
        self.painter.setPen(QPen(Qt.black, 1, Qt.SolidLine))

        points = gpoly.exterior.coords
        last = points[-1]
        for point in points:
            self.painter.drawLine(
                QLineF(
                    last[0] * scale + off_x,
                    last[1] * scale + off_y,
                    point[0] * scale + off_x,
                    point[1] * scale + off_y,
                )
            )
            last = point

        square = QRect(
            off_x - hole / 2 * scale,
            off_y - hole / 2 * scale,
            hole * scale,
            hole * scale,
        )
        self.painter.drawEllipse(square)

        self.painter.end()
