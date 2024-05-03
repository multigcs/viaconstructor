import gettext
import math
import os
import sys
import tempfile
from pathlib import Path

import ezdxf
from PyQt5.QtWidgets import (  # pylint: disable=E0611
    QCheckBox,
    QDoubleSpinBox,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


# i18n
def no_translation(text):
    return text


_ = no_translation
lang = os.environ.get("LANGUAGE")
if lang:
    localedir = os.path.join(Path(__file__).resolve().parent, "locales")
    try:
        lang_translations = gettext.translation("base", localedir=localedir, languages=[lang])

        lang_translations.install()
        _ = lang_translations.gettext
    except FileNotFoundError:
        sys.stderr.write(f"WARNING: localedir not found {localedir}\n")


class BoxTool(QWidget):
    painter = None

    def __init__(self, app):
        super().__init__()
        self.setWindowTitle("Box-Tool")
        self.app = app
        layout = QVBoxLayout()
        self.setLayout(layout)

        label = QLabel("Width")
        label.setToolTip(_("width of the box"))
        layout.addWidget(label)
        self.box_width = QDoubleSpinBox()
        self.box_width.setDecimals(2)
        self.box_width.setSingleStep(0.1)
        self.box_width.setMinimum(-100000)
        self.box_width.setMaximum(100000)
        self.box_width.setValue(200.0)
        self.box_width.setToolTip(_("width of the box"))
        layout.addWidget(self.box_width)

        label = QLabel("Height")
        label.setToolTip(_("height of the box"))
        layout.addWidget(label)
        self.box_height = QDoubleSpinBox()
        self.box_height.setDecimals(2)
        self.box_height.setSingleStep(0.1)
        self.box_height.setMinimum(-100000)
        self.box_height.setMaximum(100000)
        self.box_height.setValue(50.0)
        self.box_height.setToolTip(_("height of the box"))
        layout.addWidget(self.box_height)

        label = QLabel("Depth")
        label.setToolTip(_("depth of the box"))
        layout.addWidget(label)
        self.box_depth = QDoubleSpinBox()
        self.box_depth.setDecimals(2)
        self.box_depth.setSingleStep(0.1)
        self.box_depth.setMinimum(-100000)
        self.box_depth.setMaximum(100000)
        self.box_depth.setValue(100.0)
        self.box_depth.setToolTip(_("depth of the box"))
        layout.addWidget(self.box_depth)

        label = QLabel("Tooth-Len")
        label.setToolTip(_("len of the tooth"))
        layout.addWidget(label)
        self.box_tooth = QDoubleSpinBox()
        self.box_tooth.setDecimals(2)
        self.box_tooth.setSingleStep(0.1)
        self.box_tooth.setMinimum(-100000)
        self.box_tooth.setMaximum(100000)
        self.box_tooth.setValue(10.0)
        self.box_tooth.setToolTip(_("len of the tooth"))
        layout.addWidget(self.box_tooth)

        label = QLabel("Thickness")
        label.setToolTip(_("thickness of the material"))
        layout.addWidget(label)
        self.box_thickness = QDoubleSpinBox()
        self.box_thickness.setDecimals(2)
        self.box_thickness.setSingleStep(0.1)
        self.box_thickness.setMinimum(-100000)
        self.box_thickness.setMaximum(100000)
        self.box_thickness.setValue(3.0)
        self.box_thickness.setToolTip(_("thickness of the material"))
        layout.addWidget(self.box_thickness)

        label = QLabel("Top")
        label.setToolTip(_("with top plate"))
        layout.addWidget(label)
        self.box_top = QCheckBox()
        self.box_top.setChecked(True)
        self.box_top.setToolTip(_("with top plate"))
        layout.addWidget(self.box_top)

        self.qimage_label = QLabel()
        layout.addWidget(self.qimage_label)

        def open_box():
            self.hide()

            width = self.box_width.value()
            height = self.box_height.value()
            depth = self.box_depth.value()
            tooth_len = self.box_tooth.value()
            thickness = self.box_thickness.value()
            top = self.box_top.isChecked()
            rad = 0

            print(f"size: {width} x {height} x {depth}")

            num_tooth_width = (width - (thickness * 4)) / tooth_len / 2 + 0.5
            border_width = num_tooth_width - int(num_tooth_width)
            start_width = border_width * tooth_len + thickness * 2

            num_tooth_height = (height - (thickness * 4)) / tooth_len / 2 + 0.5
            border_height = num_tooth_height - int(num_tooth_height)
            start_height = border_height * tooth_len + thickness * 2

            num_tooth_depth = (depth - (thickness * 4)) / tooth_len / 2 + 0.5
            border_depth = num_tooth_depth - int(num_tooth_depth)
            start_depth = border_depth * tooth_len + thickness * 2

            # front and back
            points_fb = [(0, 0)]
            for n in range(int(num_tooth_width)):
                points_fb.append((start_width + n * tooth_len * 2, 0))
                if rad:
                    points_fb.append((start_width + n * tooth_len * 2, thickness - rad))
                    points_fb.append((start_width + n * tooth_len * 2 + rad, thickness, 1))
                    points_fb.append((start_width + n * tooth_len * 2 + tooth_len - rad, thickness))
                    points_fb.append((start_width + n * tooth_len * 2 + tooth_len, thickness - rad, 1))
                else:
                    points_fb.append((start_width + n * tooth_len * 2, thickness))
                    points_fb.append((start_width + n * tooth_len * 2 + tooth_len, thickness))
                points_fb.append((start_width + n * tooth_len * 2 + tooth_len, 0))
            points_fb.append((width, 0))
            for n in range(int(num_tooth_height)):
                points_fb.append((width, start_height + n * tooth_len * 2))
                if rad:
                    points_fb.append((width - thickness + rad, start_height + n * tooth_len * 2))
                    points_fb.append((width - thickness, start_height + n * tooth_len * 2 + rad, 1))
                    points_fb.append((width - thickness, start_height + n * tooth_len * 2 + tooth_len - rad))
                    points_fb.append(
                        (
                            width - thickness + rad,
                            start_height + n * tooth_len * 2 + tooth_len,
                            1,
                        )
                    )
                else:
                    points_fb.append((width - thickness, start_height + n * tooth_len * 2))
                    points_fb.append((width - thickness, start_height + n * tooth_len * 2 + tooth_len))
                points_fb.append((width, start_height + n * tooth_len * 2 + tooth_len))
            points_fb.append((width, height))
            if top:
                for n in range(int(num_tooth_width)):
                    points_fb.append((width - (start_width + n * tooth_len * 2), height))
                    if rad:
                        points_fb.append(
                            (
                                width - (start_width + n * tooth_len * 2),
                                height - thickness + rad,
                            )
                        )
                        points_fb.append(
                            (
                                width - (start_width + n * tooth_len * 2) - rad,
                                height - thickness,
                                1,
                            )
                        )
                        points_fb.append(
                            (
                                width - (start_width + n * tooth_len * 2 + tooth_len) + rad,
                                height - thickness,
                            )
                        )
                        points_fb.append(
                            (
                                width - (start_width + n * tooth_len * 2 + tooth_len),
                                height - thickness + rad,
                                1,
                            )
                        )
                    else:
                        points_fb.append((width - (start_width + n * tooth_len * 2), height - thickness))
                        points_fb.append(
                            (
                                width - (start_width + n * tooth_len * 2 + tooth_len),
                                height - thickness,
                            )
                        )
                    points_fb.append((width - (start_width + n * tooth_len * 2 + tooth_len), height))
            points_fb.append((0, height))
            for n in range(int(num_tooth_height)):
                points_fb.append((0, height - (start_height + n * tooth_len * 2)))
                if rad:
                    points_fb.append((thickness - rad, height - (start_height + n * tooth_len * 2)))
                    points_fb.append((thickness, height - (start_height + n * tooth_len * 2) - rad, 1))
                    points_fb.append(
                        (
                            thickness,
                            height - (start_height + n * tooth_len * 2 + tooth_len) + rad,
                        )
                    )
                    points_fb.append(
                        (
                            thickness - rad,
                            height - (start_height + n * tooth_len * 2 + tooth_len),
                            1,
                        )
                    )
                else:
                    points_fb.append((thickness, height - (start_height + n * tooth_len * 2)))
                    points_fb.append((thickness, height - (start_height + n * tooth_len * 2 + tooth_len)))
                points_fb.append((0, height - (start_height + n * tooth_len * 2 + tooth_len)))
            points_fb.append((0, 0))

            # top and bottom
            points_top = [(0, thickness)]
            for n in range(int(num_tooth_width)):
                if rad:
                    points_top.append((start_width + n * tooth_len * 2 - rad, thickness))
                    points_top.append((start_width + n * tooth_len * 2, thickness - rad, 1))
                    points_top.append((start_width + n * tooth_len * 2, 0))
                    points_top.append((start_width + n * tooth_len * 2 + tooth_len, 0))
                    points_top.append((start_width + n * tooth_len * 2 + tooth_len, thickness - rad))
                    points_top.append((start_width + n * tooth_len * 2 + tooth_len + rad, thickness, 1))
                else:
                    points_top.append((start_width + n * tooth_len * 2, thickness))
                    points_top.append((start_width + n * tooth_len * 2, 0))
                    points_top.append((start_width + n * tooth_len * 2 + tooth_len, 0))
                    points_top.append((start_width + n * tooth_len * 2 + tooth_len, thickness))
            points_top.append((width, thickness))
            for n in range(int(num_tooth_depth)):
                points_top.append((width, start_depth + n * tooth_len * 2))
                if rad:
                    points_top.append((width - thickness + rad, start_depth + n * tooth_len * 2))
                    points_top.append((width - thickness, start_depth + n * tooth_len * 2 + rad, 1))
                    points_top.append((width - thickness, start_depth + n * tooth_len * 2 + tooth_len - rad))
                    points_top.append(
                        (
                            width - thickness + rad,
                            start_depth + n * tooth_len * 2 + tooth_len,
                            1,
                        )
                    )
                else:
                    points_top.append((width - thickness, start_depth + n * tooth_len * 2))
                    points_top.append((width - thickness, start_depth + n * tooth_len * 2 + tooth_len))
                points_top.append((width, start_depth + n * tooth_len * 2 + tooth_len))
            points_top.append((width, depth - thickness))
            for n in range(int(num_tooth_width)):
                if rad:
                    points_top.append((width - (start_width + n * tooth_len * 2) + rad, depth - thickness))
                    points_top.append((width - (start_width + n * tooth_len * 2), depth - thickness + rad, 1))
                    points_top.append((width - (start_width + n * tooth_len * 2), depth))
                    points_top.append((width - (start_width + n * tooth_len * 2 + tooth_len), depth))
                    points_top.append(
                        (
                            width - (start_width + n * tooth_len * 2 + tooth_len),
                            depth - thickness + rad,
                        )
                    )
                    points_top.append(
                        (
                            width - (start_width + n * tooth_len * 2 + tooth_len) - rad,
                            depth - thickness,
                            1,
                        )
                    )
                else:
                    points_top.append((width - (start_width + n * tooth_len * 2), depth - thickness))
                    points_top.append((width - (start_width + n * tooth_len * 2), depth))
                    points_top.append((width - (start_width + n * tooth_len * 2 + tooth_len), depth))
                    points_top.append(
                        (
                            width - (start_width + n * tooth_len * 2 + tooth_len),
                            depth - thickness,
                        )
                    )
            points_top.append((0, depth - thickness))
            for n in range(int(num_tooth_depth)):
                if rad:
                    points_top.append((0, depth - (start_depth + n * tooth_len * 2)))
                    points_top.append((thickness - rad, depth - (start_depth + n * tooth_len * 2)))
                    points_top.append((thickness, depth - (start_depth + n * tooth_len * 2) - rad, 1))
                    points_top.append((thickness, depth - (start_depth + n * tooth_len * 2 + tooth_len) + rad))
                    points_top.append(
                        (
                            thickness - rad,
                            depth - (start_depth + n * tooth_len * 2 + tooth_len),
                            1,
                        )
                    )
                    points_top.append((0, depth - (start_depth + n * tooth_len * 2 + tooth_len)))
                else:
                    points_top.append((0, depth - (start_depth + n * tooth_len * 2)))
                    points_top.append((thickness, depth - (start_depth + n * tooth_len * 2)))
                    points_top.append((thickness, depth - (start_depth + n * tooth_len * 2 + tooth_len)))
                    points_top.append((0, depth - (start_depth + n * tooth_len * 2 + tooth_len)))
            points_top.append((0, thickness))

            # sides
            points_side = [(thickness, thickness)]
            for n in range(int(num_tooth_depth)):
                if rad:
                    points_side.append((start_depth + n * tooth_len * 2 - rad, thickness))
                    points_side.append((start_depth + n * tooth_len * 2, thickness - rad, 1))
                    points_side.append((start_depth + n * tooth_len * 2, 0))
                    points_side.append((start_depth + n * tooth_len * 2 + tooth_len, 0))
                    points_side.append((start_depth + n * tooth_len * 2 + tooth_len, thickness - rad))
                    points_side.append((start_depth + n * tooth_len * 2 + tooth_len + rad, thickness, 1))
                else:
                    points_side.append((start_depth + n * tooth_len * 2, thickness))
                    points_side.append((start_depth + n * tooth_len * 2, 0))
                    points_side.append((start_depth + n * tooth_len * 2 + tooth_len, 0))
                    points_side.append((start_depth + n * tooth_len * 2 + tooth_len, thickness))
            points_side.append((depth - thickness, thickness))
            for n in range(int(num_tooth_height)):
                if rad:
                    points_side.append((depth - thickness, start_height + n * tooth_len * 2 - rad))
                    points_side.append((depth - thickness + rad, start_height + n * tooth_len * 2, 1))
                    points_side.append((depth, start_height + n * tooth_len * 2))
                    points_side.append((depth, start_height + n * tooth_len * 2 + tooth_len))
                    points_side.append((depth - thickness + rad, start_height + n * tooth_len * 2 + tooth_len))
                    points_side.append(
                        (
                            depth - thickness,
                            start_height + n * tooth_len * 2 + tooth_len + rad,
                            1,
                        )
                    )
                else:
                    points_side.append((depth - thickness, start_height + n * tooth_len * 2))
                    points_side.append((depth, start_height + n * tooth_len * 2))
                    points_side.append((depth, start_height + n * tooth_len * 2 + tooth_len))
                    points_side.append((depth - thickness, start_height + n * tooth_len * 2 + tooth_len))
            if top:
                points_side.append((depth - thickness, height - thickness))
            else:
                points_side.append((depth - thickness, height))
            if top:
                for n in range(int(num_tooth_depth)):
                    if rad:
                        points_side.append(
                            (
                                depth - (start_depth + n * tooth_len * 2) + rad,
                                height - thickness,
                            )
                        )
                        points_side.append(
                            (
                                depth - (start_depth + n * tooth_len * 2),
                                height - thickness + rad,
                                1,
                            )
                        )
                        points_side.append((depth - (start_depth + n * tooth_len * 2), height))
                        points_side.append((depth - (start_depth + n * tooth_len * 2 + tooth_len), height))
                        points_side.append(
                            (
                                depth - (start_depth + n * tooth_len * 2 + tooth_len),
                                height - thickness + rad,
                            )
                        )
                        points_side.append(
                            (
                                depth - (start_depth + n * tooth_len * 2 + tooth_len) - rad,
                                height - thickness,
                                1,
                            )
                        )
                    else:
                        points_side.append((depth - (start_depth + n * tooth_len * 2), height - thickness))
                        points_side.append((depth - (start_depth + n * tooth_len * 2), height))
                        points_side.append((depth - (start_depth + n * tooth_len * 2 + tooth_len), height))
                        points_side.append(
                            (
                                depth - (start_depth + n * tooth_len * 2 + tooth_len),
                                height - thickness,
                            )
                        )
                points_side.append((thickness, height - thickness))
            else:
                points_side.append((thickness, height))

            for n in range(int(num_tooth_height)):
                if rad:
                    points_side.append((thickness, height - (start_height + n * tooth_len * 2) + rad))
                    points_side.append((thickness - rad, height - (start_height + n * tooth_len * 2), 1))
                    points_side.append((0, height - (start_height + n * tooth_len * 2)))
                    points_side.append((0, height - (start_height + n * tooth_len * 2 + tooth_len)))
                    points_side.append(
                        (
                            thickness - rad,
                            height - (start_height + n * tooth_len * 2 + tooth_len),
                        )
                    )
                    points_side.append(
                        (
                            thickness,
                            height - (start_height + n * tooth_len * 2 + tooth_len) - rad,
                            1,
                        )
                    )
                else:
                    points_side.append((thickness, height - (start_height + n * tooth_len * 2)))
                    points_side.append((0, height - (start_height + n * tooth_len * 2)))
                    points_side.append((0, height - (start_height + n * tooth_len * 2 + tooth_len)))
                    points_side.append((thickness, height - (start_height + n * tooth_len * 2 + tooth_len)))
            points_side.append((thickness, thickness))

            doc = ezdxf.new("R2010")
            msp = doc.modelspace()
            doc.layers.new(name="top", dxfattribs={"color": 1})
            doc.layers.new(name="bottom", dxfattribs={"color": 2})
            doc.layers.new(name="front", dxfattribs={"color": 3})
            doc.layers.new(name="back", dxfattribs={"color": 4})
            doc.layers.new(name="left", dxfattribs={"color": 5})
            doc.layers.new(name="right", dxfattribs={"color": 6})
            doc.units = ezdxf.units.MM
            for vport in doc.viewports.get_config("*Active"):
                vport.dxf.grid_on = True
                vport.dxf.center = (width * 2, height * 4)

            layers = {
                "front": (points_fb, 0, 0),
                "back": (points_fb, width + 20, 0),
                "left": (points_side, (width + 20) * 2, 0),
                "right": (points_side, (width + 20) * 2, height + 20),
            }
            if top:
                layers["bottom"] = (points_top, width + 20, height + 20)
                layers["top"] = (points_top, 0, height + 20)
            else:
                layers["bottom"] = (points_top, 0, height + 20)

            for layer, data in layers.items():
                last = (data[0][0][0] + data[1], data[0][0][1] + data[2])
                for point in data[0][1:]:
                    new = (point[0] + data[1], point[1] + data[2])
                    if len(point) == 2:
                        msp.add_line(last, new, dxfattribs={"layer": layer})
                    else:
                        (
                            center,
                            start_angle,
                            end_angle,
                            radius,
                        ) = ezdxf.math.bulge_to_arc(last, new, -1.0)
                        msp.add_arc(
                            center=center,
                            radius=radius,
                            start_angle=start_angle * 180 / math.pi,
                            end_angle=end_angle * 180 / math.pi,
                            dxfattribs={"layer": layer},
                        )
                    last = new

            temp_file = tempfile.NamedTemporaryFile(prefix=f"box_{width}_", suffix=".dxf")
            temp_file.close()
            output_file = temp_file.name
            print(f"saving gear to tempfile: {output_file}")

            doc.saveas(output_file)

            if self.app.load_drawing(output_file, no_setup=True):
                pass

        # self.gear_width.valueChanged.connect(self.preview)  # type: ignore

        self.button_open = QPushButton("Open")
        self.button_open.clicked.connect(open_box)
        layout.addWidget(self.button_open)

        self.button_close = QPushButton("Cancel")
        self.button_close.clicked.connect(self.close)
        layout.addWidget(self.button_close)
