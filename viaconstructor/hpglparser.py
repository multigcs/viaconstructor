import argparse

import ezdxf


parser = argparse.ArgumentParser()
parser.add_argument("filename", help="hpgl input file", type=str)
parser.add_argument(
    "-o", "--output", help="save to dxf file", type=str, default=None
)
args = parser.parse_args()


hpgl = open(args.filename, "r").read()

doc = ezdxf.new("R2010")
msp = doc.modelspace()


# PA  Position absolute (Stift zu absoluten Koordinaten bewegen)
# PR  Position relative (Stift um Anzahl von Einheiten bewegen)
# PD  Pen down (Stift senken)
# PU  Pen up (Stift heben)
# SP  Select pen (Stift auswählen)


last_x = 0
last_y = 0
draw = False
pen = "0"
absolute = True

hpgl = hpgl.replace(";", "\n")
for line in hpgl.split("\n"):
    line = line.strip()
    print(line)
    if line.startswith("PU"):
        draw = False
        line = line[2:]
        
    elif line.startswith("PD"):
        draw = True
        line = line[2:]

    elif line.startswith("IN"):
        print("init")
        line = ""

    elif line.startswith("CO"):
        print("comment")
        line = ""

    elif line.startswith("SP"):
        pen = line[2:]
        line = ""

    elif line.startswith("PA"):
        absolute = True
        line = ""
    elif line.startswith("PR"):
        absolute = False
        line = ""

    line = line.strip()
    if line:
        is_x = True
        for cord in line.split(","):
            if is_x:
                x = float(cord)
            else:
                y = float(cord)
                if not absolute:
                    x += last_x
                    y += last_y
                
                if draw:
                    msp.add_line((last_x, last_y), (x, y))

                last_x = x
                last_y = y


            is_x = not is_x


doc.saveas(args.output)
