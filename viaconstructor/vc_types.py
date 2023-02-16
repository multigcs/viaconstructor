class VcSegment:
    type = ""
    object = None
    layer = ""
    color = 256
    start = ()
    end = ()
    bulge = 0.0
    center = ()

    def __init__(self, data):
        self.type = data.get("type", "")
        self.object = data.get("object", None)
        self.layer = data.get("layer", "0")
        self.color = data.get("color", 256)
        self.start = data.get("start", (0, 0))
        self.end = data.get("end", (0, 0))
        self.bulge = data.get("bulge", 0.0)
        self.center = data.get("center", (0, 0))

    def __repr__(self):
        return f"VcSegment {self.start}->{self.end}"

    def dump(self):
        return {
            "type": self.type,
            "object": self.object,
            "layer": self.layer,
            "color": self.color,
            "start": self.start,
            "end": self.end,
            "bulge": self.bulge,
            "center": self.center,
        }

    def get(self, item, default=None):
        if hasattr(self, item):
            return getattr(self, item)
        return default

    def __contains__(self, item):
        if hasattr(self, item):
            return True
        return False

    def __getitem__(self, item):
        return getattr(self, item)

    def __setitem__(self, item, value):
        return setattr(self, item, value)


class VcObject:
    segments: list[VcSegment] = []
    closed = False
    tool_offset = "none"
    overwrite_offset = None
    outer_objects: list = []
    inner_objects: list = []
    layer = ""
    color = 256
    setup: dict = {}
    start = ()

    def __init__(self, data):
        self.segments = data.get("segments", [])
        self.closed = data.get("closed", False)
        self.tool_offset = data.get("tool_offset", "none")
        self.overwrite_offset = data.get("overwrite_offset", None)
        self.outer_objects = data.get("outer_objects", [])
        self.inner_objects = data.get("inner_objects", [])
        self.layer = data.get("layer", "")
        self.color = data.get("color", 256)
        self.setup = data.get("setup", "")
        self.start = data.get("start", ())

    def __repr__(self):
        return "VcObject"

    def get(self, item, default=None):
        if hasattr(self, item):
            return getattr(self, item)
        return default

    def __contains__(self, item):
        if hasattr(self, item):
            return True
        return False

    def __getitem__(self, item):
        return getattr(self, item)

    def __setitem__(self, item, value):
        return setattr(self, item, value)
