import base64
import json
import tarfile
from io import BytesIO
from itertools import chain

try:
    from statistics import multimode as statistics_multimode
    from statistics import median as statistics_median
except ImportError:
    # Python 2.7 mockup for statistics
    def statistics_multimode(data):
        return data


    def statistics_median(lst):
        n = len(lst)
        s = sorted(lst)
        return (sum(s[n // 2 - 1:n // 2 + 1]) / 2.0, s[n // 2])[n % 2] if n else None

try:
    from itertools import zip_longest
except ImportError:
    from itertools import izip_longest as zip_longest

try:
    from string import split
except ImportError:
    split = str.split


class HersheyFonts(object):
    '''The Hershey Fonts:
        - are a set of more than 2000 glyph (symbol) descriptions in vector
                ( <x,y> point-to-point ) format
        - can be grouped as almost 20 'occidental' (english, greek,
                cyrillic) fonts, 3 or more 'oriental' (Kanji, Hiragana,
                and Katakana) fonts, and a few hundred miscellaneous
                symbols (mathematical, musical, cartographic, etc etc)
        - are suitable for typographic quality output on a vector device
                (such as a plotter) when used at an appropriate scale.
        - were digitized by Dr. A. V. Hershey while working for the U.S.
                Government National Bureau of Standards (NBS).
        - are in the public domain, with a few caveats:
                - They are available from NTIS (National Technical Info.
                        Service) in a computer-readable from which is *not*
                        in the public domain. This format is described in
                        a hardcopy publication "Tables of Coordinates for
                        Hershey's Repertory of Occidental Type Fonts and
                        Graphic Symbols" available from NTIS for less than
                        $20 US (phone number +1 703 487 4763).
                - NTIS does not care about and doesn't want to know about
                        what happens to Hershey Font data that is not
                        distributed in their exact format.
                - This distribution is not in the NTIS format, and thus is
                        only subject to the simple restriction described
                        at the top of this file.

Hard Copy samples of the Hershey Fonts are best obtained by purchasing the
book described above from NTIS. It contains a sample of all of the Occidental
symbols (but none of the Oriental symbols).

This distribution:
        - contains
                * a complete copy of the Font data using the original
                        glyph-numbering sequence
                * a set of translation tables that could be used to generate
                        ASCII-sequence fonts in various typestyles
                * a couple of sample programs in C and Fortran that are
                        capable of parsing the font data and displaying it
                        on a graphic device (we recommend that if you
                        wish to write programs using the fonts, you should
                        hack up one of these until it works on your system)

        - consists of the following files...
                hershey.doc - details of the font data format, typestyles and
                                symbols included, etc.
                hersh.oc[1-4] - The Occidental font data (these files can
                                        be catenated into one large database)
                hersh.or[1-4] - The Oriental font data (likewise here)
                *.hmp - Occidental font map files. Each file is a translation
                                table from Hershey glyph numbers to ASCII
                                sequence for a particular typestyle.
                hershey.f77 - A fortran program that reads and displays all
                                of the glyphs in a Hershey font file.
                hershey.c   - The same, in C, using GKS, for MS-DOS and the
                                PC-Color Graphics Adaptor.

Additional Work To Be Done (volunteers welcome!):

        - Integrate this complete set of data with the hershey font typesetting
                program recently distributed to mod.sources
        - Come up with an integrated data structure and supporting routines
                that make use of the ASCII translation tables
        - Digitize additional characters for the few places where non-ideal
                symbol substitutions were made in the ASCII translation tables.
        - Make a version of the demo program (hershey.c or hershey.f77) that
                uses the standard Un*x plot routines.
        - Write a banner-style program using Hershey Fonts for input and
                non-graphic terminals or printers for output.
        - Anything else you'd like!

This file provides a brief description of the contents of the Occidental
Hershey Font Files. For a complete listing of the fonts in hard copy, order
NBS Special Publication 424, "A contribution to computer typesetting
techniques: Tables of Coordinates for Hershey's Repertory of Occidental
Type Fonts and Graphic Symbols". You can get it from NTIS (phone number is
+1 703 487 4763) for less than twenty dollars US.

Basic Glyph (symbol) data:

        hersh.oc1       - numbers 1 to 1199
        hersh.oc2       - numbers 1200 to 2499
        hersh.oc3       - numbers 2500 to 3199
        hersh.oc4       - numbers 3200 to 3999

        These four files contain approximately 19 different fonts in
the A-Z alphabet plus greek and cyrillic, along with hundreds of special
symbols, described generically below.

        There are also four files of Oriental fonts (hersh.or[1-4]). These
files contain symbols from three Japanese alphabets (Kanji, Hiragana, and
Katakana). It is unknown what other symbols may be contained therein, nor
is it known what order the symbols are in (I don't know Japanese!).

        Back to the Occidental files:

Fonts:
        Roman: Plain, Simplex, Duplex, Complex Small, Complex, Triplex
        Italic: Complex Small, Complex, Triplex
        Script: Simplex, Complex
        Gothic: German, English, Italian
        Greek: Plain, Simplex, Complex Small, Complex
        Cyrillic: Complex

Symbols:
        Mathematical (227-229,232,727-779,732,737-740,1227-1270,2227-2270,
                        1294-1412,2294-2295,2401-2412)
        Daggers (for footnotes, etc) (1276-1279, 2276-2279)
        Astronomical (1281-1293,2281-2293)
        Astrological (2301-2312)
        Musical (2317-2382)
        Typesetting (ffl,fl,fi sorts of things) (miscellaneous places)
        Miscellaneous (mostly in 741-909, but also elsewhere):
                - Playing card suits
                - Meteorology
                - Graphics (lines, curves)
                - Electrical
                - Geometric (shapes)
                - Cartographic
                - Naval
                - Agricultural
                - Highways
                - Etc...

ASCII sequence translation files:

        The Hershey glyphs, while in a particular order, are not in an
        ASCII sequence. I have provided translation files that give the
        sequence of glyph numbers that will most closely approximate the
        ASCII printing sequence (from space through ~, with the degree
        circle tacked on at the end) for each of the above fonts:

        File names are made up of fffffftt.hmp,

                where ffffff is the font style, one of:
                        roman   Roman
                        greek   Greek
                        italic  Italic
                        script  Script
                        cyril   Cyrillic (some characters not placed in
                                           the ASCII sequence)
                        gothgr  Gothic German
                        gothgb  Gothic English
                        gothit  Gothic Italian

                and tt is the font type, one of:
                    p       Plain (very small, no lower case)
                    s       Simplex (plain, normal size, no serifs)
                    d       Duplex (normal size, no serifs, doubled lines)
                    c       Complex (normal size, serifs, doubled lines)
                    t       Triplex (normal size, serifs, tripled lines)
                    cs      Complex Small (Complex, smaller than normal size)

The three sizes are coded with particular base line (bottom of a capital
        letter) and cap line (top of a capital letter) values for 'y':

        Size            Base Line       Cap Line

        Very Small         -5              +4
        Small              -6              +7
        Normal             -9              +12

        (Note: some glyphs in the 'Very Small' fonts are actually 'Small')

The top line and bottom line, which are normally used to define vertical
        spacing, are not given. Maybe somebody can determine appropriate
        values for these!

The left line and right line, which are used to define horizontal spacing,
        are provided with each character in the database.

Format of Hershey glyphs:

5 bytes - glyphnumber
3 bytes - length of data  length in 16-bit words including left&right numbers
1 byte  - x value of left margin
1 byte  - x value of right margin
(length*2)-2 bytes      - stroke data

left&right margins and stroke data are biased by the value of the letter 'R'
Subtract the letter 'R' to get the data.

e.g. if the data byte is 'R', the data is 0
     if the data byte is 'T', the data is +2
     if the data byte is 'J', the data is -8

and so on...

The coordinate system is x-y, with the origin (0,0) in the center of the
glyph.  X increases to the right and y increases *down*.

The stroke data is pairs of bytes, one byte for x followed by one byte for y.

A ' R' in the stroke data indicates a 'lift pen and move' instruction.'''
    __compressed_fonts_base64 = B'''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'''

    class _objdict(dict):
        def __getattr__(self, name):
            if name in self:
                return self[name]
            else:
                raise AttributeError('No such attribute: ' + name)

        def __setattr__(self, name, value):
            if name in self:
                self[name] = value
            else:
                raise AttributeError('No such attribute: ' + name)

    class _rednderopts(_objdict):
        @property
        def cap_line(self):
            return self['cap_line'] * self.scaley

        @property
        def bottom_line(self):
            return self['bottom_line'] * self.scaley

        @property
        def base_line(self):
            return self['base_line'] * self.scaley

    class _HersheyRenderIterator(object):
        def __init__(self, glyphs, text=None):
            self.__text = text or ''
            if not isinstance(glyphs, dict):
                raise TypeError('glyphs parameter has to be a dictionary')
            self.__glyphs = glyphs

        def text_glyphs(self, text=None):
            text = text or self.__text or ''
            for current_char in text:
                if current_char in self.__glyphs:
                    the_glyph = self.__glyphs[current_char]
                    if isinstance(the_glyph, _HersheyGlyph):
                        yield the_glyph

        def text_strokes(self, text=None, xofs=0, yofs=0, scalex=1, scaley=1, spacing=0, **kwargs):
            for glyph in self.text_glyphs(text=text):
                for stroke in glyph.strokes:
                    yield [(xofs + (x - glyph.left_offset) * scalex, yofs + y * scaley) for x, y in stroke]
                xofs += spacing + scalex * glyph.char_width

    def __init__(self, load_from_data_iterator='', load_default_font=None):
        self.__glyphs = {}
        self.__default_font_names_list = None
        self.__font_params = self._rednderopts({'xofs': 0, 'yofs': 0, 'scalex': 1, 'scaley': 1, 'spacing': 0, 'cap_line': -12, 'base_line': 9, 'bottom_line': 16})
        if load_default_font is not None:
            self.load_default_font(load_default_font)
        else:
            self.read_from_string_lines(data_iterator=load_from_data_iterator)

    @property
    def render_options(self):
        '''xofs=0, yofs=0,
scalex=1, scaley=1,
spacing=0,
cap_line=-12, base_line= 9, bottom_line= 16'''
        return self.__font_params

    @property
    def all_glyphs(self):
        '''Get all Glyphs stored for currently loaded font. ={} if no font loaded'''
        return dict(self.__glyphs)

    @render_options.setter
    def render_options(self, newdim):
        '''xofs=0, yofs=0,
scalex=1, scaley=1,
spacing=0,
cap_line=-12, base_line= 9, bottom_line= 16'''
        if newdim.issubset(self.render_options.keys()):
            self.render_options.update(newdim)
        else:
            raise AttributeError('Unable to set unknown parameters')

    @property
    def default_font_names(self):
        '''Get the list of built-in fonts'''
        if not self.__default_font_names_list:
            with BytesIO(self.__get_compressed_font_bytes()) as compressed_file_stream:
                with tarfile.open(fileobj=compressed_file_stream, mode='r', ) as ftar:
                    self.__default_font_names_list = list(map(lambda tar_member: tar_member.name, ftar.getmembers()))
            del ftar
            del compressed_file_stream
        return list(self.__default_font_names_list)

    def __get_compressed_font_bytes(self):
        for enc in ('64', '85', '32', '16'):
            if hasattr(self, '_HersheyFonts__compressed_fonts_base' + enc):
                if hasattr(base64, 'b' + enc + 'decode'):
                    decoded = getattr(base64, 'b' + enc + 'decode')(getattr(self, '_HersheyFonts__compressed_fonts_base' + enc))
                    return bytes(decoded)
        raise NotImplementedError('base' + enc + ' encoding not supported on this platform.')

    def normalize_rendering(self, factor=1.0):
        '''Set rendering options to output text lines in upright direction, size set to "factor"'''
        scale_factor = float(factor) / (self.render_options['bottom_line'] - self.render_options['cap_line'])
        self.render_options.scaley = -scale_factor
        self.render_options.scalex = scale_factor
        self.render_options.yofs = self.render_options['bottom_line'] * scale_factor
        self.render_options.xofs = 0

    def load_default_font(self, default_font_name=''):
        '''load built-in font by name. If default_font_name not specified, selects the predefined default font. The routine is returning the name of the loaded font.'''
        if not default_font_name:
            default_font_name = self.default_font_names[0]
        if default_font_name in self.default_font_names:
            with BytesIO(self.__get_compressed_font_bytes()) as compressed_file_stream:
                with tarfile.open(fileobj=compressed_file_stream, mode='r', ) as ftar:
                    tarmember = ftar.extractfile(default_font_name)
                    self.read_from_string_lines(tarmember)
                    return default_font_name
        raise ValueError('"{0}" font not found.'.format(default_font_name))

    def load_font_file(self, file_name):
        '''load font from external file'''
        with open(file_name, 'r') as fin:
            self.read_from_string_lines(fin)

    def read_from_string_lines(self, data_iterator=None, first_glyph_ascii_code=32, use_charcode=False, merge_existing=False):
        '''Read font from iterable list of strings
Parameters:
    - data_iterator : string list or empty to clear current font data
    - use_charcode : if True use the font embedded charcode parameter for glyph storage
    - first_glyph_ascii_code : if use_charcode is False, use this ASCII code for the first character in font line
    - merge_existing : if True merge the glyphs from data_iterator to the current font
    '''
        glyph_ascii_code = first_glyph_ascii_code
        cap = []
        base = []
        bottom = []
        cap_line = None
        base_line = None
        bottom_line = None
        aglyph = None
        if not merge_existing:
            self.__glyphs = {}
        if data_iterator:
            for line in data_iterator or '':
                if isinstance(line, str) and hasattr(line, 'decode'):
                    line = line.decode()
                elif isinstance(line, bytes) and hasattr(line, 'decode'):
                    line = line.decode('utf-8')
                if line[0] == '#':
                    extraparams = json.loads(line[1:])
                    if 'define_cap_line' in extraparams:
                        cap_line = extraparams['define_cap_line']
                    if 'define_base_line' in extraparams:
                        base_line = extraparams['define_base_line']
                    if 'define_bottom_line' in extraparams:
                        bottom_line = extraparams['define_bottom_line']
                if aglyph:
                    aglyph.parse_string_line(line)
                else:
                    aglyph = _HersheyGlyph(data_line=line, default_base_line=base_line, default_bottom_line=bottom_line, default_cap_line=cap_line)
                if line[0] != '#':
                    glyph_key = chr(aglyph.font_charcode if use_charcode else glyph_ascii_code)
                    self.__glyphs[glyph_key] = aglyph
                    cap.append(aglyph.cap_line)
                    base.append(aglyph.base_line)
                    bottom.append(aglyph.bottom_line)
                    aglyph = None
                    glyph_ascii_code += 1
            caps = statistics_multimode(cap)
            bases = statistics_multimode(base)
            bottoms = statistics_multimode(bottom)
            self.render_options.cap_line = statistics_median(caps) if cap_line is None else cap_line
            self.render_options.base_line = statistics_median(bases) if base_line is None else base_line
            self.render_options.bottom_line = statistics_median(bottoms) if bottom_line is None else bottom_line

    def glyphs_for_text(self, text):
        '''Return iterable list of glyphs for the given text'''
        return self._HersheyRenderIterator(self.__glyphs).text_glyphs(text=text)

    def strokes_for_text(self, text):
        '''Return iterable list of continuous strokes (polygons) for all characters with pre calculated offsets for the given text.
Strokes (polygons) are list of (x,y) coordinates.
        '''
        return self._HersheyRenderIterator(self.__glyphs).text_strokes(text=text, **self.__font_params)

    def lines_for_text(self, text):
        '''Return iterable list of individual lines for all characters with pre calculated offsets for the given text.
Lines are a list of ((x0,y0),(x1,y1)) coordinates.
        '''
        return chain.from_iterable(zip(stroke[::], stroke[1::]) for stroke in self._HersheyRenderIterator(self.__glyphs).text_strokes(text=text, **self.__font_params))


class _HersheyGlyph(object):
    def __init__(self, data_line='', default_cap_line=None, default_base_line=None, default_bottom_line=None):
        self.__capline = default_cap_line
        self.__baseline = default_base_line
        self.__bottomline = default_bottom_line
        self.__charcode = -1
        self.__left_side = 0
        self.__right_side = 0
        self.__strokes = []
        self.__xmin = self.__xmax = self.__ymin = self.__ymax = 0
        self.parse_string_line(data_line=data_line)

    @property
    def base_line(self):
        '''Return the base line of the glyph. e.g. Horizontal leg of letter L.
The parameter might be in or outside of the bounding box for the glyph
        '''
        return 9 if self.__baseline is None else self.__baseline

    @property
    def cap_line(self):
        '''Return the cap line of the glyph. e.g. Horizontal hat of letter T.
The parameter might be in or outside of the bounding box for the glyph
        '''
        return -12 if self.__capline is None else self.__capline

    @property
    def bottom_line(self):
        '''Return the bottom line of the glyph. e.g. Lowest point of letter j.
The parameter might be in or outside of the bounding box for the glyph
        '''
        return 16 if self.__bottomline is None else self.__bottomline

    @property
    def font_charcode(self):
        '''Get the Hershey charcode of this glyph.'''
        return self.__charcode

    @property
    def left_offset(self):
        '''Get left side of the glyph. Can be different to bounding box.'''
        return self.__left_side

    @property
    def strokes(self):
        '''Return iterable list of continuous strokes (polygons) for this glyph.
Strokes (polygons) are list of (x,y) coordinates.
        '''
        return self.__strokes

    @property
    def char_width(self):
        '''Return the width of this glyph. May be different to bounding box.'''
        return self.__right_side - self.__left_side

    @property
    def draw_box(self):
        '''Return the graphical bounding box for this Glyph in format ((xmin,ymin),(xmax,ymax))'''
        return (self.__xmin, self.__ymin), (self.__xmax, self.__ymax)

    @property
    def char_box(self):
        '''Return the typographical bounding box for this Glyph in format ((xmin,ymin),(xmax,ymax)).
Can be different to bounding box.
See draw_box property for rendering bounding box
        '''
        return (self.__left_side, self.__bottomline), (self.__right_side, self.__capline)

    def __char2val(self, c):  # data is stored as signed bytes relative to ASCII R
        return ord(c) - ord('R')

    @property
    def lines(self):
        '''Return iterable list of individual lines for this Glyph.
Lines are a list of ((x0,y0),(x1,y1)) coordinates.
        '''
        return chain.from_iterable(zip(stroke[::], stroke[1::]) for stroke in self.__strokes)

    def parse_string_line(self, data_line):
        """Interprets a line of Hershey font text """
        if data_line:
            data_line = data_line.rstrip()
            if data_line:
                if data_line[0] == '#':
                    extraparams = json.loads(data_line[1:])
                    if 'glyph_cap_line' in extraparams:
                        self.__capline = extraparams['glyph_cap_line']
                    if 'glyph_base_line' in extraparams:
                        self.__baseline = extraparams['glyph_base_line']
                    if 'glyph_bottom_line' in extraparams:
                        self.__bottomline = extraparams['glyph_bottom_line']
                elif len(data_line) > 9:
                    strokes = []
                    xmin = xmax = ymin = ymax = None
                    # individual strokes are stored separated by <space>+R
                    # starting at col 11
                    for s in split(data_line[10:], ' R'):
                        if len(s):
                            stroke = list(zip(map(self.__char2val, s[::2]), map(self.__char2val, s[1::2])))
                            xmin = min(stroke + ([xmin] if xmin else []), key=lambda t: t[0])
                            ymin = min(stroke + ([ymin] if ymin else []), key=lambda t: t[1])
                            xmax = max(stroke + ([xmax] if xmax else []), key=lambda t: t[0])
                            ymax = max(stroke + ([ymax] if ymax else []), key=lambda t: t[1])
                            strokes.append(stroke)
                    self.__charcode = int(data_line[0:5])
                    self.__left_side = self.__char2val(data_line[8])
                    self.__right_side = self.__char2val(data_line[9])
                    self.__strokes = strokes
                    self.__xmin, self.__ymin, self.__xmax, self.__ymax = (xmin[0], ymin[1], xmax[0], ymax[1]) if strokes else (0, 0, 0, 0)
                    return True
        return False


def main():
    thefont = HersheyFonts()
    main_script(thefont)
    main_gui(thefont)


def main_script(thefont=HersheyFonts()):
    print('Built in fonts:')
    default_font_names = sorted(thefont.default_font_names)
    for fontname1, fontname2 in zip_longest(default_font_names[::2], default_font_names[1::2]):
        fontname2 = '' if fontname2 is None else '- "' + fontname2 + '"'
        fontname1 = '' if fontname1 is None else '"' + fontname1 + '"'
        print(' - {0:<25} {1}'.format(fontname1, fontname2))
    print('Default font: "{0}"'.format(thefont.load_default_font()))
    print('')
    print('Rendering options:')
    for optname, defval in thefont.render_options.items():
        print(' render_options.{0} = {1}'.format(optname, defval))


def main_gui(thefont=HersheyFonts()):
    import turtle
    thefont.load_default_font()
    thefont.normalize_rendering(30)
    thefont.render_options.xofs = -367
    turtle.mode('logo')
    turtle.tracer(2, delay=3)
    for coord in range(4):
        turtle.forward(200)
        if coord < 2:
            turtle.stamp()
        turtle.back(200)
        turtle.right(90)
    turtle.color('blue')
    lineslist = thefont.lines_for_text('Pack my box with five dozen liquor jugs.')
    for pt1, pt2 in lineslist:
        turtle.penup()
        turtle.goto(pt1)
        turtle.setheading(turtle.towards(pt2))
        turtle.pendown()
        turtle.goto(pt2)
    turtle.penup()
    turtle.color('red')
    turtle.goto(0, 100)
    turtle.setheading(180)
    turtle.update()
    turtle.exitonclick()


if __name__ == '__main__':
    main()
