import ctypes, pathlib
import numpy as np

module_root = pathlib.Path(__file__).resolve().parent
libname = module_root / "lib/libCavalierContours.so"
c_lib = ctypes.CDLL(libname)

class _PointStruct(ctypes.Structure):
    _fields_ = [('x', ctypes.c_double),
                ('y', ctypes.c_double)]

class _VertexStruct(ctypes.Structure):
    _fields_ = [('x', ctypes.c_double),
                ('y', ctypes.c_double),
                ('bulge', ctypes.c_double)]

# CAVC_PLINE_NEW
c_lib.cavc_pline_new.argtypes = [
    np.ctypeslib.ndpointer(dtype=np.double, ndim=2, flags='C_CONTIGUOUS'),
    ctypes.c_uint32,
    ctypes.c_int]
c_lib.cavc_pline_new.restype = ctypes.c_void_p

# CAVC_PLINE_DELETE
c_lib.cavc_pline_delete.argtypes = [ctypes.c_void_p]
# void return

# CAVC_PLINE_CAPACITY
c_lib.cavc_pline_capacity.argtypes = [ctypes.c_void_p]
c_lib.cavc_pline_capacity.restype = ctypes.c_uint32

# CAVC_PLINE_SET_CAPACITY
c_lib.cavc_pline_set_capacity.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
# void return

# CAVC_PLINE_VERTEX_COUNT
c_lib.cavc_pline_vertex_count.argtypes = [ctypes.c_void_p]
c_lib.cavc_pline_vertex_count.restype = ctypes.c_uint32

# CAVC_PLINE_VERTEX_DATA
c_lib.cavc_pline_vertex_data.argtypes = [
    ctypes.c_void_p,
    np.ctypeslib.ndpointer(dtype=np.double, ndim=2, flags='C_CONTIGUOUS')]
# void return

# CAVC_PLINE_IS_CLOSED
c_lib.cavc_pline_is_closed.argtypes = [ctypes.c_void_p]
c_lib.cavc_pline_is_closed.restype = ctypes.c_int

# CAVC_PLINE_SET_VERTEX_DATA
c_lib.cavc_pline_set_vertex_data.argtypes = [
    ctypes.c_void_p,
    np.ctypeslib.ndpointer(dtype=np.double, ndim=2, flags='C_CONTIGUOUS'),
    ctypes.c_uint32]
# void return

# CAVC_PLINE_ADD_VERTEX
c_lib.cavc_pline_add_vertex.argtypes = [ctypes.c_void_p, _VertexStruct]
# void return

# CAVC_PLINE_REMOVE_RANGE
c_lib.cavc_pline_remove_range.argtypes = [
    ctypes.c_void_p,
    ctypes.c_uint32,
    ctypes.c_uint32]
# void return

# CAVC_PLINE_CLEAR
c_lib.cavc_pline_clear.argtypes = [ctypes.c_void_p]
# void return

# CAVC_PLINE_SET_IS_CLOSED
c_lib.cavc_pline_set_is_closed.argtypes = [ctypes.c_void_p, ctypes.c_int]
# void return

# CAVC_PLINE_LIST_DELETE
c_lib.cavc_pline_list_delete.argtypes = [ctypes.c_void_p]
# void return

# CAVC_PLINE_LIST_COUNT
c_lib.cavc_pline_list_count.argtypes = [ctypes.c_void_p]
c_lib.cavc_pline_list_count.restype = ctypes.c_uint32

# CAVC_PLINE_LIST_GET
c_lib.cavc_pline_list_get.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
c_lib.cavc_pline_list_get.restype = ctypes.c_void_p

# CAVC_PLINE_LIST_RELEASE
c_lib.cavc_pline_list_release.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
c_lib.cavc_pline_list_release.restype = ctypes.c_void_p

# CAVC_PARALLEL_OFFSET
c_lib.cavc_parallel_offset.argtypes = [
    ctypes.c_void_p,
    ctypes.c_double,
    ctypes.c_void_p,
    ctypes.c_int]
# void return

# CAVC_COMBINE_PLINES
c_lib.cavc_combine_plines.argtypes = [
    ctypes.c_void_p,
    ctypes.c_void_p,
    ctypes.c_int,
    ctypes.c_void_p,
    ctypes.c_void_p]
# void return

# CAVC_GET_PATH_LENGTH
c_lib.cavc_get_path_length.argtypes = [ctypes.c_void_p]
c_lib.cavc_get_path_length.restype = ctypes.c_double

# CAVC_GET_AREA
c_lib.cavc_get_area.argtypes = [ctypes.c_void_p]
c_lib.cavc_get_area.restype = ctypes.c_double

# CAVC_GET_WINDING_NUMBER
c_lib.cavc_get_winding_number.argtypes = [ctypes.c_void_p, _PointStruct]
c_lib.cavc_get_winding_number.restype = ctypes.c_int

# CAVC_GET_EXTENTS
c_lib.cavc_get_extents.argtypes = [
    ctypes.c_void_p,
    ctypes.c_void_p,
    ctypes.c_void_p,
    ctypes.c_void_p,
    ctypes.c_void_p]
# void return

# CAVC_GET_CLOSEST_POINT
c_lib.cavc_get_closest_point.argtypes = [
    ctypes.c_void_p,
    _PointStruct,
    ctypes.c_void_p,
    ctypes.c_void_p,
    ctypes.c_void_p]
# void return

class Polyline:
    def __init__(self, vertex_data, is_closed):
        vertex_data = np.array(vertex_data).transpose().astype(np.double)
        self._c_pline_ptr = c_lib.cavc_pline_new(
            np.ascontiguousarray(vertex_data), vertex_data.shape[0], is_closed)

    def __del__(self):
        c_lib.cavc_pline_delete(self._c_pline_ptr)

    def capacity(self):
        return c_lib.cavc_pline_capacity(self._c_pline_ptr)

    def set_capacity(self, size):
        c_lib.cavc_pline_set_capacity(self._c_pline_ptr, size)

    def vertex_count(self):
        return c_lib.cavc_pline_vertex_count(self._c_pline_ptr)

    def vertex_data(self):
        vertex_data = np.empty(shape=(self.vertex_count(), 3))
        c_lib.cavc_pline_vertex_data(self._c_pline_ptr, vertex_data)
        return np.ctypeslib.as_array(vertex_data).transpose()

    def is_closed(self):
        return bool(c_lib.cavc_pline_is_closed(self._c_pline_ptr))

    def set_vertex_data(self, vertex_data):
        vertex_data = np.array(vertex_data).transpose().astype(np.double)
        c_lib.cavc_pline_set_vertex_data(self._c_pline_ptr, vertex_data,
                                         vertex_data.shape[0])

    def add_vertex(self, vertex):
        c_lib.cavc_pline_add_vertex(self._c_pline_ptr,
            _VertexStruct(vertex[0], vertex[1], vertex[2]))

    def remove_range(self, start_index, count):
        c_lib.cavc_pline_remove_range(self._c_pline_ptr, start_index, count)

    def clear(self):
        c_lib.cavc_pline_clear(self._c_pline_ptr)

    def set_is_closed(self, is_closed):
        c_lib.cavc_pline_set_is_closed(self._c_pline_ptr, is_closed)

    def parallel_offset(self, delta, check_self_intersect):
        """Return a list of Polyline."""
        delta = ctypes.c_double(delta)
        ret_ptr = ctypes.pointer(ctypes.c_void_p())
        flags = ctypes.c_int(1 if check_self_intersect else 0)
        c_lib.cavc_parallel_offset(self._c_pline_ptr, delta, ret_ptr, flags)
        return Polyline._extract_plines(ret_ptr.contents)

    def combine_plines(self, other, combine_mode):
        """For union combine_mode = 0
        For exclude combine_mode = 1
        For intersect combine_mode = 2
        For XOR combine_mode = 3
        Return two lists of Polyline as a tuple (remaining, subtracted).
        """
        combine_mode = ctypes.c_int(combine_mode)
        remaining = ctypes.pointer(ctypes.c_void_p())
        subtracted = ctypes.pointer(ctypes.c_void_p())
        c_lib.cavc_combine_plines(self._c_pline_ptr, other._c_pline_ptr,
                                  combine_mode, remaining, subtracted)
        return {Polyline._extract_plines(remaining.contents),
                Polyline._extract_plines(subtracted.contents)}

    def get_path_length(self):
        return c_lib.cavc_get_path_length(self._c_pline_ptr)

    def get_area(self):
        return c_lib.cavc_get_area(self._c_pline_ptr)

    def get_winding_number(self, point):
        return c_lib.cavc_get_winding_number(self._c_pline_ptr,
                                             _PointStruct(point[0], point[1]))

    def get_extents(self):
        """Return (min_x, min_y, max_x, max_y) tuple."""
        min_x = ctypes.pointer(ctypes.c_double())
        min_y = ctypes.pointer(ctypes.c_double())
        max_x = ctypes.pointer(ctypes.c_double())
        max_y = ctypes.pointer(ctypes.c_double())
        c_lib.cavc_get_extents(self._c_pline_ptr, min_x, min_y, max_x, max_y)
        return (min_x.contents.value, min_y.contents.value,
                max_x.contents.value, max_y.contents.value)

    def get_closest_point(self, point):
        """Return (closest_start_index, closest_point, distance) tuple."""
        closest_start_index_ptr = ctypes.pointer(ctypes.c_uint32())
        closest_point_ptr = ctypes.pointer(_PointStruct())
        distance_ptr = ctypes.pointer(ctypes.c_double())
        c_lib.cavc_get_closest_point(
            self._c_pline_ptr,
            _PointStruct(point[0], point[1]),
            closest_start_index_ptr,
            closest_point_ptr,
            distance_ptr)
        closest_point = closest_point_ptr.contents
        return (closest_start_index_ptr.contents.value,
                (closest_point.x, closest_point.y),
                distance_ptr.contents.value)

    def _extract_plines(c_pline_list_ptr):
        """Internal helper to convert cavc_pline_list to python list."""
        plines = []
        count = c_lib.cavc_pline_list_count(c_pline_list_ptr)
        for i in reversed(range(count)):
            c_pline_ptr = c_lib.cavc_pline_list_release(c_pline_list_ptr, i)
            bare_cavc_pline = Polyline.__new__(Polyline)
            bare_cavc_pline._c_pline_ptr = c_pline_ptr
            plines.append(bare_cavc_pline)
        c_lib.cavc_pline_list_delete(c_pline_list_ptr)
        return plines
