
# viaConstructor
## Documentation
* Setup-Options
	- [Mill](#mill)
	- [Tool](#tool)
	- [Workpiece](#workpiece)
	- [Pockets](#pockets)
	- [Tabs](#tabs)
	- [Leads](#leads)
	- [Machine](#machine)
	- [View](#view)

## Mill
### Active
<p>
enable/disable this object

* Default: True
<p align="right">
</p>

</p>

### Depth
<p>
the end depth for milling

* Unit: mm/inch
* Default: -9.0
<p align="right">
</p>

</p>

### Step
<p>
the maximum depth in one move

* Unit: mm/inch
* Default: -9.0
<p align="right">
</p>

</p>

### Start-Depth
<p>
the start depth for milling

* Unit: mm/inch
* Default: 0.0
<p align="right">
</p>

</p>

### Passes
<p>
number of passes in Laser-Mode

* Default: 1
<p align="right">
</p>

</p>

### Helix
<p>
milling circles in helix mode

* Default: False
<p align="right">
<img alt="true" title="true" height="240" src="mill-helix_mode-true.png">

<img alt="false" title="false" height="240" src="mill-helix_mode-false.png">

</p>

</p>

### Fast-Move Z
<p>
the Z-Position for fast moves

* Unit: mm/inch
* Default: 5.0
<p align="right">
</p>

</p>

### G64-Value
<p>
value for the G64 command

* Default: 0.02
<p align="right">
</p>

</p>

### Reverse
<p>
Reverse

* Default: False
<p align="right">
</p>

</p>

### Back-Home
<p>
move tool back to Zero-Possition after milling

* Default: True
<p align="right">
</p>

</p>

### Small-Circles
<p>
milling small circles even if the tool is bigger

* Default: False
<p align="right">
<img alt="true" title="true" height="240" src="mill-small_circles-true.png">

<img alt="false" title="false" height="240" src="mill-small_circles-false.png">

</p>

</p>

### Overcut
<p>
Overcuting edges

* Default: False
<p align="right">
<img alt="false" title="false" height="240" src="mill-overcut-false.png">

<img alt="true" title="true" height="240" src="mill-overcut-true.png">

</p>

</p>

### Offset
<p>
tool offset

* Default: auto
### Options:
* auto
* inside
* outside
* none
<p align="right">
</p>

</p>

### Object-Order
<p>
how order the objects

* Default: nearest
### Options:
* nearest
* unordered
* per object
<p align="right">
<img alt="nearest" title="nearest" height="240" src="mill-objectorder-nearest.png">

<img alt="per_object" title="per_object" height="240" src="mill-objectorder-per_object.png">

<img alt="unsorted" title="unsorted" height="240" src="mill-objectorder-unsorted.png">

</p>

</p>

## Tool
### Number
<p>
setting the Tool-Number to load in gcode

* Default: 1
<p align="right">
</p>

</p>

### Speed
<p>
setting the Tool-Speed in RPM

* Unit: RPM
* Default: 10000
<p align="right">
</p>

</p>

### Feed-Rate(Horizontal)
<p>
the Horizotal Feetrate

* Unit: mm/min
* Default: 1000
<p align="right">
</p>

</p>

### Feed-Rate(Vertical)
<p>
the Vertical Feetrate

* Unit: mm/min
* Default: 100
<p align="right">
</p>

</p>

### Pause
<p>
tool spin up time (G04 Pn)

* Unit: s
* Default: 3
<p align="right">
</p>

</p>

### Mist
<p>
activate mist

* Default: False
<p align="right">
</p>

</p>

### Flood
<p>
activate flood

* Default: False
<p align="right">
</p>

</p>

### Tools
<p>
the tooltable

<p align="right">
</p>

</p>

## Workpiece
### Zero-Position
<p>
setting the Zero-Postition of the Workpiece

* Default: bottomLeft
### Options:
* original
* bottom left
* center
* bottom right
* top left
* top right
<p align="right">
<img alt="center" title="center" height="240" src="workpiece-zero-center.png">

<img alt="bottom-right" title="bottom-right" height="240" src="workpiece-zero-bottom-right.png">

</p>

</p>

### Offset X
<p>
Offset X (G54)


                    if G54 support is true, workpiece offsets will set with G10 command:
                     G10 L2 P1 X10.000000 Y20.000000 Z3.000000 (workpiece offsets for G54)
                    if G54 support is false, all offsets added to the G0-G3 commands
                

* Unit: mm/inch
* Default: 0.0
<p align="right">
</p>

</p>

### Offset Y
<p>
Offset Y (G54)


                    if G54 support is true, workpiece offsets will set with G10 command:
                     G10 L2 P1 X10.000000 Y20.000000 Z3.000000 (workpiece offsets for G54)
                    if G54 support is false, all offsets added to the G0-G3 commands
                

* Unit: mm/inch
* Default: 0.0
<p align="right">
</p>

</p>

### Offset Z
<p>
Offset Z (G54)


                    if G54 support is true, workpiece offsets will set with G10 command:
                     G10 L2 P1 X10.000000 Y20.000000 Z3.000000 (workpiece offsets for G54)
                    if G54 support is false, all offsets added to the G0-G3 commands
                

* Unit: mm/inch
* Default: 0.0
<p align="right">
</p>

</p>

### Materials
<p>
the materialtable


                    list of predifined materials to calculate feedrate / tool speed
                

<p align="right">
</p>

</p>

## Pockets
### Pocket
<p>
do pocket operation on this object

* Default: False
<p align="right">
<img alt="false" title="false" height="240" src="pockets-active-false.png">

<img alt="true" title="true" height="240" src="pockets-active-true.png">

</p>

</p>

### Zigzag
<p>
Zigzag

* Default: False
<p align="right">
<img alt="docs/pockets-zigzag" title="docs/pockets-zigzag" height="240" src="pockets-zigzag.png">

</p>

</p>

### Islands
<p>
keep islands

* Default: True
<p align="right">
<img alt="docs/pockets-islands" title="docs/pockets-islands" height="240" src="pockets-islands.png">

</p>

</p>

### insideout
<p>
from inside to out

* Default: True
<p align="right">
</p>

</p>

## Tabs
### active
<p>
activate tabs

* Default: True
<p align="right">
<img alt="false" title="false" height="240" src="tabs-active-false.png">

<img alt="true" title="true" height="240" src="tabs-active-true.png">

</p>

</p>

### Width
<p>
width of the tabs

* Unit: mm/inch
* Default: 10
<p align="right">
</p>

</p>

### Height
<p>
height of the tabs

* Unit: mm/inch
* Default: 2
<p align="right">
</p>

</p>

### Type
<p>
type of the tab

* Default: rectangle
### Options:
* rectangle
* triangle
<p align="right">
<img alt="triangle" title="triangle" height="240" src="tabs-type-triangle.png">

<img alt="rectangle" title="rectangle" height="240" src="tabs-type-rectangle.png">

</p>

</p>

## Leads
### in-type
<p>
type of the lead-in's

* Default: off
### Options:
* off
* arc
* straight
<p align="right">
<img alt="arc" title="arc" height="240" src="leads-in-arc.png">

</p>

</p>

### in-lenght
<p>
lenght of the lead-in's

* Unit: mm/inch
* Default: 3.0
<p align="right">
</p>

</p>

### out-type
<p>
type of the lead-out's

* Default: off
### Options:
* off
* arc
* straight
<p align="right">
<img alt="straight" title="straight" height="240" src="leads-out-straight.png">

</p>

</p>

### out-lenght
<p>
lenght of the lead-out's

* Unit: mm/inch
* Default: 3.0
<p align="right">
</p>

</p>

## Machine
### Feedrate
<p>
maximum feedrate while milling

* Default: 1000
<p align="right">
</p>

</p>

### Tool-Speed
<p>
maximum tool-speed

* Default: 15000
<p align="right">
</p>

</p>

### Plugin
<p>
output plugin selection

* Default: gcode_linuxcnc
### Options:
* gcode_linuxcnc
* gcode_grbl
* hpgl
<p align="right">
</p>

</p>

### Tool-Mode
<p>
Tool-Mode

* Default: mill
### Options:
* mode
* laser
* laser+z
<p align="right">
</p>

</p>

### Unit
<p>
Unit of the machine

* Default: mm
### Options:
* mm
* inch
<p align="right">
</p>

</p>

### Arcs-Mode (G2/G3)
<p>
Arcs-Mode - G2/G3 with IJ or R (experimental)

* Default: ij
### Options:
* offset
* radius
<p align="right">
<img alt="true" title="true" height="240" src="machine-arcs-true.png">

<img alt="false" title="false" height="240" src="machine-arcs-false.png">

</p>

</p>

### machine supports g54
<p>
machine supports g54 (workpiece offsets)


                    if true, workpiece offsets will set with G10 command:
                     G10 L2 P1 X10.000000 Y20.000000 Z3.000000 (workpiece offsets for G54)
                    if false, all offsets added to the G0-G3 commands
                

* Default: False
<p align="right">
</p>

</p>

### extra init cmds
<p>
add gcode after init

* Default: 
<p align="right">
</p>

</p>

### machine supports toolchange
<p>
machine supports toolchange

* Default: True
<p align="right">
</p>

</p>

### toolchange pre cmd
<p>
add gcode before tool-change

* Default: 
<p align="right">
</p>

</p>

### toolchange post cmd
<p>
add gcode after tool-change

* Default: 
<p align="right">
</p>

</p>

### spindle on pre cmd
<p>
add gcode before turning the spindle on

* Default: 
<p align="right">
</p>

</p>

### spindle off post cmd
<p>
add gcode after turning the spindle off

* Default: 
<p align="right">
</p>

</p>

### Comments in output
<p>
add comments to output

* Default: True
<p align="right">
</p>

</p>

### line numbers
<p>
adding line numbers

* Default: False
<p align="right">
</p>

</p>

### add thumbnail to gcode
<p>
add thumbnail to gcode output (3d-view)

* Default: False
<p align="right">
</p>

</p>

### Post-Command
<p>
Post-Command to do things after save like upload to cnc

* Default: 
<p align="right">
</p>

</p>

## View
### Auto-Recalculation
<p>
update drawing automatically

* Default: True
<p align="right">
</p>

</p>

### Autosave (Setup)
<p>
save setup as default automatically on exit

* Default: True
<p align="right">
</p>

</p>

### Path
<p>
how to show the gcode path in the 3d-View

* Default: simple
### Options:
* minimal
* simple
* full
<p align="right">
<img alt="full" title="full" height="240" src="view-path-full.png">

<img alt="minimal" title="minimal" height="240" src="view-path-minimal.png">

<img alt="simple" title="simple" height="240" src="view-path-simple.png">

</p>

</p>

### Colors-Show
<p>
showing layer colors in 3D preview

* Default: True
<p align="right">
<img alt="true" title="true" height="240" src="view-colors_show-true.png">

<img alt="false" title="false" height="240" src="view-colors_show-false.png">

</p>

</p>

### Ruler-Show
<p>
showing ruler in 3D preview

* Default: True
<p align="right">
</p>

</p>

### Grid-Show
<p>
showing grid in 3D preview

* Default: True
<p align="right">
</p>

</p>

### Grid-Size
<p>
size of the grid

* Default: 10
<p align="right">
</p>

</p>

### Show as Polygon
<p>
showing as polygon in 3D preview

* Default: True
<p align="right">
<img alt="false" title="false" height="240" src="view-polygon_show-false.png">

</p>

</p>

### Show Object-ID's
<p>
shows id of each object

* Default: True
<p align="right">
</p>

</p>

### arcs
<p>
draw arcs / Interpolation

* Default: True
<p align="right">
<img alt="true" title="true" height="240" src="view-arcs-true.png">

<img alt="false" title="false" height="240" src="view-arcs-false.png">

</p>

</p>

### Show inputfile in 3d
<p>
Show inputfile in 3d if possible

* Default: False
<p align="right">
</p>

</p>

### color
<p>
color of the workpeace in 3d view

* Default: (0.5, 0.5, 0.5)
<p align="right">
<img alt="gray" title="gray" height="240" src="view-color-gray.png">

<img alt="docs/view-colors_show-true" title="docs/view-colors_show-true" height="240" src="view-colors_show-true.png">

<img alt="docs/view-colors_show-false" title="docs/view-colors_show-false" height="240" src="view-colors_show-false.png">

</p>

</p>

### transparency
<p>
transparency of the workpeace in 3d view

* Default: 0.6
<p align="right">
<img alt="1.0" title="1.0" height="240" src="view-alpha-1.0.png">

<img alt="0.7" title="0.7" height="240" src="view-alpha-0.7.png">

</p>

</p>

