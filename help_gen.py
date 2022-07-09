import json

helpdata = json.loads(open("docs/help.json", "r").read())

index = []
index.append("<h1>Help</h1>")
index.append("<hr />")
index.append("<center>")
index.append('<table width="90%" border="0">')
for name, data in helpdata.items():

    # index.append(f"<a href=\"{name}.html\">{data['title']}</a><br />")

    index.append('<tr><td valign="top" align="left">')
    index.append(f"<h2>{data['title']}</h2>")
    index.append(data["text"])
    index.append('<br /></td><td valign="top" align="right">')
    for option, filename in data["images"].items():
        index.append(f"{option}")
        index.append(
            f'<a href="../{filename}"><img width="320" alt="{option}" src="../{filename}" /></a><br />'
        )
    index.append("</td></tr>")

    index.append("<tr><td><br /></td><td></td></tr>")

    html = []
    html.append(f"<h1>{data['title']}</h1>")
    html.append(data["text"])
    html.append("<br />")
    for option, filename in data["images"].items():
        html.append(f'<img width="320" src="../{filename}" />')

    open(f"docs/help/{name}.html", "w").write("\n".join(html))

index.append("</table>")
index.append("</center>")


open(f"docs/help/index.html", "w").write("\n".join(index))
