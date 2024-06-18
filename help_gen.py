import glob
from viaconstructor.setupdefaults import setup_defaults


# i18n
def no_translation(text):
    return text


setup = setup_defaults(no_translation)


menu = []
menu.append("")
menu.append("<h2>viaConstructor</h2>")
menu.append('<a target="main" href="readme.html">Overview</a><br />')
menu.append("Help:<br />")


readme = []
readme.append("")
readme.append("# viaConstructor")


readme.append("## Documentation")
readme.append(f'* Setup-Options')
for section_name, section_data in setup.items():
    readme.append(
        f'	- [{section_name.title()}](#{section_name})'
    )
readme.append("")


for section_name, section_data in setup.items():
    menu.append(
        f'&nbsp;&nbsp;&nbsp;<a target="main" href="help/{section_name}.html">{section_name.title()}</a><br />'
    )

    section = []
    section.append(f"<h2>{section_name.title()}</h2>")
    readme.append(f"## {section_name.title()}")
    for name, data in section_data.items():
        section.append("<center>")
        section.append('<table width="90%" border="0">')
        section.append('<tr><td valign="top" align="left">')
        section.append(f"<h3>{data['title']}:</h3>")

        readme.append(f"### {data['title']}")
        readme.append("<p>")



        section.append("<br/>")
        section.append(f"{data['tooltip']}<br/>")
        section.append("<br/>")

        readme.append(f"{data['tooltip']}")
        readme.append("")


        if "comment" in data:
            comment = data['comment'].replace("\n", "<BR/>")
            section.append(f"<i>{comment}</i><br/>")
            section.append("<br/>")

            readme.append(f"{data['comment']}")
            readme.append("")



        if "unit" in data:
            if data['unit'] == "LINEARMEASURE":
                section.append("Unit: mm/inch<br/>")
                readme.append("* Unit: mm/inch")
            else:
                section.append(f"Unit: {data['unit']}<br/>")
                readme.append(f"* Unit: {data['unit']}")
        if "default" in data:
            if data.get("type") != "table":
                section.append(f"Default: {data['default']}<br/>")
                readme.append(f"* Default: {data['default']}")

        if "type" in data:
            if data['type'] == "select":
                section.append("Options:<br/>")
                readme.append("### Options:")
                for option in data["options"]:
                    section.append(f"&nbsp;&nbsp;{option[1]}<br/>")
                    readme.append(f"* {option[1]}")

        section.append('<br /></td><td valign="top" align="right">')

        #print(f"docs/{section_name}-{name}-*.png")
        
        readme.append("<p align=\"right\">")
        
        for image in glob.glob(f"docs/{section_name}-{name}*.png"):
            ipath = image.replace("docs/", "")
            ivalue = image.replace(f"docs/{section_name}-{name}-", "").replace(
                f".png", ""
            )
            section.append(f"{ivalue}")
            section.append(
                f'<a href="../{ipath}"><img width="320" alt="{ipath}" src="../{ipath}" /></a><br />'
            )
            readme.append(
                f'<img alt="{ivalue}" title="{ivalue}" height="240" src="{ipath}">'
            )
            readme.append("")

        readme.append("</p>")
        readme.append("")

        section.append("</td></tr>")
        section.append("<tr><td><br /></td><td></td></tr>")
        section.append("</table>")
        section.append("</center>")
        open(f"docs/help/{section_name}.html", "w").write("\n".join(section))

        readme.append("</p>")
        readme.append("")


index = []
open(f"docs/help/index.html", "w").write("\n".join(index))


menu.append('<a target="main" href="pdoc/index.html">Source-Documentation</a><br />')
menu.append(
    '<a target="main" href="pytest/index.html">Pytest-Coverage-Report</a><br />'
)
menu.append("<br />")
menu.append(
    '<a target="_blank" href="https://github.com/multigcs/viaconstructor">GitHub</a><br />'
)
menu.append("")
open(f"docs/menu.html", "w").write("\n".join(menu))


readme.append("")
open(f"docs/README.md", "w").write("\n".join(readme))


